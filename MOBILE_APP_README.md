# 📱 Mobile App Setup - AIVIN

Quick guide to get the mobile app running on Android devices.

---

## 🎯 Choose Your Method

### ⚡ **Method 1: PWA (RECOMMENDED - Easiest)**

**What is it?**
- Install app directly from browser
- No APK needed
- Works immediately
- Automatic updates

**Steps:**
1. Deploy server with Cloudflare (see below)
2. Open Chrome on Android phone
3. Navigate to your domain
4. Menu (⋮) → "Add to Home Screen"
5. Done! ✅

**Time:** 5 minutes

---

### 🛠️ **Method 2: Build APK (Advanced)**

**What is it?**
- Native Android app (`.apk` file)
- Professional appearance
- Can distribute to others

**Requirements:**
- Node.js (https://nodejs.org/)
- Java JDK 11+ (https://adoptium.net/)
- Android Studio (https://developer.android.com/studio)

**Steps:**
1. Run: `build_apk.bat`
2. Follow on-screen instructions
3. Open Android Studio
4. Build → Generate Signed Bundle / APK
5. Install APK on device

**Time:** 30-60 minutes (first time)

**See:** `APK_BUILD_GUIDE.md` for detailed instructions

---

## 🌐 Cloudflare Deployment (For Remote Access)

### Why Cloudflare?
- ✅ Access server from anywhere
- ✅ Free SSL certificate (HTTPS)
- ✅ No port forwarding needed
- ✅ Secure tunnel
- ✅ Fast and reliable

### Quick Setup:

**1. Install Cloudflared**
```bash
# Download from: https://github.com/cloudflare/cloudflared/releases
# Or Windows:
winget install --id Cloudflare.cloudflared
```

**2. Login**
```bash
cloudflared tunnel login
```

**3. Create Tunnel**
```bash
cloudflared tunnel create ai-nurse-tunnel
```

**4. Create Config File**

Create `C:\Users\YourUser\.cloudflared\config.yml`:

```yaml
tunnel: ai-nurse-tunnel
credentials-file: C:\Users\YourUser\.cloudflared\[tunnel-id].json

ingress:
  - hostname: ai-nurse.yourdomain.com
    service: http://localhost:8001
  - service: http_status:404
```

**5. Route DNS**
```bash
cloudflared tunnel route dns ai-nurse-tunnel ai-nurse.yourdomain.com
```

**6. Update Django Settings**

Edit `monolith/health_kiosk/settings.py`:
```python
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "ai-nurse.yourdomain.com",
]

CSRF_TRUSTED_ORIGINS = [
    "https://ai-nurse.yourdomain.com",
]
```

**7. Start Everything**

Terminal 1:
```bash
cd AI_Nurse
quick_start.bat
```

Terminal 2:
```bash
cloudflared tunnel run ai-nurse-tunnel
```

**8. Access from Phone**
```
Open browser: https://ai-nurse.yourdomain.com
Install PWA: Menu → Add to Home Screen
```

---

## 🚀 Quick Commands

### For PWA:
```bash
# Generate icons
python generate_icons.py

# Start server
quick_start.bat

# Start tunnel
cloudflared tunnel run ai-nurse-tunnel
```

### For APK:
```bash
# Setup
build_apk.bat

# Or manual:
npm install
npx cap sync android
npx cap open android
```

---

## 📱 Features in Mobile App

### Working Features:
- ✅ Voice recognition (microphone access)
- ✅ Bluetooth device connection
- ✅ Weight scale integration
- ✅ Blood pressure monitor integration
- ✅ QR code generation
- ✅ QR code scanning (camera access)
- ✅ Patient registration
- ✅ Health measurements
- ✅ Real-time dashboard
- ✅ Offline support (PWA)

### Bluetooth Devices Supported:
- 🔹 Omron HN-289 Weight Scale
- 🔹 Omron HEM-7156T Blood Pressure Monitor
- 🔹 Other BLE medical devices

---

## 🔧 Bluetooth Configuration

### For Better Bluetooth Performance:

**1. Android Permissions**

If building APK, add to `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.BLUETOOTH" />
<uses-permission android:name="android.permission.BLUETOOTH_ADMIN" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
<uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-feature android:name="android.hardware.bluetooth_le" android:required="true" />
```

**2. Enable Location Services**
- Android requires location for Bluetooth LE
- Settings → Location → Turn ON

**3. Grant Permissions**
- When app asks for permissions, allow:
  - Bluetooth
  - Location
  - Microphone
  - Camera

---

## 📊 PWA vs APK Comparison

| Feature | PWA | APK |
|---------|-----|-----|
| Installation Time | 1 minute | 30-60 minutes |
| File Size | ~1-2 MB | ~15-20 MB |
| Updates | Automatic | Manual |
| Works on iOS | ✅ Yes | ❌ No |
| Offline Support | ✅ Yes | ✅ Yes |
| Bluetooth Support | ✅ Yes | ✅ Yes |
| Build Tools Needed | None | Node.js, Java, Android Studio |
| Distribution | Share URL | Share APK file |
| Professional Look | Good | Better |
| App Store | ❌ No | ✅ Yes (with extra steps) |

**Recommendation:** Start with PWA, build APK later if needed.

---

## 🎨 Customization

### Change App Name:
- PWA: Edit `static/manifest.json`
- APK: Edit `android/app/src/main/res/values/strings.xml`

### Change App Icon:
- Run `generate_icons.py` with custom image
- Or manually replace icons in `static/icons/`

### Change Colors:
- Edit `kiosk/templates/kiosk/base.html` (CSS variables)
- Theme color: `#00BCD4` (cyan)
- Background: `#121212` (dark)

### Change Server URL (for APK):
- Edit `capacitor.config.json`
- Change `server.url` to your domain

---

## ⚠️ Troubleshooting

### PWA Installation:

**Problem:** "Add to Home Screen" option not showing
- **Solution:** Use Chrome browser, access via HTTPS

**Problem:** PWA not working offline
- **Solution:** Visit site once online, then will work offline

### APK Build:

**Problem:** Build failed
- **Solution:** Check Java version (needs 11+)
- **Solution:** Install Android SDK Platform 33+

**Problem:** APK won't install
- **Solution:** Enable "Install from Unknown Sources"
- **Solution:** Check Android version (minimum 7.0)

### Bluetooth:

**Problem:** Can't find device
- **Solution:** Device must be measuring first, then connect within 5 seconds
- **Solution:** Enable location services
- **Solution:** Grant Bluetooth permissions

**Problem:** Connection drops
- **Solution:** Stay close to device during measurement
- **Solution:** Complete measurement on device first

### Server Connection:

**Problem:** Can't connect to server
- **Solution:** Check server is running (`quick_start.bat`)
- **Solution:** Check firewall not blocking port 8001
- **Solution:** For remote: Check Cloudflare tunnel is running

**Problem:** CORS errors
- **Solution:** Update `ALLOWED_HOSTS` in Django settings
- **Solution:** Add domain to `CSRF_TRUSTED_ORIGINS`

---

## 📂 File Structure

```
AI_Nurse/
├── static/
│   ├── manifest.json          # PWA configuration
│   ├── service-worker.js      # Offline support
│   └── icons/                 # App icons (all sizes)
│
├── android/                   # Android Studio project (after cap add)
│   └── app/
│       ├── build/
│       │   └── outputs/apk/  # Built APK files
│       └── src/main/
│           └── AndroidManifest.xml  # Permissions
│
├── capacitor.config.json      # Capacitor configuration
├── package.json               # Node.js dependencies
├── generate_icons.py          # Icon generator script
├── build_apk.bat             # APK build script
├── APK_BUILD_GUIDE.md        # Detailed build guide
└── MOBILE_APP_README.md      # This file
```

---

## 🔐 Security Notes

### For Production:

1. **Change Django SECRET_KEY**
   ```python
   # In settings.py
   SECRET_KEY = "your-new-secret-key-here"
   ```

2. **Set DEBUG = False**
   ```python
   DEBUG = False
   ```

3. **Configure ALLOWED_HOSTS**
   ```python
   ALLOWED_HOSTS = ["your-domain.com"]
   ```

4. **Use HTTPS (Cloudflare provides this)**

5. **Enable Security Headers**
   ```python
   SECURE_SSL_REDIRECT = True
   SESSION_COOKIE_SECURE = True
   CSRF_COOKIE_SECURE = True
   ```

---

## 💡 Best Practices

### 1. Start with PWA
- Test everything works
- Get user feedback
- Build APK later if needed

### 2. Use Cloudflare for Production
- Free and reliable
- Automatic HTTPS
- DDoS protection

### 3. Keep Server Running
Use Windows Task Scheduler or Linux systemd for auto-start

### 4. Regular Backups
Backup `db.sqlite3` regularly

### 5. Monitor Performance
Check server logs for errors

---

## 📞 Quick Help

### I want to test locally on phone:
1. Find your computer's IP: `ipconfig` (Windows) or `ifconfig` (Linux)
2. Start server: `python manage.py runserver 0.0.0.0:8001`
3. On phone browser: `http://192.168.1.xxx:8001`
4. Make sure phone and computer on same WiFi

### I want to access from anywhere:
1. Setup Cloudflare Tunnel (see above)
2. Start tunnel: `cloudflared tunnel run ai-nurse-tunnel`
3. Access from anywhere: `https://your-domain.com`

### I want a professional APK:
1. Run: `build_apk.bat`
2. Open Android Studio when prompted
3. Build → Generate Signed Bundle / APK
4. Create keystore and sign APK
5. Distribute APK file

### I want automatic deployment:
1. Use Cloudflare Tunnel for remote access
2. Use PWA for instant updates (no APK rebuild needed)
3. Update code → Refresh browser → Users get new version

---

## 🎉 Success Checklist

```
□ Icons generated (8 sizes)
□ PWA manifest configured
□ Service worker registered
□ Django server running
□ Cloudflare tunnel working (if remote)
□ Can access from mobile browser
□ PWA installs successfully
□ Bluetooth devices connect
□ Voice recognition works
□ QR codes generate correctly
□ Database saves measurements
□ App works offline (PWA)
```

---

## 📚 Documentation Links

- **Complete APK Guide:** `APK_BUILD_GUIDE.md` (800+ lines)
- **Autorun Scripts:** `AUTORUN_GUIDE.md`
- **Installation:** `INSTALLATION.md`
- **Quick Start:** `START_HERE.txt`
- **Batch Files:** `BATCH_FILES_README.md`

---

## 🚀 Quick Start Summary

**Fastest way to get mobile app running:**

```bash
# 1. Generate icons
python generate_icons.py

# 2. Start server
quick_start.bat

# 3. Setup Cloudflare Tunnel
cloudflared tunnel login
cloudflared tunnel create ai-nurse-tunnel
# (configure DNS and settings as shown above)

# 4. Start tunnel
cloudflared tunnel run ai-nurse-tunnel

# 5. Open on phone
# Browser → https://ai-nurse.yourdomain.com
# Menu → Add to Home Screen

# Done! ✅
```

---

**Version:** 1.0.0  
**Last Updated:** December 2024  
**Status:** ✅ Production Ready

**Need help?** Check `APK_BUILD_GUIDE.md` for detailed instructions.