from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import uuid
from decimal import Decimal

from .models import (
    Vehicle, Route, Schedule, Seat, SeatAvailability, Ticket, SpecialReservation
)


def initialize_seat_availability(schedule):
    """
    Initialize seat availability records for a new schedule.
    Called when creating a new schedule to set up availability tracking.
    
    If seat availability records already exist for this schedule, they'll be
    deleted first to avoid uniqueness constraint violations.
    """
    # Delete any existing seat availability records for this schedule
    SeatAvailability.objects.filter(schedule=schedule).delete()
    
    # Get all seats for the vehicle
    vehicle = schedule.vehicle
    seats = Seat.objects.filter(vehicle=vehicle)
    
    # Create availability records for each seat
    seat_availabilities = []
    for seat in seats:
        seat_availabilities.append(
            SeatAvailability(
                schedule=schedule,
                seat=seat,
                status='AVAILABLE'
            )
        )
    
    # Bulk create all the seat availability records
    if seat_availabilities:
        SeatAvailability.objects.bulk_create(seat_availabilities)
        
    return len(seat_availabilities)  # Return the number of records created


def calculate_special_reservation_price(source, destination, distance_km, departure_time):
    """
    Calculate the price for a special reservation based on various factors.
    This would be more complex in a real system with actual business logic.
    """
    # Base price calculation
    base_price = Decimal(distance_km) * Decimal('5.0')  # $5 per km
    
    # Distance-based surcharge/discount
    distance_surcharge = Decimal('0.0')
    if distance_km > 200:
        # 10% discount for long trips
        distance_surcharge = -base_price * Decimal('0.1')
    
    # Time-based surcharge
    time_surcharge = Decimal('0.0')
    try:
        if isinstance(departure_time, str):
            dept_time = timezone.datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
        else:
            dept_time = departure_time
            
        hour = dept_time.hour
        if 6 <= hour <= 9 or 16 <= hour <= 19:  # Peak hours
            time_surcharge = base_price * Decimal('0.2')  # 20% extra for peak hours
    except:
        pass
    
    # Demand-based surcharge - this would use more sophisticated algorithms in a real system
    demand_surcharge = Decimal('0.0')
    
    # Calculate final price
    final_price = base_price + distance_surcharge + time_surcharge + demand_surcharge
    
    return {
        'base_price': base_price,
        'distance_surcharge': distance_surcharge,
        'time_surcharge': time_surcharge,
        'demand_surcharge': demand_surcharge,
        'final_price': final_price
    }


def calculate_arrival_time(departure_time, distance_km):
    """
    Calculate estimated arrival time based on distance and average speed.
    """
    avg_speed = 60  # km/h
    duration_hours = distance_km / avg_speed
    duration_minutes = int(duration_hours * 60)
    
    if isinstance(departure_time, str):
        try:
            dept_time = timezone.datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
        except:
            dept_time = timezone.now()
    else:
        dept_time = departure_time
        
    return dept_time + timezone.timedelta(minutes=duration_minutes)


def broadcast_vehicle_status_update(vehicle_id, status):
    """
    Broadcast vehicle status updates to WebSocket clients.
    """
    channel_layer = get_channel_layer()
    group_name = f'vehicle_{vehicle_id}'
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'status_update',
            'vehicle_id': str(vehicle_id),
            'status': status,
            'timestamp': timezone.now().isoformat()
        }
    )


def broadcast_schedule_status_update(schedule_id, status):
    """
    Broadcast schedule status updates to WebSocket clients.
    """
    channel_layer = get_channel_layer()
    group_name = f'schedule_{schedule_id}'
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'status_update',
            'schedule_id': str(schedule_id),
            'status': status,
            'timestamp': timezone.now().isoformat()
        }
    )


def broadcast_seat_status_update(schedule_id, seat_id, status):
    """
    Broadcast seat availability updates to WebSocket clients.
    """
    channel_layer = get_channel_layer()
    group_name = f'seat_availability_{schedule_id}'
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'seat_update',
            'seat_id': str(seat_id),
            'status': status,
            'timestamp': timezone.now().isoformat()
        }
    )


