from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from bus_management.models import (
    Vehicle, Route, Schedule, Seat, SeatAvailability, 
    Ticket, SpecialReservation, Customer
)
from notifications.models import Notification
import datetime
import logging

logger = logging.getLogger(__name__)

def dashboard_data(request):
    """
    Unified API endpoint for dashboard statistics
    """
    logger.info("Dashboard API called")
    
    # Get current date
    today = timezone.now().date()
    
    try:
        # Total vehicles count
        total_vehicles = Vehicle.objects.count()
        
        # Total active routes count
        total_routes = Route.objects.filter(is_active=True).count()
        
        # Tickets sold today
        tickets_today = Ticket.objects.filter(
            created_at__date=today
        ).count()
        
        # Total special reservations
        special_reservations = SpecialReservation.objects.count()
        
        # Recent special reservations
        recent_reservations_data = []
        recent_special_reservations = SpecialReservation.objects.all().order_by('-created_at')[:10]
        
        for reservation in recent_special_reservations:
            try:
                reservation_data = {
                    'id': str(reservation.id),
                    'customer_name': str(reservation.customer) if reservation.customer else 'Anonymous',
                    'vehicle_name': str(reservation.vehicle) if reservation.vehicle else 'Not assigned',
                    'start_time': reservation.departure_time.isoformat() if reservation.departure_time else None,
                    'status': reservation.status,
                    'final_price': float(reservation.final_price) if reservation.final_price else 0,
                }
                recent_reservations_data.append(reservation_data)
            except Exception as e:
                logger.error(f"Error processing reservation {reservation.id}: {str(e)}")
        
        # Monthly revenue stats
        month_start = today.replace(day=1)
        monthly_revenue = 0
        
        # Revenue from tickets this month
        tickets_revenue = Ticket.objects.filter(
            created_at__gte=month_start,
            created_at__lte=today
        ).aggregate(total=Sum('final_price'))['total'] or 0
        
        # Revenue from special reservations this month
        reservations_revenue = SpecialReservation.objects.filter(
            created_at__gte=month_start,
            created_at__lte=today
        ).aggregate(total=Sum('final_price'))['total'] or 0
        
        monthly_revenue = float(tickets_revenue) + float(reservations_revenue)
        
        # Complete response data
        response_data = {
            'total_vehicles': total_vehicles,
            'total_routes': total_routes,
            'tickets_today': tickets_today,
            'special_reservations': special_reservations,
            'recent_reservations': recent_reservations_data,
            'monthly_revenue': monthly_revenue,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info("Dashboard API completed successfully")
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error in dashboard API: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse(
            {"error": "An error occurred while retrieving dashboard data"},
            status=500
        )

def dashboard_charts(request):
    """
    Unified API endpoint for dashboard chart data
    """
    logger.info("Dashboard charts API called")
    
    try:
        # Get current date
        today = timezone.now().date()
        
        # Revenue chart - last 7 days
        revenue_labels = []
        revenue_data = []
        
        for i in range(6, -1, -1):
            day = today - datetime.timedelta(days=i)
            day_name = day.strftime('%a')
            revenue_labels.append(day_name)
            
            # Calculate revenue for this day from tickets and special reservations
            
            # Revenue from tickets
            tickets_revenue = Ticket.objects.filter(
                created_at__date=day
            ).aggregate(total=Sum('final_price'))['total'] or 0
            
            # Revenue from special reservations
            reservations_revenue = SpecialReservation.objects.filter(
                deposit_paid_date=day
            ).aggregate(total=Sum('deposit_amount'))['total'] or 0
            
            day_revenue = float(tickets_revenue) + float(reservations_revenue)
            revenue_data.append(day_revenue)
        
        # Ticket distribution by type
        ticket_types = ['Regular', 'Special', 'Student', 'Senior', 'Group']
        ticket_counts = []
        
        # Regular tickets
        regular_count = Ticket.objects.filter(
            created_at__gte=today - datetime.timedelta(days=30)
        ).count()
        ticket_counts.append(regular_count)
        
        # Special reservations
        special_count = SpecialReservation.objects.filter(
            created_at__gte=today - datetime.timedelta(days=30)
        ).count()
        ticket_counts.append(special_count)
        
        # Other ticket types (placeholders)
        ticket_counts.extend([0, 0, 0])  # Student, Senior, Group tickets
        
        response_data = {
            'revenue_chart': {
                'labels': revenue_labels,
                'data': revenue_data
            },
            'ticket_distribution': {
                'labels': ticket_types,
                'data': ticket_counts
            }
        }
        
        logger.info("Dashboard charts API completed successfully")
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error in dashboard charts API: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse(
            {"error": "An error occurred while retrieving chart data"},
            status=500
        )

def notifications_data(request):
    """
    Unified API endpoint for notifications
    """
    logger.info("Notifications API called")
    
    try:
        # Get notifications for the authenticated user
        if not request.user.is_authenticated:
            return JsonResponse([], safe=False)
            
        notifications = Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:10]
        
        # Format notifications for the frontend
        notification_data = []
        for notification in notifications:
            notification_data.append({
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat() if notification.created_at else None,
                'related_object_id': str(notification.related_object_id) if notification.related_object_id else None,
                'related_object_type': notification.related_object_type,
            })
        
        logger.info("Notifications API completed successfully")
        return JsonResponse(notification_data, safe=False)
        
    except Exception as e:
        logger.error(f"Error in notifications API: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse(
            {"error": "An error occurred while retrieving notifications"},
            status=500
        ) 