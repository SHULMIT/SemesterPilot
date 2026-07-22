@echo off
cd /d "%~dp0"
for /f "delims=" %%P in ('py -c "import sys; print(sys.executable)"') do set PYTHON=%%P
schtasks /Create /TN "OU Weekly Assignment Email" /TR "\"%PYTHON%\" \"%CD%\send_weekly.py\"" /SC WEEKLY /D SAT /ST 21:00 /F
if %errorlevel%==0 (echo Weekly email scheduled for Saturdays at 21:00.) else (echo Failed. Run this file as Administrator.)
pause
