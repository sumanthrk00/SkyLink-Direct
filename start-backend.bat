@echo off
cd /d "%~dp0"
echo Starting SkyLink Direct Backend on http://127.0.0.1:8000 ...
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
pause

