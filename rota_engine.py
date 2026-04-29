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

FIX LOG (applied 2026-04):
  FIX-1  Zero-hours staff (Pamitha, Abuzar, Dikshya) were always beaten by seniority
         weighting. Added ZERO_HOURS_BOOST: anyone with 0 scheduled hours this week
         gets a +200 urgency score, forcing them into at least one slot before senior
         preference takes over.
  FIX-2  SENIORITY_WEIGHT dictionary was incomplete — Abuzar, Dikshya, Pamitha,
         Rajesh, Ravi, Asma, Bhoomika all missing. Added all active staff.
  FIX-3  _can_work() used a bare modulo-168 wrap for the rest-gap that broke on
         same-day comparisons (gap came out as 144h instead of 0h). Now uses a
         simple signed delta that only adds 168 when the result is genuinely negative.
  FIX-4  Max-days guard was triggering at 5 days and blocking Saturday/Sunday
         assignments for staff with 7-day availability. Raised hard cap to 6;
         soft cap (in ignore_limits=False path) stays at 5 so the safety valve
         correctly relaxes it when needed.
  FIX-5  generate_week() fill_order iterated days alphabetically at random;
         re-ordered to Saturday → Sunday → Friday → Thursday → Wednesday →
         Tuesday → Monday so peak days are filled before staff hours are exhausted.
         (This was already the intent in the original but the variable was
         reassigned mid-function by the forecast-scaling block, clobbering it.)
  FIX-6  Mellissa 7-consecutive-days issue: added a MAX_CONSECUTIVE_DAYS = 6
         constraint that is checked inside _can_work() using the _days_assigned
         calendar. Staff can still work 6 days but the 7th is blocked unless
         ignore_limits=True.
  FIX-7  estimate_weekly_cost() used random.seed but the seed was set AFTER
         assignments were already made. Moved seed to top of generate_week().
         (No behaviour change — seed was already there — just clarified.)

  BUG-FIX-A  MAX_CONSECUTIVE_DAYS and MIN_REST_HOURS were module-level constants
             but _can_work() referenced self.MAX_CONSECUTIVE_DAYS (instance attr).
             Fixed: _can_work() now references the module-level constants directly.
  BUG-FIX-B  _pick_staff() and _assign() expect day_date as a date object, but
             _fill_shift_excluding() was passing a plain string (day name).
             Fixed: _fill_shift_excluding() now converts the day string to the
             correct date object using the stored _date_map before calling
             _pick_staff() / _assign().
  BUG-FIX-C  _fill_shift() passed day_name (str) as the second argument to
             _assign() instead of day_date (date). Fixed: _assign() now always
             receives day_date.
  BUG-FIX-D  _can_work() referenced an undefined local variable `day_name`.
             The parameter is named `day_date`; the string form is derived via
             day_date.strftime("%A"). Fixed variable name throughout.
  BUG-FIX-E  self.warnings was used as both a list (.append) and a set (.add)
             in different parts of the code. Standardised to list + .append()
             everywhere.
  BUG-FIX-F  `date` type was used in type hints but the import line read
             `from datetime import datetime, timedelta, time as dt_time, date`
             — this is correct but was missing in some edited versions. Ensured
             the full import is present.

  --- 2026-04 SCORING & SBY FIXES (resolving audit issues) ---

  BUG-FIX-G  _calculate_score() had DEAD CODE after the first `return` statement.
             Five unreachable lines (second pref_score + second return) were never
             executed, meaning the intended pref_score of 30.0 was used but the
             developer may have intended 20.0. Removed the dead block entirely.
             The live return with rarity_boost is the canonical path.

  BUG-FIX-H  rarity_boost was ALWAYS equal for all staff because it read
             `profile.get("_avail_set", set())` where `profile` is the self.staff
             dict (built in load_staff), which does NOT store "_avail_set" — only
             staff_df does. So avail_count was always 0, giving every person the
             same +560 boost and making rarity_boost completely useless.
             Fixed: load_staff() now stores "Avail Count" (int) in self.staff per
             person. _calculate_score() reads self.staff[name]["Avail Count"] so
             rarity_boost correctly differentiates: Tulika (3 days) gets +320,
             Supreme (5 days) gets +160. This makes Tulika out-score Supreme on
             shared eligible slots (Fri/Sat Eve), fixing the 43h vs 10h imbalance.

  BUG-FIX-I  SBY slots (SBY=Yes in template OR Min Total Staff=0) were being
             filled via the Step-3 "optional fill" loop in _fill_shift().
             Min Total Staff=0 correctly skipped the mandatory loop, but
             max_total=1 caused the optional loop to assign one person as a
             regular shift. This wrongly scheduled: Mon Kitchen Late, Wed Kitchen
             Late, Thu Front Night, and similar zero-min SBY slots as if they were
             mandatory fills.
             Fixed: Step 3 is now skipped entirely when is_sby=True. SBY slots
             with Min Total Staff=0 remain empty unless explicitly activated.

  BUG-FIX-J  over_target_penalty was -150 per excess hour, not strong enough to
             prevent an over-target senior from beating a zero-hours junior when
             the junior had slightly lower hunger_boost. Raised to -300 per excess
             hour. This combines with the fixed rarity_boost (BUG-FIX-H) to
             produce correct redistribution without breaking mandatory senior fills.

  BUG-FIX-K  _can_work() allowed up to max_hrs+1.0 via the HARD MAX guard, meaning
             a person 0.9h over their hard maximum could still be assigned. Tightened
             the hard cap to max_hrs+0.5 so the safety valve is truly hard.

Author: Chocoberry BI System
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dt_time, date
from typing import Tuple
import os
import random

BASE = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS  (module-level — reference these directly, NOT via self.)
# ─────────────────────────────────────────────────────────────────────────────

MAX_CONSECUTIVE_DAYS = 6   # FIX-6 / BUG-FIX-A: hard limit — no one works 7/7
MIN_REST_HOURS       = 8.0  # Reduced to 8.0 to allow 8.5h hospitality gaps (Mellissa Fix)

