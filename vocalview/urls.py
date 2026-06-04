"""
Main URL Configuration for Vocal View
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),
    
    # Main application URLs
    path('', include('interviews.urls')),
    
    # API endpoints
    path('api/', include('interviews.api_urls')),
    
    # Redirect root to dashboard or login
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "Vocal View Administration"
admin.site.site_title = "Vocal View Admin"
admin.site.index_title = "Welcome to Vocal View Administration"
