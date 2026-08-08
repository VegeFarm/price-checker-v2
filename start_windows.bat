@echo off
cd /d %~dp0
if not exist .venv (
  py -m venv .venv
  .venv\Scripts\python.exe -m pip install --upgrade pip
  .venv\Scripts\pip.exe install -r requirements.txt
)
if not exist .env copy .env.example .env
.venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8787
pause
