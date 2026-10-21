# 📱 APK Build Guide - AIVIN

Complete guide to build an Android APK and deploy with Cloudflare Tunnel for remote access.

---

## 🎯 Overview

This guide will help you:
1. ✅ Generate PWA icons
2. ✅ Setup Capacitor for Android
3. ✅ Build APK file
4. ✅ Deploy Django server with Cloudflare Tunnel
5. ✅ Connect mobile app to remote server

---

## 📋 Prerequisites

### Required Software

#### 1. **Node.js & npm**
- Download: https://nodejs.org/ (LTS version)
- Verify installation:
  ```bash
  node --version
  npm --version
  ```

#### 2. **Java JDK 11 or higher**
- Download: https://adoptium.net/
- Set `JAVA_HOME` environment variable
- Verify:
  ```bash
  java -version
  ```

#### 3. **Android Studio**
- Download: https://developer.android.com/studio
- Install with Android SDK
- Required SDK components:
  - Android SDK Platform 33 or higher
  - Android SDK Build-Tools
  - Android SDK Platform-Tools
  - Android SDK Command-line Tools

#### 4. **Gradle** (usually comes with Android Studio)
- Verify:
  ```bash
  gradle --version
  ```

#### 5. **Python 3.8+** (already installed)
- With Pillow library:
  ```bash
  pip install Pillow
  ```

#### 6. **Cloudflare Account** (Free)
- Sign up: https://dash.cloudflare.com/sign-up
- For tunnel setup

---

## 🚀 Method 1: PWA Installation (Recommended - Easiest)

### What is PWA?
Progressive Web App - can be installed directly from browser without APK!

### Steps:

1. **Deploy your Django server with Cloudflare Tunnel** (see Method 3 below)

2. **Access from mobile browser**
   ```
   Open Chrome on Android
   Navigate to: https://your-domain.com
   ```

3. **Install PWA**
   ```
   Chrome → Menu (⋮) → "Add to Home screen"
   Or
   Chrome → Menu (⋮) → "Install app"
   ```

4. **Done!**
   - App appears on home screen
   - Opens like native app
   - Bluetooth works
   - Voice works
   - Offline support

### Advantages:
- ✅ No APK build needed
- ✅ Instant updates (just refresh)
- ✅ Works on iOS too
- ✅ Full Bluetooth API support
- ✅ Smaller download size
- ✅ Easy to distribute

---

## 🛠️ Method 2: Build APK with Capacitor (Advanced)

### Step 1: Generate Icons

```bash
cd AI_Nurse
python generate_icons.py
```

This creates all required icons in `monolith/static/icons/`

### Step 2: Install Capacitor

```bash
# Install Node.js dependencies
npm install

# Or manually:
npm install @capacitor/core @capacitor/cli @capacitor/android
```

### Step 3: Initialize Capacitor

```bash
npx cap init "AIVIN" "com.aivin.kiosk"
```

Answer the prompts:
- Package ID: `com.aivin.kiosk`
- App Name: `AIVIN`
- Web directory: `monolith/static`

### Step 4: Add Android Platform

```bash
npx cap add android
```

This creates `android/` folder with Android Studio project.

### Step 5: Update Capacitor Config

Edit `capacitor.config.json` to point to your server:

```json
{
  "server": {
    "url": "https://your-cloudflare-domain.com",
    "cleartext": false,
    "androidScheme": "https"
  }
}
```

### Step 6: Sync Web Assets

```bash
npx cap sync android
```

### Step 7: Build APK

#### Option A: Using Android Studio (Recommended)

```bash
# Open Android Studio
npx cap open android
```

Then in Android Studio:
1. Wait for Gradle sync to complete
2. Build → Generate Signed Bundle / APK
3. Choose APK
4. Create new keystore (first time only)
5. Fill in keystore details:
   - Key store path: `android/app/my-release-key.keystore`
   - Password: [your password]
   - Key alias: `my-key-alias`
   - Key password: [your password]
6. Click "Next" → "release" → "Finish"
7. APK location: `android/app/release/app-release.apk`

#### Option B: Using Command Line

```bash
cd android

# Debug build (for testing)
./gradlew assembleDebug
# Output: android/app/build/outputs/apk/debug/app-debug.apk

# Release build (for distribution)
./gradlew assembleRelease
# Output: android/app/build/outputs/apk/release/app-release.apk
```

