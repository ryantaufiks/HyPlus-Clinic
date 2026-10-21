@echo off
title AI Nurse - Health Kiosk Server
color 0A

echo ========================================
echo    AI NURSE - HEALTH KIOSK SERVER
echo ========================================
echo.
echo Starting server on port 8001...
echo.

cd /d "%~dp0monolith"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv venv
    echo Then install requirements: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/4] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if packages are installed
echo [2/4] Checking required packages...
python -c "import django, qrcode, PIL" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Some packages are missing!
    echo Installing required packages...
    python -m pip install --upgrade pip >nul 2>&1
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install packages!
        echo Please run: install_packages.bat
        pause
        exit /b 1
    )
    echo Packages installed successfully!
)
echo All packages are ready!

REM Apply migrations (if needed)
echo [3/4] Checking database migrations...
python manage.py migrate --noinput

REM Start Django server on port 8001
echo [4/4] Starting Django server on port 8002...
echo.
echo ========================================
echo Server is running at:
echo http://127.0.0.1:8002
echo http://localhost:8002
echo ========================================
echo.
echo Press CTRL+C to stop the server
echo.

REM Open browser after 3 seconds
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8002"

REM Run Django server
python manage.py runserver 0.0.0.0:8002

pause
