# 🌌 Chocoberry Business Intelligence System (CBIS) — Master User Guide

Welcome to your **Financial Command Centre**. This system is a bespoke intelligence suite designed specifically for Chocoberry, providing 360-degree visibility into your sales, staffing, inventory, and strategic growth.

---

## 🚀 1. System Entry & Security
To launch the system, run **`START_SYSTEM.bat`**. 

**Dashboard Authentication:**
*   The system uses an **Immersive Floating Login**.
*   **Username:** Not required.
*   **Security Key:** Enter the password found in your [**.env**](file:///c:/Users/GEO/Desktop/CBC/.env) file (Default: `chocoberry2026`).
*   *Security Tip: You can change your password anytime by editing the `DASHBOARD_PASSWORD` line in the `.env` file.*

---

## 📊 2. Dashboard Intelligence — Tab-by-Tab Guide

### **Tab 1: LIVE DASHBOARD**
*   **Strategic Purpose:** Real-time operational pulse.
*   **Features:** Targets vs. Actuals, peak-day highlights, and Week-over-Week (WoW) performance.
*   **Key Action:** Use the **"📄 Generate Weekly PDF Report"** button to create a high-fidelity summary for management reviews or investor reporting.

### **Tab 2: TRENDS**
*   **Strategic Purpose:** Longitudinal health analysis.
*   **Features:** Monthly revenue bar charts, AOV (Average Order Value) trends, and 7-day rolling averages.
*   **Staffing Insight:** Identify if business momentum is rising or slowing down independently of daily noise.

### **Tab 3: PATTERNS**
*   **Strategic Purpose:** Scheduling & Capacity Planning.
*   **Day-of-Week:** Visualizes that Fri-Sun generate **55%** of your weekly income.
*   **Hour-of-Day:** Pinpoints your peak trading windows (Evening/Late Night) to ensure you never under-staff during high-revenue hours.

### **Tab 4: CHANNELS**
*   **Strategic Purpose:** Profit Protection & Platform Optimization.
*   **Logic:** Tracks Uber Eats, Deliveroo, and In-Store sales.
*   **Audit Tip:** If "Flipdish Web" orders are low, you are losing profit to third-party commissions. Use this tab to track your migration to direct ordering.

### **Tab 5: EFFICIENCY**
*   **Strategic Purpose:** Profit vs. Labour Audit.
*   **The "Red Line" Rule:** The red line (Staff Cost) should always be significantly lower than the yellow bars (Revenue). If the red line crosses the bars, you are trading at a loss for those hours.

### **Tab 6: FORECAST**
*   **Strategic Purpose:** Predictive Preparation.
*   **Method:** A 4-week rolling predictive model forecasts your next 7 days of sales.
*   **Manual Overrides:** Adjust for Bank Holidays or local Cardiff events with the slider. This forecast is the "brain" that drives the **Smart Rota Builder**.

### **Tab 7: LABOUR REPORT**
*   **Strategic Purpose:** Financial Oversight.
*   **Flags:** Specifically highlights **Overstaffed** hours (wasted money) and **Understaffed** hours (lost sales).
*   **Action:** Export the **Excel Labour Report** for precise bookkeeping.

### **Tab 8: ROTA BUILDER**
*   **Strategic Purpose:** Intelligent Scheduling.
*   **Automation:** Builds a complete weekly rota in seconds based on staff availability and seniority.
*   **Smart Mode:** Automatically scales staff headcount to match the **Forecasted Sales**.

### **Tab 9: INVENTORY & COGS**
*   **Strategic Purpose:** Cost Control.
*   **Auto-Deduction:** Upload your Flipdish sales report, and the system automatically deducts recipe ingredients from your stock.
*   **PO Generator:** Tells you exactly what to order from suppliers (Cr8 Foods, etc.) based on reorder points.

### **Tab 10: WASTE LOG & VARIANCE**
*   **Strategic Purpose:** Loss Prevention.
*   **Tracking:** Log drops, expires, and customer refunds.
*   **Forensics:** Compares "Theoretical Usage" (what sales say you used) vs. "Actual Stock" to identify theft or hidden waste.

### **Tab 11: STRATEGIC OPTIMIZATION**
*   **Strategic Purpose:** Menu Engineering ("The Boston Matrix").
*   **Stars:** High Profit/High Volume. (Keep quality high).
*   **Workhorses:** Low Profit/High Volume. (**Action:** Increase prices immediately).
*   **Dogs:** Low Profit/Low Volume. (**Action:** Remove from menu).

### **Tab 12: INVOICE MANAGEMENT**
*   **Strategic Purpose:** Accounts Payable & Staff Sync.
*   **Sync:** Click **"🔄 Sync Staff Uploads Now"** to import receipts from the mobile staff portal.
*   **Analytics:** Track supplier price inflation over time.

### **Tab 13: DATABASE EXPLORER**
*   **Strategic Purpose:** Raw Transparency.
*   **Audit:** Direct access to every raw record for 100% data integrity verification.

---

## 📱 3. Staff Portal (Invoice Uploads)
Your team should access the **Staff Portal** (usually `localhost:5050`) to capture delivery notes via camera.
*   **Photo Capture:** Uploads are saved instantly to the `Invoices/` folder.
*   **Auto-Sort:** The system sorts them by Year/Month/Supplier for you.

---

## 🛠️ 4. System Maintenance
*   **Data Entry:** Keep **daily_sales_master.csv** updated (Tab 12: Revenue Ledger) to keep your analytics live.
*   **Backups:** Copy the entire `CBC` folder to a secure cloud drive monthly.
*   **Updates:** This documentation is built into the system and can be updated as your business scales.

**© 2026 Chocoberry Intelligence System — Engineered for Success.**
