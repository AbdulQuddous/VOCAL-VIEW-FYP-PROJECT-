"""
API URL Configuration for Interview Processing
"""
from django.urls import path
from . import views

urlpatterns = [
    # Interview APIs
    path('save-answer/<uuid:session_id>/', views.save_answer, name='api_save_answer'),
    path('complete-interview/<uuid:session_id>/', views.complete_interview, name='api_complete_interview'),
    
    # Export APIs
    path('export/json/<uuid:session_id>/', views.export_report_json, name='api_export_json'),
    path('export/pdf/<uuid:session_id>/', views.export_report_pdf, name='api_export_pdf'),
]
