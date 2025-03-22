from django.contrib import admin
from .models import (
    Vehicle, Route, Schedule, Seat, Customer, Offer,
    Ticket, SpecialReservation, SeatAvailability, VehicleType, VehicleSubtype, Dashboard
)
from .utils import create_vehicle_with_seats, initialize_seat_availability
from django.contrib import messages
from django.utils.html import format_html
from .forms import TicketAdminForm, SpecialReservationAdminForm  # Import the SpecialReservationAdminForm


@admin.register(VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    """Admin configuration for vehicle types"""
    list_display = ('name', 'description')
    search_fields = ('name', 'description')
    ordering = ('name',)

@admin.register(VehicleSubtype)
class VehicleSubtypeAdmin(admin.ModelAdmin):
    """Admin configuration for vehicle subtypes"""
    list_display = ('name', 'vehicle_type', 'subtype_code', 'default_rows', 'default_columns', 'rate_per_km', 'min_price', 'has_ac')
    list_filter = ('vehicle_type', 'has_ac', 'has_wifi', 'has_entertainment', 'has_charging_ports', 'has_reclining_seats')
    search_fields = ('name', 'description', 'subtype_code', 'vehicle_type__name')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'vehicle_type', 'subtype_code')
        }),
        ('Seating Configuration', {
            'fields': ('default_rows', 'default_columns')
        }),
        ('Pricing', {
            'fields': ('rate_per_km', 'min_price')
        }),
        ('Features', {
            'fields': ('has_ac', 'has_wifi', 'has_entertainment', 'has_charging_ports', 'has_reclining_seats'),
            'classes': ('collapse',)
        }),
    )
    
 

class SeatInline(admin.TabularInline):
    """Inline admin for seats to display them within the vehicle admin"""
    model = Seat
    extra = 0
    readonly_fields = ('seat_number',)
    fields = ('row_number', 'seat_group', 'position', 'seat_type', 'seat_number')
    can_delete = True
    show_change_link = True

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_number', 'capacity', 'status', 'seat_layout_summary')
    list_filter = ('status',)
    search_fields = ('name', 'registration_number')
    fieldsets = (
        (None, {
            'fields': ('name', 'registration_number', 'status', 'vehicle_subtype')
        }),
        ('Seating Configuration', {
            'fields': ('row_count', 'has_back_row'),
            'description': 'Configure the seating layout. Seats will be automatically generated.'
        }),
    )
    inlines = [SeatInline]
    
    # Add vehicle_admin.js for auto calculations
    class Media:
        js =('/static/bus_management/js/vehicle_admin.js',)
    
    def seat_layout_summary(self, obj):
        """Display a summary of the vehicle seating layout"""
        seat_count = Seat.objects.filter(vehicle=obj).count()
        expected = obj.capacity
        
        if seat_count == expected:
            return format_html(
                '<span style="color: green;">{} rows (A+B) {} back row = {} seats</span>',
                obj.row_count, 
                "+ 5 seats" if obj.has_back_row else "no", 
                obj.capacity
            )
        else:
            return format_html(
                '<span style="color: red;">Expected {} seats, found {}. Save to fix.</span>',
                expected, seat_count
            )
    
    seat_layout_summary.short_description = "Seat Layout"

    def save_model(self, request, obj, form, change):
        """Override save_model to create seats when a vehicle is created"""
        # First save the vehicle object normally
        super().save_model(request, obj, form, change)
        
        # For new vehicles or when editing seating configuration, regenerate seats
        if not change or 'row_count' in form.changed_data or 'has_back_row' in form.changed_data:
            # Calculate expected capacity based on row_count and has_back_row
            row_seats = obj.row_count * 2  # 2 seats per row
            back_row_seats = 5 if obj.has_back_row else 0
            expected_capacity = row_seats + back_row_seats
            
            # Use the existing vehicle object
            vehicle = create_vehicle_with_seats(
                name=obj.name,
                registration_number=obj.registration_number,
                capacity=expected_capacity,
                vehicle_subtype=obj.vehicle_subtype,
                existing_vehicle=obj
            )
            
            if not change:
                messages.success(request, f'Created {expected_capacity} seats for vehicle {obj.name}')
            else:
                messages.success(request, f'Updated seating configuration for vehicle {obj.name}. Now has {expected_capacity} seats.')

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'source', 'destination', 'distance_km', 'estimated_duration_minutes')
    search_fields = ('name', 'source', 'destination')
    
    

class SeatAvailabilityInline(admin.TabularInline):
    """Inline admin for seat availability to display them within the schedule admin"""
    model = SeatAvailability
    extra = 0
    fields = ('seat', 'status')
    readonly_fields = ('seat',)
    can_delete = False
    max_num = 0  # Don't allow adding new availability records manually

