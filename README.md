# AIVIN — AI-Vital Intake

**Kiosk pemeriksaan tanda vital mandiri untuk tahap pra-konsultasi.**

Before a patient sees the doctor, a nurse usually measures their vital signs, writes them down, and passes the notes on to the doctor. AIVIN takes over this intake step: an AI voice assistant guides the patient, Bluetooth medical devices take the measurements, everything is recorded automatically, and the doctor receives the results ready for further examination. The goal is to **reduce nurse workload**, not to replace nurses.

## 🎯 Overview

AIVIN is a full-stack monolithic application designed to run on tablets in kiosk mode. It provides:
- AI-powered voice interaction for patient guidance
- Bluetooth integration with Omron medical devices
- Automated queue management with QR codes
- Real-time dashboard and analytics
- Complete patient record management

## ✨ Key Features

- **Voice-Guided Interface**: Web Speech API for natural voice interaction
- **Bluetooth Device Integration**: Direct connection to Omron scales and BP monitors
- **Queue Management**: Automatic queue number generation with QR codes
- **Patient Management**: Complete CRUD operations with search and filtering
- **Real-Time Dashboard**: Statistics and recent activity monitoring
- **QR Code Scanner**: Camera-based and manual QR code scanning
- **Health Assessments**: Automatic health status indicators based on measurements
- **Responsive Design**: Modern glassmorphism UI optimized for tablets
- **Print Support**: Print-friendly ticket layouts

## 🏗️ Architecture

**Monolithic Design**: Single Django application combining frontend and backend
- **Backend**: Django 5.2.9 with REST API
- **Frontend**: Server-side rendered templates with Bootstrap 5.3
- **Database**: SQLite (development) / PostgreSQL (production ready)
- **Voice**: Web Speech API (STT & TTS)
- **Bluetooth**: Web Bluetooth API
- **QR Codes**: QRCode.js library

## 📁 Project Structure

```
AI_Nurse/
├── monolith/                  # Main application directory
│   ├── kiosk/                # Django app
│   │   ├── models.py         # Patient, Measurement, QueueTicket models
│   │   ├── views.py          # API endpoints and web views
│   │   ├── urls.py           # URL routing
│   │   ├── admin.py          # Admin panel configuration
│   │   └── templates/        # HTML templates
│   │       └── kiosk/
│   │           ├── base.html              # Base template
│   │           ├── home.html              # Main kiosk interface
│   │           ├── dashboard.html         # Statistics dashboard
│   │           ├── patient_list.html      # Patient listing
│   │           ├── patient_detail.html    # Patient details
│   │           ├── qr_scanner.html        # QR code scanner
│   │           └── queue_ticket.html      # Ticket details
│   ├── health_kiosk/         # Django project settings
│   ├── manage.py             # Django management script
│   ├── start.py              # Quick start script
│   ├── db.sqlite3            # SQLite database
│   ├── README.md             # Detailed setup guide
│   └── UPDATES.md            # Latest updates and fixes
├── docs/                     # Additional documentation
└── README.md                 # This file
```

### 🔑 Configure secrets (required)

Secrets are read from `monolith/.env`, which is **not** committed to git. Before the first run:

```bash
cd monolith
copy .env.example .env      # Windows (use `cp` on Linux/macOS)
```

