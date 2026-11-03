@echo off
title SkyLink Direct - Master Launcher
cd /d "%~dp0"

echo ===================================================
echo           SkyLink Direct - System Launcher
echo ===================================================
echo.
echo [1/2] Starting Python FastAPI Backend on port 8000...
start "SkyLink Direct - Backend Server (Port 8000)" cmd /k "cd /d "%~dp0" && .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload"

echo [2/2] Starting React Web App on port 5173...
start "SkyLink Direct - Web App (Port 5173)" cmd /k "cd /d "%~dp0web" && npm run dev"

timeout /t 3 /nobreak >nul
echo.
echo ===================================================
echo  Both services launched successfully!
echo  Backend:  http://127.0.0.1:8000/docs
echo  Frontend: http://localhost:5173
echo ===================================================
start http://localhost:5173

