# Chocoberry Intelligence (CBC) — Operational Guide
### High-Fidelity Restaurant Business Intelligence Ecosystem

Welcome to the **Chocoberry Intelligence (CBC)** platform. This system is a custom-engineered, end-to-end Business Intelligence (BI) suite designed to transform raw restaurant data into high-margin operational strategy. 

---

## 🚀 1. Quick Start: The "One-Click" Launch
The entire ecosystem is automated. You do not need to run manual code.

1.  Open the `CBC` project folder.
2.  Double-click the **`START_SYSTEM.bat`** file.
3.  **What happens next?**
    *   The **Staff Invoice Portal** starts (Back-end).
    *   The **BI Dashboard** opens in your browser (Front-end).
    *   A **Cloud Sync** is performed to pull in any recent staff-uploaded invoices.

---

## 📊 2. Core Components

### A. The BI Dashboard (Financial Command Centre)
The main dashboard ([http://localhost:8501](http://localhost:8501)) provides 13+ tabs of forensic analysis:
*   **Executive Overview**: Real-time KPIs (Revenue, AOV, Gross Margin).
*   **Labour Intelligence**: Visual mapping of Sales vs. Staffing. It identifies exactly when you are overstaffed (wasting money) or understaffed (losing sales).
*   **Menu Engineering**: A "Boston Matrix" that classifies your menu into **Stars** (High Profit/High Volume) and **Dogs** (Low Profit/Low Volume).

### B. The Staff Invoice Portal (Input Gateway)
A phone-optimised web app that replaces inefficient WhatsApp-based invoice management.
*   **Staff Access**: Staff open the link on their phones while on the shop WiFi.
*   **AI Capture**: They take a photo of the invoice; the system auto-reads the Supplier and Amount.
*   **Secure Storage**: Photos are renamed and filed into a "Drive-Ready" folder structure (Year > Month > Supplier).

### C. The Rota Engine (Predictive Scheduling)
A constraint-based engine that generates weekly rotas automatically.
*   It looks at your **Historical Sales Trends** to suggest how many staff you need.
*   It ensures **Fairness** by tracking how many hours each person worked in previous weeks to hit their contract targets.

---

## 🛠️ 3. Operational Workflow (How to run the business)

### Step 1: Data Ingestion (Monday Morning)
*   Ensure Flipdish sales reports and Rota CSVs are dropped into the `Sales Summary Data` and `Rota week...` folders.
*   The system includes a **Zero-Trust Integrity Audit** that verifies every CSV for corruption or missing rows before processing.

### Step 2: Invoice Management
1.  Staff upload photos to the portal throughout the week.
2.  In the Dashboard (Tab 12), click **"Sync Staff Uploads"**. 
3.  Invoices are moved into the **Forensic Ledger**, where you can track "Paid" vs. "Unpaid" status to protect cash flow.

### Step 3: Weekly Optimization
*   **Tab 10 (Waste Analysis)**: Compare what you "Should Have Used" (based on sales) vs. what was actually used to find theft or portion-control issues.
*   **Tab 11 (Menu Strategy)**: Identify which items need a price increase or a recipe change to hit your 70% target margin.

---

## 🔒 4. Data Security & Integrity
*   **Relational Databases**: The system uses SQLite (`recipes.db`, `invoices.db`, `cbc_invoice_intelligence.db`) to ensure data is never lost or accidentally deleted from Excel sheets.
*   **Secret-Key Auth**: The staff portal is protected by a secret key (`chocoberry2026`) to ensure only authorised dashboard users can sync financial data.
*   **Auto-Cleaning**: The system automatically fixes currency symbols, commas, and spelling mistakes in raw supplier invoices.

---

## ❓ 5. Troubleshooting
*   **"Portal Offline"**: If the dashboard says the portal is offline, ensure the black terminal window opened by the `.bat` file is still running.
*   **"Missing Data"**: Check the `dash_integrity_audit.txt` file; the system logs every single error there if a CSV file is formatted incorrectly.

---

**System Author**: Chocoberry BI Development Team  
**Version**: 2.0.4 (Production-Live)  
**Environment**: Windows Local Deployment  
