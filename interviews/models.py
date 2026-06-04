from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
import uuid
import random
import string
from datetime import timedelta

class JobRole(models.Model):
    role_id = models.AutoField(primary_key=True)
    role_name = models.CharField(max_length=200, unique=True)
    role_description = models.TextField()
    role_category = models.CharField(max_length=100)  # Tech, Business, Healthcare, etc.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'job_roles'
        ordering = ['role_category', 'role_name']
    
    def __str__(self):
        return f"{self.role_name} ({self.role_category})"


class Question(models.Model):
    """
    Question model - stores interview questions
    """
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    question_id = models.AutoField(primary_key=True)
    session = models.ForeignKey('InterviewSession', on_delete=models.CASCADE, related_name='questions', null=True)
    question_text = models.TextField()
    question_type = models.CharField(max_length=50)  # Technical, Behavioral, Situational
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='medium')
    expected_keywords = models.JSONField(default=list)  # List of keywords expected in answer
    expected_answer = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'questions'
        ordering = ['question_id']
    
    def __str__(self):
        return f"Q{self.question_id}: {self.question_text[:50]}..."


class InterviewSession(models.Model):
    """
    Interview Session model - represents a complete interview
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interview_sessions')
    job_role = models.ForeignKey(JobRole, on_delete=models.SET_NULL, null=True)
    
    # Timestamps
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Settings
    max_duration_minutes = models.IntegerField(default=15)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'interview_sessions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Interview {self.session_id} - {self.user.username} - {self.job_role}"
    
    def start_interview(self):
        """Start the interview session"""
        self.status = 'in_progress'
        self.start_time = timezone.now()
        self.save()
    
    def end_interview(self):
        """End the interview session"""
        self.status = 'completed'
        self.end_time = timezone.now()
        self.save()
    
    @property
    def duration_minutes(self):
        """Calculate interview duration in minutes"""
        if self.end_time and self.start_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() / 60
        return 0


class Answer(models.Model):
    """
    Answer model - stores user's answers to questions
    """
    answer_id = models.AutoField(primary_key=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name='answers')
    
    # Answer content
    transcribed_text = models.TextField()
    
    # Media files
    audio_file = models.FileField(upload_to='interviews/audio/%Y/%m/%d/', null=True, blank=True)
    video_file = models.FileField(upload_to='interviews/video/%Y/%m/%d/', null=True, blank=True)
    
    # Timing
    duration = models.FloatField(help_text="Duration in seconds")
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    # Processing status
    is_processed = models.BooleanField(default=False)

    content_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        help_text="Legacy content score (now keyword_relevance_score)"
    )
    
    # === SCORING FIELDS ===
    
    semantic_similarity_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Semantic similarity score (0-100)"
    )
    
    keyword_relevance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Keyword relevance score (0-100)"
    )
    
    completeness_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Answer completeness score (0-100)"
    )
    
    # Final weighted score
    final_content_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Final weighted content score (0-100)"
    )
    
    # Detailed breakdown stored as JSON
    score_breakdown = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detailed scoring breakdown with weights and contributions"
    )
    
    # Detected keywords
    detected_keywords = models.JSONField(
        default=list,
        blank=True,
        help_text="Keywords detected in answer"
    )
    
    class Meta:
        db_table = 'answers'
        ordering = ['question__question_id']
    
    def __str__(self):
        return f"Answer to Q{self.question.question_id} by {self.session.user.username}"


class ContentAnalysis(models.Model):
    analysis_id = models.AutoField(primary_key=True)
    answer = models.OneToOneField(Answer, on_delete=models.CASCADE, related_name='content_analysis')
    
    # Scores (0-100)
    relevance_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    clarity_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Analysis details
    filler_word_count = models.IntegerField(default=0)
    keyword_matches = models.JSONField(default=list)  # List of matched keywords
    grammar_issues = models.JSONField(default=list)   # List of grammar issues
    improvement_tips = models.TextField()
    
    # Word statistics
    word_count = models.IntegerField(default=0)
    unique_word_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'content_analysis'
    
    def __str__(self):
        return f"Content Analysis for Answer {self.answer.answer_id}"


class FacialAnalysis(models.Model):
    analysis_id = models.AutoField(primary_key=True)
    answer = models.OneToOneField(Answer, on_delete=models.CASCADE, related_name='facial_analysis')
    
    # Confidence and stress scores (0-100)
    confidence_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    stress_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Dominant emotion throughout the answer
    dominant_emotion = models.CharField(max_length=50)  # happy, neutral, stressed, confident, etc.
    
    # Timeline data (JSON with timestamps and values)
    emotion_timeline = models.JSONField(default=dict)
    
    # Eye contact and posture metrics
    eye_contact_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'facial_analysis'
    
    def __str__(self):
        return f"Facial Analysis for Answer {self.answer.answer_id}"


class ProsodyAnalysis(models.Model):
    analysis_id = models.AutoField(primary_key=True)
    answer = models.OneToOneField(Answer, on_delete=models.CASCADE, related_name='prosody_analysis')
    
    # Speech metrics
    speaking_pace_wpm = models.FloatField(help_text="Words per minute")
    average_pitch_hz = models.FloatField(help_text="Average pitch in Hz")
    pitch_variation = models.FloatField(help_text="Pitch variation coefficient")
    volume_consistency = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # NEW: Energy and vocal metrics
    energy_stability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Energy stability score (0-100)"
    )
    
    vocal_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Vocal confidence score (0-100)"
    )
    
    # Pause analysis
    pause_count = models.IntegerField(default=0)
    average_pause_duration = models.FloatField(help_text="Average pause duration in seconds")
    
    # NEW: Detailed pause types
    natural_pauses = models.IntegerField(default=0, help_text="Natural pauses (<1 second)")
    hesitation_pauses = models.IntegerField(default=0, help_text="Hesitation pauses (1-2 seconds)")
    long_pauses = models.IntegerField(default=0, help_text="Long pauses (>2 seconds)")
    
    # NEW: Duration metrics
    speech_duration = models.FloatField(null=True, blank=True, help_text="Actual speech duration in seconds")
    audio_duration = models.FloatField(null=True, blank=True, help_text="Total audio duration in seconds")
    
    # Timeline data
    pace_timeline = models.JSONField(default=dict)
    pitch_timeline = models.JSONField(default=dict)
    
    # NEW: Energy timeline
    energy_timeline = models.JSONField(default=dict, help_text="Energy timeline data")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'prosody_analysis'
    
    def __str__(self):
        return f"Prosody Analysis for Answer {self.answer.answer_id}"


class EmotionTimeline(models.Model):
    timeline_id = models.AutoField(primary_key=True)
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name='emotion_timelines')
    
    # Timeline data points
    timestamp = models.DateTimeField()
    confidence_value = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    stress_value = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    class Meta:
        db_table = 'emotion_timeline'
        ordering = ['timestamp']
    
    def __str__(self):
        return f"Timeline point for session {self.session.session_id} at {self.timestamp}"


class FeedbackReport(models.Model):
    report_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(InterviewSession, on_delete=models.CASCADE, related_name='feedback_report')
    
    # Overall scores (0-100)
    overall_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Component scores
    content_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    delivery_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    confidence_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Feedback text
    summary_feedback = models.TextField()
    strengths = models.JSONField(default=list)
    areas_for_improvement = models.JSONField(default=list)
    
    # Detailed analysis
    detailed_analysis = models.JSONField(default=dict)
    
    # Report files
    pdf_report = models.FileField(upload_to='reports/pdf/%Y/%m/%d/', null=True, blank=True)
    json_report = models.FileField(upload_to='reports/json/%Y/%m/%d/', null=True, blank=True)
    
    # Timestamps
    generated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'feedback_reports'
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"Feedback Report for {self.session.user.username} - Score: {self.overall_score}"
    
    def generate_report(self):
        """Generate the comprehensive feedback report"""
        # This will be implemented in the service layer
        pass
    
    def export_to_pdf(self):
        """Export report to PDF format"""
        # This will be implemented in the service layer
        pass


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Personal information
    full_name = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    
    # Career information
    target_role = models.ForeignKey(JobRole, on_delete=models.SET_NULL, null=True, blank=True)
    experience_level = models.CharField(
        max_length=20,
        choices=[
            ('entry', 'Entry Level'),
            ('intermediate', 'Intermediate'),
            ('senior', 'Senior'),
            ('expert', 'Expert'),
        ],
        default='entry'
    )
    
    # Statistics
    total_interviews = models.IntegerField(default=0)
    average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Preferences
    preferred_interview_duration = models.IntegerField(default=15, help_text="Duration in minutes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
    
    def __str__(self):
        return f"Profile: {self.user.username}"
    
    def update_statistics(self):
        """Update user statistics after completing an interview"""
        completed_sessions = InterviewSession.objects.filter(
            user=self.user,
            status='completed'
        )
        self.total_interviews = completed_sessions.count()
        
        if self.total_interviews > 0:
            reports = FeedbackReport.objects.filter(session__user=self.user)
            if reports.exists():
                from django.db.models import Avg
                avg_score = reports.aggregate(Avg('overall_score'))['overall_score__avg']
                self.average_score = avg_score or 0
        
        self.save()


class PasswordResetToken(models.Model):
    """Password reset token model"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=6)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'password_reset_tokens'
    
    @staticmethod
    def generate_token():
        """Generate a 6-digit numeric token"""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_valid(self):
        """Check if token is still valid (10 minutes)"""
        if self.is_used:
            return False
        expiry_time = self.created_at + timedelta(minutes=10)
        return timezone.now() < expiry_time
    
    def __str__(self):
        return f"Reset token for {self.user.username}"