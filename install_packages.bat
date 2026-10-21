@echo off
title Install AI Nurse Packages
color 0B

cls
echo ========================================
echo    AI NURSE - PACKAGE INSTALLATION
echo ========================================
echo.
echo This script will install all required
echo Python packages for the AI Nurse system.
echo.
echo ========================================
echo.

cd /d "%~dp0monolith"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.8 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/4] Python version detected:
python --version
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [2/4] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo     Virtual environment created successfully!
) else (
    echo [2/4] Virtual environment already exists.
)
echo.

REM Activate virtual environment
echo [3/4] Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Upgrade pip
echo [4/4] Installing packages...
echo.
echo     Upgrading pip...
python -m pip install --upgrade pip
echo.

REM Install requirements
if exist "requirements.txt" (
    echo     Installing from requirements.txt...
    echo.
    pip install -r requirements.txt
    echo.

    if errorlevel 1 (
        echo [ERROR] Failed to install some packages!
        echo.
        echo Please check the error messages above.
        pause
        exit /b 1
    )

    echo ========================================
    echo [SUCCESS] All packages installed!
    echo ========================================
    echo.
    echo Installed packages:
    echo   - Django (Web framework)
    echo   - qrcode (QR code generation)
    echo   - Pillow (Image processing)
    echo.
    echo You can now run the server using:
    echo   - quick_start.bat
    echo   - autorun.bat
    echo.
) else (
    echo [ERROR] requirements.txt not found!
    echo.
    echo Please make sure you are in the correct directory.
    pause
    exit /b 1
)

echo ========================================
echo.
echo Would you like to create a superuser now?
set /p create_user="Create superuser? (Y/N): "

if /i "%create_user%"=="Y" (
    echo.
    echo Creating superuser...
    python manage.py migrate
    python manage.py createsuperuser
)

echo.
echo ========================================
echo Installation complete!
echo ========================================
pause
