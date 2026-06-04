# interviews/admin.py

from django.contrib import admin
from .models import (
    JobRole,
    Question,
    InterviewSession,
    Answer,
    ContentAnalysis,
    FacialAnalysis,
    ProsodyAnalysis,
    EmotionTimeline,
    FeedbackReport,
    UserProfile,
    PasswordResetToken
)

# =========================================================
# JOB ROLE ADMIN
# =========================================================
@admin.register(JobRole)
class JobRoleAdmin(admin.ModelAdmin):
    list_display = (
        'role_id',
        'role_name',
        'role_category',
        'created_at',
    )

    search_fields = (
        'role_name',
        'role_category',
        'role_description',
    )

    list_filter = (
        'role_category',
        'created_at',
    )

    ordering = (
        'role_category',
        'role_name',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
    )

    list_per_page = 25


# =========================================================
# QUESTION ADMIN
# =========================================================
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = (
        'question_id',
        'short_question',
        'question_type',
        'difficulty',
        'session',
        'created_at',
    )

    search_fields = (
        'question_text',
        'question_type',
        'expected_answer',
        'session__user__username',
        'session__job_role__role_name',
    )

    list_filter = (
        'difficulty',
        'question_type',
        'created_at',
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'created_at',
    )

    list_per_page = 25

    def short_question(self, obj):
        return obj.question_text[:80]

    short_question.short_description = "Question"


# =========================================================
# INTERVIEW SESSION ADMIN
# =========================================================
@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = (
        'short_session_id',
        'user',
        'job_role',
        'status',
        'max_duration_minutes',
        'start_time',
        'end_time',
        'created_at',
    )

    search_fields = (
        'session_id',
        'user__username',
        'user__email',
        'job_role__role_name',
    )

    list_filter = (
        'status',
        'job_role',
        'created_at',
        'start_time',
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'session_id',
        'created_at',
        'updated_at',
        'duration_minutes',
    )

    list_per_page = 25

    def short_session_id(self, obj):
        return str(obj.session_id)[:8]

    short_session_id.short_description = "Session ID"


# =========================================================
# ANSWER ADMIN
# =========================================================
@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = (
        'answer_id',
        'question',
        'session_user',
        'duration',
        'semantic_similarity_score',
        'keyword_relevance_score',
        'final_content_score',
        'is_processed',
        'recorded_at',
    )

    search_fields = (
        'transcribed_text',
        'question__question_text',
        'session__user__username',
        'session__job_role__role_name',
    )

    list_filter = (
        'is_processed',
        'recorded_at',
        'question__difficulty',
        'session__job_role',
    )

    ordering = ('-recorded_at',)

    readonly_fields = (
        'recorded_at',
    )

    list_per_page = 20

    def session_user(self, obj):
        return obj.session.user.username

    session_user.short_description = "User"


# =========================================================
# CONTENT ANALYSIS ADMIN
# =========================================================
@admin.register(ContentAnalysis)
class ContentAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        'analysis_id',
        'answer',
        'relevance_score',
        'clarity_score',
        'word_count',
        'filler_word_count',
        'created_at',
    )

    search_fields = (
        'answer__transcribed_text',
        'answer__session__user__username',
    )

    list_filter = (
        'created_at',
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'created_at',
    )

    list_per_page = 25


# =========================================================
# FACIAL ANALYSIS ADMIN
# =========================================================
@admin.register(FacialAnalysis)
class FacialAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        'analysis_id',
        'answer',
        'confidence_score',
        'stress_score',
        'eye_contact_score',
        'dominant_emotion',
        'created_at',
    )

    search_fields = (
        'dominant_emotion',
        'answer__session__user__username',
    )

    list_filter = (
        'dominant_emotion',
        'created_at',
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'created_at',
    )

    list_per_page = 25


# =========================================================
# PROSODY ANALYSIS ADMIN
# =========================================================
@admin.register(ProsodyAnalysis)
class ProsodyAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        'analysis_id',
        'answer',
        'speaking_pace_wpm',
        'average_pitch_hz',
        'pitch_variation',
        'pause_count',
        'created_at',
    )

    search_fields = (
        'answer__session__user__username',
    )

    list_filter = (
        'created_at',
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'created_at',
    )

    list_per_page = 25


# =========================================================
# EMOTION TIMELINE ADMIN
# =========================================================
@admin.register(EmotionTimeline)
class EmotionTimelineAdmin(admin.ModelAdmin):
    list_display = (
        'timeline_id',
        'session',
        'confidence_value',
        'stress_value',
        'timestamp',
    )

    search_fields = (
        'session__user__username',
        'session__job_role__role_name',
    )

    list_filter = (
        'timestamp',
    )

    ordering = ('-timestamp',)

    list_per_page = 25


# =========================================================
# FEEDBACK REPORT ADMIN
# =========================================================
@admin.register(FeedbackReport)
class FeedbackReportAdmin(admin.ModelAdmin):
    list_display = (
        'short_report_id',
        'session',
        'overall_score',
        'content_score',
        'delivery_score',
        'confidence_score',
        'generated_at',
    )

    search_fields = (
        'session__user__username',
        'session__job_role__role_name',
        'summary_feedback',
    )

    list_filter = (
        'generated_at',
    )

    ordering = ('-generated_at',)

    readonly_fields = (
        'report_id',
        'generated_at',
    )

    list_per_page = 25

    def short_report_id(self, obj):
        return str(obj.report_id)[:8]

    short_report_id.short_description = "Report ID"


# =========================================================
# USER PROFILE ADMIN
# =========================================================
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'full_name',
        'target_role',
        'experience_level',
        'total_interviews',
        'average_score',
        'created_at',
    )

    search_fields = (
        'user__username',
        'user__email',
        'full_name',
        'phone_number',
    )

    list_filter = (
        'experience_level',
        'target_role',
        'created_at',
    )

    ordering = ('-average_score',)

    readonly_fields = (
        'created_at',
        'updated_at',
    )

    list_per_page = 25


# =========================================================
# PASSWORD RESET TOKEN ADMIN
# =========================================================
@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'email',
        'token',
        'is_used',
        'created_at',
    )

    search_fields = (
        'user__username',
        'email',
        'token',
    )

    list_filter = (
        'is_used',
        'created_at',
    )

    ordering = ('-created_at',)

    readonly_fields = (
        'created_at',
    )

    list_per_page = 25


# =========================================================
# ADMIN PANEL CUSTOMIZATION
# =========================================================
admin.site.site_header = "Vocal View Administration"
admin.site.site_title = "Vocal View Admin"
admin.site.index_title = "AI Interview System"