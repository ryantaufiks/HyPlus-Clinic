@echo off
title AIVIN - Health Kiosk Server (Advanced)
color 0B

:MENU
cls
echo ========================================
echo    AIVIN - HEALTH KIOSK SERVER
echo           ADVANCED LAUNCHER
echo ========================================
echo.
echo Please select an option:
echo.
echo [1] Start Server (Port 8002)
echo [2] Start Server + Open Browser
echo [3] Start Server (Custom Port)
echo [4] Run Migrations Only
echo [5] Create Superuser
echo [6] Collect Static Files
echo [7] Install/Update Requirements
echo [8] Check System Status
echo [9] Exit
echo.
echo ========================================
set /p choice="Enter your choice (1-9): "

if "%choice%"=="1" goto START_SERVER
if "%choice%"=="2" goto START_WITH_BROWSER
if "%choice%"=="3" goto CUSTOM_PORT
if "%choice%"=="4" goto RUN_MIGRATIONS
if "%choice%"=="5" goto CREATE_SUPERUSER
if "%choice%"=="6" goto COLLECT_STATIC
if "%choice%"=="7" goto INSTALL_REQUIREMENTS
if "%choice%"=="8" goto CHECK_STATUS
if "%choice%"=="9" goto EXIT

echo Invalid choice! Please try again.
timeout /t 2 >nul
goto MENU

:START_SERVER
cls
echo ========================================
echo    STARTING SERVER ON PORT 8002
echo ========================================
echo.
cd /d "%~dp0monolith"
call :ACTIVATE_VENV
python manage.py runserver 0.0.0.0:8002
pause
goto MENU

:START_WITH_BROWSER
cls
echo ========================================
echo    STARTING SERVER WITH BROWSER
echo ========================================
echo.
cd /d "%~dp0monolith"
call :ACTIVATE_VENV
echo Starting server...
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8002"
python manage.py runserver 0.0.0.0:8002
pause
goto MENU

:CUSTOM_PORT
cls
echo ========================================
echo    START SERVER ON CUSTOM PORT
echo ========================================
echo.
set /p custom_port="Enter port number (default 8002): "
if "%custom_port%"=="" set custom_port=8002
echo.
cd /d "%~dp0monolith"
call :ACTIVATE_VENV
echo Starting server on port %custom_port%...
echo Server URL: http://127.0.0.1:%custom_port%
echo.
python manage.py runserver 0.0.0.0:%custom_port%
pause
goto MENU

:RUN_MIGRATIONS
cls
echo ========================================
echo    RUNNING DATABASE MIGRATIONS
echo ========================================
echo.
cd /d "%~dp0monolith"
call :ACTIVATE_VENV
python manage.py makemigrations
python manage.py migrate
echo.
echo Migrations completed!
pause
goto MENU

:CREATE_SUPERUSER
cls
echo ========================================
echo    CREATE DJANGO SUPERUSER
echo ========================================
echo.
cd /d "%~dp0monolith"
call :ACTIVATE_VENV
python manage.py createsuperuser
pause
goto MENU

:COLLECT_STATIC
cls
echo ========================================
echo    COLLECTING STATIC FILES
echo ========================================
echo.
cd /d "%~dp0monolith"
call :ACTIVATE_VENV
python manage.py collectstatic --noinput
echo.
echo Static files collected!
pause
goto MENU

:INSTALL_REQUIREMENTS
cls
echo ========================================
echo    INSTALLING REQUIREMENTS
echo ========================================
echo.
cd /d "%~dp0monolith"

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call :ACTIVATE_VENV

if exist "requirements.txt" (
    echo Installing requirements...
    pip install --upgrade pip
    pip install -r requirements.txt
    echo.
    echo Requirements installed successfully!
) else (
    echo ERROR: requirements.txt not found!
)
pause
goto MENU

:CHECK_STATUS
cls
echo ========================================
echo    SYSTEM STATUS CHECK
echo ========================================
echo.
cd /d "%~dp0monolith"

echo [1] Python Version:
python --version
echo.

echo [2] Virtual Environment:
if exist "venv\Scripts\activate.bat" (
    echo    Status: EXISTS
) else (
    echo    Status: NOT FOUND
)
echo.

echo [3] Django Version:
call :ACTIVATE_VENV
python -c "import django; print('   ', django.get_version())" 2>nul || echo    Not installed
echo.

echo [4] Database File:
if exist "db.sqlite3" (
    echo    Status: EXISTS
    for %%I in (db.sqlite3) do echo    Size: %%~zI bytes
) else (
    echo    Status: NOT FOUND
)
echo.

echo [5] Requirements File:
if exist "requirements.txt" (
    echo    Status: EXISTS
) else (
    echo    Status: NOT FOUND
)
echo.

echo [6] Port 8001 Availability:
netstat -ano | findstr ":8001" >nul
if errorlevel 1 (
    echo    Status: AVAILABLE
) else (
    echo    Status: IN USE
)
echo.

pause
goto MENU

:ACTIVATE_VENV
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run option [7] to install requirements first.
    pause
    goto MENU
)
call venv\Scripts\activate.bat
goto :eof

:EXIT
cls
echo.
echo Thank you for using AIVIN!
echo.
timeout /t 2 >nul
exit
