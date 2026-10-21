# AIVIN - Project Index

## 📂 Project Structure

```
AI_Nurse/
├── monolith/                          # ⭐ MAIN APPLICATION
│   ├── kiosk/                        # Django app
│   ├── health_kiosk/                 # Django settings
│   ├── manage.py                     # Django CLI
│   ├── start.py                      # ⚡ Quick start script
│   ├── db.sqlite3                    # Database
│   ├── README.md                     # Setup guide
│   ├── UPDATES.md                    # Latest changes
│   └── .env.example                  # Environment template
├── README.md                          # Main documentation
├── MIGRATION_TO_MONOLITH.md          # Migration guide
└── INDEX.md                          # This file
```

## 🚀 Quick Start

```bash
cd monolith
python start.py
```

**Access at**: http://127.0.0.1:8000/

**Login**: admin / admin123

## 📚 Documentation Guide

### 1. Getting Started
- **[README.md](README.md)** - Start here! Main project overview, features, and setup
- **[monolith/README.md](monolith/README.md)** - Detailed installation and configuration

### 2. Understanding Changes
- **[MIGRATION_TO_MONOLITH.md](MIGRATION_TO_MONOLITH.md)** - Why we moved to monolith architecture
- **[monolith/UPDATES.md](monolith/UPDATES.md)** - ⭐ IMPORTANT! Recent bug fixes and improvements

### 3. Configuration
- **[monolith/.env.example](monolith/.env.example)** - Environment variables template

## 🎯 Main Features

1. **Kiosk Interface** (http://127.0.0.1:8000/)
   - Voice-guided patient registration
   - Bluetooth device integration
   - Real-time measurements

2. **Dashboard** (http://127.0.0.1:8000/dashboard/)
   - Statistics and analytics
   - Recent patients
   - Active queue tickets

3. **Patient Management** (http://127.0.0.1:8000/patients/)
   - Search and filter
   - Complete patient records
   - Measurement history

4. **QR Scanner** (http://127.0.0.1:8000/scanner/)
   - Camera-based scanning
   - Manual entry option
   - Patient data access

5. **Admin Panel** (http://127.0.0.1:8000/admin/)
   - User management
   - Data administration
   - System configuration

## 🔧 Important Files

### Configuration
- `monolith/health_kiosk/settings.py` - Django settings
- `monolith/kiosk/models.py` - Database models
- `monolith/kiosk/views.py` - Views and API endpoints

### Templates (UI)
- `monolith/kiosk/templates/kiosk/home.html` - Main kiosk (voice + Bluetooth)
- `monolith/kiosk/templates/kiosk/dashboard.html` - Dashboard
- `monolith/kiosk/templates/kiosk/patient_list.html` - Patient list
- `monolith/kiosk/templates/kiosk/qr_scanner.html` - QR scanner

### Scripts
- `monolith/start.py` - Quick start script (recommended)
- `monolith/manage.py` - Django management commands

## 📖 Common Tasks

### Start Application
```bash
cd monolith
python start.py
```

### Access Admin Panel
1. Go to http://127.0.0.1:8000/admin/
2. Login: admin / admin123

### Create New Superuser
```bash
cd monolith
python manage.py createsuperuser
```

### Run Migrations
```bash
cd monolith
python manage.py makemigrations
python manage.py migrate
```

### Reset Database
```bash
cd monolith
# Delete database
rm db.sqlite3
# Recreate
python manage.py migrate
python manage.py createsuperuser
```

## 🐛 Troubleshooting

### Issue: Voice not working
- **Solution**: Use Chrome or Edge browser
- **Check**: Microphone permissions granted
- **Verify**: Using HTTPS in production

### Issue: Bluetooth not connecting
- **Solution**: Use Chrome or Edge browser
- **Check**: Bluetooth enabled on device
- **Verify**: Device is powered on

### Issue: Server won't start
- **Solution**: Check if port 8000 is in use
- **Command**: `netstat -ano | findstr :8000` (Windows)
- **Alternative**: Use different port: `python manage.py runserver 8080`

## 🔍 Finding Information

### Want to know about...

**Setup & Installation?**
→ Read [README.md](README.md) (Main) or [monolith/README.md](monolith/README.md)

**Recent Fixes & Updates?**
→ Read [monolith/UPDATES.md](monolith/UPDATES.md) ⭐ IMPORTANT!

**Why Monolith Architecture?**
→ Read [MIGRATION_TO_MONOLITH.md](MIGRATION_TO_MONOLITH.md)

**API Endpoints?**
→ Check [monolith/kiosk/views.py](monolith/kiosk/views.py) or [monolith/README.md](monolith/README.md)

**Database Models?**
→ Check [monolith/kiosk/models.py](monolith/kiosk/models.py)

**Bluetooth Integration?**
→ Read [monolith/UPDATES.md](monolith/UPDATES.md) section on Bluetooth

**Voice Integration?**
→ Read [monolith/UPDATES.md](monolith/UPDATES.md) section on Voice

## 📊 File Purposes

| File | Purpose | When to Read |
|------|---------|--------------|
| `README.md` | Main overview | First time setup |
| `MIGRATION_TO_MONOLITH.md` | Architecture explanation | Understanding changes |
| `monolith/README.md` | Detailed setup | Installation |
| `monolith/UPDATES.md` | Latest fixes | ⭐ Before using! |
| `monolith/start.py` | Quick start script | Running the app |
| `INDEX.md` | This file | Navigation help |

## 🎓 Recommended Reading Order

1. **[README.md](README.md)** - Get overview (5 min)
2. **[monolith/UPDATES.md](monolith/UPDATES.md)** - Understand recent fixes (10 min) ⭐
3. **[monolith/README.md](monolith/README.md)** - Setup details (10 min)
4. **[MIGRATION_TO_MONOLITH.md](MIGRATION_TO_MONOLITH.md)** - Architecture context (optional, 15 min)

**Total Time**: ~30 minutes to understand everything

## 🎯 Quick Reference

### URLs (when server is running)
- Kiosk: http://127.0.0.1:8000/
- Dashboard: http://127.0.0.1:8000/dashboard/
- Patients: http://127.0.0.1:8000/patients/
- Scanner: http://127.0.0.1:8000/scanner/
- Admin: http://127.0.0.1:8000/admin/

### Default Credentials
- **Username**: admin
- **Password**: admin123

### Key Technologies
- Python 3.8+
- Django 5.2.9
- Bootstrap 5.3
- Web Speech API
- Web Bluetooth API

### Browser Support
- ✅ Chrome/Edge (Recommended - Full features)
- ⚠️ Firefox (Limited voice support)
- ⚠️ Safari (Limited features)

## 💡 Tips

1. Always use **Chrome or Edge** for full functionality
2. Grant **microphone** and **Bluetooth** permissions when prompted
3. Use **simulation mode** for testing without real devices
4. Check **[monolith/UPDATES.md](monolith/UPDATES.md)** for latest fixes
5. The **quick start script** (`start.py`) handles everything automatically

## 📞 Support

Having issues?
1. Check browser console for errors
2. Read [monolith/UPDATES.md](monolith/UPDATES.md) for known fixes
3. Verify you're using Chrome/Edge
4. Try simulation mode first
5. Check permissions (microphone, Bluetooth)

## ✨ Status

- **Version**: 1.1.0
- **Status**: Production Ready ✅
- **Architecture**: Monolithic Django Application
- **Last Updated**: December 2024

---

**Navigation**: You are here → INDEX.md