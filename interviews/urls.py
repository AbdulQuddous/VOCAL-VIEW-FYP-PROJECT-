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
    path('export/pdf/<uuid:session_id>/', views.export_report_pdf, name='api_export_pdf'),

     # Profile & Settings
    path('profile/', views.user_profile, name='user_profile'),
    path('settings/', views.user_settings, name='user_settings'),
    path('interview/delete/<uuid:session_id>/', views.delete_interview, name='delete_interview'),

     # Password Reset
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-code/', views.verify_reset_code, name='verify_reset_code'),
    path('reset-password/', views.reset_password, name='reset_password'),
]