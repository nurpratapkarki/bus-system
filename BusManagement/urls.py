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
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from . import api
from bus_management.models import SpecialReservation
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
import datetime

# Helper function to get admin context
def get_admin_context(request, title):
    """Returns the admin context dictionary for templates."""
    from django.contrib.admin.sites import site
    
    return {
        'site_title': settings.JAZZMIN_SETTINGS.get('site_title', 'Bus Management Admin'),
        'site_header': settings.JAZZMIN_SETTINGS.get('site_header', 'Bus Management'),
        'site_url': '/',
        'has_permission': request.user.is_staff,
        'available_apps': site.get_app_list(request),
        'is_popup': False,
        'is_nav_sidebar_enabled': True,
        'user': request.user,
    }

# Simple dashboard view
@login_required
def dashboard_view(request):
    """
    Renders the dashboard template with admin context
    """
    context = {
        'title': 'Dashboard',
        **get_admin_context(request, 'Dashboard')
    }
    return render(request, 'dashboard/dashboard.html', context)

# Reservation ticket list view
@login_required
def ticket_list_view(request):
    """View for displaying a list of all special reservation tickets."""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Start with all reservations
    reservations = SpecialReservation.objects.all().order_by('-created_at')
    
    # Apply filters
    if status_filter:
        reservations = reservations.filter(status=status_filter)
    
    if search_query:
        filter_conditions = Q()
        filter_conditions |= Q(id__icontains=search_query)
        
        # Check if customer_name field exists in the model
        if hasattr(SpecialReservation, 'customer_name'):
            filter_conditions |= Q(customer_name__icontains=search_query)
            
        # Check if source field exists in the model
        if hasattr(SpecialReservation, 'source'):
            filter_conditions |= Q(source__icontains=search_query)
        elif hasattr(SpecialReservation, 'source_location'):
            filter_conditions |= Q(source_location__icontains=search_query)
            
        # Check if destination field exists in the model
        if hasattr(SpecialReservation, 'destination'):
            filter_conditions |= Q(destination__icontains=search_query)
        elif hasattr(SpecialReservation, 'destination_location'):
            filter_conditions |= Q(destination_location__icontains=search_query)
            
        reservations = reservations.filter(filter_conditions)
    
    # Apply date filters with proper attribute checks
    date_field = None
    if hasattr(SpecialReservation, 'start_date'):
        date_field = 'start_date'
    elif hasattr(SpecialReservation, 'start_time'):
        date_field = 'start_time'
        
    if date_field and date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            reservations = reservations.filter(**{f"{date_field}__gte": date_from_obj})
        except (ValueError, TypeError):
            pass
    
    if date_field and date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            reservations = reservations.filter(**{f"{date_field}__lte": date_to_obj})
        except (ValueError, TypeError):
            pass
    
    # Format reservations for display
    formatted_reservations = []
    for reservation in reservations:
        # Handle customer name properly
        customer_name = "N/A"
        if hasattr(reservation, 'customer') and reservation.customer:
            if hasattr(reservation.customer, 'full_name') and reservation.customer.full_name:
                customer_name = reservation.customer.full_name
            elif hasattr(reservation.customer, 'username') and reservation.customer.username:
                customer_name = reservation.customer.username
            elif hasattr(reservation.customer, 'name') and reservation.customer.name:
                customer_name = reservation.customer.name
        elif hasattr(reservation, 'customer_name') and reservation.customer_name:
            customer_name = reservation.customer_name
        
        # Get vehicle name safely
        vehicle_name = "N/A"
        if hasattr(reservation, 'vehicle') and reservation.vehicle:
            if hasattr(reservation.vehicle, 'name'):
                vehicle_name = reservation.vehicle.name
        
        # Get departure time safely
        departure_time = "N/A"
        if hasattr(reservation, 'start_date'):
            departure_time = reservation.start_date
        elif hasattr(reservation, 'start_time'):
            departure_time = reservation.start_time
        
        # Get status safely
        status = "PENDING"
        if hasattr(reservation, 'status'):
            status = reservation.status
        
        # Get price safely
        final_price = 0
        if hasattr(reservation, 'final_price'):
            final_price = reservation.final_price or 0
        elif hasattr(reservation, 'total_price'):
            final_price = reservation.total_price or 0
        
        formatted_reservations.append({
            'id': reservation.id,
            'customer_name': customer_name,
            'vehicle_name': vehicle_name,
            'departure_time': departure_time,
            'status': status,
            'final_price': final_price,
        })
    
    # Pagination
    paginator = Paginator(formatted_reservations, 10)  # Show 10 reservations per page
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # Get all possible status values for the filter dropdown
    try:
        status_choices = [choice[0] for choice in SpecialReservation._meta.get_field('status').choices]
    except:
        status_choices = ['PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED']
    
    context = {
        'title': 'Ticket List',
        'reservations': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
        'status_choices': status_choices,
        **get_admin_context(request, 'Ticket List')
    }
    
    return render(request, 'dashboard/ticket_list.html', context)

