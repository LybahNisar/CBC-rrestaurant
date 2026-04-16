"""
Chocoberry Intelligent Rota Engine
===================================
Constraint-based greedy scheduler for automatic weekly rota generation.

Algorithm:
  1. Load staff profiles + shift templates from CSV
  2. For each shift slot (day + shift + department):
     a. Filter eligible staff (available, under max hours, not already assigned that day)
     b. Fill Senior slots first (hard constraint: min_senior must be met)
     c. Fill Junior slots to reach min_total_staff
  3. Fairness rebalance: redistribute shifts from over-target to under-target staff
  4. Export to detailed_rota_with_shifts.csv (compatible with Labour Cost Tab)

Author: Chocoberry BI System
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dt_time
from typing import Tuple   
import os
import random

BASE = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────────────
# TIME UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def parse_time(t_str):
    """Parse HH:MM string → decimal hours (handles overnight: e.g. 01:45 → 25.75)."""
    try:
        h, m = map(int, str(t_str).split(":"))
        return h + m / 60
    except:
        return 0.0


def shift_duration(start_str, end_str):
    """Calculate shift duration in hours, handling overnight shifts."""
    s = parse_time(start_str)
    e = parse_time(end_str)
    if e < s:          # overnight shift (e.g. 23:00 → 01:30)
        e += 24
    return round(e - s, 2)


def format_time_range(start_str, end_str):
    """Return 'HH:MM - HH:MM' display string."""
    return f"{start_str} - {end_str}"


# ─────────────────────────────────────────────────────────────────────────────
# ROTA ENGINE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class RotaEngine:

    def __init__(self,
                 staff_csv: str = None,
                 shifts_csv: str = None):

        self.staff_csv  = staff_csv  or os.path.join(BASE, "staff_profiles.csv")
        self.shifts_csv = shifts_csv or os.path.join(BASE, "shift_templates.csv")

        self.staff_df  = None
        self.shifts_df = None

        # Runtime state — reset each generation
        self._hours_worked  = {}   # name -> total hours scheduled so far
        self._historical_hours = {} # name -> hours from previous weeks
        self._days_assigned = {}   # name -> set of days already assigned
        self._assignments   = []   # list of dicts → final rota rows

        self.errors   = []         # validation errors
        self.warnings = []         # soft warnings

    # ── Loaders ───────────────────────────────────────────────────────────────

    def load_staff(self, df: pd.DataFrame = None) -> pd.DataFrame:
        """Load from CSV or accept an already-loaded DataFrame."""
        if df is not None:
            self.staff_df = df.copy()
        else:
            self.staff_df = pd.read_csv(self.staff_csv, encoding="utf-8-sig")

        # Normalise
        self.staff_df.columns = [c.strip() for c in self.staff_df.columns]
        self.staff_df["Name"]             = self.staff_df["Name"].str.strip()
        self.staff_df["Role"]             = self.staff_df["Role"].str.strip().str.capitalize()
        self.staff_df["Department"]       = self.staff_df["Department"].str.strip()
        self.staff_df["Shift Preference"] = self.staff_df["Shift Preference"].str.strip()
        self.staff_df["Active"]           = self.staff_df["Active"].str.strip().str.lower() == "yes"

        # Parse availability into sets
        _ABBREV_TO_FULL = {
            "Mon":"Monday",  "Tue":"Tuesday",  "Wed":"Wednesday",
            "Thu":"Thursday","Fri":"Friday",   "Sat":"Saturday","Sun":"Sunday",
        }
        def _expand_availability(raw):
            return set(_ABBREV_TO_FULL.get(d.strip(), d.strip())
                       for d in str(raw).split(","))
        self.staff_df["_avail_set"] = self.staff_df["Availability"].apply(
            _expand_availability
        )

        return self.staff_df

    def load_shifts(self, df: pd.DataFrame = None) -> pd.DataFrame:
        """Load shift templates."""
        if df is not None:
            self.shifts_df = df.copy()
        else:
            self.shifts_df = pd.read_csv(self.shifts_csv, encoding="utf-8-sig")

        self.shifts_df.columns = [c.strip() for c in self.shifts_df.columns]
        self.shifts_df["Duration"] = self.shifts_df.apply(
            lambda r: shift_duration(r["Start Time"], r["End Time"]), axis=1
        )
        return self.shifts_df

    def load_historical_hours(self, weeks_back: int = 3):
        """
        Scans previous week folders and aggregates total hours worked by each staff member.
        Enables the Fairness Balance algorithm to operate across multiple weeks.
        """
        self._historical_hours = {}
        today = datetime.today()
        
        for w in range(1, weeks_back + 1):
            target_dt = today - timedelta(weeks=w)
            w_start = target_dt - timedelta(days=target_dt.weekday())
            w_end   = w_start + timedelta(days=6)
            
            # Check multiple naming conventions
            candidates = [
                f"Rota week {w_start.strftime('%d %b').lower()} - {w_end.strftime('%d %B').lower()} {w_start.year}",
                f"Rota week {w_start.strftime('%d %b')} - {w_end.strftime('%d %B %Y')}",
                f"Rota week {w_start.strftime('%d %B').lower()} - {w_end.strftime('%d %B').lower()} {w_start.year}",
            ]
            
            found_path = None
            for cand in candidates:
                p = os.path.join(os.getcwd(), cand, "detailed_rota_with_shifts.csv")
                if os.path.exists(p):
                    found_path = p
                    break
            
            if found_path:
                try:
                    hist_df = pd.read_csv(found_path)
                    if not hist_df.empty and "Name" in hist_df.columns and "Duration" in hist_df.columns:
                        totals = hist_df.groupby("Name")["Duration"].sum()
                        for name, hrs in totals.items():
                            self._historical_hours[name] = self._historical_hours.get(name, 0) + hrs
                except:
                    continue
        
        return self._historical_hours

    # ── Constraint Checker ────────────────────────────────────────────────────

    def _can_work(self, name: str, day: str, dept: str, shift_duration: float) -> Tuple[bool, str]:
        """Returns (eligible: bool, reason: str)."""
        row = self.staff_df[self.staff_df["Name"] == name].iloc[0]

        # Hard: availability
        if day not in row["_avail_set"]:
            return False, f"Not available on {day}"

        # Hard: max hours (Check if adding this shift would exceed max)
        current = self._hours_worked.get(name, 0)
        if (current + shift_duration) > row["Max Hours/Week"]:
            return False, f"Shift would exceed max hours ({current} + {shift_duration} > {row['Max Hours/Week']})"

        # Hard: already assigned today
        if day in self._days_assigned.get(name, set()):
            return False, "Already assigned today"

        # Hard: department match
        if row["Department"].lower() != dept.lower():
            return False, f"Wrong department ({row['Department']} != {dept})"

        return True, "ok"

    def _preference_score(self, name: str, shift_name: str) -> int:
        """Higher score = better match. Used to sort candidates."""
        row = self.staff_df[self.staff_df["Name"] == name].iloc[0]
        pref = row["Shift Preference"].lower()
        shift_lower = shift_name.lower()

        if pref == "any":
            return 2
        if pref in shift_lower:
            return 3   # exact preference match
        return 1       # available but not preferred

    def _fairness_score(self, name: str) -> float:
        """Lower score = more under-target = should be scheduled first."""
        row = self.staff_df[self.staff_df["Name"] == name].iloc[0]
        target  = float(row["Target Hours/Week"])
        current = self._hours_worked.get(name, 0) + self._historical_hours.get(name, 0)
        return current - target   # negative = needs hours

    # ── Greedy Scheduler ─────────────────────────────────────────────────────

    def _pick_staff(self, day: str, shift_row: pd.Series,
                    role_filter: str, already_picked: list) -> list:
        """Pick the best candidate(s) for a role."""
        active_staff = self.staff_df[self.staff_df["Active"]]
        dept = shift_row["Department"]
        duration = shift_row["Duration"]

        candidates = []
        for _, s in active_staff.iterrows():
            name = s["Name"]
            if name in already_picked:
                continue
            if role_filter != "Any" and s["Role"] != role_filter:
                continue

            eligible, reason = self._can_work(name, day, dept, duration)
            if not eligible:
                continue

            pref_score    = self._preference_score(name, shift_row["Shift Name"])
            fairness_score = self._fairness_score(name)

            candidates.append({
                "name":          name,
                "role":          s["Role"],
                "score":         pref_score - (fairness_score * 0.1),
                "fairness":      fairness_score,
            })

        # Randomize candidates with same score to ensure variety
        random.shuffle(candidates)
        # Sort primarily by lowest fairness score (most under target), then by preference, then random tiebreaker
        candidates.sort(key=lambda x: (x["fairness"], -x["score"], random.random()))
        return candidates

    def _assign(self, name: str, day: str, shift_row: pd.Series,
                is_sby: bool = False):
        """Record an assignment and update runtime state."""
        duration = shift_row["Duration"]
        self._hours_worked[name]  = self._hours_worked.get(name, 0) + duration
        if name not in self._days_assigned:
            self._days_assigned[name] = set()
        self._days_assigned[name].add(day)

        self._assignments.append({
            "Day":        day,
            "Department": shift_row["Department"],
            "Shift":      shift_row["Shift Name"],
            "Start":      str(shift_row["Start Time"]),
            "End":        str(shift_row["End Time"]),
            "Duration":   duration,
            "Name":       name,
            "Role":       self.staff_df.loc[
                              self.staff_df["Name"] == name, "Role"].values[0],
            "SBY":        "Yes" if is_sby else "No",
        })

    def _fill_shift(self, day: str, shift_row: pd.Series):
        """Fill one shift slot with eligible staff."""
        min_senior = int(shift_row["Min Senior"])
        min_total  = int(shift_row["Min Total Staff"])
        max_total  = int(shift_row["Max Total Staff"])

        picked = []

        # Step 1: Fill Senior slots first (hard constraint)
        for _ in range(min_senior):
            candidates = self._pick_staff(day, shift_row, "Senior", picked)
            if candidates:
                self._assign(candidates[0]["name"], day, shift_row)
                picked.append(candidates[0]["name"])
            else:
                # FIXED: Try Any role if no Senior available (graceful degradation)
                fallback = self._pick_staff(day, shift_row, "Any", picked)
                if fallback:
                    self._assign(fallback[0]["name"], day, shift_row)
                    picked.append(fallback[0]["name"])
                    self.warnings.append(
                        f"⚠️ {day} {shift_row['Department']} {shift_row['Shift Name']}: "
                        f"No Senior available — filled with Junior as fallback."
                    )
                else:
                    self.warnings.append(
                        f"⚠️ {day} {shift_row['Department']} {shift_row['Shift Name']}: "
                        f"Could not fill Senior slot — no staff available at all."
                    )

        # Step 2: Fill remaining slots with any eligible staff (Junior preferred for fairness)
        while len(picked) < min_total:
            candidates = self._pick_staff(day, shift_row, "Any", picked)
            if not candidates:
                self.warnings.append(
                    f"⚠️ {day} {shift_row['Department']} {shift_row['Shift Name']}: "
                    f"Understaffed — only {len(picked)}/{min_total} filled."
                )
                break
            self._assign(candidates[0]["name"], day, shift_row)
            picked.append(candidates[0]["name"])

        # Step 3: Fill up to max_total with remaining available staff
        # CRITICAL: If this is a quiet day (scaled down), skip the extra 'Fill to Max' 
        # to ensure we don't overstaff just to hit hour targets.
        if "Is_Quiet_Day" in shift_row.index and shift_row["Is_Quiet_Day"]:
            return

        while len(picked) < max_total:
            candidates = self._pick_staff(day, shift_row, "Any", picked)
            if not candidates:
                break
            
            # FIXED: Allow assignment up to Max Hours even if Target is reached
            assigned_this_loop = False
            for cand in candidates:
                cand_name = cand["name"]
                cand_row  = self.staff_df[self.staff_df["Name"] == cand_name].iloc[0]
                current_hrs = self._hours_worked.get(cand_name, 0)
                
                # Check Max Hours strictly
                if (current_hrs + shift_row["Duration"]) <= float(cand_row["Max Hours/Week"]):
                    self._assign(cand_name, day, shift_row)
                    picked.append(cand_name)
                    assigned_this_loop = True
                    break # Slot filled, move to next slot in 'while' loop
            
            if not assigned_this_loop:
                break # No more candidates can fit this shift without hitting Max Hours

    def _check_week_viability(self) -> list:
        """Pre-flight check before generation to warn about staff shortages."""
        issues = []
        try:
            # Calculate total shift slots needed (Min Total Staff)
            # Add Duration column to staff_df for easy multiplication if needed, but it's in shifts_df
            
            # Estimate total shift hours needed
            demand_hours = (self.shifts_df["Duration"] * self.shifts_df["Min Total Staff"]).sum()
            
            # Calculate total active staff capacity
            active_staff = self.staff_df[self.staff_df["Active"]]
            total_capacity = active_staff["Max Hours/Week"].sum()
            
            if total_capacity < (demand_hours * 0.95): # 5% buffer
                shortfall_hrs = demand_hours - total_capacity
                issues.append(
                    f"🚨 CRITICAL STAFF SHORTAGE: Total staff capacity ({total_capacity:.1f}h) "
                    f"is less than shift demand ({demand_hours:.1f}h). "
                    f"Expected shortfall: ~{shortfall_hrs:.1f} hours. Add staff to fix."
                )
        except:
            pass
        return issues

    # ── Main Generator ────────────────────────────────────────────────────────

    def generate_week(self, week_start: datetime = None,
                      sby_pool: list = None,
                      forecast_scaling: dict = None) -> pd.DataFrame:
        """
        Generate a full week rota.
        forecast_scaling: {DayName: ForecastValue, ...}
        If provided, shift templates will be dynamically adjusted based on Sales per Staff Hour logic.
        """
        random.seed(42)  # Ensure deterministic, reproducible schedules and wage estimates
        
        if week_start is None:
            today = datetime.today()
            days_ahead = (7 - today.weekday()) % 7
            week_start = today + timedelta(days=days_ahead if days_ahead else 7)
        if not isinstance(week_start, datetime):
            week_start = datetime.combine(week_start, dt_time.min)

        # Reset session state
        self._hours_worked  = {}
        # Keep _historical_hours if they were loaded via a separate call
        self._days_assigned = {}
        self._assignments   = []
        self.warnings       = []
        
        # Pre-flight viability check
        viability_issues = self._check_week_viability()
        for issue in viability_issues:
            self.warnings.append(issue)

        day_names   = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        departments = ["Kitchen", "Front"]

        # Deep copy to avoid mutating the original template
        working_shifts_df = self.shifts_df.copy()
        working_shifts_df["Is_Quiet_Day"] = False    # <- add this

        # --- DYNAMIC FORECAST SCALING ---
        if forecast_scaling:
            avg_day_rev = 1800.0  # reference point
            for idx, row in working_shifts_df.iterrows():
                day = row["Day"]
                forecast = forecast_scaling.get(day, avg_day_rev)
                
                # Simple logic: 
                # +20% rev = +1 staff min
                # +50% rev = +2 staff min
                # -20% rev = -1 staff min
                shift_name = str(row["Shift Name"]).lower()
                
                # Focus scaling on Evening shifts as they handle the bulk of peaks
                if "evening" in shift_name or "mid" in shift_name:
                    if forecast > (avg_day_rev * 1.5):
                        working_shifts_df.at[idx, "Min Total Staff"] += 2
                        working_shifts_df.at[idx, "Max Total Staff"] += 2
                    elif forecast > (avg_day_rev * 1.2):
                        working_shifts_df.at[idx, "Min Total Staff"] += 1
                        working_shifts_df.at[idx, "Max Total Staff"] += 1
                    elif forecast < (avg_day_rev * 0.7):
                        working_shifts_df.at[idx, "Min Total Staff"] = max(1, row["Min Total Staff"] - 1)
                        working_shifts_df.at[idx, "Max Total Staff"] = max(1, row["Max Total Staff"] - 1)
                        working_shifts_df.at[idx, "Is_Quiet_Day"] = True


        for day in day_names:
            for dept in departments:
                dept_shifts = working_shifts_df[
                    (working_shifts_df["Day"] == day) &
                    (working_shifts_df["Department"] == dept)
                ]
                for _, shift_row in dept_shifts.iterrows():
                    self._fill_shift(day, shift_row)

        rota_df = pd.DataFrame(self._assignments)
        if rota_df.empty:
            return rota_df

        # Add calendar dates
        date_map = {day: week_start + timedelta(days=i) for i, day in enumerate(day_names)}
        rota_df["Date"] = rota_df["Day"].map(date_map).dt.strftime("%d/%m/%Y")

        return rota_df

    # ── Fairness Report ───────────────────────────────────────────────────────

    def get_hours_summary(self) -> pd.DataFrame:
        """Returns per-person hours summary with target comparison."""
        if self.staff_df is None or self.staff_df.empty:
            return pd.DataFrame(columns=["Name","Role","Department","Target Hrs","Scheduled Hrs","Delta","Status"])

        rows = []
        for _, s in self.staff_df[self.staff_df["Active"]].iterrows():
            name    = s["Name"]
            actual  = self._hours_worked.get(name, 0)
            target  = float(s.get("Target Hours/Week", 0))
            max_hrs = float(s.get("Max Hours/Week", 48))
            delta   = actual - target
            flag    = "✅ On Target" if abs(delta) <= 2 else (
                      "🔴 Over"   if delta > 2 else "🟡 Under")
            rows.append({
                "Name":           name,
                "Role":           s.get("Role", "Junior"),
                "Department":     s.get("Department", "Floor"),
                "Target Hrs":     target,
                "Scheduled Hrs":  round(actual, 1),
                "Delta":          round(delta, 1),
                "Status":         flag,
            })
        
        if not rows:
            return pd.DataFrame(columns=["Name","Role","Department","Target Hrs","Scheduled Hrs","Delta","Status"])

        return pd.DataFrame(rows).sort_values("Delta", ascending=False)

    # ── Export ────────────────────────────────────────────────────────────────

    def export_rota(self, rota_df: pd.DataFrame, output_path: str = None) -> str:
        """
        Export rota to CSV.
        Default: saves to Rota week <date> folder matching existing format.
        """
        if output_path is None:
            output_path = os.path.join(os.getcwd(), "generated_rota.csv")

        rota_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    def get_coverage_heatmap(self, rota_df: pd.DataFrame) -> pd.DataFrame:
        """Returns a Day × Shift headcount matrix for heatmap display."""
        if rota_df.empty:
            return pd.DataFrame()

        non_sby = rota_df[rota_df["SBY"] == "No"]
        pivot   = non_sby.groupby(["Day", "Shift"])["Name"].count().unstack(fill_value=0)

        day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        pivot     = pivot.reindex([d for d in day_order if d in pivot.index])
        return pivot

    def estimate_weekly_cost(self, rota_df: pd.DataFrame,
                              rates_csv: str = None) -> dict:
        """
        Estimate wage cost for the generated rota using personnel_rates_master.csv.
        """
        if rota_df.empty:
            return {"total": 0, "breakdown": {}}

        rates_path = rates_csv or os.path.join(BASE, "personnel_rates_master.csv")
        try:
            rates_df = pd.read_csv(rates_path, encoding="utf-8-sig")
            rates_df.columns = [c.strip() for c in rates_df.columns]
        except:
            self.warnings.append("⚠️ Could not read personnel_rates_master.csv — Wage estimation defaulted to £0.")
            return {"total": 0, "breakdown": {}}

        def clean_rate(v):
            try:
                return float(str(v).replace(",","").strip())
            except:
                return 0.0

        breakdown = {}
        for name, grp in rota_df.groupby("Name"):
            total_hrs = grp["Duration"].sum()
            r = rates_df[rates_df["Name"].str.strip() == name]
            if r.empty:
                rate = 8.00   # fallback minimum
            else:
                fixed = clean_rate(r.iloc[0].get("Fixed Wage", 0))
                if fixed > 0:
                    breakdown[name] = fixed
                    continue
                rate = clean_rate(r.iloc[0].get("Hourly Rate", 8.0))

            breakdown[name] = round(total_hrs * rate, 2)

        return {
            "total":     round(sum(breakdown.values()), 2),
            "breakdown": breakdown,
        }


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = RotaEngine()
    engine.load_staff()
    engine.load_shifts()

    print("Generating rota for next week...")
    rota = engine.generate_week()
    print(f"✅ {len(rota)} shift assignments generated.\n")

    # Hours summary
    summary = engine.get_hours_summary()
    print("=== Hours Summary ===")
    print(summary.to_string(index=False))

    # Warnings
    if engine.warnings:
        print("\n=== Scheduling Warnings ===")
        for w in engine.warnings:
            print(w)

    # Cost estimate
    cost = engine.estimate_weekly_cost(rota)
    print(f"\n=== Estimated Weekly Wage Cost ===")
    print(f"  Total: £{cost['total']:,.2f}")
    for name, amt in sorted(cost["breakdown"].items(), key=lambda x: -x[1]):
        print(f"  {name:<35} £{amt:>7,.2f}")

    # Export
    out = engine.export_rota(rota)
    print(f"\n✅ Rota exported to: {out}")
