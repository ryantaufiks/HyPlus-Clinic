# 📱 PWA Testing Guide - AIVIN

## ✅ PWA is Ready!

Your Progressive Web App is now configured and ready to test!

---

## 🚀 Quick Test (Local Network)

### Step 1: Start Server

Open Command Prompt and run:

```bash
cd C:\AI_Nurse
quick_start.bat
```

Server will start on: `http://127.0.0.1:8001`

### Step 2: Find Your Computer's IP Address

In another Command Prompt:

```bash
ipconfig
```

Look for **IPv4 Address** (usually starts with 192.168.x.x)

Example: `192.168.1.105`

### Step 3: Access from Mobile Phone

**Requirements:**
- Phone and computer on **same WiFi network**
- Chrome browser on Android (recommended)
- Or Safari on iOS

**On your phone:**

1. Open Chrome browser
2. Navigate to: `http://192.168.1.105:8001` (use YOUR IP address)
3. Wait for page to load
4. Test that the kiosk works

### Step 4: Install PWA

**On Android (Chrome):**
1. Tap menu icon (⋮) top-right
2. Tap **"Add to Home screen"** or **"Install app"**
3. Confirm installation
4. App icon appears on home screen
5. Tap icon to open as full-screen app

**On iOS (Safari):**
1. Tap share button (box with arrow)
2. Scroll down, tap **"Add to Home Screen"**
3. Tap **"Add"**
4. App icon appears on home screen

### Step 5: Test PWA Features

Open the installed app and test:

- ✅ Voice recognition (allow microphone permission)
- ✅ Bluetooth device connection
- ✅ Weight measurement (real or simulated)
- ✅ Blood pressure measurement (real or simulated)
- ✅ QR code generation
- ✅ Offline mode (turn off WiFi, should still load cached pages)

---

## 🌐 Advanced: Remote Access with Cloudflare

For accessing from anywhere (not just local network):

### Step 1: Install Cloudflared

**Windows:**
```bash
winget install --id Cloudflare.cloudflared
```

Or download from: https://github.com/cloudflare/cloudflared/releases

**Verify installation:**
```bash
cloudflared --version
```

### Step 2: Login to Cloudflare

```bash
cloudflared tunnel login
```

This opens browser for authentication. Login with your Cloudflare account (free).

### Step 3: Create Tunnel

```bash
cloudflared tunnel create ai-nurse-tunnel
```

Save the **Tunnel ID** that appears!

### Step 4: Configure Tunnel

Create file: `C:\Users\[YourUser]\.cloudflared\config.yml`

```yaml
tunnel: ai-nurse-tunnel
credentials-file: C:\Users\[YourUser]\.cloudflared\[TUNNEL-ID].json

ingress:
  - hostname: ai-nurse.yourdomain.com
    service: http://localhost:8001
  - service: http_status:404
```

Replace:
- `[YourUser]` with your Windows username
- `[TUNNEL-ID]` with your actual tunnel ID
- `ai-nurse.yourdomain.com` with your desired subdomain

### Step 5: Add DNS Record

```bash
cloudflared tunnel route dns ai-nurse-tunnel ai-nurse.yourdomain.com
```

Or manually in Cloudflare Dashboard:
- Login to Cloudflare
- Select your domain
- DNS → Add Record
- Type: CNAME
- Name: ai-nurse
- Target: [TUNNEL-ID].cfargotunnel.com
- Proxy: ON (orange cloud)

### Step 6: Update Django Settings

Edit `C:\AI_Nurse\monolith\health_kiosk\settings.py`:

Find `ALLOWED_HOSTS` and update:

```python
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "ai-nurse.yourdomain.com",  # Add your domain
    "*.yourdomain.com",
]
```

Find `CSRF_TRUSTED_ORIGINS` and update:

```python
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8001",
    "http://127.0.0.1:8001",
    "https://ai-nurse.yourdomain.com",  # Add your domain
]
```

### Step 7: Start Everything

**Terminal 1 - Django Server:**
```bash
cd C:\AI_Nurse
quick_start.bat
```

