from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from bus_management.models import SpecialReservation, Schedule, Vehicle, Customer
from .services import send_notification
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=SpecialReservation)
def handle_special_reservation_changes(sender, instance, created, **kwargs):
    """
    Send notifications when a special reservation is created or updated
    """
    try:
        # Get the customer and staff users
        customer = instance.customer
        staff_users = User.objects.filter(is_staff=True)
        
        if created:
            # New reservation created - notify staff
            for staff in staff_users:
                send_notification(
                    recipient=staff,
                    notification_type='reservation_created',
                    title='New Special Reservation',
                    message=f'A new special reservation has been created by {customer.username} for {instance.start_time.date()} to {instance.end_time.date()}.',
                    related_obj=instance
                )
            
            # Notify the customer
            send_notification(
                recipient=customer,
                notification_type='reservation_created',
                title='Reservation Submitted',
                message=f'Your special reservation for {instance.start_time.date()} to {instance.end_time.date()} has been submitted and is pending approval.',
                related_obj=instance
            )
        
        else:
            # Check for status changes
            if hasattr(instance, '_previous_status') and instance._previous_status != instance.status:
                if instance.status == 'approved':
                    # Reservation approved - notify customer
                    send_notification(
                        recipient=customer,
                        notification_type='reservation_approved',
                        title='Reservation Approved',
                        message=f'Your special reservation for {instance.start_time.date()} to {instance.end_time.date()} has been approved.',
                        related_obj=instance
                    )
                    
                    # Notify staff
                    for staff in staff_users:
                        if hasattr(instance, '_changed_by') and staff != instance._changed_by:  # Don't notify the staff member who made the change
                            send_notification(
                                recipient=staff,
                                notification_type='reservation_approved',
                                title='Reservation Approved',
                                message=f'Special reservation #{instance.id} has been approved by {instance._changed_by.username}.',
                                related_obj=instance
                            )
                
                elif instance.status == 'rejected':
                    # Reservation rejected - notify customer
                    send_notification(
                        recipient=customer,
                        notification_type='reservation_rejected',
                        title='Reservation Rejected',
                        message=f'Your special reservation for {instance.start_time.date()} to {instance.end_time.date()} has been rejected.',
                        related_obj=instance
                    )
                
                elif instance.status == 'completed':
                    # Reservation completed - notify customer
                    send_notification(
                        recipient=customer,
                        notification_type='reservation_completed',
                        title='Reservation Completed',
                        message=f'Your special reservation for {instance.start_time.date()} to {instance.end_time.date()} has been marked as completed.',
                        related_obj=instance
                    )
            
            # Check for payment updates
            if hasattr(instance, '_previous_deposit') and instance._previous_deposit != instance.deposit_amount:
                # Payment received - notify staff
                for staff in staff_users:
                    send_notification(
                        recipient=staff,
                        notification_type='payment_received',
                        title='Payment Received',
                        message=f'Payment of Rs. {instance.deposit_amount - instance._previous_deposit} received for special reservation #{instance.id}.',
                        related_obj=instance
                    )
                
                # Notify customer
                send_notification(
                    recipient=customer,
                    notification_type='payment_received',
                    title='Payment Confirmed',
                    message=f'Your payment of Rs. {instance.deposit_amount - instance._previous_deposit} for special reservation has been recorded.',
                    related_obj=instance
                )
    
    except Exception as e:
        logger.error(f"Error sending notification for special reservation: {str(e)}")

@receiver(pre_save, sender=SpecialReservation)
def store_previous_reservation_state(sender, instance, **kwargs):
    """
    Store the previous state of a special reservation before it's saved
    """
    if instance.pk:
        try:
            previous = SpecialReservation.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
            instance._previous_deposit = previous.deposit_amount
        except SpecialReservation.DoesNotExist:
            pass

@receiver(post_save, sender=Schedule)
def handle_schedule_conflicts(sender, instance, created, **kwargs):
    """
    Check for conflicts when a schedule is created or updated
    """
    from django.db.models import Q
    
    try:
        if not instance.is_active:
            return
            
        # Check for conflicts with special reservations
        conflicts = SpecialReservation.objects.filter(
            Q(start_time__lt=instance.end_time) & Q(end_time__gt=instance.start_time),
            status__in=['approved', 'pending'],
            vehicle=instance.vehicle
        )
        
        if conflicts.exists():
            # Notify staff about the conflict
            staff_users = User.objects.filter(is_staff=True)
            
            for staff in staff_users:
                send_notification(
                    recipient=staff,
                    notification_type='schedule_conflict',
                    title='Schedule Conflict Detected',
                    message=f'Schedule #{instance.id} conflicts with {conflicts.count()} special reservation(s) for vehicle {instance.vehicle.name}.',
                    related_obj=instance
                )
    
    except Exception as e:
        logger.error(f"Error checking for schedule conflicts: {str(e)}")

@receiver(post_save, sender=Vehicle)
def handle_vehicle_status_change(sender, instance, created, **kwargs):
    """
    Send notifications when a vehicle's status changes
    """
    try:
        if not created and hasattr(instance, '_previous_status') and instance._previous_status != instance.status:
            # Vehicle status changed - notify staff
            staff_users = User.objects.filter(is_staff=True)
            
            for staff in staff_users:
                send_notification(
                    recipient=staff,
                    notification_type='vehicle_maintenance',
                    title='Vehicle Status Changed',
                    message=f'Vehicle {instance.name} status changed from {instance._previous_status} to {instance.status}.',
                    related_obj=instance
                )
    
    except Exception as e:
        logger.error(f"Error sending notification for vehicle status change: {str(e)}")

@receiver(pre_save, sender=Vehicle)
def store_previous_vehicle_state(sender, instance, **kwargs):
    """
    Store the previous state of a vehicle before it's saved
    """
    if instance.pk:
        try:
            previous = Vehicle.objects.get(pk=instance.pk)
            instance._previous_status = previous.status
        except Vehicle.DoesNotExist:
            pass 