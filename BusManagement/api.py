from django.http import JsonResponse
from django.shortcuts import get_object_or_404
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

def tickets_data(request):
    """
    API endpoint for regular tickets data
    """
    logger.info("Regular tickets API called")
    
    try:
        # Get parameters for filtering
        status_filter = request.GET.get('status', '')
        search_query = request.GET.get('search', '')
        
        # Get date range filters
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        # Start with all tickets
        tickets_query = Ticket.objects.all().order_by('-booking_time')
        
        # Apply status filter if provided
        if status_filter:
            tickets_query = tickets_query.filter(status=status_filter)
        
        # Apply search filter if provided
        if search_query:
            tickets_query = tickets_query.filter(
                Q(customer__username__icontains=search_query) |
                Q(customer__email__icontains=search_query) |
                Q(customer__first_name__icontains=search_query) |
                Q(customer__last_name__icontains=search_query) |
                Q(schedule__vehicle__name__icontains=search_query) |
                Q(schedule__route__source__icontains=search_query) |
                Q(schedule__route__destination__icontains=search_query)
            )
        
        # Apply date filters if provided
        if date_from:
            try:
                from datetime import datetime
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                tickets_query = tickets_query.filter(booking_time__gte=date_from_obj)
            except (ValueError, TypeError):
                pass
        
        if date_to:
            try:
                from datetime import datetime
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
                date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
                tickets_query = tickets_query.filter(booking_time__lte=date_to_obj)
            except (ValueError, TypeError):
                pass
        
        # Format tickets for the response
        tickets_data = []
        for ticket in tickets_query:
            ticket_data = {
                'id': str(ticket.id),
                'customer_name': f"{ticket.customer.first_name} {ticket.customer.last_name}" if ticket.customer else "Not Available",
                'vehicle_name': ticket.schedule.vehicle.name if ticket.schedule and ticket.schedule.vehicle else "Not Available",
                'seat_number': ticket.seat.seat_number if ticket.seat and hasattr(ticket.seat, 'seat_number') else "Not Available",
                'route': {
                    'source': ticket.schedule.route.source if ticket.schedule and ticket.schedule.route else "Not Available",
                    'destination': ticket.schedule.route.destination if ticket.schedule and ticket.schedule.route else "Not Available",
                    'name': ticket.schedule.route.name if ticket.schedule and ticket.schedule.route else "Not Available",
                },
                'departure_time': ticket.schedule.departure_time.isoformat() if ticket.schedule and ticket.schedule.departure_time else None,
                'arrival_time': ticket.schedule.arrival_time.isoformat() if ticket.schedule and ticket.schedule.arrival_time else None,
                'status': ticket.status,
                'base_price': float(ticket.base_price) if ticket.base_price else 0,
                'discount_amount': float(ticket.discount_amount) if ticket.discount_amount else 0,
                'final_price': float(ticket.final_price) if ticket.final_price else 0,
                'booking_time': ticket.booking_time.isoformat() if ticket.booking_time else None,
            }
            tickets_data.append(ticket_data)
        
        # Get all possible status values
        status_choices = [choice[0] for choice in Ticket._meta.get_field('status').choices]
        
        response_data = {
            'tickets': tickets_data,
            'status_choices': status_choices,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info("Regular tickets API completed successfully")
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Error in regular tickets API: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse(
            {"error": "An error occurred while retrieving ticket data"},
            status=500
        )

def ticket_detail(request, ticket_id):
    """
    API endpoint for retrieving a specific ticket's details
    """
    logger.info(f"Ticket detail API called for ticket_id: {ticket_id}")
    
    try:
        # Get the ticket by ID (using UUID)
        ticket = get_object_or_404(Ticket, id=ticket_id)
        
        # Format ticket data
        ticket_data = {
            'id': str(ticket.id),
            'customer': {
                'id': str(ticket.customer.id) if ticket.customer else None,
                'name': f"{ticket.customer.first_name} {ticket.customer.last_name}" if ticket.customer else "Not Available",
                'username': ticket.customer.username if ticket.customer else None,
                'email': ticket.customer.email if ticket.customer else None,
                'phone_number': ticket.customer.phone_number if ticket.customer else None,
            },
            'schedule': {
                'id': str(ticket.schedule.id) if ticket.schedule else None,
                'departure_time': ticket.schedule.departure_time.isoformat() if ticket.schedule and ticket.schedule.departure_time else None,
                'arrival_time': ticket.schedule.arrival_time.isoformat() if ticket.schedule and ticket.schedule.arrival_time else None,
            },
            'vehicle': {
                'name': ticket.schedule.vehicle.name if ticket.schedule and ticket.schedule.vehicle else "Not Available",
                'registration_number': ticket.schedule.vehicle.registration_number if ticket.schedule and ticket.schedule.vehicle else None,
            },
            'route': {
                'name': ticket.schedule.route.name if ticket.schedule and ticket.schedule.route else "Not Available",
                'source': ticket.schedule.route.source if ticket.schedule and ticket.schedule.route else "Not Available",
                'destination': ticket.schedule.route.destination if ticket.schedule and ticket.schedule.route else "Not Available",
                'distance_km': float(ticket.schedule.route.distance_km) if ticket.schedule and ticket.schedule.route and ticket.schedule.route.distance_km else 0,
            },
            'seat': {
                'seat_number': ticket.seat.seat_number if ticket.seat and hasattr(ticket.seat, 'seat_number') else "Not Available",
                'seat_type': ticket.seat.seat_type if ticket.seat else None,
            },
            'pricing': {
                'base_price': float(ticket.base_price) if ticket.base_price else 0,
                'discount_amount': float(ticket.discount_amount) if ticket.discount_amount else 0,
                'final_price': float(ticket.final_price) if ticket.final_price else 0,
            },
            'status': ticket.status,
            'booking_time': ticket.booking_time.isoformat() if ticket.booking_time else None,
            'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
            'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
        }
        
        logger.info("Ticket detail API completed successfully")
        return JsonResponse(ticket_data)
        
    except Exception as e:
        logger.error(f"Error in ticket detail API: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse(
            {"error": "An error occurred while retrieving ticket details"},
            status=500
        ) 