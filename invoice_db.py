import sqlite3
import os
from datetime import datetime, timedelta

class InvoiceDB:
    def __init__(self, db_path='cbc_invoice_intelligence.db'):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Builds the 100% forensic relational schema for Chocoberry Intelligence."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Suppliers Table — FULL PORTAL SPECS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    category TEXT,
                    vat_number TEXT,
                    account_number TEXT,
                    bank_sort_code TEXT,
                    bank_account TEXT,
                    payment_terms TEXT DEFAULT '30 Days',
                    total_spend_ytd REAL DEFAULT 0.0
                )
            ''')
            
            # 2. Invoices Master Table — ACCOUNTS REGISTRY SPECS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number TEXT NOT NULL,
                    supplier_id INTEGER NOT NULL,
                    invoice_date DATE,
                    due_date DATE,
                    net_amount REAL DEFAULT 0.0,
                    vat_amount REAL DEFAULT 0.0,
                    total_amount REAL NOT NULL,
                    payment_status TEXT DEFAULT 'UNPAID',
                    category TEXT,
                    image_path TEXT,
                    uploaded_by TEXT DEFAULT 'DHIRAJ',
                    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
                )
            ''')
            
            # 3. Invoice Line Items — FORENSIC AUDIT SPECS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS invoice_line_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id INTEGER NOT NULL,
                    item_description TEXT,
                    product_code TEXT,
                    quantity REAL,
                    unit TEXT,
                    unit_rate REAL,
                    vat_pct REAL,
                    vat_amount REAL,
                    line_total REAL,
                    FOREIGN KEY (invoice_id) REFERENCES invoices (id)
                )
            ''')
            conn.commit()

    # ── Supplier Operations ───────────────────────────────────────────────────

    def add_supplier(self, name, **kwargs):
        """Adds or updates a supplier with bank/category info."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO suppliers (name) VALUES (?)', (name,))
            
            if kwargs:
                sets = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                vals = list(kwargs.values()) + [name]
                cursor.execute(f'UPDATE suppliers SET {sets} WHERE name = ?', vals)
            
            conn.commit()
            cursor.execute('SELECT id FROM suppliers WHERE name = ?', (name,))
            return cursor.fetchone()[0]

    def get_suppliers(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM suppliers ORDER BY name ASC')
            return cursor.fetchall()

    # ── Invoice Operations ────────────────────────────────────────────────────

    def insert_invoice(self, data, items=None):
        """Standard insertion for Phase 2 Upload Form."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Default due date calculation if missing
            if 'due_date' not in data and 'invoice_date' in data:
                d = datetime.strptime(data['invoice_date'], '%Y-%m-%d')
                data['due_date'] = (d + timedelta(days=30)).strftime('%Y-%m-%d')

            cols = ", ".join(data.keys())
            placeholders = ", ".join(["?" for _ in data])
            cursor.execute(f'INSERT INTO invoices ({cols}) VALUES ({placeholders})', list(data.values()))
            
            inv_id = cursor.lastrowid
            
            if items:
                for item in items:
                    item['invoice_id'] = inv_id
                    i_cols = ", ".join(item.keys())
                    i_placeholders = ", ".join(["?" for _ in item])
                    cursor.execute(f'INSERT INTO invoice_line_items ({i_cols}) VALUES ({i_placeholders})', list(item.values()))
            
            conn.commit()
            return inv_id

    def check_duplicate(self, inv_no, supplier_id):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM invoices WHERE invoice_number = ? AND supplier_id = ?', (inv_no, supplier_id))
            return cursor.fetchone()

    def update_payment_status(self, inv_id, status='PAID'):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE invoices SET payment_status = ? WHERE id = ?', (status, inv_id))
            conn.commit()

    # ── Query Operations (Tab 12 Registry) ────────────────────────────────────

    def get_all_invoices(self, status=None, supplier_id=None):
        query = '''
            SELECT i.id, i.invoice_number, s.name, i.invoice_date, i.due_date, 
                   i.total_amount, i.payment_status, i.category, i.image_path
            FROM invoices i
            JOIN suppliers s ON i.supplier_id = s.id
        '''
        params = []
        conditions = []
        if status:
            conditions.append("i.payment_status = ?")
            params.append(status)
        if supplier_id:
            conditions.append("i.supplier_id = ?")
            params.append(supplier_id)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY i.invoice_date DESC"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def get_all_line_items(self):
        """Retrieves every single line item across all invoices for forensic auditing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT i.invoice_number, s.name, li.item_description, li.product_code, 
                       li.quantity, li.unit, li.unit_rate, li.line_total
                FROM invoice_line_items li
                JOIN invoices i ON li.invoice_id = i.id
                JOIN suppliers s ON i.supplier_id = s.id
                ORDER BY i.invoice_date DESC
            ''')
            return cursor.fetchall()

    def get_overdue_invoices(self):
        today = datetime.now().strftime('%Y-%m-%d')
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT i.invoice_number, s.name, i.total_amount, i.due_date
                FROM invoices i
                JOIN suppliers s ON i.supplier_id = s.id
                WHERE i.payment_status != 'PAID' AND i.due_date < ?
                ORDER BY i.due_date ASC
            ''', (today,))
            return cursor.fetchall()

    # ── Intelligence Operations (Tab 12 Analytics) ────────────────────────────

    def get_supplier_analytics(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.name, SUM(i.total_amount) as spend, COUNT(i.id) as count
                FROM suppliers s
                JOIN invoices i ON s.id = i.supplier_id
                GROUP BY s.name
                ORDER BY spend DESC
            ''')
            return cursor.fetchall()

    def get_category_analytics(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT category, SUM(total_amount) as spend
                FROM invoices
                GROUP BY category
                ORDER BY spend DESC
            ''')
            return cursor.fetchall()

    def get_monthly_spend_trend(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT strftime('%Y-%m', invoice_date) as month, SUM(total_amount) as spend
                FROM invoices
                WHERE invoice_date IS NOT NULL
                GROUP BY month
                ORDER BY month ASC
            ''')
            return cursor.fetchall()

    def get_supplier_monthly_analytics(self):
        """Returns spend per supplier per month for MoM comparison."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.name, strftime('%Y-%m', i.invoice_date) as month, SUM(i.total_amount) as spend
                FROM suppliers s
                JOIN invoices i ON s.id = i.supplier_id
                WHERE i.invoice_date IS NOT NULL
                GROUP BY s.name, month
                ORDER BY month ASC, spend DESC
            ''')
            return cursor.fetchall()

if __name__ == "__main__":
    db = InvoiceDB()
    print("✅ Chocoberry Invoice Intelligence Schema V2.0 Initialized.")
