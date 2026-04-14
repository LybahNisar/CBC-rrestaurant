@echo off
TITLE CHOCOBERRY LIVE SYSTEM CONTROL
COLOR 0A
CD /D "%~dp0"

echo ======================================================
echo    CHOCOBERRY RESTAURANT INTELLIGENCE — LIVE STARTUP
echo ======================================================
echo.

:: 1. Start the Invoice Portal API in the background
echo [1/3] Starting Invoice Portal API on Port 5050...
start /b python invoice_portal.py

:: 2. Start the Dashboard
echo [2/3] Launching Business Intelligence Dashboard...
echo Dashboard will open in your browser shortly...
start /b streamlit run app_dashboard.py --server.port 8501

:: 3. Run initial Sync
echo [3/3] Running initial Invoice Sync...
python sync_portal_invoices.py

echo.
echo ------------------------------------------------------
echo LIVE SYSTEM IS RUNNING
echo - Dashboard: http://localhost:8501
echo - Portal API: http://localhost:5050
echo ------------------------------------------------------
echo.
echo Keep this window open to maintain the system.
echo Press Ctrl+C to shut down all processes.
pause > nul
