@echo off
title AI Nurse - APK Build Setup
color 0B

cls
echo ========================================
echo    AI NURSE - APK BUILD SETUP
echo ========================================
echo.
echo This script will help you build an Android APK
echo for the AI Nurse Health Kiosk application.
echo.
echo ========================================
echo.

REM Check if Node.js is installed
echo [1/8] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed!
    echo.
    echo Please download and install Node.js from:
    echo https://nodejs.org/
    echo.
    pause
    exit /b 1
)
echo     Node.js: OK
node --version
echo.

REM Check if Java is installed
echo [2/8] Checking Java JDK installation...
java -version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Java JDK not found!
    echo.
    echo Please download and install Java JDK 11+ from:
    echo https://adoptium.net/
    echo.
    echo You can continue with PWA setup (no APK build)
    echo.
    set /p continue="Continue anyway? (Y/N): "
    if /i not "%continue%"=="Y" exit /b 1
) else (
    echo     Java JDK: OK
    java -version 2>&1 | findstr "version"
)
echo.

REM Generate PWA icons
echo [3/8] Generating PWA icons...
python generate_icons.py
if errorlevel 1 (
    echo [WARNING] Icon generation failed or skipped
) else (
    echo     Icons generated successfully!
)
echo.

REM Install npm dependencies
echo [4/8] Installing Node.js dependencies...
if exist "package.json" (
    npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed!
        pause
        exit /b 1
    )
    echo     Dependencies installed!
) else (
    echo [ERROR] package.json not found!
    pause
    exit /b 1
)
echo.

REM Check if Capacitor is initialized
echo [5/8] Checking Capacitor setup...
if not exist "capacitor.config.json" (
    echo [INFO] Initializing Capacitor...
    npx cap init "AI Nurse Health Kiosk" "com.ainurse.healthkiosk" --web-dir="monolith/static"
    echo     Capacitor initialized!
) else (
    echo     Capacitor already initialized
)
echo.

REM Add Android platform
echo [6/8] Setting up Android platform...
if not exist "android" (
    echo [INFO] Adding Android platform...
    npx cap add android
    if errorlevel 1 (
        echo [ERROR] Failed to add Android platform!
        echo Please check:
        echo - Android Studio is installed
        echo - ANDROID_HOME environment variable is set
        pause
        exit /b 1
    )
    echo     Android platform added!
) else (
    echo     Android platform already exists
)
echo.

REM Sync web assets
echo [7/8] Syncing web assets to Android...
npx cap sync android
if errorlevel 1 (
    echo [WARNING] Sync failed or incomplete
) else (
    echo     Assets synced successfully!
)
echo.

REM Final instructions
echo [8/8] Setup complete!
echo.
echo ========================================
echo    WHAT'S NEXT?
echo ========================================
echo.
echo Choose your build method:
echo.
echo [1] PWA (Progressive Web App) - RECOMMENDED
echo     - No APK build needed
echo     - Install directly from browser
echo     - Works on Android and iOS
echo     - Automatic updates
echo.
echo     To deploy PWA:
echo     a) Run: start_tunnel.bat (if created)
echo     b) Or: quick_start.bat
echo     c) Open browser on mobile
echo     d) Navigate to your URL
echo     e) Menu → "Add to Home Screen"
echo.
echo [2] APK (Android Package) - ADVANCED
echo     - Native app experience
echo     - Requires Android Studio
echo.
echo     To build APK:
echo     a) Run: npx cap open android
echo     b) Wait for Android Studio to load
echo     c) Build → Generate Signed Bundle / APK
echo     d) Choose APK → Create keystore → Build
echo     e) APK location: android/app/release/
echo.
echo [3] BOTH - Build APK + Deploy PWA
echo     - Best of both worlds
echo     - APK for distribution
echo     - PWA for instant access
echo.
echo ========================================
echo.
echo IMPORTANT CONFIGURATION:
echo ========================================
echo.
echo Before building, update server URL in:
echo   capacitor.config.json
echo.
echo For local network:
echo   "url": "http://192.168.1.xxx:8001"
echo.
echo For Cloudflare (recommended):
echo   "url": "https://your-domain.com"
echo.
echo ========================================
echo.
set /p next="Open Android Studio now? (Y/N): "
if /i "%next%"=="Y" (
    echo.
    echo Opening Android Studio...
    npx cap open android
) else (
    echo.
    echo You can open Android Studio later with:
    echo   npx cap open android
)

echo.
echo ========================================
echo    ADDITIONAL RESOURCES
echo ========================================
echo.
echo Documentation:
echo   - APK_BUILD_GUIDE.md (complete guide)
echo   - PWA: See base.html (already configured)
echo   - Cloudflare: See APK_BUILD_GUIDE.md
echo.
echo Scripts:
echo   - npm run sync           (sync web assets)
echo   - npm run open-android   (open Android Studio)
echo   - npm run build-android  (build debug APK)
echo   - npm run build-release  (build release APK)
echo.
echo Troubleshooting:
echo   - If Bluetooth doesn't work, check AndroidManifest.xml
echo   - If build fails, check Java and Android SDK
echo   - If sync fails, check web directory path
echo   - For CORS errors, update Django settings.py
echo.
echo ========================================
echo.
echo Server must be running for app to work!
echo Start server with: quick_start.bat
echo.
echo For remote access, setup Cloudflare Tunnel:
echo   1. Install cloudflared
echo   2. Run: cloudflared tunnel login
echo   3. Create tunnel: cloudflared tunnel create ai-nurse
echo   4. Configure DNS and route
echo   5. Run: cloudflared tunnel run ai-nurse
echo.
echo See APK_BUILD_GUIDE.md for detailed instructions.
echo.
echo ========================================
pause
