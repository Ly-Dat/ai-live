@echo off
cd /d "%~dp0"
echo Starting ai-live ...
python launcher.py %*
if errorlevel 1 pause
