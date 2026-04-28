# 🧠 Chocoberry Rota Intelligence: Technical & Business Logic

This document details the end-to-end logic, mathematical formulas, and operational architecture of the automated rota system.

---

## 1. Data Foundation (The Inputs)
The system operates on three independent data layers to ensure 100% editability and accuracy.

| Data Layer | Source File | Description |
| :--- | :--- | :--- |
| **Staff Registry** | `staff_profiles.csv` | Tracks name, active status, department, role (Senior/Junior), availability days, and absolute **Max Hours/Week**. |
| **Shift Schematics** | `shift_templates.csv` | Defines the daily demand: Start/End times, **Min Total Staff** (Hard Minimum), and **Min Senior Requirements**. |
| **Payroll Master** | `personnel_rates_master.csv` | Stores the financial DNA: NI Limits (Bank), Bank Pay Rates, Cash Pay Rates, and Fixed Bonuses. |

---

## 2. The Rota Algorithm (The Brain)
To generate a week, the **Rota Engine** follows a strict priority hierarchy:

### Step 1: Physical Viability Check
Before starting, the system calculates the **Capacity Balance**:
> `Σ(All Active Staff Max Hours) vs Σ(Required Shift Hours)`
If the team is too small to cover the templates, the system issues a **Critical Alert** before any staff are assigned.

### Step 2: The "Safety First" Pass (Role Constraints)
The engine scans for shifts requiring a **Senior**.
*   **Hard Constraint:** It will only assign staff marked as "Senior" in the Registry.
*   **Fallback Logic:** If no Senior is available, it provides a "Junior Fallback" to ensure the store stays open, but flags a **Security Warning** in the final report.

### Step 3: The "Fairness & Target" Pass (Greedy Optimization)
The system uses a **Priority Score** to decide who gets the next available shift:
> **Formula:** `Fairness Score = (Current Hours Scheduled + Previous Week Carryover) - Target Hours`
*   **Logic:** The staff member with the lowest score (those farthest behind their target) is picked first. This ensures no staff member is forgotten and hours are distributed evenly.

### Step 4: The "Efficiency" Pass (Filling the Gaps)
Finally, any optional slots (between *Min* and *Max* staff) are filled by anyone who is available AND has not yet hit their **Max Hours/Week** limit.

---

## 3. The Financial Calculation Model (The Payroll)
The system calculates wages using a **Tiered Split-Pay Architecture** that precisely mirrors the business's real-world payment style.

### System 1: Bank Payment (Bacs Portion)
Used for official on-books reporting.
> `Bank_Pay = MIN(Total_Scheduled_Hours, NI_Hours_Limit) × NI_Bank_Rate`

### System 2: Cash Payment (Off-Books/Minute Accurate)
Used for cash payouts from the till. The system is accurate to the minute.
> `Total_Cash = (Remaining_Hours × Cash_Hourly_Rate) + (Remaining_Minutes × [Cash_Hourly_Rate / 60]) + Fixed_Bonus`

### System 3: Mixed Consolidation (The Total)
Calculates the final business cost for the week.
> `Total_Weekly_Cost = Σ(Bank_Pay + Total_Cash + Employer_Ni_Tax + Fixed_Expenses)`

---

## 4. Quality Assurance (The Audit System)
The system continuously audits the generated rota and provides three layers of feedback:
1.  **Staffing Insights:** Identifies specific hours (like weekend nights) where the team is too small to cover the demand.
2.  **SBY (Standby) Guide:** Recommends specific staff to be "on call" based on their available hours vs. the peak revenue signals (e.g., if predicted Saturday revenue > £3,000).
3.  **PDF Evidence:** Produces a printable report that captures all the above, ensuring the client has a "Paper Trail" for every scheduling decision.

---
**Status:** Certified & Implemented
**System Version:** 3.0 (April 2026 Release)
