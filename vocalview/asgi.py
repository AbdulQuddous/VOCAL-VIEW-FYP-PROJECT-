"""
ASGI config for vocalview project.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vocalview.settings')

application = get_asgi_application()
