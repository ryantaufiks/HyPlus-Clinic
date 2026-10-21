@echo off
title Create Admin User - AI Nurse
color 0D

cls
echo ========================================
echo    AI NURSE - CREATE ADMIN USER
echo ========================================
echo.
echo This script will help you create a superuser
echo for accessing the Django admin panel.
echo.
echo ========================================
echo.

cd /d "%~dp0monolith"

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo.
    echo Please run autorun_advanced.bat first and
    echo select option [7] to install requirements.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo.

echo ========================================
echo    CREATING SUPERUSER ACCOUNT
echo ========================================
echo.
echo You will be asked to provide:
echo   - Username (e.g., admin)
echo   - Email address (optional)
echo   - Password (enter twice for confirmation)
echo.
echo NOTE: Password won't be visible while typing
echo       (this is normal for security)
echo.
echo ========================================
echo.

REM Create superuser
python manage.py createsuperuser

echo.
echo ========================================
echo.

if errorlevel 1 (
    echo [ERROR] Failed to create superuser
    echo Please check the error message above
) else (
    echo [SUCCESS] Superuser created successfully!
    echo.
    echo You can now login to the admin panel at:
    echo http://127.0.0.1:8001/admin
    echo.
    echo Would you like to start the server now?
    echo.
    set /p start_server="Start server? (Y/N): "

    if /i "%start_server%"=="Y" (
        echo.
        echo Starting server...
        echo.
        start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8001/admin"
        python manage.py runserver 0.0.0.0:8001
    ) else (
        echo.
        echo To start the server later, run:
        echo   - quick_start.bat
        echo   - autorun.bat
        echo.
    )
)

pause
