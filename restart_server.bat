@echo off
title Restart AIVIN Server
color 0E

echo ========================================
echo    RESTARTING AIVIN SERVER
echo ========================================
echo.

echo [Step 1/2] Stopping existing server...
echo.

REM Find and stop process using port 8001
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do (
    set PID=%%a
)

if defined PID (
    echo Found server with PID: %PID%
    taskkill /PID %PID% /F >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] Could not stop server gracefully
    ) else (
        echo [SUCCESS] Server stopped
    )
    timeout /t 2 /nobreak >nul
) else (
    echo [INFO] No server running on port 8001
)

echo.
echo [Step 2/2] Starting server...
echo.

cd /d "%~dp0monolith"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run autorun_advanced.bat and select option [7]
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start server
echo Server starting on port 8001...
echo.
echo ========================================
echo Server URL: http://127.0.0.1:8001
echo ========================================
echo.
echo Press CTRL+C to stop the server
echo.

REM Open browser after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8001"

REM Run Django server
python manage.py runserver 0.0.0.0:8001

pause
