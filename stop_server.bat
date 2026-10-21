@echo off
title Stop AI Nurse Server
color 0C

echo ========================================
echo    STOPPING AI NURSE SERVER
echo ========================================
echo.

echo Searching for Django server on port 8001...
echo.

REM Find process using port 8001
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001') do (
    set PID=%%a
)

if defined PID (
    echo Found process with PID: %PID%
    echo Stopping server...
    taskkill /PID %PID% /F
    echo.
    if errorlevel 1 (
        echo [ERROR] Failed to stop server
        echo You may need to run this as Administrator
    ) else (
        echo [SUCCESS] Server stopped successfully!
    )
) else (
    echo [INFO] No server running on port 8001
)

echo.
echo ========================================
pause
