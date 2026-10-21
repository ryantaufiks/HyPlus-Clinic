# 🚀 Batch Files Reference - AI Nurse Health Kiosk

Quick reference guide for all available batch files to manage your AI Nurse server.

---

## 📦 Available Batch Files

### ⚡ `quick_start.bat` 
**The Fastest Way to Start!**

```
Purpose: Quick launch with minimal steps
Usage:   Double-click the file
Port:    8001 (fixed)
Browser: Opens automatically
```

**What it does:**
- ✅ Activates virtual environment
- ✅ Starts Django server on port 8001
- ✅ Opens browser automatically
- ⚡ No questions, no delays!

**Best for:** Daily use, quick testing

---

### 🎯 `autorun.bat`
**Standard Launch with Safety Checks**

```
Purpose: Start server with auto-migration
Usage:   Double-click the file
Port:    8001 (fixed)
Browser: Opens after 3 seconds
```

**What it does:**
- ✅ Checks virtual environment
- ✅ Activates virtual environment
- ✅ Runs database migrations
- ✅ Starts Django server
- ✅ Opens browser automatically
- ✅ Shows detailed progress
- ✅ Colorful console output

**Best for:** First-time setup, after code updates

---

### 🛠️ `autorun_advanced.bat`
**Full Control Menu**

```
Purpose: Complete management interface
Usage:   Double-click, then select from menu
Port:    8001 (or custom)
Browser: Optional
```

**Menu Options:**
```
[1] Start Server (Port 8001)           - Standard server start
[2] Start Server + Open Browser        - With auto browser
[3] Start Server (Custom Port)         - Choose your port
[4] Run Migrations Only                - Database updates only
[5] Create Superuser                   - Make admin account
[6] Collect Static Files               - Gather static assets
[7] Install/Update Requirements        - Manage packages
[8] Check System Status                - Full diagnostics
[9] Exit                               - Close menu
```

**Best for:** Development, maintenance, troubleshooting

---

### 👤 `create_admin.bat`
**Create Admin User**

```
Purpose: Create Django superuser account
Usage:   Double-click the file
```

**What it does:**
- ✅ Activates virtual environment
- ✅ Runs Django createsuperuser command
- ✅ Prompts for username, email, password
- ✅ Offers to start server after creation

**What you'll need:**
- Username (e.g., `admin`)
- Email (optional, can skip)
- Password (entered twice, hidden)

**Best for:** First-time setup, creating new admins

---

### 🔄 `restart_server.bat`
**Restart Running Server**

```
Purpose: Stop and restart server
Usage:   Double-click the file
Port:    8001 (fixed)
Browser: Opens after restart
```

**What it does:**
- ✅ Finds running server on port 8001
- ✅ Stops the server gracefully
- ✅ Waits 2 seconds
- ✅ Starts server again
- ✅ Opens browser

**Best for:** After code changes, when server hangs

---

### 🛑 `stop_server.bat`
**Stop Running Server**

```
Purpose: Stop Django server on port 8001
Usage:   Double-click the file
```

**What it does:**
- ✅ Finds process using port 8001
- ✅ Terminates the process
- ✅ Shows success/failure message

**Best for:** When Ctrl+C doesn't work, clean shutdown

---

## 🎯 Quick Decision Tree

```
┌─────────────────────────────────────┐
│   What do you want to do?           │
└─────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │                         │
  START                     MANAGE
    │                         │
    ├──────────┬──────────┐   ├──────────┬──────────┐
    │          │          │   │          │          │
  FIRST     DAILY      CODE  CREATE   STOPPED   HUNG
  TIME       USE      CHANGE  ADMIN    SERVER   SERVER
    │          │          │   │          │          │
    ▼          ▼          ▼   ▼          ▼          ▼
 autorun  quick_start restart create  restart   stop
  .bat       .bat      .bat   _admin   _server  _server
                               .bat     .bat     .bat
```

---

## 📋 Common Scenarios

### Scenario 1: First Time Setup
```
Step 1: autorun_advanced.bat → Option [7] (Install Requirements)
Step 2: create_admin.bat (Create your admin account)
Step 3: quick_start.bat (Start using!)
```

### Scenario 2: Daily Usage
```
Just run: quick_start.bat
That's it! 🎉
```

### Scenario 3: After Git Pull / Code Update
```
Run: autorun.bat
(It will handle migrations automatically)
```

### Scenario 4: Server Not Responding
```
Step 1: stop_server.bat
Step 2: quick_start.bat
```

### Scenario 5: Need Different Port
```
Run: autorun_advanced.bat → Option [3]
Enter your preferred port number
```

### Scenario 6: Creating Additional Admins
```
Run: create_admin.bat
Enter new credentials
```

### Scenario 7: Check if Everything is OK
```
Run: autorun_advanced.bat → Option [8]
View complete system diagnostics
```

---

## 🔧 Technical Details

### Port Configuration
- **Default Port:** 8001
- **Change Port:** Edit `.bat` file or use `autorun_advanced.bat` → Option [3]
- **Check Port Usage:** `netstat -ano | findstr :8001`

