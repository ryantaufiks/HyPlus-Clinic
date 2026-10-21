# 📦 Installation Guide - AIVIN

Complete installation guide for setting up the AIVIN system.

---

## 🎯 Quick Installation (Recommended)

### Windows - One-Click Install

1. **Run the installer:**
   ```
   Double-click: install_packages.bat
   ```

2. **The script will:**
   - ✅ Check Python installation
   - ✅ Create virtual environment
   - ✅ Install all required packages
   - ✅ Offer to create superuser

3. **Start the server:**
   ```
   Double-click: quick_start.bat
   ```

**That's it! 🎉**

---

## 📋 System Requirements

### Minimum Requirements
- **OS:** Windows 10/11 (64-bit)
- **Python:** 3.8 or higher
- **RAM:** 4GB minimum
- **Storage:** 500MB free space
- **Browser:** Chrome 90+ or Edge 90+ (for Bluetooth support)
- **Internet:** Required for initial setup and CDN resources

### Recommended
- **RAM:** 8GB or more
- **Browser:** Latest Chrome or Edge
- **Bluetooth:** Built-in or USB adapter (for medical devices)

---

## 🔧 Manual Installation

### Step 1: Verify Python Installation

```bash
python --version
```

Should output: `Python 3.8.x` or higher

**If Python is not installed:**
1. Download from: https://www.python.org/downloads/
2. During installation, **CHECK "Add Python to PATH"**
3. Restart your computer

---

### Step 2: Navigate to Project Directory

```bash
cd C:\AI_Nurse\monolith
```

---

### Step 3: Create Virtual Environment

```bash
python -m venv venv
```

This creates an isolated Python environment in the `venv` folder.

---

### Step 4: Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

You should see `(venv)` in your command prompt.

---

### Step 5: Upgrade pip

```bash
python -m pip install --upgrade pip
```

---

### Step 6: Install Required Packages

```bash
pip install -r requirements.txt
```

This installs:
- **Django 5.x** - Web framework
- **qrcode[pil] 7.4.2+** - QR code generation
- **Pillow 10.0.0+** - Image processing

---

### Step 7: Run Database Migrations

```bash
python manage.py migrate
```

Creates the SQLite database and tables.

---

### Step 8: Create Superuser (Admin Account)

```bash
python manage.py createsuperuser
```

Enter:
- Username (e.g., `admin`)
- Email (optional, can skip)
- Password (enter twice)

---

### Step 9: Start the Server

```bash
python manage.py runserver 0.0.0.0:8001
```

---

### Step 10: Access the Application

Open browser: http://127.0.0.1:8001

**Admin Panel:** http://127.0.0.1:8001/admin

---

## 📦 Package Details

### Core Dependencies

#### Django (>=5.0, <6.0)
- **Purpose:** Web framework
- **License:** BSD
- **Documentation:** https://docs.djangoproject.com/

#### qrcode[pil] (>=7.4.2)
- **Purpose:** Generate QR codes for queue tickets
- **License:** BSD
- **Documentation:** https://pypi.org/project/qrcode/
- **Features Used:**
  - QR code generation
  - Image output (PNG)
  - Customizable size and error correction

#### Pillow (>=10.0.0)
- **Purpose:** Image processing (required by qrcode)
- **License:** PIL License
- **Documentation:** https://pillow.readthedocs.io/
- **Features Used:**
  - Image creation and manipulation
  - PNG format support
  - Base64 encoding

---

## 🔍 Verify Installation

### Check Installed Packages

```bash
pip list
```

Should show:
```
Django          5.x.x
qrcode          7.x.x
Pillow          10.x.x
```

### Check Django Version

```bash
python -m django --version
```

### Run System Check

```bash
python manage.py check
```

Should output: `System check identified no issues (0 silenced).`

---

## ⚠️ Troubleshooting Installation

### Issue 1: "Python not found"

**Solution:**
1. Install Python from https://www.python.org/
2. During install, CHECK "Add Python to PATH"
3. Restart computer
4. Verify: `python --version`

---

### Issue 2: "pip not found"

