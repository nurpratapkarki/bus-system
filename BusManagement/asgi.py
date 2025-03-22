"""
ASGI config for BusManagement project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BusManagement.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import bus_management.routing
import notifications.routing

# Initialize Django ASGI application
django_asgi_app = get_asgi_application()

# Combine WebSocket URL patterns from different apps
websocket_urlpatterns = bus_management.routing.websocket_urlpatterns + notifications.routing.websocket_urlpatterns

# Configure the ASGI application with both HTTP and WebSocket support
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