# Reservation ticket view
@login_required
def reservation_ticket_view(request, reservation_id):
    """View for displaying a special reservation ticket."""
    reservation = get_object_or_404(SpecialReservation, id=reservation_id)
    
    # Handle customer name properly
    customer_name = "N/A"
    if hasattr(reservation, 'customer') and reservation.customer:
        if hasattr(reservation.customer, 'full_name') and reservation.customer.full_name:
            customer_name = reservation.customer.full_name
        elif hasattr(reservation.customer, 'username') and reservation.customer.username:
            customer_name = reservation.customer.username
        elif hasattr(reservation.customer, 'name') and reservation.customer.name:
            customer_name = reservation.customer.name
    elif hasattr(reservation, 'customer_name') and reservation.customer_name:
        customer_name = reservation.customer_name
    
    # Format vehicle name safely
    vehicle_name = "N/A"
    if hasattr(reservation, 'vehicle') and reservation.vehicle:
        if hasattr(reservation.vehicle, 'name'):
            if hasattr(reservation.vehicle, 'registration_number'):
                vehicle_name = f"{reservation.vehicle.name} ({reservation.vehicle.registration_number})"
            elif hasattr(reservation.vehicle, 'license_plate'):
                vehicle_name = f"{reservation.vehicle.name} ({reservation.vehicle.license_plate})"
            else:
                vehicle_name = reservation.vehicle.name
    
    # Calculate total price and balance safely
    deposit_amount = 0
    if hasattr(reservation, 'deposit_amount'):
        deposit_amount = reservation.deposit_amount or 0
    
    final_price = 0
    if hasattr(reservation, 'final_price'):
        final_price = reservation.final_price or 0
    elif hasattr(reservation, 'total_price'):
        final_price = reservation.total_price or 0
    
    balance_amount = final_price - deposit_amount
    
    # Handle dates safely
    departure_time = "N/A"
    if hasattr(reservation, 'start_date'):
        departure_time = reservation.start_date
    elif hasattr(reservation, 'start_time'):
        departure_time = reservation.start_time
    
    end_time = None
    if hasattr(reservation, 'end_date'):
        end_time = reservation.end_date
    elif hasattr(reservation, 'end_time'):
        end_time = reservation.end_time
    
    duration_days = 1
    if departure_time != "N/A" and end_time and not isinstance(departure_time, str):
        try:
            duration_days = (end_time - departure_time).days
            if duration_days < 1:
                duration_days = 1
        except:
            duration_days = 1
    
    # Handle other fields safely
    source = "N/A"
    if hasattr(reservation, 'source'):
        source = reservation.source or "N/A"
    elif hasattr(reservation, 'source_location'):
        source = reservation.source_location or "N/A"
    
    destination = "N/A"
    if hasattr(reservation, 'destination'):
        destination = reservation.destination or "N/A"
    elif hasattr(reservation, 'destination_location'):
        destination = reservation.destination_location or "N/A"
    
    passenger_count = 1
    if hasattr(reservation, 'passenger_count'):
        passenger_count = reservation.passenger_count or 1
    
    is_round_trip = False
    if hasattr(reservation, 'is_round_trip'):
        is_round_trip = reservation.is_round_trip
    
    # Get status safely
    status = "PENDING"
    if hasattr(reservation, 'status'):
        status = reservation.status
    
    # Build reservation data for the template
    reservation_data = {
        'id': reservation.id,
        'customer_name': customer_name,
        'vehicle_name': vehicle_name,
        'source': source,
        'destination': destination,
        'departure_time': departure_time,
        'duration_days': duration_days,
        'status': status,
        'passenger_count': passenger_count,
        'is_round_trip': is_round_trip,
        'deposit_amount': deposit_amount,
        'final_price': final_price,
        'balance_amount': balance_amount,
    }
    
    # Check if print mode is requested
    print_mode = request.GET.get('print', False)
    
    context = {
        'title': 'Reservation Ticket',
        'reservation': reservation_data,
        'print_mode': print_mode,
        **get_admin_context(request, 'Reservation Ticket')
    }
    
    return render(request, 'dashboard/reservation_ticket.html', context)

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
    path('dashboard/tickets/', ticket_list_view, name='ticket_list'),
    path('dashboard/reservation/<uuid:reservation_id>/ticket/', reservation_ticket_view, name='reservation_ticket'),
    
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