@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('vehicle', 'route', 'departure_time', 'arrival_time', 'status', 'base_price', 'available_seats')
    list_filter = ('status', 'vehicle__status')
    search_fields = ('vehicle__name', 'route__name', 'route__source', 'route__destination')
    date_hierarchy = 'departure_time'
    inlines = [SeatAvailabilityInline]
    
    # Use the correct JavaScript file for Schedule admin
    class Media:
        js = ('/static/vehicle_management/js/schedule_admin.js',)
    
    def available_seats(self, obj):
        """Display count of available seats"""
        count = SeatAvailability.objects.filter(schedule=obj, status='AVAILABLE').count()
        total = SeatAvailability.objects.filter(schedule=obj).count()
        return f"{count}/{total} available"
    
    available_seats.short_description = "Available Seats"
    
    def get_readonly_fields(self, request, obj=None):
        """Make vehicle field readonly after creation if vehicle is specially reserved"""
        if obj and obj.vehicle.status == 'RESERVED':
            return ('vehicle',) + self.readonly_fields
        return self.readonly_fields
        
    def save_model(self, request, obj, form, change):
        """Override save_model to initialize seat availability when a schedule is created or vehicle is changed"""
        # Check if the vehicle is available for this schedule's timeframe
        if obj.vehicle:
            is_available, conflict, conflict_type = obj.vehicle.is_available(
                obj.departure_time, obj.arrival_time,
                # No need to exclude this schedule since it's not saved yet
            )
            
            if not is_available and conflict_type == 'special_reservation':
                conflict_detail = (f"{conflict.source} to {conflict.destination}, "
                                  f"{conflict.departure_time.strftime('%Y-%m-%d %H:%M')} to "
                                  f"{conflict.estimated_arrival_time.strftime('%Y-%m-%d %H:%M')}")
                messages.error(
                    request,
                    f"Cannot save schedule: Vehicle {obj.vehicle.name} is already reserved for a special trip: {conflict_detail}"
                )
                return  # Don't save the schedule
        
        # Save the schedule object first
        super().save_model(request, obj, form, change)
        
        # Initialize seat availability if this is a new schedule or the vehicle was changed
        if not change or 'vehicle' in form.changed_data:
            seats_count = initialize_seat_availability(obj)
            
            if not change:
                messages.success(request, f'Created {seats_count} seat availability records for this schedule')
            else:
                messages.success(request, f'Updated seat availability. Now tracking {seats_count} seats for this schedule')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'verification_status')
    list_filter = ('verification_status', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone_number')
    readonly_fields = ('date_joined', 'last_login')
    fieldsets = (
        (None, {
            'fields': ('username', 'email', 'first_name', 'last_name')
        }),
        ('Contact Information', {
            'fields': ('phone_number',)
        }),
        ('Status', {
            'fields': ('verification_status', 'is_active')
        }),
        ('Security', {
            'fields': ('password',),
            'description': 'Password is stored securely hashed. Use the set password form to change it.'
        }),
        ('Dates', {
            'fields': ('date_joined', 'last_login'),
            'classes': ('collapse',)
        }),
    )
    
   
    
    def save_model(self, request, obj, form, change):
        """Handle password hashing when saving from admin"""
        if 'password' in form.changed_data:
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)

@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'valid_from', 'valid_until', 'is_active')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code', 'description')
    date_hierarchy = 'valid_from'
  

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('customer', 'schedule', 'seat', 'status', 'final_price', 'booking_time')
    list_filter = ('status',)
    search_fields = ('customer__username', 'customer__email', 'schedule__vehicle__name', 'schedule__route__source', 'schedule__route__destination')
    date_hierarchy = 'booking_time'
    form = TicketAdminForm  # Reference the imported form class (not as a string)
    
    # Add ticket_admin.js for auto calculations
    class Media:
        js = ('/static/vehicle_management/js/ticket_admin.js',)