**Terminal 2 - Cloudflare Tunnel:**
```bash
cloudflared tunnel run ai-nurse-tunnel
```

### Step 8: Access from Anywhere!

Open browser on **any device** (phone, tablet, another computer):

```
https://ai-nurse.yourdomain.com
```

Install PWA:
- Chrome → Menu → "Add to Home screen"
- Safari → Share → "Add to Home Screen"

---

## 🎯 Testing Checklist

After installing PWA, verify:

```
□ App icon appears on home screen
□ App opens in full-screen (no browser UI)
□ Splash screen shows on launch
□ Voice recognition works (allow microphone)
□ Bluetooth devices can be discovered
□ Weight measurement works (real or simulated)
□ Blood pressure measurement works (real or simulated)
□ QR code generates correctly
□ QR code can be scanned
□ Patient registration saves
□ Dashboard shows data
□ Works offline (after first load)
□ Service worker caches pages
□ Debug panel shows real-time values
```

---

## ⚠️ Troubleshooting

### PWA Installation Option Not Showing

**Problem:** "Add to Home Screen" not appearing

**Solution:**
- Use Chrome browser (not other browsers)
- Access via HTTPS (Cloudflare provides this)
- Make sure manifest.json loads (check browser console)
- Try desktop mode: Chrome menu → Desktop site

### PWA Not Installing on iOS

**Problem:** Can't find "Add to Home Screen"

**Solution:**
- Use Safari browser (not Chrome on iOS)
- Tap share button (box with arrow pointing up)
- Scroll down in the menu
- Look for "Add to Home Screen"

### Service Worker Not Registering

**Problem:** Console shows service worker errors

**Solution:**
- Check browser console (F12)
- Service workers require HTTPS or localhost
- Clear browser cache
- Hard refresh: Ctrl+Shift+R
- Check service-worker.js is accessible: `/static/service-worker.js`

### Bluetooth Not Working

**Problem:** Can't discover devices

**Solution:**
- Bluetooth only works on HTTPS (except localhost)
- Use Cloudflare tunnel for remote access
- Grant Bluetooth permissions when prompted
- Enable location services (Android requirement)
- Measure on device first, then click connect within 5 seconds

### Voice Recognition Not Working

**Problem:** Microphone not capturing voice

**Solution:**
- Grant microphone permission when prompted
- HTTPS required for microphone access
- Check microphone works in device settings
- Speak clearly and close to device
- Check browser console for errors

### Offline Mode Not Working

**Problem:** App doesn't work without internet

**Solution:**
- Visit app once while online first
- Service worker needs to cache files
- Check service worker is registered
- Clear cache and revisit
- Check browser supports service workers

### CORS Errors

**Problem:** Console shows CORS policy errors

**Solution:**
- Update Django settings.py:
  ```python
  CORS_ALLOW_ALL_ORIGINS = True  # For development
  ALLOWED_HOSTS = ["*"]  # For development
  ```
- Restart Django server
- Clear browser cache

### Can't Access from Phone

**Problem:** Connection refused or timeout

**Solution:**
- Check computer and phone on same WiFi
- Check Windows Firewall allows port 8001
- Use correct IP address (run `ipconfig`)
- Make sure server is running
- Try: `python manage.py runserver 0.0.0.0:8001`

---

## 📊 PWA Features Overview

### What Works:
- ✅ Full-screen app experience
- ✅ Works offline after first load
- ✅ Push notifications (future)
- ✅ Background sync (future)
- ✅ Install prompt
- ✅ Splash screen
- ✅ All browser APIs (Bluetooth, Voice, Camera)
- ✅ Automatic updates
- ✅ Responsive design
- ✅ Fast loading (cached)

### What's Cached:
- HTML pages (home, dashboard, patients, scanner)
- CSS files (Bootstrap)
- JavaScript files (jQuery, app scripts)
- Icons and images
- Manifest file

### What Requires Network:
- API calls (creating patients, measurements)
- Real-time data updates
- QR code generation (calls backend)
- Database queries

