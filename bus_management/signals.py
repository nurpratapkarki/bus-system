from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Vehicle, Schedule, Seat, SeatAvailability, SpecialReservation, Ticket
from .utils import broadcast_seat_status_update

# Commenting out this signal as we're now handling seat creation in the admin interface
# and utils.py to avoid conflicts
# @receiver(post_save, sender=Vehicle)
# def create_seats_for_vehicle(sender, instance, created, **kwargs):
#     """
#     Signal to automatically create seats when a new vehicle is created
#     or when a vehicle's row_count or has_back_row is updated.
#     """
#     # Check if this is a new vehicle or an existing vehicle with seats that need updating
#     existing_seats = Seat.objects.filter(vehicle=instance).count()
#     expected_capacity = instance.capacity
#     
#     # If seats already exist but don't match the expected capacity, delete and recreate
#     if existing_seats > 0 and existing_seats != expected_capacity:
#         # This is an update that affects seating - delete existing seats
#         Seat.objects.filter(vehicle=instance).delete()
#         # Flag to continue with seat creation
#         create_new_seats = True
#     # If this is a new vehicle, create seats
#     elif created:
#         create_new_seats = True
#     else:
#         # No changes needed to seats
#         create_new_seats = False
#     
#     if create_new_seats:
#         seats = []
#         
#         # Create regular row seats (A and B groups)
#         for row in range(1, instance.row_count + 1):
#             # Group A - Window Side
#             seats.append(
#                 Seat(
#                     vehicle=instance,
#                     row_number=row,
#                     seat_group='A',
#                     seat_type='WINDOW',
#                     position=None
#                 )
#             )
#             
#             # Group B - Aisle Side
#             seats.append(
#                 Seat(
#                     vehicle=instance,
#                     row_number=row,
#                     seat_group='B',
#                     seat_type='AISLE',
#                     position=None
#                 )
#             )
#         
#         # Create back row if the vehicle has one
#         if instance.has_back_row:
#             for position in range(1, 6):  # 5 seats in the back row
#                 seats.append(
#                     Seat(
#                         vehicle=instance,
#                         row_number=0,  # Using 0 to indicate back row
#                         seat_group='BACK',
#                         seat_type='BACK',
#                         position=position
#                     )
#                 )
#         
#         # Bulk create all seats
#         if seats:
#             Seat.objects.bulk_create(seats)

# Commenting out this signal as we're now handling seat availability initialization in the admin interface
# and utils.py to avoid conflicts
# @receiver(post_save, sender=Schedule)
# def create_seat_availability(sender, instance, created, **kwargs):
#     """
#     Signal to automatically create seat availability records when a new schedule is created.
#     """
#     if created:  # Only run when a new schedule is created, not when updated
#         # Get all seats for this vehicle
#         vehicle = instance.vehicle
#         seats = Seat.objects.filter(vehicle=vehicle)
#         
#         # Create availability records for each seat
#         seat_availabilities = []
#         for seat in seats:
#             seat_availabilities.append(
#                 SeatAvailability(
#                     schedule=instance,
#                     seat=seat,
#                     status='AVAILABLE'
#                 )
#             )
#         
#         # Bulk create all the seat availability records
#         if seat_availabilities:
#             SeatAvailability.objects.bulk_create(seat_availabilities)

@receiver(post_save, sender=SpecialReservation)
def update_vehicle_status_for_special_reservation(sender, instance, created, **kwargs):
    """
    Signal to update vehicle status when a special reservation is created, approved, or cancelled.
    """
    from django.db import transaction
    
    try:
        with transaction.atomic():
            vehicle = instance.vehicle
            
            # If special reservation is approved, mark vehicle as reserved
            if instance.status == 'APPROVED':
                vehicle.status = 'RESERVED'
                vehicle.save(update_fields=['status'])
            # If special reservation is cancelled or rejected, check if other active reservations exist
            elif instance.status in ['CANCELLED', 'REJECTED', 'COMPLETED']:
                # Check if there are other active special reservations for this vehicle
                active_reservations = SpecialReservation.objects.filter(
                    vehicle=vehicle,
                    status='APPROVED'
                ).exclude(id=instance.id).exists()
                
                # If no other active reservations, set vehicle status back to active
                if not active_reservations:
                    vehicle.status = 'ACTIVE'
                    vehicle.save(update_fields=['status'])
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating vehicle status for special reservation {instance.id}: {e}")

