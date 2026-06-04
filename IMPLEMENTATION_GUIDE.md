# VOCAL VIEW - COMPLETE IMPLEMENTATION GUIDE

## Overview
This document contains the complete implementation of the Vocal View AI-Powered Virtual Interview Coach system as per the SRS document specifications.

## Project Status: ✅ CORE FRAMEWORK COMPLETE

### ✅ Completed Components

1. **Project Structure** - DONE
2. **Django Settings** - DONE
3. **Database Models** - DONE (All 10 models as per SRS)
4. **AI Services** - DONE
   - Whisper STT Service
   - SpaCy NLP Service
   - MediaPipe Facial Analysis
   - Librosa Prosody Analysis

### 📋 Additional Files Needed (Code provided below)

## REMAINING FILES TO CREATE

### 1. interviews/views.py

```python
"""
Main Views for Vocal View Application
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import (
    InterviewSession, JobRole, Question, Answer,
    FeedbackReport, UserProfile
)
from .forms import UserRegistrationForm, InterviewConfigForm
import json
import uuid


def index(request):
    """Landing page"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'interviews/index.html')


def register(request):
    """User registration"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create user profile
            UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'auth/register.html', {'form': form})


def user_login(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials')
    
    return render(request, 'auth/login.html')


@login_required
def user_logout(request):
    """User logout"""
    logout(request)
    return redirect('index')


@login_required
def dashboard(request):
    """User dashboard"""
    profile = request.user.profile
    recent_sessions = InterviewSession.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    context = {
        'profile': profile,
        'recent_sessions': recent_sessions,
    }
    return render(request, 'interviews/dashboard.html', context)


@login_required
def interview_config(request):
    """Configure new interview"""
    job_roles = JobRole.objects.all()
    
    if request.method == 'POST':
        job_role_id = request.POST.get('job_role')
        job_role = get_object_or_404(JobRole, role_id=job_role_id)
        
        # Create new interview session
        session = InterviewSession.objects.create(
            user=request.user,
            job_role=job_role,
            status='pending'
        )
        
        return redirect('interview_conduct', session_id=session.session_id)
    
    context = {'job_roles': job_roles}
    return render(request, 'interviews/config.html', context)


@login_required
def interview_conduct(request, session_id):
    """Conduct interview"""
    session = get_object_or_404(InterviewSession, session_id=session_id, user=request.user)
    
    # Start session if pending
    if session.status == 'pending':
        session.start_interview()
    
    context = {
        'session': session,
        'max_duration': session.max_duration_minutes,
    }
    return render(request, 'interviews/conduct.html', context)


@login_required
def interview_history(request):
    """View interview history"""
    sessions = InterviewSession.objects.filter(
        user=request.user,
        status='completed'
    ).order_by('-created_at')
    
    context = {'sessions': sessions}
    return render(request, 'interviews/history.html', context)


@login_required
def feedback_report(request, session_id):
    """View feedback report"""
    session = get_object_or_404(InterviewSession, session_id=session_id, user=request.user)
    
    try:
        report = session.feedback_report
    except FeedbackReport.DoesNotExist:
        messages.error(request, 'Report not yet generated')
        return redirect('dashboard')
    
    context = {
        'session': session,
        'report': report,
    }
    return render(request, 'reports/feedback.html', context)
```

### 2. interviews/forms.py

```python
"""
Django Forms for Vocal View
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile, JobRole


class UserRegistrationForm(UserCreationForm):
    """Extended user registration form"""
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=200, required=False)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'full_name']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class InterviewConfigForm(forms.Form):
    """Interview configuration form"""
    job_role = forms.ModelChoiceField(
        queryset=JobRole.objects.all(),
        required=True,
        label="Select Job Role"
    )
    
    duration = forms.IntegerField(
        min_value=5,
        max_value=15,
        initial=15,
        label="Interview Duration (minutes)"
    )
```

### 3. interviews/urls.py

```python
"""
URL Configuration for Interviews App
"""
from django.urls import path
from . import views

urlpatterns = [
    # Public pages
    path('', views.index, name='index'),
    
    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Interview management
    path('interview/config/', views.interview_config, name='interview_config'),
    path('interview/conduct/<uuid:session_id>/', views.interview_conduct, name='interview_conduct'),
    path('interview/history/', views.interview_history, name='interview_history'),
    
    # Reports
    path('report/<uuid:session_id>/', views.feedback_report, name='feedback_report'),
]
```

### 4. interviews/admin.py

```python
"""
Django Admin Configuration
"""
from django.contrib import admin
from .models import (
    JobRole, Question, InterviewSession, Answer,
    ContentAnalysis, FacialAnalysis, ProsodyAnalysis,
    EmotionTimeline, FeedbackReport, UserProfile
)


@admin.register(JobRole)
class JobRoleAdmin(admin.ModelAdmin):
    list_display = ['role_name', 'role_category', 'created_at']
    search_fields = ['role_name', 'role_category']
    list_filter = ['role_category']


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'job_role', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'job_role__role_name']
    readonly_fields = ['session_id', 'created_at', 'updated_at']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['question_id', 'question_type', 'difficulty', 'created_at']
    list_filter = ['question_type', 'difficulty']
    search_fields = ['question_text']


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['answer_id', 'question', 'session', 'duration', 'is_processed']
    list_filter = ['is_processed', 'recorded_at']


@admin.register(FeedbackReport)
class FeedbackReportAdmin(admin.ModelAdmin):
    list_display = ['report_id', 'session', 'overall_score', 'generated_at']
    readonly_fields = ['report_id', 'generated_at']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'experience_level', 'total_interviews', 'average_score']
    list_filter = ['experience_level']
    search_fields = ['user__username', 'full_name']


# Register remaining models
admin.site.register(ContentAnalysis)
admin.site.register(FacialAnalysis)
admin.site.register(ProsodyAnalysis)
admin.site.register(EmotionTimeline)
```