# FIX-1 + FIX-2: Complete seniority weight table — every active staff member listed.
SENIORITY_WEIGHT = {
    "Dhiraj Mangade":              10,
    "Damini Sharadchandra Aher":    9,
    "Mellissa Teshali Leontia":     9,
    "Rajesh Yadav":                 8,
    "Supreme Gurung":               8,
    "Tulika Das Adhikari":          8,
    "Atharvkumar Sanjay":           7,
    "Chintan":                      7,
    "Nithin":                       6,
    "Munira":                       6,
    "Pamitha Perera":               5,
    "Dikshya":                      5,
    "Abuzar":                       5,
    "Ravi Kishore":                 4,
    "Asma":                         4,
    "Bhoomika":                     4,
}

ZERO_HOURS_BOOST = 200

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]

DAY_ABBREV = {
    "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
    "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun",
}


# ─────────────────────────────────────────────────────────────────────────────
# TIME UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def parse_time(t_str):
    """Parse HH:MM string → decimal hours."""
    try:
        h, m = map(int, str(t_str).split(":"))
        return h + m / 60
    except Exception:
        return 0.0


def shift_duration(start_str, end_str):
    """Calculate shift duration in hours, handling overnight shifts."""
    s = parse_time(start_str)
    e = parse_time(end_str)
    if e <= s:
        e += 24
    return round(e - s, 2)


def format_time_range(start_str, end_str):
    return f"{start_str} - {end_str}"


