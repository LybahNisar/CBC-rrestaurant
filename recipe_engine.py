"""
╔══════════════════════════════════════════════════════════════════╗
║         CHOCOBERRY — RECIPE CARD ENGINE                         ║
║  Manages recipe cards, auto-deducts ingredients from sales,     ║
║  calculates COGS, food cost %, and generates reorder alerts.    ║
║                                                                  ║
║  Add as a tab in your Streamlit dashboard by importing:         ║
║    from recipe_engine import RecipeEngine                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import csv
import json
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "recipes.db"


# ── Database Setup ────────────────────────────────────────────────

def init_recipe_db():
    with sqlite3.connect(DB_PATH) as conn:

        # Ingredients master — what you buy from suppliers
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT UNIQUE NOT NULL,
                unit          TEXT NOT NULL,       -- kg, g, litre, ml, each, portion
                unit_cost     REAL DEFAULT 0.0,    -- £ per unit
                supplier      TEXT DEFAULT '',
                opening_stock REAL DEFAULT 0.0,
                current_stock REAL DEFAULT 0.0,
                reorder_point REAL DEFAULT 0.0,
                updated_at    TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Menu items — matches Flipdish item names exactly
        conn.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                flipdish_name TEXT UNIQUE NOT NULL,
                display_name  TEXT,
                category      TEXT DEFAULT 'Main',
                selling_price REAL DEFAULT 0.0,
                active        INTEGER DEFAULT 1
            )
        """)

        # Recipe cards — one row per ingredient per menu item
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipe_cards (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                menu_item_id  INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                quantity      REAL NOT NULL,       -- quantity of ingredient used per portion
                UNIQUE(menu_item_id, ingredient_id),
                FOREIGN KEY (menu_item_id)  REFERENCES menu_items(id),
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
            )
        """)

        # Stock deduction log — audit trail
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_deductions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                deduction_date TEXT NOT NULL,
                ingredient_id  INTEGER NOT NULL,
                quantity_used  REAL NOT NULL,
                source         TEXT DEFAULT 'sales',  -- sales / waste / manual
                menu_item      TEXT DEFAULT '',
                units_sold     INTEGER DEFAULT 0,
                created_at     TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Waste log
        conn.execute("""
            CREATE TABLE IF NOT EXISTS waste_events (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                waste_date    TEXT NOT NULL,
                ingredient_id INTEGER,
                item_name     TEXT,
                quantity      REAL,
                reason        TEXT,
                cost_impact   REAL DEFAULT 0.0,
                logged_by     TEXT DEFAULT '',
                created_at    TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


init_recipe_db()


# ══════════════════════════════════════════════════════════════════
# RecipeEngine class
# ══════════════════════════════════════════════════════════════════

class RecipeEngine:

    def __init__(self, db_path: str = None):
        self.db = str(db_path or DB_PATH)

    def _conn(self):
        return sqlite3.connect(self.db)

    # ── Ingredients ───────────────────────────────────────────────

    def upsert_ingredient(self, name: str, unit: str, unit_cost: float = 0.0,
                          supplier: str = "", opening_stock: float = 0.0,
                          reorder_point: float = 0.0) -> int:
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM ingredients WHERE name=?", (name,)
            ).fetchone()
            if existing:
                conn.execute("""
                    UPDATE ingredients
                    SET unit=?, unit_cost=?, supplier=?, reorder_point=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE name=?
                """, (unit, unit_cost, supplier, reorder_point, name))
                return existing[0]
            else:
                cur = conn.execute("""
                    INSERT INTO ingredients
                      (name, unit, unit_cost, supplier, opening_stock,
                       current_stock, reorder_point)
                    VALUES (?,?,?,?,?,?,?)
                """, (name, unit, unit_cost, supplier, opening_stock,
                      opening_stock, reorder_point))
                return cur.lastrowid

    def get_ingredients(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT id, name, unit, unit_cost, supplier,
                       current_stock, reorder_point
                FROM ingredients ORDER BY name
            """).fetchall()
        return [
            dict(id=r[0], name=r[1], unit=r[2], unit_cost=r[3],
                 supplier=r[4], current_stock=r[5], reorder_point=r[6])
            for r in rows
        ]

    def get_reorder_alerts(self) -> list[dict]:
        items = self.get_ingredients()
        return [i for i in items if i["current_stock"] <= i["reorder_point"]]

    def update_stock(self, ingredient_id: int, new_stock: float):
        with self._conn() as conn:
            conn.execute(
                "UPDATE ingredients SET current_stock=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_stock, ingredient_id)
            )
            conn.commit()

    # ── Menu Items ────────────────────────────────────────────────

    def upsert_menu_item(self, flipdish_name: str, display_name: str = "",
                         category: str = "Main", selling_price: float = 0.0) -> int:
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM menu_items WHERE flipdish_name=?", (flipdish_name,)
            ).fetchone()
            if existing:
                conn.execute("""
                    UPDATE menu_items
                    SET display_name=?, category=?, selling_price=?
                    WHERE flipdish_name=?
                """, (display_name or flipdish_name, category, selling_price, flipdish_name))
                return existing[0]
            cur = conn.execute("""
                INSERT INTO menu_items (flipdish_name, display_name, category, selling_price)
                VALUES (?,?,?,?)
            """, (flipdish_name, display_name or flipdish_name, category, selling_price))
            return cur.lastrowid

    def get_menu_items(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT id, flipdish_name, display_name, category, selling_price
                FROM menu_items WHERE active=1 ORDER BY category, display_name
            """).fetchall()
        return [
            dict(id=r[0], flipdish_name=r[1], display_name=r[2],
                 category=r[3], selling_price=r[4])
            for r in rows
        ]

    # ── Recipe Cards ──────────────────────────────────────────────

    def set_recipe(self, menu_item_id: int, ingredients: list[dict]):
        """
        ingredients: [{"ingredient_id": int, "quantity": float}, ...]
        Replaces the full recipe for this item.
        """
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM recipe_cards WHERE menu_item_id=?", (menu_item_id,)
            )
            for ing in ingredients:
                conn.execute("""
                    INSERT OR REPLACE INTO recipe_cards
                      (menu_item_id, ingredient_id, quantity)
                    VALUES (?,?,?)
                """, (menu_item_id, ing["ingredient_id"], ing["quantity"]))
            conn.commit()

    def get_recipe(self, menu_item_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT rc.ingredient_id, i.name, i.unit, rc.quantity, i.unit_cost,
                       rc.quantity * i.unit_cost as line_cost
                FROM recipe_cards rc
                JOIN ingredients i ON i.id = rc.ingredient_id
                WHERE rc.menu_item_id = ?
            """, (menu_item_id,)).fetchall()
        return [
            dict(ingredient_id=r[0], name=r[1], unit=r[2],
                 quantity=r[3], unit_cost=r[4], line_cost=r[5])
            for r in rows
        ]

    def get_recipe_cost(self, menu_item_id: int) -> float:
        """Total ingredient cost for one portion."""
        recipe = self.get_recipe(menu_item_id)
        return round(sum(r["line_cost"] for r in recipe), 4)

    # ── COGS Calculations ─────────────────────────────────────────

    def calc_item_profitability(self) -> list[dict]:
        """
        Returns per-item COGS, GP, GP%, and food cost % for all menu items
        that have a recipe card.
        """
        items  = self.get_menu_items()
        result = []
        for item in items:
            # Initialize with safe defaults to prevent UnboundLocalError
            cost = 0.0
            price = 0.0
            gp = 0.0
            gp_pct = 0.0
            fc_pct = 0.0
            
            try:
                cost  = self.get_recipe_cost(item["id"])
                price = item["selling_price"]
                
                if price > 0:
                    gp = round(price - cost, 4)
                    gp_pct = round(gp / price * 100, 1)
                    fc_pct = round(cost / price * 100, 1)
                    
                    # SAFETY FILTER: CAP EXTREME OUTLIERS
                    if cost > price * 10:
                        gp_pct = -100.0
                        fc_pct = 0.0
                
                result.append({
                    "menu_item":       item["display_name"],
                    "flipdish_name":   item["flipdish_name"],
                    "category":        item["category"],
                    "selling_price":   price,
                    "ingredient_cost": cost,
                    "gross_profit":    gp,
                    "gp_pct":          gp_pct,
                    "food_cost_pct":   fc_pct,
                    "has_recipe":      cost > 0,
                })
            except Exception:
                continue
                
        return sorted(result, key=lambda x: x["gp_pct"], reverse=True)

    def get_theoretical_usage(self, sales_data: list[dict]) -> dict:
        """
        Calculates expected ingredient consumption without modifying stock.
        Used for forensic waste analysis and 'Should-Have-Used' reporting.
        Returns: { ingredient_name: {'usage': float, 'cost': float, 'unit': str} }
        """
        usage = {}
        with self._conn() as conn:
            for sale in sales_data:
                item_name  = str(sale.get("item_name", "")).strip()
                try:
                    units_sold = int(float(sale.get("units_sold", 0)))
                except (ValueError, TypeError):
                    units_sold = 0
                
                if not item_name or units_sold <= 0:
                    continue

                # SMART MATCHING - IMPROVED RESILIENCE
                row = conn.execute("SELECT id FROM menu_items WHERE flipdish_name=? AND active=1", (item_name,)).fetchone()
                if not row: 
                    # Try lowercase or contains
                    row = conn.execute("SELECT id FROM menu_items WHERE LOWER(flipdish_name)=LOWER(?) AND active=1", (item_name,)).fetchone()
                if not row:
                    row = conn.execute("SELECT id FROM menu_items WHERE ? LIKE '%'||flipdish_name||'%' AND active=1", (item_name,)).fetchone()

                if not row: continue
                
                recipe = conn.execute("""
                    SELECT i.name, rc.quantity, i.unit_cost, i.unit
                    FROM recipe_cards rc
                    JOIN ingredients i ON i.id = rc.ingredient_id
                    WHERE rc.menu_item_id = ?
                """, (row[0],)).fetchall()
                
                for ing_name, qty_per, cost_per, unit in recipe:
                    total_q = qty_per * units_sold
                    total_c = total_q * cost_per
                    if ing_name not in usage:
                        usage[ing_name] = {"usage": 0.0, "cost": 0.0, "unit": unit}
                    usage[ing_name]["usage"] += total_q
                    usage[ing_name]["cost"]  += total_c
        return usage


    def deduct_from_sales(self, sales_data: list[dict],
                          deduction_date: str = None) -> dict:
        """
        sales_data: [{"item_name": str, "units_sold": int}, ...]
        Matches item_name to flipdish_name in menu_items, looks up recipe,
        deducts ingredients from current_stock.

        Returns summary dict.
        """
        if not deduction_date:
            deduction_date = datetime.now().strftime("%Y-%m-%d")

        summary = {
            "date":           deduction_date,
            "items_processed": 0,
            "items_skipped":  [],
            "deductions":     [],
            "total_cogs":     0.0,
        }

        with self._conn() as conn:
            for sale in sales_data:
                item_name  = str(sale.get("item_name", "")).strip()
                try:
                    units_sold = int(float(sale.get("units_sold", 0)))
                except (ValueError, TypeError):
                    units_sold = 0

                if not item_name or units_sold <= 0:
                    continue

                # Look up menu item (exact then fuzzy)
                row = conn.execute(
                    "SELECT id FROM menu_items WHERE flipdish_name=? AND active=1",
                    (item_name,)
                ).fetchone()

                if not row:
                    # Try case-insensitive
                    row = conn.execute(
                        "SELECT id FROM menu_items WHERE LOWER(flipdish_name)=LOWER(?)",
                        (item_name,)
                    ).fetchone()

                if not row:
                    summary["items_skipped"].append(item_name)
                    continue

                menu_item_id = row[0]
                recipe = conn.execute("""
                    SELECT rc.ingredient_id, i.name, rc.quantity, i.unit_cost
                    FROM recipe_cards rc
                    JOIN ingredients i ON i.id = rc.ingredient_id
                    WHERE rc.menu_item_id = ?
                """, (menu_item_id,)).fetchall()

                if not recipe:
                    summary["items_skipped"].append(f"{item_name} (no recipe)")
                    continue

                item_cogs = 0.0
                for ing_id, ing_name, qty_per_portion, unit_cost in recipe:
                    total_qty = qty_per_portion * units_sold
                    item_cogs += total_qty * unit_cost

                    # Deduct from stock
                    conn.execute(
                        """UPDATE ingredients
                           SET current_stock = MAX(0, current_stock - ?),
                               updated_at = CURRENT_TIMESTAMP
                           WHERE id = ?""",
                        (total_qty, ing_id)
                    )

                    # Log the deduction
                    conn.execute("""
                        INSERT INTO stock_deductions
                          (deduction_date, ingredient_id, quantity_used,
                           source, menu_item, units_sold)
                        VALUES (?,?,?,?,?,?)
                    """, (deduction_date, ing_id, total_qty,
                          "sales", item_name, units_sold))

                    summary["deductions"].append({
                        "ingredient": ing_name,
                        "qty_deducted": round(total_qty, 4),
                        "menu_item": item_name,
                    })

                summary["items_processed"] += 1
                summary["total_cogs"]      += item_cogs

            conn.commit()

        summary["total_cogs"] = round(summary["total_cogs"], 2)
        return summary

    # ── Manual Stock Adjustment ───────────────────────────────────

    def set_opening_stock(self, ingredient_id: int, qty: float):
        """Set stock from a physical count."""
        with self._conn() as conn:
            conn.execute("""
                UPDATE ingredients
                SET current_stock = ?, opening_stock = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (qty, qty, ingredient_id))
            conn.commit()

    def log_waste(self, ingredient_id: int, quantity: float,
                  reason: str, logged_by: str = ""):
        with self._conn() as conn:
            ing = conn.execute(
                "SELECT name, unit_cost, current_stock FROM ingredients WHERE id=?",
                (ingredient_id,)
            ).fetchone()
            if not ing:
                return

            cost_impact = round(quantity * ing[1], 2)

            conn.execute("""
                INSERT INTO waste_events
                  (waste_date, ingredient_id, item_name, quantity,
                   reason, cost_impact, logged_by)
                VALUES (?,?,?,?,?,?,?)
            """, (
                datetime.now().strftime("%Y-%m-%d"),
                ingredient_id, ing[0], quantity,
                reason, cost_impact, logged_by,
            ))

            # Deduct waste from stock
            conn.execute("""
                UPDATE ingredients
                SET current_stock = MAX(0, current_stock - ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (quantity, ingredient_id))

            conn.commit()
        return cost_impact

    # ── Weekly Summary ────────────────────────────────────────────

    def weekly_stock_summary(self) -> dict:
        """High-level summary for the dashboard KPI row."""
        ings    = self.get_ingredients()
        alerts  = self.get_reorder_alerts()
        items   = self.calc_item_profitability()

        items_with_recipe  = [i for i in items if i["has_recipe"]]
        avg_food_cost      = (
            sum(i["food_cost_pct"] for i in items_with_recipe) /
            len(items_with_recipe)
            if items_with_recipe else 0.0
        )

        with self._conn() as conn:
            waste_cost = conn.execute(
                "SELECT COALESCE(SUM(cost_impact),0) FROM waste_events"
                " WHERE waste_date >= date('now','-7 days')"
            ).fetchone()[0]

            cogs_7d = conn.execute(
                """SELECT COALESCE(SUM(sd.quantity_used * i.unit_cost),0)
                   FROM stock_deductions sd
                   JOIN ingredients i ON i.id = sd.ingredient_id
                   WHERE sd.deduction_date >= date('now','-7 days')
                     AND sd.source = 'sales'"""
            ).fetchone()[0]

        return {
            "total_ingredients":   len(ings),
            "reorder_alerts":      len(alerts),
            "avg_food_cost_pct":   round(avg_food_cost, 1),
            "weekly_cogs":         round(cogs_7d, 2),
            "weekly_waste_cost":   round(waste_cost, 2),
            "items_with_recipe":   len(items_with_recipe),
            "items_without_recipe": len(items) - len(items_with_recipe),
        }

    # ── CSV Import ────────────────────────────────────────────────

    def import_ingredients_csv(self, path: str) -> int:
        """
        Import ingredients from CSV.
        Expected columns: name, unit, unit_cost, supplier, opening_stock, reorder_point
        """
        count = 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.upsert_ingredient(
                    name          = row.get("name", "").strip(),
                    unit          = row.get("unit", "each").strip(),
                    unit_cost     = float(row.get("unit_cost", 0) or 0),
                    supplier      = row.get("supplier", "").strip(),
                    opening_stock = float(row.get("opening_stock", 0) or 0),
                    reorder_point = float(row.get("reorder_point", 0) or 0),
                )
                count += 1
        return count

    def import_menu_items_csv(self, path: str) -> int:
        """
        Import menu items from CSV.
        Expected columns: flipdish_name, display_name, category, selling_price
        """
        count = 0
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.upsert_menu_item(
                    flipdish_name = row.get("flipdish_name", "").strip(),
                    display_name  = row.get("display_name", "").strip(),
                    category      = row.get("category", "Main").strip(),
                    selling_price = float(row.get("selling_price", 0) or 0),
                )
                count += 1
        return count

    def export_profitability_csv(self, path: str):
        """Export profitability table — ready to replace master_profitability_lookup.csv."""
        items = self.calc_item_profitability()
        if not items:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(items[0].keys()))
            writer.writeheader()
            writer.writerows(items)


# ── Standalone demo ───────────────────────────────────────────────

if __name__ == "__main__":
    engine = RecipeEngine()

    # Demo: add a couple of ingredients
    waffle_mix_id = engine.upsert_ingredient(
        "Waffle Mix", "kg", unit_cost=2.40,
        supplier="Cr8 Foods", opening_stock=20.0, reorder_point=5.0
    )
    cream_id = engine.upsert_ingredient(
        "Whipped Cream", "litre", unit_cost=3.10,
        supplier="Freshways", opening_stock=10.0, reorder_point=2.0
    )
    choc_id = engine.upsert_ingredient(
        "Chocolate Sauce", "litre", unit_cost=4.50,
        supplier="Bookers", opening_stock=8.0, reorder_point=2.0
    )

    # Demo: add a menu item and recipe
    item_id = engine.upsert_menu_item(
        "Classic Waffle", "Classic Waffle", "Waffles", selling_price=7.50
    )
    engine.set_recipe(item_id, [
        {"ingredient_id": waffle_mix_id, "quantity": 0.15},  # 150g
        {"ingredient_id": cream_id,       "quantity": 0.05},  # 50ml
        {"ingredient_id": choc_id,         "quantity": 0.03},  # 30ml
    ])

    cost = engine.get_recipe_cost(item_id)
    print(f"\nClassic Waffle — ingredient cost: £{cost:.4f} per portion")
    print(f"Selling price: £7.50 | GP: £{7.50 - cost:.2f} | GP%: {(7.50-cost)/7.50*100:.1f}%")

    # Simulate 100 sales
    summary = engine.deduct_from_sales(
        [{"item_name": "Classic Waffle", "units_sold": 100}]
    )
    print(f"\nDeducted for 100 Classic Waffles — Total COGS: £{summary['total_cogs']:.2f}")

    alerts = engine.get_reorder_alerts()
    print(f"\nReorder alerts ({len(alerts)} items):")
    for a in alerts:
        print(f"  🔴 {a['name']} — stock: {a['current_stock']} {a['unit']} (reorder at {a['reorder_point']})")

    summary = engine.weekly_stock_summary()
    print(f"\nWeekly summary: {summary}")
