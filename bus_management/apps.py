from django.apps import AppConfig


class BusManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bus_management'
    
    def ready(self):
        """Import signals when the app is ready"""
        import bus_management.signals