def create_vehicle_with_seats(name, registration_number, capacity, vehicle_subtype, existing_vehicle=None):
    """
    Create a new vehicle and initialize its seats.
    The capacity parameter is used to calculate row_count and has_back_row.
    
    Parameters:
    - name: Vehicle name
    - registration_number: Vehicle registration number
    - capacity: Desired total capacity of the vehicle
    - vehicle_subtype: VehicleSubtype model instance
    - existing_vehicle: Optional existing Vehicle object to use instead of creating a new one
    """
    # Calculate row_count based on capacity (assuming 2 seats per row + 5 back seats)
    has_back_row = True
    if capacity <= 5:
        # Small capacity vehicle, all seats in back row
        row_count = 0
    else:
        # Normal vehicle with rows of 2 seats each + optional back row
        back_seats = 5 if has_back_row else 0
        row_count = (capacity - back_seats) // 2
        # Adjust if there are odd number of seats
        if (capacity - back_seats) % 2 != 0:
            row_count += 1
    
    # Use existing vehicle or create a new one
    if existing_vehicle:
        vehicle = existing_vehicle
        # Update the vehicle properties if necessary
        if vehicle.row_count != row_count or vehicle.has_back_row != has_back_row:
            vehicle.row_count = row_count
            vehicle.has_back_row = has_back_row
            vehicle.save()
    else:
        vehicle = Vehicle.objects.create(
            name=name,
            registration_number=registration_number,
            row_count=row_count,
            has_back_row=has_back_row,
            vehicle_subtype=vehicle_subtype,
            status='ACTIVE'
        )
    
    # Delete any existing seats for this vehicle first to avoid uniqueness violation
    Seat.objects.filter(vehicle=vehicle).delete()
    
    # Create seats for the vehicle
    seats = []
    
    # Create regular row seats
    for row in range(1, row_count + 1):
        # Create A seat (window side)
        seats.append(Seat(
            vehicle=vehicle,
            row_number=row,
            seat_group='A',
            seat_type='WINDOW'
        ))
        # Create B seat (aisle side)
        seats.append(Seat(
            vehicle=vehicle,
            row_number=row,
            seat_group='B',
            seat_type='AISLE'
        ))
    
    # Create back row seats if applicable
    if has_back_row:
        for pos in range(1, 6):
            seats.append(Seat(
                vehicle=vehicle,
                row_number=row_count + 1,
                seat_group='BACK',
                position=pos,
                seat_type='BACK'
            ))
    
    # Bulk create all seats
    Seat.objects.bulk_create(seats)
    
    return vehicle


def get_sales_analytics(start_date=None, end_date=None):
    """
    Get analytics data for sales in a date range.
    """
    if not start_date:
        start_date = timezone.now() - timezone.timedelta(days=30)
    if not end_date:
        end_date = timezone.now()
    
    # Get all confirmed tickets in the date range
    tickets = Ticket.objects.filter(
        booking_time__gte=start_date,
        booking_time__lte=end_date
    )
    
    # Get all completed special reservations in the date range
    special_reservations = SpecialReservation.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date,
        status__in=['APPROVED', 'COMPLETED']
    )
    
    # Calculate total sales
    ticket_sales = sum(ticket.final_price for ticket in tickets)
    reservation_sales = sum(reservation.final_price for reservation in special_reservations)
    total_sales = ticket_sales + reservation_sales
    
    # Count transactions
    ticket_count = tickets.count()
    reservation_count = special_reservations.count()
    total_transactions = ticket_count + reservation_count
    
    # Count cancellations
    cancelled_tickets = tickets.filter(status='CANCELLED').count()
    cancelled_reservations = special_reservations.filter(status='CANCELLED').count()
    total_cancellations = cancelled_tickets + cancelled_reservations
    
    # Calculate cancellation rate
    cancellation_rate = 0
    if total_transactions > 0:
        cancellation_rate = (total_cancellations / (total_transactions + total_cancellations)) * 100
    
    # Get top routes by ticket sales
    route_sales = {}
    for ticket in tickets:
        route_name = f"{ticket.schedule.route.source} to {ticket.schedule.route.destination}"
        if route_name in route_sales:
            route_sales[route_name]['count'] += 1
            route_sales[route_name]['revenue'] += ticket.final_price
        else:
            route_sales[route_name] = {
                'count': 1,
                'revenue': ticket.final_price
            }
    
    # Sort routes by revenue
    top_routes = sorted(
        [{'route': k, 'count': v['count'], 'revenue': v['revenue']} for k, v in route_sales.items()],
        key=lambda x: x['revenue'],
        reverse=True
    )[:5]  # Top 5 routes
    
    return {
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'ticket_sales': ticket_sales,
        'reservation_sales': reservation_sales,
        'total_sales': total_sales,
        'ticket_count': ticket_count,
        'reservation_count': reservation_count,
        'total_transactions': total_transactions,
        'cancelled_tickets': cancelled_tickets,
        'cancelled_reservations': cancelled_reservations,
        'total_cancellations': total_cancellations,
        'cancellation_rate': cancellation_rate,
        'top_routes': top_routes
    } 