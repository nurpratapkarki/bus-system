from django.contrib import admin
from .models import Notification, NotificationPreference

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'notification_type', 'recipient', 'created_at', 'is_read')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'recipient__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    
    fieldsets = (
        (None, {
            'fields': ('recipient', 'notification_type', 'title', 'message')
        }),
        ('Status', {
            'fields': ('is_read', 'created_at')
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Device Information', {
            'fields': ('device_id',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Notifications should typically be created programmatically, not manually
        return False

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_notifications', 'push_notifications', 'in_app_notifications')
    list_filter = ('email_notifications', 'push_notifications', 'in_app_notifications')
    search_fields = ('user__username', 'user__email')
    
    fieldsets = (
        (None, {
            'fields': ('user',)
        }),
        ('Notification Channels', {
            'fields': ('email_notifications', 'push_notifications', 'in_app_notifications'),
        }),
        ('Notification Types', {
            'fields': ('reservation_notifications', 'payment_notifications', 'system_notifications'),
        }),
    )