### Step 8: Sign APK (Release Only)

```bash
# Generate keystore (first time only)
keytool -genkey -v -keystore my-release-key.keystore -alias my-key-alias -keyalg RSA -keysize 2048 -validity 10000

# Sign APK
jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 -keystore my-release-key.keystore android/app/build/outputs/apk/release/app-release-unsigned.apk my-key-alias

# Optimize APK
zipalign -v 4 android/app/build/outputs/apk/release/app-release-unsigned.apk android/app/build/outputs/apk/release/app-release.apk
```

### Step 9: Install APK

**On Device:**
1. Enable "Unknown Sources" in Settings → Security
2. Transfer APK to device
3. Open APK file
4. Click "Install"

**Via ADB:**
```bash
adb install android/app/build/outputs/apk/debug/app-debug.apk
```

---

## 🌐 Method 3: Deploy with Cloudflare Tunnel

### Why Cloudflare Tunnel?
- ✅ Free SSL certificate
- ✅ No port forwarding needed
- ✅ Secure tunnel to localhost
- ✅ Access from anywhere
- ✅ DDoS protection

### Step 1: Install Cloudflared

**Windows:**
```bash
# Download from: https://github.com/cloudflare/cloudflared/releases
# Or use winget:
winget install --id Cloudflare.cloudflared
```

**Linux:**
```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

**Verify:**
```bash
cloudflared --version
```

### Step 2: Login to Cloudflare

```bash
cloudflared tunnel login
```

This opens browser for authentication.

### Step 3: Create Tunnel

```bash
cloudflared tunnel create ai-nurse-tunnel
```

This creates:
- Tunnel ID (save this!)
- Tunnel credentials: `~/.cloudflared/[tunnel-id].json`

### Step 4: Configure Tunnel

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: ai-nurse-tunnel
credentials-file: C:\Users\YourUser\.cloudflared\[tunnel-id].json

ingress:
  - hostname: ai-nurse.yourdomain.com
    service: http://localhost:8001
  - service: http_status:404
```

Replace:
- `[tunnel-id]` with your actual tunnel ID
- `ai-nurse.yourdomain.com` with your desired subdomain

### Step 5: Add DNS Record

```bash
cloudflared tunnel route dns ai-nurse-tunnel ai-nurse.yourdomain.com
```

Or manually in Cloudflare dashboard:
- Type: CNAME
- Name: ai-nurse
- Target: [tunnel-id].cfargotunnel.com

### Step 6: Update Django Settings

Edit `monolith/health_kiosk/settings.py`:

```python
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "ai-nurse.yourdomain.com",
    "*.yourdomain.com",
]

CSRF_TRUSTED_ORIGINS = [
    "https://ai-nurse.yourdomain.com",
]
```

### Step 7: Start Server

**Terminal 1: Django Server**
```bash
cd AI_Nurse
python monolith/manage.py runserver 0.0.0.0:8001
```

**Terminal 2: Cloudflare Tunnel**
```bash
cloudflared tunnel run ai-nurse-tunnel
```

### Step 8: Access from Mobile

Open browser on phone:
```
https://ai-nurse.yourdomain.com
```

Install PWA or use APK configured with this URL.

---

## 🔧 Troubleshooting

### Issue 1: Gradle Build Failed

**Solution:**
```bash
cd android
./gradlew clean
./gradlew build --stacktrace
```

Check for errors and install missing SDK components.

### Issue 2: Java Version Mismatch

**Solution:**
```bash
# Check Java version
java -version

# Should be 11 or higher
# If not, update JAVA_HOME:
export JAVA_HOME=/path/to/jdk-11
```

### Issue 3: Android SDK Not Found

**Solution:**
- Open Android Studio → SDK Manager
- Install required SDK versions
- Set ANDROID_HOME environment variable:
  ```bash
  export ANDROID_HOME=$HOME/Android/Sdk
  export PATH=$PATH:$ANDROID_HOME/tools
  export PATH=$PATH:$ANDROID_HOME/platform-tools
  ```

### Issue 4: APK Install Failed

**Solution:**
- Enable "Install from Unknown Sources"
- Check Android version (minimum: 7.0)
- Free up storage space
- Try debug APK first