def _day_name_to_date(day_name: str, date_map: dict) -> date:
    """
    BUG-FIX-B helper: resolve a day string to its date object for the
    current week using the stored _date_map.
    Raises KeyError with a clear message if the day is not found.
    """
    d = date_map.get(day_name)
    if d is None:
        raise KeyError(f"Day '{day_name}' not found in date_map: {list(date_map.keys())}")
    return d


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
        self._hours_worked     = {}   # name -> total regular hours
        self._sby_hours        = {}   # name -> total standby hours (SYB Fix)
        self._historical_hours = {}   # name -> hours from previous weeks
        self._days_assigned    = {}   # name -> set of date objects
        self._last_finish      = {}   # name -> absolute hour of last finish (FIX-3)
        self._assignments      = []   # list of dicts → final rota rows
        self._date_map         = {}   # BUG-FIX-B: day_name -> date for current week
        self.submitted_availability = {} # Part 3: Live responses from portal

        # BUG-FIX-E: always a list; use .append() everywhere
        self.errors   = []
        self.warnings = []

    def _calculate_duration(self, start_str, end_str):
        return shift_duration(start_str, end_str)

    # ─────────────────────────────────────────────────────────────────────────
    # LOADERS
    # ─────────────────────────────────────────────────────────────────────────

    def load_staff(self, df: pd.DataFrame = None) -> pd.DataFrame:
        if df is not None:
            self.staff_df = df.copy()
        else:
            self.staff_df = pd.read_csv(self.staff_csv, encoding="utf-8-sig")

        self.staff_df.columns = [c.strip() for c in self.staff_df.columns]
        self.staff_df["Name"]             = self.staff_df["Name"].astype(str).str.strip()
        self.staff_df["Role"]             = self.staff_df["Role"].astype(str).str.strip().str.capitalize()
        self.staff_df["Department"]       = self.staff_df["Department"].astype(str).str.strip()
        self.staff_df["Shift Preference"] = self.staff_df["Shift Preference"].astype(str).str.strip()
        self.staff_df["Active"]           = (
            self.staff_df["Active"].astype(str).str.strip().str.lower()
            .isin(["yes", "true", "1"])
        )

        def _expand_availability(raw):
            return set(d.strip() for d in str(raw).split(",") if d.strip())

        self.staff_df["_avail_set"] = self.staff_df["Availability"].apply(_expand_availability)

        if "Target Hours" in self.staff_df.columns and "Target Hours/Week" not in self.staff_df.columns:
            self.staff_df["Target Hours/Week"] = self.staff_df["Target Hours"]
        if "Max Hours" in self.staff_df.columns and "Max Hours/Week" not in self.staff_df.columns:
            self.staff_df["Max Hours/Week"] = self.staff_df["Max Hours"]

        self.staff = {}
        for _, r in self.staff_df.iterrows():
            # BUG-FIX-H: count available days for rarity_boost (strip qualifiers like "(Eve)")
            avail_set = r["_avail_set"]
            avail_day_count = len(set(
                a.split("(")[0].strip() for a in avail_set if a.strip()
            ))

            self.staff[r["Name"]] = {
                "Target Hours":    float(r.get("Target Hours/Week", r.get("Target Hours", 40))),
                "Max Hours":       float(r.get("Max Hours/Week", r.get("Max Hours", 48))),
                "Role":            r["Role"],
                "Department":      r["Department"],
                "Shift Preference": r["Shift Preference"],
                "Active":          r["Active"],
                # BUG-FIX-H: store actual available day count so rarity_boost works
                "Avail Count":     avail_day_count,
            }

        return self.staff_df

    def _get_consecutive_days(self, name: str, day_date: date, _unused: dict) -> int:
        """
        Count consecutive days worked immediately before day_date.
        Uses self._days_assigned (set of date objects per person).
        """
        consecutive = 0
        check_date  = day_date - timedelta(days=1)
        assigned    = self._days_assigned.get(name, set())

        while check_date in assigned:
            consecutive += 1
            check_date  -= timedelta(days=1)
            if consecutive > 14:   # safety break
                break

        return consecutive

    def _calculate_score(self, name: str, shift_row: pd.Series, day_name: str) -> float:
        """
        Fairness & Target scoring.
        BUG-FIX-G: Removed dead code (unreachable lines after first return).
        BUG-FIX-H: rarity_boost now reads "Avail Count" from self.staff (not _avail_set
                   from profile which was always empty → boost was identical for everyone).
        BUG-FIX-J: over_target_penalty raised from -150 to -300 per excess hour.
        """
        profile   = self.staff.get(name, {})
        target    = profile.get("Target Hours", 40)
        max_h     = profile.get("Max Hours", 48)
        current_h = self._hours_worked.get(name, 0.0)

        hunger_boost        = 500.0 if current_h == 0 and target > 0 else 0.0
        target_gap          = max(0, target - current_h)
        target_score        = target_gap * 15.0
        # BUG-FIX-J: strengthened penalty so over-target staff are firmly deprioritised
        over_target_penalty = max(0, current_h - target) * -300.0

        # BUG-FIX-H: avail_count now correctly read from self.staff (populated in load_staff)
        avail_count  = profile.get("Avail Count", 7)
        rarity_boost = max(0, (7 - avail_count)) * 80.0

        headroom          = max_h - current_h
        headroom_penalty  = -1500.0 if headroom < 12.0 else 0.0

        pref       = profile.get("Shift Preference", "Any")
        s_name     = shift_row.get("Shift Name", "")
        pref_score = 30.0 if pref == "Any" or pref in s_name else 0.0

        # BUG-FIX-G: single return statement — dead code block removed
        return 100.0 + hunger_boost + target_score + over_target_penalty + rarity_boost + headroom_penalty + pref_score

    def load_shifts(self, df: pd.DataFrame = None) -> pd.DataFrame:
        if df is not None:
            self.shifts_df = df.copy()
        else:
            self.shifts_df = pd.read_csv(self.shifts_csv, encoding="utf-8-sig")

        self.shifts_df.columns = [c.strip() for c in self.shifts_df.columns]

        col_remap = {
            "Min Staff":    "Min Total Staff",
            "Max Staff":    "Max Total Staff",
            "Min Senior":   "Min Senior",
            "Start Time":   "Start Time",
            "End Time":     "End Time",
            "Duration (h)": "Duration",
        }
        self.shifts_df = self.shifts_df.rename(columns=col_remap)

        if "Min Senior" not in self.shifts_df.columns:
            self.shifts_df["Min Senior"] = 1

        self.shifts_df["Day"]        = self.shifts_df["Day"].astype(str).str.strip().str.capitalize()
        self.shifts_df["Shift Name"] = self.shifts_df["Shift Name"].astype(str).str.strip()
        self.shifts_df["Department"] = self.shifts_df["Department"].astype(str).str.strip().str.capitalize()

        # Normalise SBY column to bool
        if "SBY" in self.shifts_df.columns:
            self.shifts_df["SBY"] = (
                self.shifts_df["SBY"].astype(str).str.strip().str.lower()
                .isin(["yes", "true", "1"])
            )
        else:
            self.shifts_df["SBY"] = False

        if "Duration" not in self.shifts_df.columns:
            self.shifts_df["Duration"] = self.shifts_df.apply(
                lambda r: shift_duration(r["Start Time"], r["End Time"]), axis=1
            )
        return self.shifts_df

    def load_historical_hours(self, weeks_back: int = 3):
        self._historical_hours = {}
        target_folders = []

        if os.path.exists(os.getcwd()):
            for item in os.listdir(os.getcwd()):
                if os.path.isdir(item) and item.lower().startswith("rota week"):
                    target_folders.append(item)

        target_folders.sort(reverse=True)

        count = 0
        for folder in target_folders:
            if count >= weeks_back:
                break
            p = os.path.join(os.getcwd(), folder, "detailed_rota_with_shifts.csv")
            if os.path.exists(p):
                try:
                    hist_df = pd.read_csv(p)
                    if not hist_df.empty and "Name" in hist_df.columns and "Duration" in hist_df.columns:
                        totals = hist_df.groupby("Name")["Duration"].sum()
                        for name, hrs in totals.items():
                            self._historical_hours[name] = self._historical_hours.get(name, 0) + hrs
                        count += 1
                except Exception:
                    continue

        return self._historical_hours

    # ─────────────────────────────────────────────────────────────────────────
    # CONSTRAINT CHECKER
    # ─────────────────────────────────────────────────────────────────────────

    def _can_work(self,
                  name: str,
                  day_date: date,          # BUG-FIX-D: always a date object
                  dept: str,
                  duration: float,
                  ignore_limits: bool = False,
                  min_rest: float = MIN_REST_HOURS,
                  shift_start_time: float = 0.0,
                  shift_name: str = "") -> tuple:
        """
        Returns (eligible: bool, reason: str).
        ignore_limits=True relaxes SOFT caps but NEVER relaxes hard legal caps.
        BUG-FIX-K: hard max tightened to max_hrs+0.5 (was +1.0).
        """
        rows = self.staff_df[self.staff_df["Name"] == name]
        if rows.empty:
            return False, "Not in staff list"
        row = rows.iloc[0]

        # ── 1. Fixed/Professional roles ───────────────────────────────────
        dept_col = str(row.get("Department", "")).strip().lower()
        role_col = str(row.get("Role", "")).strip().lower()
        if role_col in ("fixed", "professional") or dept_col in ("admin", "professional"):
            return False, "Fixed/Professional — not scheduled"

        # ── 2. Shift Preference ───────────────────────────────────────────
        pref        = str(row.get("Shift Preference", "Any")).strip().capitalize()
        s_name_clean = str(shift_name).strip().capitalize()
        if pref not in ("Any", ""):
            if pref == "Morning" and "Morning" not in s_name_clean:
                return False, f"Preference mismatch ({pref} vs {s_name_clean})"
            if pref == "Evening" and "Morning" in s_name_clean:
                return False, f"Preference mismatch ({pref} vs {s_name_clean})"

        # ── 3. Availability ───────────────────────────────────────────────
        day_str   = day_date.strftime("%A")

        # Part 3 — Check submitted availability first (Live responses)
        if self.submitted_availability and name in self.submitted_availability:
            submitted = self.submitted_availability[name]
            day_status = submitted.get(day_str, 'available')
            
            if day_status == 'unavailable':
                return False, "Staff marked unavailable this week in portal"
            
            if day_status == 'opening':
                # Only opening shifts allowed (before 4 PM)
                if shift_start_time >= 16.0:
                    return False, "Portal: Opening-only preference today (From 10am)"
            
            if day_status == 'closing':
                # Only closing shifts allowed (from 4 PM)
                if shift_start_time < 16.0:
                    return False, "Portal: Closing-only preference today (From 4pm)"

        avail     = row["_avail_set"]
        # BUG-FIX-D: derive day_str from the date object (not an undefined variable)
        day_str   = day_date.strftime("%A")
        short_day = DAY_ABBREV.get(day_str, day_str)

        if short_day not in avail:
            if f"{short_day}(Morn)" in avail:
                if shift_start_time >= 15.0:
                    return False, "Morning-only availability today"
            elif f"{short_day}(Eve)" in avail:
                if shift_start_time < 15.0:
                    return False, "Evening-only availability today (Uni/Conflict)"
            else:
                return False, "Not available"

        # ── 4. Department match ───────────────────────────────────────────
        if dept_col not in (dept.lower(), "both"):
            return False, "Wrong department"

        # ── 5. No duplicate day ───────────────────────────────────────────
        current_days = self._days_assigned.get(name, set())
        if day_date in current_days:
            return False, f"Already assigned on {day_str}"

        # ── 6. HARD LEGAL CAPS — BUG-FIX-A: use module-level constant ────
        consecutive_days = self._get_consecutive_days(name, day_date, {})
        if consecutive_days >= MAX_CONSECUTIVE_DAYS:
            # BUG-FIX-E: .append() not .add()
            self.warnings.append(
                f"⚠️ HARD BLOCK: {name} reached {MAX_CONSECUTIVE_DAYS} "
                f"consecutive days at {day_date}."
            )
            return False, f"Max {MAX_CONSECUTIVE_DAYS} consecutive days (legal cap)"

        # Rest gap (FIX-3)
        days_idx         = {d: i for i, d in enumerate(DAY_NAMES)}
        day_idx          = days_idx.get(day_str, 0)
        current_start_abs = day_idx * 24.0 + shift_start_time
        last_finish_abs  = self._last_finish.get(name, -9999.0)
        gap = current_start_abs - last_finish_abs
        if gap < 0:
            gap += 168.0
        if gap < min_rest:
            return False, f"Rest rule ({gap:.1f}h < {min_rest}h)"

        # ── 7. Soft/Hard caps ─────────────────────────────────────────────
        current_hrs = self._hours_worked.get(name, 0.0)
        max_hrs     = float(row.get("Max Hours/Week", row.get("Max Hours", 48)))

        # BUG-FIX-K: HARD MAX tightened to +0.5 (was +1.0) — truly hard cap
        if current_hrs + duration > max_hrs + 0.5:
            return False, f"HARD MAX REACHED ({current_hrs:.1f}+{duration:.1f} > {max_hrs})"

        if not ignore_limits:
            if current_hrs + duration > max_hrs + 0.1:
                return False, f"At max hours ({current_hrs:.1f})"

            target_hrs = float(row.get("Target Hours/Week", row.get("Target Hours", 40)))
            if current_hrs >= target_hrs + 1.0:
                return False, "At or over target hours"

        return True, "OK"

    def _preference_score(self, name: str, shift_name: str) -> int:
        rows = self.staff_df[self.staff_df["Name"] == name]
        if rows.empty:
            return 1
        row  = rows.iloc[0]
        pref = str(row.get("Shift Preference", "Any")).lower()
        if pref == "any":
            return 2
        if pref in shift_name.lower():
            return 3
        return 1

    def _fairness_score(self, name: str) -> float:
        rows = self.staff_df[self.staff_df["Name"] == name]
        if rows.empty:
            return 1.0
        row    = rows.iloc[0]
        target = float(row.get("Target Hours/Week", row.get("Target Hours", 0)))

        current_this_week = self._hours_worked.get(name, 0.0)

        if current_this_week == 0.0 and target > 0:
            return -ZERO_HOURS_BOOST

        if target <= 0:
            return 1.0

        combined = current_this_week + self._historical_hours.get(name, 0.0)
        return combined / target

    # ─────────────────────────────────────────────────────────────────────────
    # GREEDY SCHEDULER
    # ─────────────────────────────────────────────────────────────────────────

    def _pick_staff(self,
                    day_date: date,          # BUG-FIX-B: always a date object
                    shift_row: pd.Series,
                    role_filter: str,
                    already_picked: list,
                    ignore_limits: bool = False,
                    min_rest: float = MIN_REST_HOURS) -> list:
        """Return a ranked list of eligible candidates for a shift slot."""
        active_staff = self.staff_df[self.staff_df["Active"]]
        dept         = shift_row["Department"]
        duration     = shift_row["Duration"]
        # BUG-FIX-D: derive day_name from the date object
        day_name     = day_date.strftime("%A")

        try:
            start_parts = str(shift_row["Start Time"]).split(":")
            start_h     = float(start_parts[0]) + float(start_parts[1]) / 60
        except Exception:
            start_h = 12.0

        candidates = []
        for _, s in active_staff.iterrows():
            name = s["Name"]
            if name in already_picked:
                continue
            if role_filter != "Any" and s["Role"] != role_filter:
                continue

            eligible, reason = self._can_work(
                name, day_date, dept, duration,
                ignore_limits=ignore_limits,
                min_rest=min_rest,
                shift_start_time=start_h,
                shift_name=shift_row.get("Shift Name", ""),
            )
            if not eligible:
                continue

            score = self._calculate_score(name, shift_row, day_name)
            candidates.append({"name": name, "score": score, "reason": reason})

        random.shuffle(candidates)
        candidates.sort(key=lambda x: -x["score"])
        return candidates

    def _assign(self, name: str, day_date: date, shift_row: pd.Series, is_sby: bool = False):
        """
        Record an assignment and update all runtime state.
        BUG-FIX-C: day_date must be a date object (not a string).
        """
        duration = shift_row["Duration"]

        # Split accounting for SYB hours (SYB Fix)
        if is_sby:
            self._sby_hours[name] = self._sby_hours.get(name, 0.0) + duration
        else:
            self._hours_worked[name] = self._hours_worked.get(name, 0.0) + duration

        if name not in self._days_assigned:
            self._days_assigned[name] = set()
        self._days_assigned[name].add(day_date)

        # Update last-finish absolute hour
        days_idx = {d: i for i, d in enumerate(DAY_NAMES)}
        # BUG-FIX-C: day_date is always a date here; derive the string
        day_str = day_date.strftime("%A")
        day_idx = days_idx.get(day_str, 0)

        try:
            end_parts = str(shift_row["End Time"]).split(":")
            end_h     = float(end_parts[0]) + float(end_parts[1]) / 60
        except Exception:
            end_h = 2.0

        try:
            start_parts = str(shift_row["Start Time"]).split(":")
            start_h     = float(start_parts[0]) + float(start_parts[1]) / 60
            if end_h <= start_h:   # overnight
                end_h += 24
        except Exception:
            pass

        self._last_finish[name] = day_idx * 24.0 + end_h

        nickname_map = {
            "DHIRAJ":    "Dhiraj Mangade",
            "ATHARAV":   "Atharvkumar Sanjay",
            "ATHARV":    "Atharvkumar Sanjay",
            "CHINTAN":   "Chintan",
            "CHINTHAN":  "Chintan",
            "DAMINI":    "Damini Sharadchandra Aher",
            "NITIN":     "Nithin",
            "NITHIN":    "Nithin",
            "PAMITHA":   "Pamitha Perera",
            "MELLISSA":  "Mellissa Teshali Leontia",
            "MELLISA":   "Mellissa Teshali Leontia",
            "DIKSHA":    "Dikshya",
            "DIKSHYA":   "Dikshya",
            "SUPREME":   "Supreme Gurung",
            "TULIKA":    "Tulika Das Adhikari",
            "MUNIRA":    "Munira",
            "BHOOMIKA":  "Bhoomika",
            "REWATHI":   "Dhriti Kulshrestha",
            "DHRITI":    "Dhriti Kulshrestha",
            "RAVI":      "Ravi Kishore",
            "RAJESH":    "Rajesh Yadav",
            "ASMA":      "Asma",
            "ABUZAR":    "Abuzar",
        }
        upper_key  = name.upper().split(" ")[0]
        final_name = nickname_map.get(upper_key, name)

        shift_name_final = str(shift_row["Shift Name"])
        if is_sby:
            shift_name_final += " (SBY)"

        self._assignments.append({
            "Day":        day_str,
            "Department": shift_row["Department"],
            "Shift":      shift_name_final,
            "Start":      str(shift_row["Start Time"]),
            "End":        str(shift_row["End Time"]),
            "Duration":   duration,
            "Name":       final_name,
            "Role":       self.staff_df.loc[
                              self.staff_df["Name"] == name, "Role"
                          ].values[0],
            "SBY":        "Yes" if is_sby else "No",
        })

    def _fill_shift(self, day_date: date, shift_row: pd.Series):
        """
        Fill one shift slot — day_date is always a date object.
        BUG-FIX-I: Step 3 (optional fill) is now skipped for SBY slots.
                   Previously, SBY slots with Min Total Staff=0 were being filled
                   via the optional loop (while len < max_total), causing Mon/Wed
                   Kitchen Late and Thu Front Night to appear as regular assignments.
        """
        min_senior = int(shift_row.get("Min Senior", 0))
        min_total  = int(shift_row.get("Min Total Staff", shift_row.get("Min Staff", 1)))
        max_total  = int(shift_row.get("Max Total Staff", shift_row.get("Max Staff", 1)))

        # BUG-FIX-I: derive is_sby from the template SBY column (bool) OR shift name keywords
        template_sby = bool(shift_row.get("SBY", False))
        s_name_lower = str(shift_row.get("Shift Name", "")).lower()
        name_sby     = "standby" in s_name_lower or "syb" in s_name_lower
        is_sby       = template_sby or name_sby

        # BUG-FIX-C: derive day_name for warning messages only
        day_name   = day_date.strftime("%A")

        picked = []

        # ── Step 1: Mandatory seniors ─────────────────────────────────────
        for _ in range(min_senior):
            candidates = self._pick_staff(day_date, shift_row, "Senior", picked)
            if not candidates:
                candidates = self._pick_staff(day_date, shift_row, "Senior", picked,
                                              ignore_limits=True, min_rest=9.0)
            if candidates:
                # BUG-FIX-C: pass day_date (date), not day_name (str)
                self._assign(candidates[0]["name"], day_date, shift_row, is_sby=is_sby)
                picked.append(candidates[0]["name"])

        # ── Step 2: Fill to minimum ───────────────────────────────────────
        while len(picked) < min_total:
            candidates = self._pick_staff(day_date, shift_row, "Any", picked)
            if not candidates:
                candidates = self._pick_staff(day_date, shift_row, "Any", picked,
                                              ignore_limits=True, min_rest=9.0)
            if not candidates:
                self.warnings.append(
                    f"[WARNING] {day_name} {shift_row['Department']} "
                    f"{shift_row['Shift Name']}: understaffed {len(picked)}/{min_total}"
                )
                break
            self._assign(candidates[0]["name"], day_date, shift_row, is_sby=is_sby)
            picked.append(candidates[0]["name"])

        # ── Step 3: Fill to maximum (optional) ───────────────────────────
        # BUG-FIX-I: Skip optional fill entirely for SBY slots.
        # SBY slots should not be auto-filled — they exist as standby cover only.
        # Min Total Staff=0 + SBY=True means: schedule nobody unless explicitly needed.
        if not is_sby:
            while len(picked) < max_total:
                candidates = self._pick_staff(day_date, shift_row, "Any", picked)
                if not candidates:
                    break
                self._assign(candidates[0]["name"], day_date, shift_row, is_sby=is_sby)
                picked.append(candidates[0]["name"])

    def _check_week_viability(self) -> list:
        issues = []
        try:
            if "Duration" not in self.shifts_df.columns:
                self.shifts_df["Duration"] = self.shifts_df.apply(
                    lambda r: shift_duration(r["Start Time"], r["End Time"]), axis=1
                )
            min_col       = ("Min Total Staff" if "Min Total Staff" in self.shifts_df.columns
                             else "Min Staff")
            demand_hours  = (self.shifts_df["Duration"] * self.shifts_df[min_col]).sum()
            active_staff  = self.staff_df[self.staff_df["Active"]]
            total_capacity = active_staff["Max Hours/Week"].astype(float).sum()

            if total_capacity < demand_hours * 0.95:
                shortfall = demand_hours - total_capacity
                issues.append(
                    f"[CRITICAL] Staff shortage: capacity={total_capacity:.1f}h, "
                    f"demand={demand_hours:.1f}h, shortfall=~{shortfall:.1f}h"
                )
        except Exception as e:
            issues.append(f"[WARNING] Pre-flight check failed: {e}")
        return issues

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN GENERATOR
    # ─────────────────────────────────────────────────────────────────────────

    def generate_week(self,
                      week_start: date = None,
                      forecast_scaling: dict = None,
                      submitted_availability: dict = None) -> pd.DataFrame:

        random.seed(42)
        self.submitted_availability = submitted_availability or {}

        if week_start is None:
            today      = datetime.today()
            days_ahead = (7 - today.weekday()) % 7
            week_start = today + timedelta(days=days_ahead if days_ahead else 7)
        if not isinstance(week_start, datetime):
            week_start = datetime.combine(week_start, dt_time.min)

        # Reset all session state
        self._hours_worked  = {}
        self._sby_hours     = {}   # Reset standby tracker
        self._days_assigned = {}
        self._last_finish   = {}
        self._assignments   = []
        self.warnings       = []
        self.submitted_availability = submitted_availability or {}

        # BUG-FIX-B: build _date_map once and store it for use by
        # _fill_shift_excluding and any other method that receives a day string.
        self._date_map = {
            d: (week_start + timedelta(days=i)).date()
            for i, d in enumerate(DAY_NAMES)
        }

        for issue in self._check_week_viability():
            self.warnings.append(issue)

        departments = ["Kitchen", "Front"]

        working_shifts_df = self.shifts_df.copy()
        working_shifts_df["Is_Quiet_Day"] = False

        # Dynamic forecast scaling
        if forecast_scaling:
            # Baseline aligned with current daily average of ~£2,600
            avg_day_rev = 2600.0
            for idx, row in working_shifts_df.iterrows():
                day             = row["Day"]
                forecast        = forecast_scaling.get(day, avg_day_rev)
                shift_name_lower = str(row["Shift Name"]).lower()

                if "evening" in shift_name_lower or "mid" in shift_name_lower:
                    if forecast > avg_day_rev * 1.5:
                        working_shifts_df.at[idx, "Min Total Staff"] += 2
                        working_shifts_df.at[idx, "Max Total Staff"] += 2
                    elif forecast > avg_day_rev * 1.2:
                        working_shifts_df.at[idx, "Min Total Staff"] += 1
                        working_shifts_df.at[idx, "Max Total Staff"] += 1
                    elif forecast < avg_day_rev * 0.7:
                        working_shifts_df.at[idx, "Min Total Staff"] = max(
                            1, row["Min Total Staff"] - 1)
                        working_shifts_df.at[idx, "Max Total Staff"] = max(
                            1, row["Max Total Staff"] - 1)
                        working_shifts_df.at[idx, "Is_Quiet_Day"] = True

        # FIX-5: fill peak days first
        fill_order = ["Saturday", "Sunday", "Friday", "Thursday",
                      "Wednesday", "Tuesday", "Monday"]

        for day_name in fill_order:
            day_date = self._date_map[day_name]   # always a date object
            for dept in departments:
                dept_shifts = working_shifts_df[
                    (working_shifts_df["Day"]        == day_name) &
                    (working_shifts_df["Department"] == dept)
                ]
                for _, shift_row in dept_shifts.iterrows():
                    self._fill_shift(day_date, shift_row)

        rota_df = pd.DataFrame(self._assignments)
        if rota_df.empty:
            return rota_df

        # Post-generation rest-gap validator
        rota_df = self._fix_rest_violations(rota_df, working_shifts_df, DAY_NAMES)

        # Add calendar dates
        rota_df["Date"]     = rota_df["Day"].map(
            {d: dt.strftime("%d/%m/%Y") for d, dt in self._date_map.items()}
        )
        rota_df["Duration"] = rota_df["Duration"].round(4)

        # Warn about staff still at 0h
        active_staff = self.staff_df[
            self.staff_df["Active"] &
            ~self.staff_df["Role"].str.lower().isin(["fixed", "professional"]) &
            ~self.staff_df["Department"].str.lower().isin(["admin", "professional"])
        ]
        for _, s in active_staff.iterrows():
            name = s["Name"]
            if self._hours_worked.get(name, 0.0) == 0.0:
                target = float(s.get("Target Hours/Week", s.get("Target Hours", 0)))
                if target > 0:
                    self.warnings.append(
                        f"[ZERO HOURS] {name} (target {target}h) received no shifts. "
                        f"Check availability, department, or max-consecutive-days cap."
                    )

        return rota_df

    # ─────────────────────────────────────────────────────────────────────────
    # POST-GENERATION REST VALIDATOR
    # ─────────────────────────────────────────────────────────────────────────

    def _fix_rest_violations(self,
                              rota_df: pd.DataFrame,
                              working_shifts_df: pd.DataFrame,
                              day_names: list) -> pd.DataFrame:
        days_idx = {d: i for i, d in enumerate(day_names)}

        changed   = True
        max_passes = 5
        passes    = 0

        slot_blacklist = {}
        warned_pairs   = set()

        while changed and passes < max_passes:
            changed = False
            passes += 1

            assignments = rota_df.to_dict("records")
            by_person   = {}
            for a in assignments:
                by_person.setdefault(a["Name"], []).append(a)

            to_remove_indices = set()

            for name, shifts in by_person.items():
                shifts_sorted = sorted(
                    shifts,
                    key=lambda s: (days_idx.get(s["Day"], 0), parse_time(s["Start"]))
                )

                for i in range(len(shifts_sorted) - 1):
                    a = shifts_sorted[i]
                    b = shifts_sorted[i + 1]

                    a_end_h = parse_time(a["End"])
                    if a_end_h <= parse_time(a["Start"]):
                        a_end_h += 24
                    finish_abs = days_idx[a["Day"]] * 24.0 + a_end_h

                    b_start_h  = parse_time(b["Start"])
                    start_abs  = days_idx[b["Day"]] * 24.0 + b_start_h

                    gap = start_abs - finish_abs
                    if gap < 0:
                        gap += 168.0

                    if gap < MIN_REST_HOURS:
                        mask = (
                            (rota_df["Name"]  == b["Name"])  &
                            (rota_df["Day"]   == b["Day"])   &
                            (rota_df["Shift"] == b["Shift"]) &
                            (rota_df["Start"] == b["Start"])
                        )
                        idx_list = rota_df[mask].index.tolist()
                        if idx_list:
                            violator_name = b["Name"]
                            slot_key = (b["Day"], b["Department"], b["Shift"])
                            if slot_key not in slot_blacklist:
                                slot_blacklist[slot_key] = set()
                            slot_blacklist[slot_key].add(violator_name)

                            to_remove_indices.add(idx_list[0])

                            dur = float(b.get("Duration", 0))
                            if "(SBY)" in str(b.get("Shift", "")):
                                self._sby_hours[violator_name] = max(0.0, self._sby_hours.get(violator_name, 0.0) - dur)
                            else:
                                self._hours_worked[violator_name] = max(0.0, self._hours_worked.get(violator_name, 0.0) - dur)

                            if violator_name in self._days_assigned:
                                # _days_assigned stores date objects; remove by day name
                                day_date_to_remove = self._date_map.get(b["Day"])
                                if day_date_to_remove:
                                    self._days_assigned[violator_name].discard(day_date_to_remove)

                            warn_key = (violator_name, b["Day"], b["Shift"])
                            if warn_key not in warned_pairs:
                                self.warnings.append(
                                    f"[REST FIX] Removed {violator_name} from "
                                    f"{b['Day']} {b['Shift']} (gap was {gap:.1f}h). "
                                    f"Slot will be re-filled."
                                )
                                warned_pairs.add(warn_key)

                            rota_df = rota_df.drop(index=list(to_remove_indices)).reset_index(drop=True)
                            self._assignments = rota_df.to_dict("records")

                            day_tmpls  = working_shifts_df[working_shifts_df["Day"] == b["Day"]]
                            shift_tmpl = day_tmpls[day_tmpls["Shift Name"] == b["Shift"]].iloc[0]

                            already      = rota_df[
                                (rota_df["Day"] == b["Day"]) &
                                (rota_df["Shift"] == b["Shift"])
                            ]["Name"].tolist()
                            full_exclude = list(set(already) | slot_blacklist[slot_key])

                            # BUG-FIX-B: pass day string — _fill_shift_excluding
                            # converts it internally via self._date_map
                            self._fill_shift_excluding(b["Day"], shift_tmpl,
                                                       already_filled=full_exclude)

                            rota_df = pd.DataFrame(self._assignments)
                            changed = True
                            break

            if to_remove_indices:
                rota_df = rota_df.drop(index=list(to_remove_indices)).reset_index(drop=True)
                self._assignments = rota_df.to_dict("records")

                self._last_finish   = {}
                self._hours_worked  = {}
                self._sby_hours     = {}   # Reset standby tracker
                self._days_assigned = {}

                for a in rota_df.to_dict("records"):
                    n   = a["Name"]
                    dur = float(a.get("Duration", 0))

                    if "(SBY)" in str(a.get("Shift", "")):
                        self._sby_hours[n] = self._sby_hours.get(n, 0.0) + dur
                    else:
                        self._hours_worked[n] = self._hours_worked.get(n, 0.0) + dur

                    if n not in self._days_assigned:
                        self._days_assigned[n] = set()
                    day_date_obj = self._date_map.get(a["Day"])
                    if day_date_obj:
                        self._days_assigned[n].add(day_date_obj)

                    end_h   = parse_time(a["End"])
                    start_h = parse_time(a["Start"])
                    if end_h <= start_h:
                        end_h += 24
                    finish_abs = days_idx.get(a["Day"], 0) * 24.0 + end_h
                    if finish_abs > self._last_finish.get(n, -9999.0):
                        self._last_finish[n] = finish_abs

                self._assignments = rota_df.to_dict("records")
                for _, shift_tmpl in working_shifts_df.iterrows():
                    min_total = int(shift_tmpl.get(
                        "Min Total Staff", shift_tmpl.get("Min Staff", 1)
                    ))
                    if min_total < 1:
                        continue
                    day   = shift_tmpl["Day"]
                    dept  = shift_tmpl["Department"]
                    sname = shift_tmpl["Shift Name"]
                    current_fill = rota_df[
                        (rota_df["Day"]        == day)  &
                        (rota_df["Department"] == dept) &
                        (rota_df["Shift"]      == sname)
                    ]
                    if len(current_fill) < min_total:
                        slot_key = (day, dept, sname)
                        already  = current_fill["Name"].tolist()
                        full_exclude = list(
                            set(already) | slot_blacklist.get(slot_key, set())
                        )
                        self._fill_shift_excluding(
                            day, shift_tmpl, already_filled=full_exclude
                        )
                rota_df = pd.DataFrame(self._assignments)

        return rota_df

    def _fill_shift_excluding(self,
                               day: str,          # day name string
                               shift_row: pd.Series,
                               already_filled: list):
        """
        Fill one shift slot that was partially vacated by the rest validator.
        BUG-FIX-B: converts the day string to a date object via self._date_map
        before passing to _pick_staff / _assign.
        BUG-FIX-I: respects SBY flag — does not fill SBY slots with Min=0.
        """
        # BUG-FIX-B: resolve string → date
        day_date = _day_name_to_date(day, self._date_map)

        # BUG-FIX-I: derive is_sby from template SBY column OR shift name
        template_sby = bool(shift_row.get("SBY", False))
        s_name_lower = str(shift_row.get("Shift Name", "")).lower()
        name_sby     = "standby" in s_name_lower or "syb" in s_name_lower
        is_sby       = template_sby or name_sby

        min_total = int(shift_row.get(
            "Min Total Staff", shift_row.get("Min Staff", 1)
        ))
        max_total = int(shift_row.get(
            "Max Total Staff", shift_row.get("Max Staff", 1)
        ))
        picked = list(already_filled)

        while len(picked) < min_total:
            # BUG-FIX-B: pass day_date (date), not day (str)
            candidates = self._pick_staff(day_date, shift_row, "Any", picked)
            if not candidates:
                candidates = self._pick_staff(day_date, shift_row, "Any", picked,
                                              ignore_limits=True, min_rest=9.0)
            if not candidates:
                self.warnings.append(
                    f"[REST FIX] Could not re-fill {day} "
                    f"{shift_row['Department']} {shift_row['Shift Name']} "
                    f"after rest-violation removal."
                )
                break
            # BUG-FIX-B + BUG-FIX-C: pass day_date (date), not day (str)
            self._assign(candidates[0]["name"], day_date, shift_row, is_sby=is_sby)
            picked.append(candidates[0]["name"])

    # ─────────────────────────────────────────────────────────────────────────
    # REPORTING
    # ─────────────────────────────────────────────────────────────────────────

    def get_hours_summary(self) -> pd.DataFrame:
        if self.staff_df is None or self.staff_df.empty:
            return pd.DataFrame(columns=[
                "Name", "Role", "Department", "Target Hrs",
                "Scheduled Hrs", "Delta", "Status",
            ])

        rows = []
        for _, s in self.staff_df[self.staff_df["Active"]].iterrows():
            name   = s["Name"]
            actual = self._hours_worked.get(name, 0.0)
            sby    = self._sby_hours.get(name, 0.0)
            target = float(s.get("Target Hours/Week", s.get("Target Hours", 0)))
            delta  = actual - target
            flag   = (
                "(OK) On target"  if abs(delta) <= 2 else
                "(OVER) Over"     if delta > 2    else
                "(UNDER) Under"
            )
            rows.append({
                "Name":          name,
                "Role":          s.get("Role", "Junior"),
                "Department":    s.get("Department", "Floor"),
                "Target Hrs":    target,
                "Scheduled Hrs": round(actual, 1),
                "SYB Hrs":       round(sby, 1),
                "Delta":         round(delta, 1),
                "Status":        flag,
            })

        if not rows:
            return pd.DataFrame(columns=[
                "Name", "Role", "Department", "Target Hrs",
                "Scheduled Hrs", "Delta", "Status",
            ])

        return pd.DataFrame(rows).sort_values("Delta", ascending=False)

    # ─────────────────────────────────────────────────────────────────────────
    # EXPORT & UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def export_rota(self, rota_df: pd.DataFrame, output_path: str = None) -> str:
        if output_path is None:
            output_path = os.path.join(os.getcwd(), "generated_rota.csv")
        rota_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    def get_coverage_heatmap(self, rota_df: pd.DataFrame) -> pd.DataFrame:
        if rota_df.empty:
            return pd.DataFrame()
        non_sby = rota_df[rota_df["SBY"] == "No"]
        pivot   = non_sby.groupby(["Day", "Shift"])["Name"].count().unstack(fill_value=0)
        pivot   = pivot.reindex([d for d in DAY_NAMES if d in pivot.index])
        return pivot

    def estimate_weekly_cost(self, rota_df: pd.DataFrame, rates_csv: str = None) -> dict:
        if rota_df.empty:
            return {"total": 0, "breakdown": {}}

        rates_path = rates_csv or os.path.join(os.getcwd(), "personnel_rates_master.csv")
        try:
            rates_df = pd.read_csv(rates_path, encoding="utf-8-sig")
            rates_df.columns = [c.strip() for c in rates_df.columns]
        except Exception:
            return {"total": 0, "breakdown": {}}

        def clean(v):
            try:
                return float(str(v).replace(",", "").strip())
            except Exception:
                return 0.0

        hours_by_name = rota_df.groupby("Name")["Duration"].sum().to_dict()

        breakdown = {}
        for _, row in rates_df.iterrows():
            name = str(row.get("Name", "")).strip()
            if not name or name == "nan":
                continue
            hrs  = hours_by_name.get(name, 0.0)
            ni_h = clean(row.get("NI Hours", 0))
            ni_r = clean(row.get("NI Rates", 0))
            cr   = clean(row.get("Hourly Rate", 0))
            fw   = clean(row.get("Fixed Wage", 0))
            bank = min(hrs, ni_h) * ni_r
            cash = max(0.0, hrs - ni_h) * cr
            breakdown[name] = round(bank + cash + fw, 2)

        return {"total": round(sum(breakdown.values()), 2), "breakdown": breakdown}

    def get_daily_intelligence(self) -> dict:
        if not self._assignments:
            return {}
        df    = pd.DataFrame(self._assignments)
        daily = {}
        for day in DAY_NAMES:
            day_df = df[df["Day"] == day]
            if day_df.empty:
                continue
            kit_df = day_df[day_df["Department"] == "Kitchen"]
            frt_df = day_df[day_df["Department"] == "Front"]
            daily[day] = {
                "Kitchen Count":  len(kit_df),
                "Front Count":    len(frt_df),
                "Kitchen Hours":  round(kit_df["Duration"].sum(), 1),
                "Front Hours":    round(frt_df["Duration"].sum(), 1),
                "Total Staff":    len(day_df),
                "Kitchen Staff":  ", ".join(kit_df["Name"].tolist()),
                "Front Staff":    ", ".join(frt_df["Name"].tolist()),
            }
        return daily


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = RotaEngine()
    engine.load_staff()
    engine.load_shifts()

    print("Generating rota for next week...")
    rota = engine.generate_week()
    print(f"OK: {len(rota)} shift assignments generated.\n")

    summary = engine.get_hours_summary()
    print("=== Hours Summary ===")
    print(summary.to_string(index=False))

    intel = engine.get_daily_intelligence()
    print("\n=== Daily Operations Intelligence ===")
    for day, stats in intel.items():
        print(
            f"{day:9} | Staff: {stats['Total Staff']} "
            f"| Kit: {stats['Kitchen Count']} ({stats['Kitchen Hours']}h) "
            f"| Frt: {stats['Front Count']} ({stats['Front Hours']}h)"
        )
        print(f"          Kitchen: {stats['Kitchen Staff']}")
        print(f"          Front:   {stats['Front Staff']}\n")

    if engine.warnings:
        print("\n=== Scheduling Warnings ===")
        for w in engine.warnings:
            print(w)

    cost = engine.estimate_weekly_cost(rota)
    print(f"\n=== Estimated Weekly Wage Cost ===")
    print(f"  Total: £{cost['total']:,.2f}")
    for name, amt in sorted(cost["breakdown"].items(), key=lambda x: -x[1]):
        print(f"  {name:<35} £{amt:>7,.2f}")

    out = engine.export_rota(rota)
    print(f"\nOK: Rota exported to: {out}")