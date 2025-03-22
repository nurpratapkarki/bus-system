import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async
from bus_management.models import Customer

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumer for handling WebSocket connections for real-time notifications
    """
    async def connect(self):
        """
        Called when a WebSocket connection is established
        """
        # Get the user from the scope
        self.user = self.scope.get('user')
        self.customer_id = self.scope.get('customer_id')
        
        # Set the recipient type
        if not self.user.is_anonymous:
            self.recipient_type = 'user'
            self.recipient_id = self.user.id
            self.group_name = f'notifications_{self.user.id}'
        elif self.customer_id:
            self.recipient_type = 'customer'
            self.recipient_id = self.customer_id
            self.group_name = f'customer_notifications_{self.customer_id}'
        else:
            # Anonymous users without customer ID cannot receive notifications
            await self.close()
            return
        
        # Device ID could be passed as a query parameter
        self.device_id = None
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        if query_string:
            params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
            self.device_id = params.get('device_id')
        
        # Add the connection to the user's group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the connection
        await self.accept()
        
        # Send any unread notifications
        await self.send_unread_notifications()
        
    async def disconnect(self, close_code):
        """
        Called when the WebSocket closes
        """
        # Remove the connection from the user's group
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """
        Called when data is received from the WebSocket
        """
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'mark_read':
                notification_id = data.get('notification_id')
                if notification_id:
                    await self.mark_notification_read(notification_id)
                    await self.send(text_data=json.dumps({
                        'status': 'success',
                        'action': 'mark_read',
                        'notification_id': notification_id
                    }))
            
            elif action == 'mark_all_read':
                await self.mark_all_notifications_read()
                await self.send(text_data=json.dumps({
                    'status': 'success',
                    'action': 'mark_all_read'
                }))
            
            elif action == 'get_unread':
                await self.send_unread_notifications()
        
        except Exception as e:
            await self.send(text_data=json.dumps({
                'status': 'error',
                'message': str(e)
            }))
    
    async def notification_message(self, event):
        """
        Called when a notification is sent to the user's group
        """
        notification = event.get('notification')
        
        # Only send the notification if it's for this device or all devices
        device_id = notification.get('device_id')
        if not device_id or not self.device_id or device_id == self.device_id:
            # Forward the notification to the WebSocket
            await self.send(text_data=json.dumps(notification))
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """
        Mark a notification as read
        """
        from .models import Notification
        try:
            # Create base query
            query = Notification.objects.filter(id=notification_id)
            
            # Add appropriate filter based on recipient type
            if self.recipient_type == 'user':
                query = query.filter(user_id=self.recipient_id)
            else:
                query = query.filter(customer_id=self.recipient_id)
                
            notification = query.get()
            notification.mark_as_read()
            return True
        except Notification.DoesNotExist:
            return False
    
    @database_sync_to_async
    def mark_all_notifications_read(self):
        """
        Mark all notifications as read for this recipient
        """
        from .models import Notification
        
        # Create base query
        query = Notification.objects.filter(is_read=False)
        
        # Add appropriate filter based on recipient type
        if self.recipient_type == 'user':
            query = query.filter(user_id=self.recipient_id)
        else:
            query = query.filter(customer_id=self.recipient_id)
            
        query.update(is_read=True)
    
    @database_sync_to_async
    def get_unread_notifications(self):
        """
        Get all unread notifications for this recipient
        """
        from .models import Notification
        from django.forms.models import model_to_dict
        
        # Create base query
        query = Notification.objects.filter(is_read=False)
        
        # Add appropriate filter based on recipient type
        if self.recipient_type == 'user':
            query = query.filter(user_id=self.recipient_id)
        else:
            query = query.filter(customer_id=self.recipient_id)
            
        notifications = query.order_by('-created_at')
        
        result = []
        for notification in notifications:
            notification_dict = model_to_dict(
                notification, 
                exclude=['user', 'customer', 'content_type', 'object_id']
            )
            notification_dict['created_at'] = notification.created_at.isoformat()
            result.append(notification_dict)
        
        return result
    
    async def send_unread_notifications(self):
        """
        Send all unread notifications to the WebSocket
        """
        notifications = await self.get_unread_notifications()
        await self.send(text_data=json.dumps({
            'type': 'unread_notifications',
            'notifications': notifications
        })) 