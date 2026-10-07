@echo off
chcp 65001
where git > nul 2>&1
if %errorlevel% neq 0 (
    echo Git command not found, please install the git client first.
    pause
    exit /b
)

echo Running a backup script first so you don't lose your config
Miniconda3\python.exe bak_config_data.py

git fetch --all
git reset --hard origin/main
echo Pull finished (if there were no errors).
pause