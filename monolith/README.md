# Health Check Kiosk - Monolithic Application

A complete monolithic Django application for health check kiosks with AI voice assistance and Bluetooth device integration.

## Features

- **Patient Management**: Voice-guided patient registration with speech-to-text
- **Health Measurements**: 
  - Weight measurement via Bluetooth scale
  - Blood pressure and heart rate monitoring
- **AI Voice Assistant**: Text-to-speech guidance throughout the process
- **Queue Management**: Automatic queue number generation with QR codes
- **Dashboard**: Real-time statistics and activity monitoring
- **QR Scanner**: For doctors to quickly access patient data
- **Admin Panel**: Full Django admin for data management

## Technology Stack

- **Backend**: Django 5.2.9
- **Frontend**: HTML5, CSS3, Bootstrap 5.3, JavaScript (ES6+)
- **Database**: SQLite (development)
- **APIs**: 
  - Web Speech API (Speech Recognition & Synthesis)
  - Web Bluetooth API (for device communication)
- **UI**: Glassmorphism design with dark theme

## Installation

1. **Clone the repository**:
   ```bash
   cd AI_Nurse/monolith
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   ```

3. **Activate virtual environment**:
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**:
   ```bash
   pip install django djangorestframework django-cors-headers requests
   ```

5. **Run migrations**:
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**:
   ```bash
   python manage.py createsuperuser
   ```
   - Username: `admin`
   - Email: `admin@example.com`
   - Password: `admin123` (or your choice)

7. **Run the development server**:
   ```bash
   python manage.py runserver
   ```

8. **Access the application**:
   - Kiosk Interface: http://127.0.0.1:8000/
   - Dashboard: http://127.0.0.1:8000/dashboard/
   - Admin Panel: http://127.0.0.1:8000/admin/
   - API Endpoints: http://127.0.0.1:8000/api/

## Application Structure

```
monolith/
├── health_kiosk/          # Django project configuration
│   ├── settings.py        # Settings
│   ├── urls.py           # Main URL routing
│   └── wsgi.py           # WSGI configuration
├── kiosk/                # Main Django app
│   ├── models.py         # Patient, Measurement, QueueTicket models
│   ├── views.py          # Views and API endpoints
│   ├── admin.py          # Admin configuration
│   ├── urls.py           # App URL routing
│   └── templates/        # HTML templates
│       └── kiosk/
│           ├── base.html          # Base template
│           ├── home.html          # Main kiosk interface
│           ├── dashboard.html     # Dashboard
│           ├── patient_list.html  # Patient list
│           └── ...
├── manage.py             # Django management script
└── db.sqlite3           # SQLite database
```

## API Endpoints

### 1. Create Patient
- **URL**: `/api/patients/`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "name": "John Doe",
    "symptoms": "Headache and fever"
  }
  ```
- **Response**:
  ```json
  {
    "id": 1,
    "name": "John Doe",
    "symptoms": "Headache and fever",
    "created_at": "2024-12-03T10:00:00Z"
  }
  ```

### 2. Create Measurement
- **URL**: `/api/measurements/`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "patient_id": 1,
    "weight_kg": 75.5,
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "heart_rate_bpm": 72
  }
  ```

### 3. Generate Queue Ticket
- **URL**: `/api/queue/generate/`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "patient_id": 1
  }
  ```
- **Response**:
  ```json
  {
    "id": 1,
    "patient_id": 1,
    "queue_number": "A001",
    "qr_code_data": "550e8400-e29b-41d4-a716-446655440000",
    "is_active": true,
    "created_at": "2024-12-03T10:00:00Z"
  }
  ```

## User Flow

1. **Welcome Screen**: Initial greeting with AI voice
2. **Patient Information**: 
   - Voice input for name
   - Voice input for symptoms
3. **Weight Measurement**: 
   - Connect to Bluetooth scale
   - Record weight
4. **Blood Pressure**: 
   - Connect to BP monitor
   - Record BP and heart rate
5. **Completion**: 
   - Generate queue number
   - Display QR code
   - Auto-reset for next patient

## Testing

### Manual Testing

1. **Start the server**:
   ```bash
   python manage.py runserver
   ```

2. **Open browser** and navigate to http://127.0.0.1:8000/

3. **Click "Start Health Check"** to begin the process

4. **For testing without actual devices**:
   - The application has simulation mode built-in
   - Click "Connect to Scale" or "Connect to BP Monitor"
   - Simulated measurements will be generated

### API Testing

Use curl or Postman to test the API:

```bash
# Create a patient
curl -X POST http://127.0.0.1:8000/api/patients/ \
  -H "Content-Type: application/json" \
  -d '{"name":"John Doe","symptoms":"Headache"}'

# Create a measurement
curl -X POST http://127.0.0.1:8000/api/measurements/ \
  -H "Content-Type: application/json" \
  -d '{"patient_id":1,"weight_kg":75.5,"systolic_bp":120,"diastolic_bp":80,"heart_rate_bpm":72}'

# Generate queue ticket
curl -X POST http://127.0.0.1:8000/api/queue/generate/ \
  -H "Content-Type: application/json" \
  -d '{"patient_id":1}'
```

## Browser Requirements

- **Chrome/Edge**: Recommended (full Web Speech API support)
- **Firefox**: Limited speech recognition support
- **Safari**: Limited support

For Bluetooth device integration:
- **Chrome/Edge**: Full Web Bluetooth API support
- **Firefox**: Not supported
- **Safari**: Not supported

## Features Details

### Voice Assistant

The application uses the Web Speech API for:
- **Speech Recognition**: Captures patient name and symptoms
- **Speech Synthesis**: Provides voice guidance throughout the process

### Bluetooth Integration

The application is prepared for Web Bluetooth API integration with:
- Weight scales using Weight Scale Service UUID: `0000181d-0000-1000-8000-00805f9b34fb`
- Blood pressure monitors using BP Service UUID: `00001810-0000-1000-8000-00805f9b34fb`

**Note**: Currently in simulation mode for testing without physical devices.

### Glassmorphism UI

Modern, elegant interface with:
- Dark theme with cyan accents
- Glass morphism effects
- Smooth animations
- Responsive design

## Production Deployment

For production deployment:

1. Update `settings.py`:
   - Set `DEBUG = False`
   - Update `ALLOWED_HOSTS`
   - Use PostgreSQL instead of SQLite
   - Set proper `SECRET_KEY`

2. Collect static files:
   ```bash
   python manage.py collectstatic
   ```

3. Use a production WSGI server (Gunicorn, uWSGI)

4. Set up HTTPS for secure communication

5. Configure proper CORS settings

## Troubleshooting

### Voice recognition not working
- Ensure you're using Chrome or Edge
- Check microphone permissions
- Use HTTPS in production (required for Web Speech API)

### Bluetooth not connecting
- Ensure you're using Chrome or Edge
- Check Bluetooth permissions
- Verify device compatibility

### Database errors
- Delete `db.sqlite3` and run migrations again
- Check file permissions

## Security Notes

- Change default admin credentials
- Use environment variables for sensitive data
- Enable HTTPS in production
- Implement rate limiting for API endpoints
- Regular security updates

## License

Proprietary and Confidential

## Support

For issues or questions, contact the development team.

---

**Version**: 1.0.0  
**Last Updated**: December 2024