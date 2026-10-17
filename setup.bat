@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo OmniPost v2.5 - Local Setup & Onboarding Installer
echo ===================================================

:: 1. Check for Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python was not found in your system PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: 2. Check Python version
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [*] Detected Python %PY_VER%

:: 3. Setup Virtual Environment
if not exist ".venv" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: 4. Activate Virtual Environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment activation script not found.
    pause
    exit /b 1
)

:: 5. Install Dependencies
echo [*] Installing / updating dependencies from requirements.txt...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: 6. Launch Wizard
echo.
echo ===================================================
echo Launching Onboarding Wizard...
echo ===================================================
echo.
python scripts\wizard.py

endlocal
