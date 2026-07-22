@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% neq 0 (
  echo Python is not installed. Install Python from python.org and mark "Add Python to PATH".
  pause
  exit /b 1
)
py app.py
pause
