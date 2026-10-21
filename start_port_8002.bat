@echo off
title AIVIN - Server Port 8002 (Cloudflare Tunnel)
color 0A

echo ========================================
echo    AIVIN - HEALTH KIOSK SERVER
echo    Running on Port 8002
echo    For Cloudflare Tunnel
echo ========================================
echo.
echo Starting server...
echo.

cd /d "%~dp0monolith"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run: install_packages.bat
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if packages are installed
echo [2/3] Checking required packages...
python -c "import django, qrcode, PIL" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Some packages are missing!
    echo Installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install packages!
        pause
        exit /b 1
    )
)

REM Run migrations
echo [3/3] Running database migrations...
python manage.py migrate --noinput

echo.
echo ========================================
echo Server is running at:
echo.
echo Local:      http://127.0.0.1:8002
echo Local:      http://localhost:8002
echo.
echo Cloudflare: https://ainurse.sc2platform.biz.id
echo ========================================
echo.
echo IMPORTANT: Make sure Cloudflare Tunnel is running!
echo.
echo Access from mobile:
echo https://ainurse.sc2platform.biz.id
echo.
echo Press CTRL+C to stop the server
echo.

REM Open browser after 3 seconds
start "" cmd /c "timeout /t 3 /nobreak >nul && start https://ainurse.sc2platform.biz.id"

REM Run Django server on port 8002
python manage.py runserver 0.0.0.0:8002

pause