### 5. interviews/ai_services/question_generator.py

```python
"""
Question Generation Service using GPT-2
"""
from transformers import pipeline, set_seed
import logging
from django.conf import settings
import random

logger = logging.getLogger(__name__)


class QuestionGeneratorService:
    """Generate interview questions using AI"""
    
    def __init__(self):
        self.generator = None
        
    def _load_model(self):
        """Lazy load GPT-2 model"""
        if self.generator is None:
            logger.info("Loading GPT-2 for question generation")
            try:
                self.generator = pipeline('text-generation', model='gpt2')
                set_seed(42)
                logger.info("Question generator loaded")
            except Exception as e:
                logger.error(f"Failed to load generator: {str(e)}")
                raise
    
    def generate_questions(self, job_role, num_questions=5):
        """
        Generate interview questions for a job role
        
        Args:
            job_role: JobRole instance
            num_questions: Number of questions to generate
            
        Returns:
            list: Generated questions
        """
        # For initial version, use predefined questions
        # In production, use GPT-2 or other LLM
        
        questions_bank = self._get_questions_bank(job_role.role_category)
        
        # Select random questions
        selected = random.sample(
            questions_bank,
            min(num_questions, len(questions_bank))
        )
        
        return selected
    
    def _get_questions_bank(self, category):
        """Get predefined questions by category"""
        
        tech_questions = [
            {"text": "Tell me about your experience with Python programming.", "type": "technical"},
            {"text": "How do you approach debugging a complex issue?", "type": "technical"},
            {"text": "Describe a challenging project you worked on recently.", "type": "behavioral"},
            {"text": "How do you stay updated with new technologies?", "type": "behavioral"},
            {"text": "Explain your understanding of object-oriented programming.", "type": "technical"},
        ]
        
        business_questions = [
            {"text": "Describe your experience with project management.", "type": "behavioral"},
            {"text": "How do you prioritize tasks when working on multiple projects?", "type": "situational"},
            {"text": "Tell me about a time you resolved a conflict in your team.", "type": "behavioral"},
            {"text": "What are your salary expectations?", "type": "general"},
            {"text": "Where do you see yourself in 5 years?", "type": "general"},
        ]
        
        # Return appropriate question set
        if category.lower() in ['tech', 'technology', 'it', 'software']:
            return tech_questions
        else:
            return business_questions


def get_question_generator():
    """Get singleton instance"""
    global _generator
    if '_generator' not in globals():
        _generator = QuestionGeneratorService()
    return _generator
```

## DEPLOYMENT INSTRUCTIONS

### Step 1: Activate Virtual Environment
```bash
cd /home/claude/vocal_view_project
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Step 3: PostgreSQL Setup
```sql
CREATE DATABASE vocalview_db;
CREATE USER vocalview_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE vocalview_db TO vocalview_user;
```

### Step 4: Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### Step 5: Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 6: Create Sample Data
```bash
python manage.py shell
```
```python
from interviews.models import JobRole

# Create sample job roles
JobRole.objects.create(
    role_name="Software Engineer",
    role_description="Backend development with Python/Django",
    role_category="Tech"
)
JobRole.objects.create(
    role_name="Data Scientist",
    role_description="Machine Learning and Analytics",
    role_category="Tech"
)
```

### Step 7: Create Superuser
```bash
python manage.py createsuperuser
```

### Step 8: Run Server
```bash
python manage.py runserver
```

## ARCHITECTURE SUMMARY

### Tech Stack
- **Backend**: Django 4.2
- **Database**: PostgreSQL
- **AI/ML**: Whisper, SpaCy, MediaPipe, Librosa
- **Frontend**: Django Templates + JavaScript

### AI Processing Pipeline

1. **Speech-to-Text** (Whisper)
   - Converts audio to text
   - Extracts word timestamps
   - Calculates speaking pace

2. **NLP Analysis** (SpaCy)
   - Filler word detection
   - Keyword matching
   - Grammar checking
   - Clarity scoring

3. **Facial Analysis** (MediaPipe)
   - Emotion detection
   - Confidence scoring
   - Stress level analysis

4. **Prosody Analysis** (Librosa)
   - Pitch analysis
   - Speaking pace
   - Pause detection
   - Volume consistency

### Database Schema
- 10 Models as per SRS Class Diagram
- Proper relationships and constraints
- JSON fields for timeline data

## NEXT STEPS FOR COMPLETE SYSTEM

1. Create HTML templates
2. Create JavaScript for recording
3. Create API endpoints
4. Implement PDF generation
5. Add real-time processing
6. Create admin dashboard
7. Add unit tests
8. Deploy to production server

## CONTACT
For questions or support, contact the development team.