@receiver(pre_save, sender=Schedule)
def check_completed_schedule(sender, instance, **kwargs):
    """
    Signal to check if a schedule is being marked as completed
    and reset seat availability automatically.
    """
    # Check if this is an existing schedule (not new)
    try:
        old_instance = Schedule.objects.get(pk=instance.pk)
    except Schedule.DoesNotExist:
        # This is a new schedule, no action needed
        return
    
    # Check if status is being updated to COMPLETED
    if old_instance.status != 'COMPLETED' and instance.status == 'COMPLETED':
        # Reset all seat availabilities for this schedule
        SeatAvailability.objects.filter(schedule=instance).update(status='AVAILABLE')

# Automatically reset seat availability after estimated arrival time
from django.db.models import Q
from django.db.models.signals import post_migrate
from django.apps import apps

@receiver(post_migrate)
def create_availability_reset_periodic_task(sender, **kwargs):
    """
    After migrations, set up a periodic task to reset seat availability
    for schedules past their estimated arrival time.
    
    Note: This would normally use Celery or similar, but we're showing the core logic here.
    """
    app_config = apps.get_app_config('bus_management')
    if sender.name == app_config.name:
        # This would be implemented with a Celery task in a real app
        # For demonstration, we're implementing the logic that would run periodically
        
        # Logic to reset availability after journey completion
        def reset_completed_journey_availability():
            now = timezone.now()
            
            # Find schedules that have passed their arrival time but aren't marked as completed
            completed_schedules = Schedule.objects.filter(
                Q(arrival_time__lt=now) & 
                ~Q(status='COMPLETED') &
                ~Q(status='CANCELLED')
            )
            
            # Update their status to completed
            for schedule in completed_schedules:
                schedule.status = 'COMPLETED'
                schedule.save()  # This will trigger the check_completed_schedule signal 

# New signals for ticket and seat status management

@receiver(post_save, sender=Ticket)
def update_seat_availability_on_ticket_change(sender, instance, created, **kwargs):
    """
    Signal to automatically update seat availability status when a ticket is created,
    confirmed, or cancelled.
    
    - When a ticket is created: Seat status -> RESERVED
    - When a ticket is confirmed: Seat status -> BOOKED
    - When a ticket is cancelled: Seat status -> AVAILABLE
    """
    try:
        # Get the seat availability record for this ticket
        seat_availability = SeatAvailability.objects.get(
            schedule=instance.schedule,
            seat=instance.seat
        )
        
        old_status = seat_availability.status
        new_status = None
        
        # Set the appropriate status based on ticket status
        if instance.status == 'RESERVED':
            new_status = 'RESERVED'
        elif instance.status == 'CONFIRMED':
            new_status = 'BOOKED'
        elif instance.status == 'CANCELLED':
            new_status = 'AVAILABLE'
        elif instance.status == 'COMPLETED':
            new_status = 'AVAILABLE'
            
        # Only update if the status has changed
        if new_status and old_status != new_status:
            seat_availability.status = new_status
            seat_availability.save()
            
            # Broadcast the status change via WebSockets
            broadcast_seat_status_update(
                str(instance.schedule.id), 
                str(instance.seat.id), 
                new_status
            )
            
    except SeatAvailability.DoesNotExist:
        # This should not happen in normal operation
        pass

# Signal to automatically confirm tickets a certain time before departure
@receiver(pre_save, sender=Schedule)
def auto_confirm_reserved_tickets(sender, instance, **kwargs):
    """
    Signal to automatically confirm tickets that are still in RESERVED status
    when we're approaching the departure time.
    
    This executes when a schedule is updated, checking if we're within 30 minutes
    of departure. If so, all RESERVED tickets are changed to CONFIRMED.
    """
    # Check if we're within 30 minutes of departure
    now = timezone.now()
    time_to_departure = instance.departure_time - now
    
    # If less than 30 minutes to departure and schedule is still active
    if time_to_departure.total_seconds() < 1800 and instance.status == 'SCHEDULED':
        # Find all reserved tickets for this schedule
        reserved_tickets = Ticket.objects.filter(
            schedule=instance,
            status='RESERVED'
        )
        
        # Confirm all reserved tickets
        for ticket in reserved_tickets:
            ticket.status = 'CONFIRMED'
            ticket.save() 