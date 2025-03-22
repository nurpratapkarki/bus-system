from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from bus_management.models import Customer

class Notification(models.Model):
    """
    A model for storing notifications sent to users
    """
    NOTIFICATION_TYPES = (
        ('reservation_created', 'Reservation Created'),
        ('reservation_approved', 'Reservation Approved'),
        ('reservation_rejected', 'Reservation Rejected'),
        ('payment_received', 'Payment Received'),
        ('reservation_completed', 'Reservation Completed'),
        ('schedule_conflict', 'Schedule Conflict'),
        ('vehicle_maintenance', 'Vehicle Maintenance'),
        ('system', 'System Message'),
    )
    
    # Recipient fields - can be either a User or a Customer
    # We use nullable ForeignKeys and enforce in clean() that one recipient type must be set
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # GenericForeignKey to the related object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # For targeting specific devices (e.g., mobile app, web browser)
    device_id = models.CharField(max_length=255, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['customer', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        recipient = self.user.username if self.user else self.customer.username if self.customer else "Unknown"
        return f"{self.notification_type} to {recipient}: {self.title}"
    
    def clean(self):
        """Ensure that either user or customer is set, but not both"""
        from django.core.exceptions import ValidationError
        if not self.user and not self.customer:
            raise ValidationError("Either user or customer must be set")
        if self.user and self.customer:
            raise ValidationError("Only one of user or customer can be set")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def mark_as_read(self):
        """Mark the notification as read"""
        self.is_read = True
        self.save(update_fields=['is_read'])
    
    @property
    def recipient(self):
        """
        Return the recipient, regardless of whether it's a User or Customer
        This simplifies use in templates and services
        """
        return self.user or self.customer

class NotificationPreference(models.Model):
    """
    User preferences for notification delivery
    """
    # Allow setting preferences for either User or Customer
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences', null=True, blank=True)
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name='notification_preferences', null=True, blank=True)
    
    # Email notification preferences
    email_notifications = models.BooleanField(default=True)
    
    # Push notification preferences (for mobile apps)
    push_notifications = models.BooleanField(default=True)
    
    # In-app notification preferences
    in_app_notifications = models.BooleanField(default=True)
    
    # Specific notification types to enable/disable
    reservation_notifications = models.BooleanField(default=True)
    payment_notifications = models.BooleanField(default=True)
    system_notifications = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"
    
    def __str__(self):
        recipient = self.user.username if self.user else self.customer.username if self.customer else "Unknown"
        return f"Notification preferences for {recipient}"
    
    def clean(self):
        """Ensure that either user or customer is set, but not both"""
        from django.core.exceptions import ValidationError
        if not self.user and not self.customer:
            raise ValidationError("Either user or customer must be set")
        if self.user and self.customer:
            raise ValidationError("Only one of user or customer can be set")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
