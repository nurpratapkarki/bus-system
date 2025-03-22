from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.forms.models import model_to_dict
from django.contrib.contenttypes.models import ContentType
from bus_management.models import Customer
from .models import Notification, NotificationPreference

def send_notification(recipient, notification_type, title, message, related_obj=None, device_id=None):
    """
    Send a notification to a user or customer
    
    Args:
        recipient: The recipient (User or Customer)
        notification_type: The type of notification (from Notification.NOTIFICATION_TYPES)
        title: The notification title
        message: The notification message
        related_obj: The related object (optional)
        device_id: Specific device to target (optional)
        
    Returns:
        The created Notification object
    """
    # Determine if the recipient is a User or Customer
    is_user = isinstance(recipient, User)
    is_customer = isinstance(recipient, Customer)
    
    if not (is_user or is_customer):
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Invalid recipient type for notification: {type(recipient)}")
        return None
    
    # Get ID for querying preferences
    recipient_id = recipient.id
    
    # Check if the recipient has notification preferences
    try:
        # Query based on recipient type
        if is_user:
            prefs = NotificationPreference.objects.get(user_id=recipient_id)
        else:
            prefs = NotificationPreference.objects.get(customer_id=recipient_id)
            
        # Check if the recipient wants this type of notification
        if notification_type.startswith('reservation_') and not prefs.reservation_notifications:
            return None
        elif notification_type.startswith('payment_') and not prefs.payment_notifications:
            return None
        elif notification_type == 'system' and not prefs.system_notifications:
            return None
            
        # Check if in-app notifications are enabled
        if not prefs.in_app_notifications:
            return None
    except NotificationPreference.DoesNotExist:
        # If no preferences exist, proceed with default values (all enabled)
        pass
    
    # Create notification object
    notification = Notification(
        notification_type=notification_type,
        title=title,
        message=message,
        device_id=device_id
    )
    
    # Set the appropriate recipient field
    if is_user:
        notification.user = recipient
    else:
        notification.customer = recipient
    
    # Add related object if provided
    if related_obj:
        content_type = ContentType.objects.get_for_model(related_obj)
        notification.content_type = content_type
        notification.object_id = related_obj.id
    
    # Save the notification
    notification.save()
    
    # Send the notification via WebSocket if needed
    _send_ws_notification(notification)
    
    return notification

def send_bulk_notifications(recipients, notification_type, title, message, related_obj=None):
    """
    Send the same notification to multiple recipients
    
    Args:
        recipients: List of User or Customer objects
        notification_type: The type of notification
        title: The notification title
        message: The notification message
        related_obj: The related object (optional)
    
    Returns:
        List of created Notification objects
    """
    notifications = []
    
    for recipient in recipients:
        notification = send_notification(recipient, notification_type, title, message, related_obj)
        if notification:
            notifications.append(notification)
    
    return notifications

def _send_ws_notification(notification):
    """
    Send a notification to a recipient via WebSocket
    
    Args:
        notification: The Notification object
    """
    # Convert to dictionary
    notification_dict = model_to_dict(
        notification, 
        exclude=['user', 'customer', 'content_type', 'object_id']
    )
    notification_dict['created_at'] = notification.created_at.isoformat()
    
    # Get the channel layer
    channel_layer = get_channel_layer()
    
    # Determine user ID for the group name
    if notification.user:
        group_name = f'notifications_{notification.user.id}'
    else:
        group_name = f'customer_notifications_{notification.customer.id}'
    
    # Send the notification to the recipient's group
    try:
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': notification_dict
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error sending notification via WebSocket: {str(e)}")

def mark_notification_read(notification_id, recipient):
    """
    Mark a notification as read
    
    Args:
        notification_id: The notification ID
        recipient: The user or customer who owns the notification
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create base query
        query = Notification.objects.filter(id=notification_id)
        
        # Add filter based on recipient type
        if isinstance(recipient, User):
            query = query.filter(user=recipient)
        else:
            query = query.filter(customer=recipient)
            
        notification = query.get()
        notification.mark_as_read()
        return True
    except Notification.DoesNotExist:
        return False

def mark_all_read(recipient):
    """
    Mark all notifications as read for a recipient
    
    Args:
        recipient: The user or customer
    """
    # Create base query
    query = Notification.objects.filter(is_read=False)
    
    # Add filter based on recipient type
    if isinstance(recipient, User):
        query = query.filter(user=recipient)
    else:
        query = query.filter(customer=recipient)
        
    query.update(is_read=True)

def get_unread_count(recipient):
    """
    Get the count of unread notifications for a recipient
    
    Args:
        recipient: The user or customer
        
    Returns:
        The count of unread notifications
    """
    # Create base query
    query = Notification.objects.filter(is_read=False)
    
    # Add filter based on recipient type
    if isinstance(recipient, User):
        query = query.filter(user=recipient)
    else:
        query = query.filter(customer=recipient)
        
    return query.count()

def delete_old_notifications(days=30):
    """
    Delete notifications older than the specified number of days
    
    Args:
        days: The number of days (default: 30)
    """
    from django.utils import timezone
    import datetime
    
    cutoff_date = timezone.now() - datetime.timedelta(days=days)
    
    Notification.objects.filter(created_at__lt=cutoff_date).delete()