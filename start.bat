@echo off
cd /d "%~dp0"
echo Starting ai-live ...
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" launcher.py %*
) else (
  python launcher.py %*
)
if errorlevel 1 pause
