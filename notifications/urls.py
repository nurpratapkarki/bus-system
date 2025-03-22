from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'preferences', views.NotificationPreferenceViewSet, basename='preference')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Dashboard view - renamed to app_dashboard to avoid conflict
    path('dashboard/', views.notification_dashboard, name='app_dashboard'),
] 