**Solution:**
```bash
python -m ensurepip --upgrade
python -m pip install --upgrade pip
```

---

### Issue 3: "Cannot create virtual environment"

**Solution:**
```bash
# Install venv module
python -m pip install virtualenv

# Try creating again
python -m venv venv
```

---

### Issue 4: "Permission denied"

**Solution:**
- Run Command Prompt as Administrator
- Or use: `install_packages.bat` (right-click → Run as Administrator)

---

### Issue 5: "pip install fails"

**Possible causes:**
- No internet connection
- Firewall blocking
- Antivirus blocking

**Solution:**
```bash
# Try with trusted host
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Or install packages individually
pip install Django
pip install qrcode[pil]
pip install Pillow
```

---

### Issue 6: "Pillow installation fails on Windows"

**Solution:**
1. Download Visual C++ Build Tools:
   https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Install with default options
3. Retry: `pip install Pillow`

**Alternative:**
```bash
# Use pre-compiled wheel
pip install --upgrade pip setuptools wheel
pip install Pillow
```

---

### Issue 7: "Module not found" when starting server

**Solution:**
```bash
# Ensure virtual environment is activated
venv\Scripts\activate

# Reinstall packages
pip install -r requirements.txt

# Verify
python -c "import django, qrcode, PIL"
```

---

## 🔄 Updating Packages

### Update All Packages

```bash
pip install --upgrade -r requirements.txt
```

### Update Specific Package

```bash
pip install --upgrade Django
pip install --upgrade qrcode
pip install --upgrade Pillow
```

### Check for Outdated Packages

```bash
pip list --outdated
```

---

## 🗑️ Uninstallation

### Remove Virtual Environment

```bash
# Deactivate first
deactivate

# Delete folder
rmdir /s venv
```

### Remove Packages Only

```bash
pip uninstall -r requirements.txt -y
```

---

## 🌐 Production Deployment Notes

For production deployment, you'll need additional packages:

```bash
pip install gunicorn psycopg2-binary whitenoise
```

**Additional requirements.txt for production:**
```
Django>=5.0,<6.0
qrcode[pil]>=7.4.2
Pillow>=10.0.0
gunicorn>=21.0.0
psycopg2-binary>=2.9.0
whitenoise>=6.5.0
```

---

## 📊 Installation Checklist

Use this checklist to ensure proper installation:

```
□ Python 3.8+ installed
□ Python in PATH
□ Virtual environment created
□ Virtual environment activated
□ pip upgraded
□ requirements.txt packages installed
□ Django installed successfully
□ qrcode installed successfully
□ Pillow installed successfully
□ Database migrations completed
□ Superuser created
□ Server starts without errors
□ Can access http://127.0.0.1:8001
□ Can login to admin panel
□ QR codes generate correctly
```

---

## 💡 Tips

### Tip 1: Keep Virtual Environment
Never delete the `venv` folder! It contains all your packages.

### Tip 2: Activate Before Running
Always activate virtual environment before running commands:
```bash
venv\Scripts\activate
```

### Tip 3: Use Batch Files
Use the provided `.bat` files - they handle activation automatically.

### Tip 4: Freeze Requirements
After installing new packages, update requirements:
```bash
pip freeze > requirements.txt
```

### Tip 5: Backup Database
Regularly backup `db.sqlite3` file.

---

## 🆘 Getting Help

### Quick Links
- **Quick Start:** `START_HERE.txt`
- **Autorun Guide:** `AUTORUN_GUIDE.md`
- **Main README:** `README.md`

### Check Logs
Server logs appear in the console window when running.

### Debug Mode
Set in `health_kiosk/settings.py`:
```python
DEBUG = True  # Development
DEBUG = False  # Production
```

---

## ✅ Installation Complete!

After successful installation:

1. **Start server:** `quick_start.bat`
2. **Access kiosk:** http://127.0.0.1:8001
3. **Admin panel:** http://127.0.0.1:8001/admin

**Next Steps:**
- Configure settings in Django admin
- Test QR code generation
- Test Bluetooth devices (optional)
- Customize as needed

---

**Happy coding! 🚀💙**

*Last Updated: December 2024*