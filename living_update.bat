@echo off
REM Living Update — Windows Task Scheduler wrapper
REM Schedule via Task Scheduler: daily at 03:00, action = this .bat file
REM Logs to logs\living_YYYYMMDD.log

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Create logs directory if needed
if not exist "logs" mkdir "logs"

REM Build log filename with date
for /f "tokens=1-3 delims=-" %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do (
    set "LOG_DATE=%%a%%b%%c"
)
set "LOG_FILE=logs\living_%LOG_DATE%.log"

REM Find Python
where python3 >nul 2>&1 && (set "PYTHON=python3") || (set "PYTHON=python")

echo [%date% %time%] Living update starting >> "%LOG_FILE%"
%PYTHON% living_update.py >> "%LOG_FILE%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] Living update finished (exit code %EXIT_CODE%) >> "%LOG_FILE%"

exit /b %EXIT_CODE%
