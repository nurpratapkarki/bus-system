"""
URL configuration for BusManagement project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from . import api

# Simple dashboard view
@login_required
def dashboard_view(request):
    """
    Renders the dashboard template with admin context
    """
    from django.contrib.admin.sites import site
    
    context = {
        'title': 'Dashboard',
        'site_title': settings.JAZZMIN_SETTINGS.get('site_title', 'Bus Management Admin'),
        'site_header': settings.JAZZMIN_SETTINGS.get('site_header', 'Bus Management'),
        'site_url': '/',
        'has_permission': request.user.is_staff,
        'available_apps': site.get_app_list(request),
        'is_popup': False,
        'is_nav_sidebar_enabled': True,
        'user': request.user,
    }
    return render(request, 'dashboard/dashboard.html', context)

# Swagger documentation setup
schema_view = get_schema_view(
   openapi.Info(
      title="Bus Management API",
      default_version='v1',
      description="API for a bus ticketing system with regular and special reservations",
      terms_of_service="https://www.busmanagement.com/terms/",
      contact=openapi.Contact(email="contact@busmanagement.com"),
      license=openapi.License(name="MIT License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # Dashboard must come before admin to prevent admin catch-all from capturing it
    path('dashboard/', dashboard_view, name='admin_dashboard'),
    
    # New unified API endpoints
    path('api/v1/dashboard/', api.dashboard_data, name='api_dashboard'),
    path('api/v1/dashboard/charts/', api.dashboard_charts, name='api_dashboard_charts'),  
    path('api/v1/notifications/', api.notifications_data, name='api_notifications'),
    
    # Admin URLs
    path('', admin.site.urls),
    
    # Include app URLs
    path('', include('bus_management.urls')),  # Include the bus_management URLs
    path('notifications/', include('notifications.urls')),  # Include the notifications URLs
    
    # API documentation with Swagger
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
