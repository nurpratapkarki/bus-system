from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required
from .models import Notification, NotificationPreference
from .services import mark_notification_read, mark_all_read, get_unread_count
from bus_management.models import Customer, Vehicle, Schedule, SpecialReservation
from django.db.models import Sum, Count, Q
from django.utils import timezone
import datetime

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API for managing user notifications
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get notifications for the authenticated user or customer"""
        request = self.request
        
        # Determine the recipient type
        if hasattr(request, 'user') and not request.user.is_anonymous:
            # This is a standard Django User
            return Notification.objects.filter(user=request.user).order_by('-created_at')
        elif hasattr(request.auth, 'payload') and request.auth.payload.get('customer_id'):
            # This is a Customer using JWT token
            customer_id = request.auth.payload.get('customer_id')
            return Notification.objects.filter(customer_id=customer_id).order_by('-created_at')
        else:
            # No valid recipient found
            return Notification.objects.none()
    
    def list(self, request):
        """Get all notifications for the current user or customer"""
        queryset = self.get_queryset()
        
        # Optional filter for unread notifications
        unread_only = request.query_params.get('unread', False)
        if unread_only and unread_only.lower() == 'true':
            queryset = queryset.filter(is_read=False)
        
        # Simple serialization for performance
        notifications = []
        for notification in queryset:
            notifications.append({
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat() if notification.created_at else None,
                'related_object_id': str(notification.related_object_id) if notification.related_object_id else None,
                'related_object_type': notification.related_object_type,
            })
            
        # Add CORS headers to allow requests from the dashboard page
        response = Response(notifications)
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, X-CSRFToken"
        return response
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a notification as read"""
        # Determine the recipient
        if hasattr(request, 'user') and not request.user.is_anonymous:
            recipient = request.user
        elif hasattr(request.auth, 'payload') and request.auth.payload.get('customer_id'):
            customer_id = request.auth.payload.get('customer_id')
            try:
                recipient = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return Response(
                    {'error': 'Customer not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {'error': 'No valid recipient found'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        success = mark_notification_read(pk, recipient)
        
        if success:
            return Response({'status': 'notification marked as read'})
        else:
            return Response(
                {'error': 'Notification not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        # Determine the recipient
        if hasattr(request, 'user') and not request.user.is_anonymous:
            recipient = request.user
        elif hasattr(request.auth, 'payload') and request.auth.payload.get('customer_id'):
            customer_id = request.auth.payload.get('customer_id')
            try:
                recipient = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return Response(
                    {'error': 'Customer not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {'error': 'No valid recipient found'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        mark_all_read(recipient)
        return Response({'status': 'all notifications marked as read'})

class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    """
    API for managing notification preferences
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get preferences for the authenticated user or customer"""
        request = self.request
        
        # Determine the recipient type
        if hasattr(request, 'user') and not request.user.is_anonymous:
            # This is a standard Django User
            return NotificationPreference.objects.filter(user=request.user)
        elif hasattr(request.auth, 'payload') and request.auth.payload.get('customer_id'):
            # This is a Customer using JWT token
            customer_id = request.auth.payload.get('customer_id')
            return NotificationPreference.objects.filter(customer_id=customer_id)
        else:
            # No valid recipient found
            return NotificationPreference.objects.none()
    
    def list(self, request):
        """Get notification preferences for the current user or customer"""
        # Determine the recipient type and ID
        if hasattr(request, 'user') and not request.user.is_anonymous:
            # This is a standard Django User
            recipient_type = 'user'
            recipient_id = request.user.id
            recipient_obj = request.user
        elif hasattr(request.auth, 'payload') and request.auth.payload.get('customer_id'):
            # This is a Customer using JWT token
            recipient_type = 'customer'
            recipient_id = request.auth.payload.get('customer_id')
            try:
                recipient_obj = Customer.objects.get(id=recipient_id)
            except Customer.DoesNotExist:
                return Response(
                    {'error': 'Customer not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {'error': 'No valid recipient found'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Try to get existing preferences
        try:
            if recipient_type == 'user':
                pref = NotificationPreference.objects.get(user=recipient_obj)
            else:
                pref = NotificationPreference.objects.get(customer=recipient_obj)
                
            return Response({
                'email_notifications': pref.email_notifications,
                'push_notifications': pref.push_notifications,
                'in_app_notifications': pref.in_app_notifications,
                'reservation_notifications': pref.reservation_notifications,
                'payment_notifications': pref.payment_notifications,
                'system_notifications': pref.system_notifications,
            })
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            pref = NotificationPreference()
            if recipient_type == 'user':
                pref.user = recipient_obj
            else:
                pref.customer = recipient_obj
            pref.save()
            
            return Response({
                'email_notifications': True,
                'push_notifications': True,
                'in_app_notifications': True,
                'reservation_notifications': True,
                'payment_notifications': True,
                'system_notifications': True,
            })
    
    def update(self, request, pk=None):
        """Update notification preferences"""
        # Determine the recipient type and ID
        if hasattr(request, 'user') and not request.user.is_anonymous:
            # This is a standard Django User
            recipient_type = 'user'
            recipient_obj = request.user
        elif hasattr(request.auth, 'payload') and request.auth.payload.get('customer_id'):
            # This is a Customer using JWT token
            recipient_type = 'customer'
            recipient_id = request.auth.payload.get('customer_id')
            try:
                recipient_obj = Customer.objects.get(id=recipient_id)
            except Customer.DoesNotExist:
                return Response(
                    {'error': 'Customer not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {'error': 'No valid recipient found'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Try to get existing preferences or create new ones
        try:
            if recipient_type == 'user':
                pref = NotificationPreference.objects.get(user=recipient_obj)
            else:
                pref = NotificationPreference.objects.get(customer=recipient_obj)
        except NotificationPreference.DoesNotExist:
            pref = NotificationPreference()
            if recipient_type == 'user':
                pref.user = recipient_obj
            else:
                pref.customer = recipient_obj
        
        # Update the preferences
        pref.email_notifications = request.data.get('email_notifications', pref.email_notifications)
        pref.push_notifications = request.data.get('push_notifications', pref.push_notifications)
        pref.in_app_notifications = request.data.get('in_app_notifications', pref.in_app_notifications)
        pref.reservation_notifications = request.data.get('reservation_notifications', pref.reservation_notifications)
        pref.payment_notifications = request.data.get('payment_notifications', pref.payment_notifications)
        pref.system_notifications = request.data.get('system_notifications', pref.system_notifications)
        
        pref.save()
        
        return Response({
            'email_notifications': pref.email_notifications,
            'push_notifications': pref.push_notifications,
            'in_app_notifications': pref.in_app_notifications,
            'reservation_notifications': pref.reservation_notifications,
            'payment_notifications': pref.payment_notifications,
            'system_notifications': pref.system_notifications,
        })

@login_required
def notification_dashboard(request):
    """
    Admin dashboard with real-time notifications and key business metrics
    Provides a comprehensive overview of the system status
    """
    # Get current date
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    # Basic statistics
    context = {
        'unread_count': get_unread_count(request.user),
        'active_vehicles': Vehicle.objects.filter(is_active=True).count(),
        'total_vehicles': Vehicle.objects.count(),
        'total_customers': Customer.objects.count(),
        'today_schedules': Schedule.objects.filter(
            start_time__date=today,
            is_active=True
        ).count(),
        'pending_reservations': SpecialReservation.objects.filter(
            status='pending'
        ).count(),
    }
    
    # Try to get financial data
    try:
        monthly_revenue = SpecialReservation.objects.filter(
            deposit_paid_date__gte=month_start,
            status__in=['approved', 'completed']
        ).aggregate(
            total=Sum('deposit_amount')
        )['total'] or 0
        
        context['monthly_revenue'] = monthly_revenue
    except Exception:
        context['monthly_revenue'] = 0
    
    # Recent notifications
    context['recent_notifications'] = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:10]
    
    return render(request, 'notifications/dashboard.html', context)