### Issue 5: Bluetooth Not Working in APK

**Solution:**
- Add permissions to `android/app/src/main/AndroidManifest.xml`:
  ```xml
  <uses-permission android:name="android.permission.BLUETOOTH" />
  <uses-permission android:name="android.permission.BLUETOOTH_ADMIN" />
  <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
  <uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
  <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
  ```

### Issue 6: Cloudflare Tunnel Not Connecting

**Solution:**
```bash
# Check tunnel status
cloudflared tunnel info ai-nurse-tunnel

# Test tunnel
cloudflared tunnel run ai-nurse-tunnel --loglevel debug

# Restart tunnel
# Kill existing process, then:
cloudflared tunnel run ai-nurse-tunnel
```

### Issue 7: CORS Errors

**Solution:**
Update Django settings:
```python
CORS_ALLOW_ALL_ORIGINS = True  # For testing

# Or specific origins:
CORS_ALLOWED_ORIGINS = [
    "https://ai-nurse.yourdomain.com",
    "capacitor://localhost",
    "http://localhost",
]
```

---

## 📱 APK Configuration Guide

### Update Server URL

#### For Development (Local Server):
```json
{
  "server": {
    "url": "http://192.168.1.100:8001",
    "cleartext": true
  }
}
```

Replace `192.168.1.100` with your computer's local IP.

#### For Production (Cloudflare):
```json
{
  "server": {
    "url": "https://ai-nurse.yourdomain.com",
    "cleartext": false
  }
}
```

After changing, run:
```bash
npx cap sync android
```

---

## 🎨 Customization

### Change App Name

Edit `android/app/src/main/res/values/strings.xml`:
```xml
<resources>
    <string name="app_name">AIVIN</string>
</resources>
```

### Change App Icon

Replace icons in:
- `android/app/src/main/res/mipmap-*/ic_launcher.png`

Or use Android Studio:
- Right-click `res` → New → Image Asset
- Choose icon type and upload image

### Change Splash Screen

Edit `android/app/src/main/res/drawable/splash.png`

---

## 📊 Build Scripts Summary

We've created npm scripts for easy building:

```bash
# Generate icons
npm run generate-icons

# Install Capacitor
npm run install-capacitor

# Complete setup
npm run setup

# Sync web assets to Android
npm run sync

# Open Android Studio
npm run open-android

# Build debug APK (via Gradle)
npm run build-android

# Build release APK
npm run build-release

# Clean build
npm run clean
```

---

## 🚀 Quick Start Commands

### For PWA (Recommended):

```bash
# 1. Generate icons
python generate_icons.py

# 2. Start Django server
python monolith/manage.py runserver 0.0.0.0:8001

# 3. Start Cloudflare tunnel
cloudflared tunnel run ai-nurse-tunnel

# 4. Open on mobile browser
# Navigate to: https://ai-nurse.yourdomain.com
# Install PWA from browser menu
```

### For APK Build:

```bash
# 1. Generate icons
python generate_icons.py

# 2. Setup Capacitor
npm install
npx cap init
npx cap add android

# 3. Update server URL in capacitor.config.json

# 4. Sync and build
npx cap sync android
npx cap open android

# 5. In Android Studio:
# Build → Generate Signed Bundle / APK → APK
```

---

## 📦 Distribution

### Option 1: Direct APK Distribution

1. Build release APK
2. Upload to file sharing service
3. Share download link
4. Users download and install

**Pros:**
- ✅ Simple
- ✅ Free
- ✅ Quick updates

**Cons:**
- ❌ Manual updates
- ❌ Security warnings

### Option 2: PWA Distribution

1. Deploy with Cloudflare
2. Share website URL
3. Users install from browser

**Pros:**
- ✅ Automatic updates
- ✅ Works on iOS too
- ✅ No APK needed
- ✅ Smaller size

**Cons:**
- ❌ Requires browser first

### Option 3: Google Play Store (Advanced)

1. Create Google Play Developer account ($25 one-time fee)
2. Build signed APK or AAB
3. Upload to Play Console
4. Wait for review (~3-7 days)

**Pros:**
- ✅ Official distribution
- ✅ Automatic updates
- ✅ Trusted source

**Cons:**
- ❌ Requires paid account
- ❌ Review process
- ❌ More complex

