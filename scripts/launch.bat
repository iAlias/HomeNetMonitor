@echo off
setlocal EnableDelayedExpansion

:: ============================================================
:: HomeNetMonitor launcher
:: Double-click this file to start the application.
:: Admin elevation is requested automatically.
:: ============================================================

:: Check if already running as administrator
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: Move to the repository root (one level above this script)
cd /d "%~dp0.."

:: -------------------------------------------------------
:: Locate Python
:: -------------------------------------------------------
where python >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] Python was not found in PATH.
    echo Please install Python 3.11 or later from https://www.python.org/downloads/
    echo and make sure the "Add Python to PATH" option is selected during installation.
    pause
    exit /b 1
)

:: -------------------------------------------------------
:: Create virtual environment if it doesn't exist
:: -------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if !errorLevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: -------------------------------------------------------
:: Activate virtual environment
:: -------------------------------------------------------
call ".venv\Scripts\activate.bat"

:: -------------------------------------------------------
:: Install / update dependencies
:: -------------------------------------------------------
echo Checking dependencies...
pip install -q -r requirements.txt
if %errorLevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: -------------------------------------------------------
:: Launch the application (window stays open on error)
:: -------------------------------------------------------
echo Starting HomeNetMonitor...
python src/main.py
if %errorLevel% neq 0 (
    echo.
    echo [ERROR] HomeNetMonitor exited with an error.  See the log above.
    pause
)