---

## 💡 Tips & Tricks

### 1. Clear Cache to Test Updates

When you make changes:
```javascript
// In browser console:
navigator.serviceWorker.getRegistrations().then(function(registrations) {
  for(let registration of registrations) {
    registration.unregister();
  }
});
```

Then refresh page.

### 2. Test Service Worker

```javascript
// In browser console:
navigator.serviceWorker.ready.then(registration => {
  console.log('Service Worker ready:', registration);
});
```

### 3. Check Cache Size

```javascript
// In browser console:
navigator.storage.estimate().then(estimate => {
  console.log('Storage used:', estimate.usage, 'bytes');
  console.log('Storage quota:', estimate.quota, 'bytes');
  console.log('Percentage used:', (estimate.usage / estimate.quota * 100).toFixed(2) + '%');
});
```

### 4. Force Update Service Worker

```javascript
// In browser console:
navigator.serviceWorker.getRegistration().then(registration => {
  registration.update();
});
```

### 5. Desktop Testing

You can test PWA on desktop Chrome:
- Open DevTools (F12)
- Application tab
- Service Workers section
- Check "Offline" to simulate offline mode
- Check "Update on reload" for development

---

## 🎨 Customization

### Change App Name

Edit `static/manifest.json`:
```json
{
  "name": "Your App Name",
  "short_name": "App Name"
}
```

### Change Theme Color

Edit `static/manifest.json`:
```json
{
  "theme_color": "#00BCD4",
  "background_color": "#121212"
}
```

### Change Splash Screen

- Theme color and background color define splash
- Icon used is largest (512x512)
- Automatically generated by browser

---

## 🚀 Performance Tips

### 1. Preload Critical Resources

Already configured in service worker!

### 2. Cache Strategy

- **Static files:** Cache first, network fallback
- **API calls:** Network first, cache fallback
- **Images:** Cache first

### 3. Optimize Icons

Icons are already optimized PNG format.

### 4. Minimize API Calls

App caches pages and loads from cache when offline.

---

## 📱 Browser Support

| Browser | PWA Install | Offline | Bluetooth | Voice |
|---------|-------------|---------|-----------|-------|
| Chrome Android | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| Safari iOS | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |
| Edge Android | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| Firefox Android | ⚠️ Limited | ✅ Yes | ❌ No | ✅ Yes |
| Chrome Desktop | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |

**Best Experience:** Chrome on Android

---

## ✅ Success Criteria

Your PWA is working correctly if:

1. ✅ "Add to Home Screen" prompt appears
2. ✅ App installs successfully
3. ✅ Icon appears on home screen with correct logo
4. ✅ Splash screen shows on launch
5. ✅ App opens full-screen (no browser bars)
6. ✅ All features work (voice, Bluetooth, QR)
7. ✅ Works offline after first load
8. ✅ Smooth performance
9. ✅ No console errors
10. ✅ Service worker registers successfully

---

## 📞 Need Help?

**Check Console:**
- Press F12 (desktop) or use Chrome DevTools via USB
- Look for errors in red
- Check Network tab for failed requests
- Check Application tab for service worker status

**Common URLs to verify:**
- Manifest: `http://localhost:8001/static/manifest.json`
- Service Worker: `http://localhost:8001/static/service-worker.js`
- Icons: `http://localhost:8001/static/icons/icon-192x192.png`

**Test Manifest:**
- Chrome DevTools → Application → Manifest
- Should show app name, icons, theme color

**Test Service Worker:**
- Chrome DevTools → Application → Service Workers
- Should show "activated and running"

---

## 🎉 You're Done!

Your PWA is now:
- ✅ Installed on mobile
- ✅ Works offline
- ✅ Smooth Bluetooth integration
- ✅ Professional appearance
- ✅ Automatic updates

**Next Steps:**
- Test all features
- Share with users
- Setup Cloudflare for remote access
- Monitor usage and performance

---

**Version:** 1.0.0  
**Status:** ✅ READY TO USE  
**Last Updated:** December 2024