Then edit `monolith/.env` and set at least `SECRET_KEY` (generate one with
`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
and, if you use AI features, `OPENAI_API_KEY`.

## 🚀 Quick Start (Windows)

### ⚡ Easiest Method - Just Double Click!

**For Windows users, we provide ready-to-use batch files:**

1. **Double-click `quick_start.bat`** in the `AI_Nurse` folder
   - Server starts automatically on port 8001
   - Browser opens automatically
   - That's it! 🎉

**Alternative scripts:**
- `autorun.bat` - With auto-migration and detailed info
- `autorun_advanced.bat` - Full menu with management tools
- `stop_server.bat` - Stop running server

📖 **See [AUTORUN_GUIDE.md](AUTORUN_GUIDE.md) for detailed instructions**

---

## 🚀 Quick Start (Manual Setup)

### Prerequisites

- Python 3.8 or higher
- Modern web browser (Chrome or Edge recommended)
- Bluetooth-enabled device (for real device testing)

### Installation

1. **Navigate to the monolith directory**:
   ```bash
   cd AI_Nurse/monolith
   ```

2. **Run the quick start script**:
   ```bash
   python start.py
   ```

   This script will automatically:
   - Check Python version
   - Create virtual environment
   - Install dependencies
   - Run database migrations
   - Create superuser (admin/admin123)
   - Start the development server

3. **Access the application**:
   - Kiosk Interface: http://127.0.0.1:8000/
   - Dashboard: http://127.0.0.1:8000/dashboard/
   - Patient List: http://127.0.0.1:8000/patients/
   - QR Scanner: http://127.0.0.1:8000/scanner/
   - Admin Panel: http://127.0.0.1:8000/admin/

### Default Credentials

- **Username**: `admin`
- **Password**: `admin123`

## 🎮 User Guide

### For Patients (Kiosk Interface)

1. Click "Start Health Check"
2. Speak your full name when prompted
3. Describe your symptoms when asked
4. Follow instructions for weight measurement
5. Follow instructions for blood pressure measurement
6. Receive your queue number and QR code

### For Healthcare Staff

#### Dashboard
- View real-time statistics
- Monitor recent patients
- Track active queue tickets
- Access quick actions

#### Patient Management
- Search and filter patients
- View complete patient records
- See measurement history
- Access health assessments

#### QR Scanner
- Scan patient QR codes with camera
- Manual QR code entry option
- Instant patient data access
- Print ticket functionality

## 🔧 Technical Details

### API Endpoints

- `POST /api/patients/` - Create new patient
- `POST /api/measurements/` - Save measurements
- `POST /api/queue/generate/` - Generate queue ticket
- `GET /patients/` - List all patients
- `GET /patients/<id>/` - Patient details
- `GET /ticket/<uuid>/` - Ticket details

### Device Integration

**Weight Scale (Omron)**
- Service UUID: `0000181d-0000-1000-8000-00805f9b34fb`
- Characteristic: `00002a9d-0000-1000-8000-00805f9b34fb`
- Data format: IEEE 11073 (weight in kg)

**Blood Pressure Monitor (Omron)**
- Service UUID: `00001810-0000-1000-8000-00805f9b34fb`
- Characteristic: `00002a35-0000-1000-8000-00805f9b34fb`
- Data format: IEEE 11073 (systolic/diastolic/pulse)

### Browser Compatibility

| Feature | Chrome/Edge | Firefox | Safari |
|---------|-------------|---------|--------|
| Voice Input | ✅ Full | ⚠️ Limited | ⚠️ Limited |
| Voice Output | ✅ Full | ✅ Full | ✅ Full |
| Bluetooth | ✅ Full | ❌ None | ❌ None |
| QR Scanner | ✅ Full | ✅ Full | ✅ Full |

**Recommendation**: Use Chrome or Microsoft Edge for full functionality.

## 🧪 Testing

### Voice Input Testing
```bash
1. Open kiosk in Chrome/Edge
2. Click "Start Health Check"
3. Grant microphone permissions
4. Speak clearly when prompted
5. Verify both name and symptoms are recorded
```

### Bluetooth Device Testing
```bash
1. Enable Bluetooth on your device
2. Power on Omron medical device
3. Click "Connect to Real [Device]"
4. Grant Bluetooth permissions
5. Select device from list
6. Perform measurement
7. Verify data appears correctly
```

### Simulation Mode
```bash
# For testing without actual hardware
1. Use "Simulate (Test)" buttons
2. Simulated data will be generated
3. All API calls function normally
4. Perfect for development and demos
```

## 🔐 Security Notes

- Change default admin credentials in production
- Use environment variables for sensitive data
- Enable HTTPS in production (required for Web APIs)
- Implement rate limiting for API endpoints
- Regular security updates recommended
- Follow HIPAA guidelines for patient data

## 📊 Production Deployment

### Prerequisites
- PostgreSQL database
- HTTPS certificate
- Production web server (Gunicorn/uWSGI)
- Reverse proxy (Nginx/Apache)

### Steps
1. Update `settings.py`:
   ```python
   DEBUG = False
   ALLOWED_HOSTS = ['your-domain.com']
   # Configure PostgreSQL
   # Set SECRET_KEY from environment
   ```

2. Collect static files:
   ```bash
   python manage.py collectstatic
   ```

3. Use production WSGI server:
   ```bash
   gunicorn health_kiosk.wsgi:application
   ```

4. Configure Nginx as reverse proxy
5. Set up SSL certificate
6. Configure firewall rules

## 📚 Documentation

- `monolith/README.md` - Detailed setup and configuration
- `monolith/UPDATES.md` - Latest updates and bug fixes
- `docs/` - Additional documentation and guides

## 🐛 Troubleshooting

### Voice recognition not working
- Ensure using Chrome or Edge
- Check microphone permissions
- Verify microphone is working
- Use HTTPS in production

### Bluetooth connection fails
- Ensure using Chrome or Edge
- Check Bluetooth permissions
- Verify Bluetooth is enabled
- Ensure device is powered on
- Check device compatibility

### Database errors
- Delete `db.sqlite3` and run migrations again
- Check file permissions
- Verify SQLite installation

## 🎯 Features Roadmap

- [ ] Patient photo capture
- [ ] Doctor authentication system
- [ ] Appointment scheduling
- [ ] PDF report generation
- [ ] Multi-language support
- [ ] Offline mode capability
- [ ] EMR system integration
- [ ] SMS/Email notifications
- [ ] Advanced analytics
- [ ] Backup and restore

## 🤝 Contributing

This is a proprietary project. For internal development:
1. Create feature branch
2. Make changes
3. Test thoroughly
4. Submit for review

## 📄 License

Proprietary and Confidential - All Rights Reserved

## 👥 Support

For technical support:
- Check browser console for errors
- Review `UPDATES.md` for recent fixes
- Verify device compatibility
- Test with simulation mode first
- Check network connectivity

## 📝 Changelog

### Version 1.1.0 (December 2024)
- ✅ Fixed voice recording for symptoms
- ✅ Implemented real Bluetooth device integration
- ✅ Added patient list and detail pages
- ✅ Created QR scanner with camera support
- ✅ Added queue ticket detail page with health assessments
- ✅ Improved UI/UX with glassmorphism design
- ✅ Added dual mode (Real device + Simulation)
- ✅ Enhanced voice feedback and error handling

### Version 1.0.0 (December 2024)
- Initial monolithic application release
- Basic patient management
- Voice-guided interface
- Queue system with QR codes
- Dashboard and admin panel

---

**Version**: 1.1.0  
**Last Updated**: December 2024  
**Status**: Production Ready  
**Architecture**: Monolithic Django Application  
**Deployment**: Single Server