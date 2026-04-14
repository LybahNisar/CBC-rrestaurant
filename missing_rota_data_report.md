# 👥 BI System — Rota Data Gap Analysis

To achieve **100% Operational Intelligence** (Sales per Man-Hour, Peak Efficiency), the following data points are currently missing from the provided `rota_week.csv` files.

### **1. Daily Time Tracking (Missing)**
The current CSV only shows the final **Total Wage (£)**. For the BI system to calculate productivity by the hour, we need:
- **Daily Start Time** (e.g., 10:00 AM)
- **Daily End Time** (e.g., 22:00 PM)
- **Total Hours Per Day** (excluding unpaid breaks)

### **2. Staff Pay Rate (Missing)**
We currently have to guess hours based on wages. To be forensic, we need:
- **Hourly Rate (£)** for each staff member. This ensures the BI model can verify if a high labour cost is due to **overstaffing** or **higher pay rates**.

### **3. Shift Type (Missing)**
The BI system cannot distinguish between:
- **Opening Shift** (Prep)
- **Lunch Shift** (Rush)
- **Dinner Shift** (Peak)
- **Closing Shift** (Cleanup)
Without shift names, the "Labour vs Revenue" heatmaps in the dashboard are less precise.

---

## 📅 Recommended Rota Format (Future Ready)
If the client provides a CSV with these columns, the **Dashbaord will unlock "Sales per Man Hour" analytics**:

| Name | Role | Dept | Hourly Rate | Mon | Tue | Wed | ... | Weekly Hours | Weekly Wage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| राजेश  | Team Member | BOH | £11.44 | 10:00 - 18:00 (8h) | OFF | 12:00 - 22:00 (10h) | ... | 38.0 | £434.72 |

---

### **✅ BI Impact**
- **Existing Logic (Cost only)**: "We spent £3,600 on staff this week."
- **Full Logic (Efficiency)**: "Team A produced £50 sales/hour on Monday, but Team B produced only £30 sales/hour on Tuesday."