### Virtual Environment
- **Location:** `monolith/venv/`
- **Activation:** `venv\Scripts\activate.bat`
- **Required:** All scripts need this to work

### Database
- **Type:** SQLite (development)
- **Location:** `monolith/db.sqlite3`
- **Migrations:** Automatic with `autorun.bat`

### Requirements
- **File:** `monolith/requirements.txt`
- **Install:** Use `autorun_advanced.bat` → Option [7]
- **Update:** Same as install

---

## ⚠️ Troubleshooting

### Error: "Virtual environment not found"
**Cause:** Virtual environment not created or corrupted

**Solution:**
```batch
# Method 1: Use advanced menu
autorun_advanced.bat → Option [7]

# Method 2: Manual
cd monolith
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

### Error: "Port 8001 already in use"
**Cause:** Server already running or port occupied

**Solution:**
```batch
# Method 1: Stop current server
stop_server.bat

# Method 2: Use different port
autorun_advanced.bat → Option [3]

# Method 3: Manual kill
netstat -ano | findstr :8001
taskkill /PID <PID_NUMBER> /F
```

---

### Error: "Module not found" or Import errors
**Cause:** Missing Python packages

**Solution:**
```batch
autorun_advanced.bat → Option [7]
```

---

### Browser doesn't open automatically
**Cause:** Security settings or browser not set as default

**Solution:**
Manually open: http://127.0.0.1:8001

---

### Server starts but shows errors
**Cause:** Database needs migration

**Solution:**
```batch
autorun_advanced.bat → Option [4]
```

---

## 💡 Pro Tips

### Tip 1: Create Desktop Shortcut
```
1. Right-click quick_start.bat
2. "Send to" → "Desktop (create shortcut)"
3. Rename to "🏥 AI Nurse"
4. Double-click anytime to start!
```

### Tip 2: Pin to Taskbar
```
1. Create shortcut (see Tip 1)
2. Right-click shortcut
3. "Pin to taskbar"
4. One-click access!
```

### Tip 3: Run as Administrator
```
If you get permission errors:
- Right-click any .bat file
- "Run as administrator"
```

### Tip 4: Silent Background Mode
Create `silent_start.vbs`:
```vbscript
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "C:\AI_Nurse\quick_start.bat", 0
Set WshShell = Nothing
```
No console window will appear!

### Tip 5: Custom Batch File
Copy any .bat file and modify:
```batch
# Change port
python manage.py runserver 0.0.0.0:9000

# Change browser URL
start http://127.0.0.1:9000/dashboard

# Add custom commands
python manage.py collectstatic --noinput
```

---

## 📊 Comparison Table

| Feature                  | quick_start | autorun | autorun_advanced | create_admin | restart | stop |
|--------------------------|-------------|---------|------------------|--------------|---------|------|
| Speed                    | ⚡⚡⚡       | ⚡⚡     | ⚡               | ⚡⚡         | ⚡⚡     | ⚡⚡⚡ |
| Auto Migration           | ❌          | ✅       | ✅ (manual)       | ❌           | ❌      | N/A  |
| Auto Browser             | ✅          | ✅       | ✅ (optional)     | ✅ (optional)| ✅      | N/A  |
| Custom Port              | ❌          | ❌       | ✅               | ❌           | ❌      | N/A  |
| Error Handling           | Basic       | ✅       | ✅✅              | ✅           | ✅      | ✅   |
| Progress Info            | ❌          | ✅       | ✅✅              | ✅           | ✅      | ✅   |
| Management Tools         | ❌          | ❌       | ✅✅              | ❌           | ❌      | ❌   |
| System Diagnostics       | ❌          | ❌       | ✅               | ❌           | ❌      | ❌   |
| Best For                 | Daily use   | Setup   | Development      | Admin setup  | Refresh | Stop |

---

## 🆘 Need More Help?

### Documentation
- **Full Guide:** `AUTORUN_GUIDE.md`
- **Setup Manual:** `monolith/README.md`
- **Latest Updates:** `monolith/UPDATES.md`
- **Device Guide:** `monolith/DEVICE_TESTING_GUIDE.md`

### Quick Help
- **Start Here:** `START_HERE.txt`
- **Main README:** `README.md`

### Online Resources
- Django Documentation: https://docs.djangoproject.com/
- Python Documentation: https://docs.python.org/

---

## 📝 Version History

- **v1.0** - Initial release with basic scripts
- **v2.0** - Added advanced menu and diagnostics
- **v2.1** - Added create_admin and restart scripts
- **v2.2** - Enhanced error handling and logging

---

## ✅ Checklist for First-Time Users

```
□ Python 3.8+ installed
□ Git repository cloned
□ Run: autorun_advanced.bat → [7] Install Requirements
□ Run: create_admin.bat (create superuser)
□ Run: quick_start.bat
□ Access: http://127.0.0.1:8001
□ Login to admin: http://127.0.0.1:8001/admin
□ Create desktop shortcut (optional)
□ Bookmark URLs in browser
```

---

**Happy coding! 🚀💙**

*Last Updated: December 2024*