---

## 🔐 Security Checklist

Before deploying to production:

```
□ Change Django SECRET_KEY
□ Set DEBUG = False
□ Update ALLOWED_HOSTS
□ Configure CSRF_TRUSTED_ORIGINS
□ Enable HTTPS (Cloudflare provides this)
□ Use strong passwords for admin
□ Backup database regularly
□ Monitor server logs
□ Keep dependencies updated
□ Test on multiple devices
```

---

## 📊 Architecture Diagram

```
┌─────────────────┐
│  Mobile Device  │
│   (Android)     │
└────────┬────────┘
         │
         │ HTTPS
         ▼
┌─────────────────────┐
│ Cloudflare Tunnel   │
│  (SSL/CDN/DDoS)     │
└────────┬────────────┘
         │
         │ HTTP (local)
         ▼
┌─────────────────────┐
│  Django Server      │
│  (localhost:8001)   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   SQLite Database   │
│   (db.sqlite3)      │
└─────────────────────┘
```

---

## 💡 Best Practices

### 1. Use PWA for Prototyping
- Fast iterations
- Easy testing
- No build overhead

### 2. Build APK for Distribution
- Professional appearance
- Offline capabilities
- Better performance

### 3. Use Cloudflare for Production
- Free SSL
- Fast delivery
- Secure access

### 4. Keep Server Running
```bash
# Use screen or tmux for persistent sessions
screen -S django
python monolith/manage.py runserver 0.0.0.0:8001

# Detach: Ctrl+A then D
# Reattach: screen -r django
```

### 5. Automate Tunnel Startup

**Windows - Create `start-tunnel.bat`:**
```batch
@echo off
start "Django Server" cmd /k "cd AI_Nurse\monolith && python manage.py runserver 0.0.0.0:8001"
timeout /t 5
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel run ai-nurse-tunnel"
```

**Linux - Create `start-tunnel.sh`:**
```bash
#!/bin/bash
cd /path/to/AI_Nurse/monolith
python manage.py runserver 0.0.0.0:8001 &
cloudflared tunnel run ai-nurse-tunnel
```

---

## 📞 Support & Resources

### Official Documentation
- **Capacitor:** https://capacitorjs.com/docs
- **Cloudflare Tunnel:** https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- **Android Studio:** https://developer.android.com/studio/intro
- **PWA:** https://web.dev/progressive-web-apps/

### Helpful Commands

```bash
# Check APK size
du -h android/app/build/outputs/apk/release/app-release.apk

# List connected devices
adb devices

# View device logs
adb logcat

# Install APK via ADB
adb install app-release.apk

# Uninstall app
adb uninstall com.aivin.kiosk

# Check Bluetooth permissions
adb shell dumpsys bluetooth_manager
```

---

## ✅ Deployment Checklist

### Pre-Deployment

```
□ Icons generated (8 sizes)
□ Service worker configured
□ PWA manifest created
□ Django CORS configured
□ Database migrated
□ Static files collected
□ Admin user created
□ Test data loaded
□ Local testing complete
```

### Cloudflare Setup

```
□ Cloudflared installed
□ Tunnel created
□ DNS configured
□ config.yml created
□ Django settings updated
□ Tunnel tested locally
□ HTTPS working
□ CORS configured
```

### APK Build

```
□ Node.js installed
□ Java JDK installed
□ Android Studio installed
□ Capacitor initialized
□ Android platform added
□ Server URL configured
□ Build successful
□ APK signed
□ App tested on device
□ Bluetooth working
□ Voice recognition working
```

### Production Deployment

```
□ SECRET_KEY changed
□ DEBUG = False
□ ALLOWED_HOSTS configured
□ HTTPS enforced
□ Database backed up
□ Error monitoring setup
□ Performance tested
□ Security audit done
□ Documentation updated
□ User training complete
```

---

## 🎉 Success!

Your AIVIN is now available as:
- ✅ **PWA** - Install from browser
- ✅ **APK** - Native Android app
- ✅ **Web** - Access via Cloudflare

**Access URL:** `https://ai-nurse.yourdomain.com`

**APK Location:** `android/app/build/outputs/apk/release/app-release.apk`

---

**Last Updated:** December 2024

**Version:** 1.0.0

**Status:** ✅ PRODUCTION READY