@admin.register(SpecialReservation)
class SpecialReservationAdmin(admin.ModelAdmin):
    form = SpecialReservationAdminForm
    list_display = ('customer', 'vehicle', 'source', 'destination', 'departure_time', 'duration_days', 'status', 'final_price', 'is_fully_paid')
    list_filter = ('status', 'is_round_trip', 'duration_days', 'is_fully_paid')
    search_fields = ('customer__username', 'customer__email', 'source', 'destination', 'vehicle__name')
    date_hierarchy = 'departure_time'
    
    fieldsets = (
        ('Customer & Vehicle', {
            'fields': ('customer', 'vehicle', 'passenger_count')
        }),
        ('Trip Details', {
            'fields': ('source', 'destination', 'distance_km', 'trip_purpose', 
                       'is_round_trip', 'has_multiple_stops', 'stops')
        }),
        ('Schedule', {
            'fields': ('departure_time', 'estimated_arrival_time', 'return_time', 'duration_days')
        }),
        ('Pricing Factors', {
            'fields': ('season_factor', 'driver_allowance', 'distance_surcharge', 
                      'time_surcharge', 'demand_surcharge', 'discount_amount')
        }),
        ('Calculated Prices', {
            'fields': ('base_price', 'multi_day_surcharge', 'final_price'),
            'classes': ('collapse',)
        }),
        ('Payment Information', {
            'fields': ('deposit_amount', 'deposit_paid_date', 'balance_amount', 'is_fully_paid')
        }),
        ('Status', {
            'fields': ('status',)
        }),
    )
    
    # Create special_reservation_admin.js for price calculations
    class Media:
        js = ('/static/vehicle_management/js/special_reservation_admin.js',)
    
    def get_readonly_fields(self, request, obj=None):
        """Make vehicle field readonly after creation if status is APPROVED"""
        readonly_fields = list(self.readonly_fields)
        if obj:
            if obj.status == 'APPROVED':
                readonly_fields.extend(['vehicle', 'customer'])
            if obj.status in ['COMPLETED', 'CANCELLED']:
                readonly_fields.extend(['vehicle', 'customer', 'source', 'destination', 
                                       'departure_time', 'duration_days'])
        return readonly_fields
        
    def save_model(self, request, obj, form, change):
        """Override save_model to update vehicle status and check conflicts"""
        old_status = None
        if change and obj.pk:
            try:
                old_obj = self.model.objects.get(pk=obj.pk)
                old_status = old_obj.status
            except self.model.DoesNotExist:
                pass
                
        # Check if status is changing to APPROVED
        if old_status != 'APPROVED' and obj.status == 'APPROVED':
            # When approving, check for any conflicts first
            end_time = obj.return_time if obj.is_round_trip and obj.return_time else obj.estimated_arrival_time
            is_available, conflict, conflict_type = obj.vehicle.is_available(
                obj.departure_time, end_time, exclude_reservation_id=obj.pk
            )
            
            if not is_available:
                if conflict_type == 'schedule':
                    conflict_detail = (f"{conflict.route.source} to {conflict.route.destination}, "
                                     f"{conflict.departure_time.strftime('%Y-%m-%d %H:%M')} to "
                                     f"{conflict.arrival_time.strftime('%Y-%m-%d %H:%M')}")
                    messages.error(
                        request,
                        f"Cannot approve: Vehicle is already scheduled for a regular route: {conflict_detail}"
                    )
                    # Revert to previous status
                    obj.status = old_status or 'REQUESTED'
                    return super().save_model(request, obj, form, change)
                    
                elif conflict_type == 'special_reservation':
                    conflict_detail = (f"{conflict.source} to {conflict.destination}, "
                                     f"{conflict.departure_time.strftime('%Y-%m-%d %H:%M')} to "
                                     f"{conflict.estimated_arrival_time.strftime('%Y-%m-%d %H:%M')}")
                    messages.error(
                        request,
                        f"Cannot approve: Vehicle is already reserved for another special trip: {conflict_detail}"
                    )
                    # Revert to previous status
                    obj.status = old_status or 'REQUESTED'
                    return super().save_model(request, obj, form, change)
            
            # If no conflicts, update vehicle status to RESERVED
            obj.vehicle.status = 'RESERVED'
            obj.vehicle.save(update_fields=['status'])
            messages.success(request, f"Vehicle {obj.vehicle.name} status updated to RESERVED.")
            
        # If status is changing from APPROVED to something else, update vehicle status back to ACTIVE
        elif old_status == 'APPROVED' and obj.status != 'APPROVED':
            obj.vehicle.status = 'ACTIVE'
            obj.vehicle.save(update_fields=['status'])
            messages.success(request, f"Vehicle {obj.vehicle.name} status updated to ACTIVE.")
            
        # Save the special reservation
        super().save_model(request, obj, form, change)

@admin.register(SeatAvailability)
class SeatAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'seat', 'status')
    list_filter = ('status',)
    search_fields = ('schedule__vehicle__name', 'seat__row_number', 'seat__seat_group')
    
@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Dashboard
    This doesn't actually manage a model, it just provides a link to the dashboard
    """
    # Empty changelist to prevent errors
    def get_queryset(self, request):
        return Dashboard.objects.none()
    
    # Redirect to the dashboard view
    def changelist_view(self, request, extra_context=None):
        from django.shortcuts import redirect
        from django.urls import reverse
        return redirect(reverse('admin_dashboard'))
    