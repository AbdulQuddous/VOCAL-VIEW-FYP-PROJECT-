# Vocal View - AI-Powered Virtual Interview Coach

## Project Overview
Vocal View is a comprehensive web-based application that helps students and job seekers prepare for interviews through AI-powered mock interviews with real-time and detailed feedback analysis.

## Features
- 🎯 **Dynamic Interview Questions**: AI-generated questions based on job roles
- 🎤 **Real-time Speech Analysis**: Live transcription using OpenAI Whisper
- 📹 **Facial Expression Analysis**: Emotion detection using MediaPipe
- 📊 **Comprehensive Feedback**: Detailed reports with visualizations
- 🔒 **Secure Authentication**: User registration and login system
- 📈 **Interview History**: Track progress over time
- 📄 **Export Reports**: JSON and PDF download options

## Technology Stack
- **Backend**: Django 4.2+
- **Database**: PostgreSQL
- **AI/ML Libraries**:
  - OpenAI Whisper (Speech-to-Text)
  - SpaCy (NLP Analysis)
  - MediaPipe (Facial Landmarks)
  - Librosa (Prosody Analysis)
- **Frontend**: Django Templates + JavaScript
- **Report Generation**: ReportLab (PDF)

## System Requirements
- Python 3.10+
- PostgreSQL 14+
- Minimum 8GB RAM
- Webcam and Microphone

## Installation Guide

### 1. Clone or Extract Project
```bash
cd vocal_view_project
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Download AI Models
```bash
# Download SpaCy English model
python -m spacy download en_core_web_sm

# Whisper models will download automatically on first use
```

### 5. PostgreSQL Setup
```bash
# Create database
sudo -u postgres psql
CREATE DATABASE vocalview_db;
CREATE USER vocalview_user WITH PASSWORD 'your_secure_password';
ALTER ROLE vocalview_user SET client_encoding TO 'utf8';
ALTER ROLE vocalview_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE vocalview_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE vocalview_db TO vocalview_user;
\q
```

### 6. Configure Environment Variables
Create `.env` file in project root:
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_NAME=vocalview_db
DATABASE_USER=vocalview_user
DATABASE_PASSWORD=your_secure_password
DATABASE_HOST=localhost
DATABASE_PORT=5432
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 7. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 8. Create Superuser
```bash
python manage.py createsuperuser
```

### 9. Collect Static Files
```bash
python manage.py collectstatic --noinput
```

### 10. Run Development Server
```bash
python manage.py runserver
```

Access the application at: http://127.0.0.1:8000/

## Project Structure
```
vocal_view_project/
├── vocalview/              # Main Django project
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── interviews/             # Main application
│   ├── models.py          # Database models
│   ├── views.py           # View controllers
│   ├── urls.py            # URL routing
│   ├── forms.py           # Django forms
│   ├── ai_services/       # AI processing modules
│   │   ├── whisper_stt.py
│   │   ├── spacy_nlp.py
│   │   ├── mediapipe_facial.py
│   │   ├── librosa_prosody.py
│   │   └── question_generator.py
│   ├── templates/         # HTML templates
│   ├── static/            # CSS, JS, images
│   └── utils/             # Helper functions
├── media/                 # User uploads (audio/video)
├── static/                # Static files
├── requirements.txt       # Python dependencies
└── manage.py             # Django management script
```

## Usage Guide

### For Users
1. **Register/Login**: Create account or login
2. **Select Job Role**: Choose your target position
3. **Start Interview**: Click "Start Mock Interview"
4. **Answer Questions**: Respond to AI-generated questions (max 15 min)
5. **Get Feedback**: View comprehensive analysis report
6. **Export Report**: Download as PDF or JSON

### For Administrators
Access admin panel at: http://127.0.0.1:8000/admin/
- Manage users
- View interview statistics
- Monitor system performance

## Interview Analysis Metrics

### Verbal Analysis (SpaCy)
- Filler word count (um, uh, like, etc.)
- Technical keyword relevance
- Grammar and clarity score
- Answer structure quality

### Non-Verbal Analysis (MediaPipe)
- Confidence level (facial expressions)
- Stress indicators
- Eye contact estimation
- Posture analysis

### Prosody Analysis (Librosa)
- Speaking pace (words per minute)
- Pitch variation
- Volume consistency
- Pause patterns

## Performance Optimization
- Interview recordings are processed in chunks
- AI models are loaded once and cached
- Database queries are optimized
- Static files are served efficiently

## Security Features
- Password hashing (Django default)
- CSRF protection
- SQL injection prevention
- XSS protection
- Secure session management
- User data isolation

## Troubleshooting

### Common Issues

**1. Database Connection Error**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify credentials in .env file
```

**2. Whisper Model Download Fails**
```bash
# Manually download model
pip install --upgrade openai-whisper
```

**3. MediaPipe Installation Issues**
```bash
# Install system dependencies
sudo apt-get install python3-opencv
pip install --upgrade mediapipe
```

**4. Memory Issues**
```bash
# Use smaller Whisper model
# Edit settings.py: WHISPER_MODEL = "base"
```

## Development

### Running Tests
```bash
python manage.py test interviews
```

### Code Quality
```bash
# Format code
black .

# Lint code
flake8 .
```

## API Endpoints

### Authentication
- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - User login
- `POST /api/auth/logout/` - User logout

### Interviews
- `GET /api/interviews/` - List user interviews
- `POST /api/interviews/start/` - Start new interview
- `POST /api/interviews/process-answer/` - Process answer chunk
- `GET /api/interviews/<id>/report/` - Get feedback report
- `GET /api/interviews/<id>/export/pdf/` - Export PDF
- `GET /api/interviews/<id>/export/json/` - Export JSON

## Contributing
This is an academic project. For issues or suggestions, contact the development team.

## Team
- Abdur Rafay Akbar (BSE-F22-M10)
- Abdul Quddous (BSE-F22-M50)
- Muddasir Mushtaq (BSE-F22-M15)

**Supervisor**: Sir Rehmat Ullah  
**Institution**: University of Mianwali

## License
Educational Use Only - University of Mianwali © 2026

## Version
1.0.0 - Initial Release (November 2026)
