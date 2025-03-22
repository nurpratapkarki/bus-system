from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from django.contrib.auth.hashers import make_password, check_password


class VehicleType(models.Model):
    """Model representing different types of vehicles (e.g., vechile, Van, Car, etc.)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Vehicle Type'
        verbose_name_plural = 'Vehicle Types'
        ordering = ['name']


class VehicleSubtype(models.Model):
    """Model representing different subtypes of vehicles with their configurations and pricing."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.CASCADE, related_name='subtypes')
    
    # Default seating configuration
    default_rows = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    default_columns = models.PositiveIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    
    # Pricing information
    rate_per_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Base rate per kilometer"
    )
    min_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Minimum price regardless of distance"
    )
    
    # Additional features
    has_ac = models.BooleanField(default=True)
    has_wifi = models.BooleanField(default=False)
    has_entertainment = models.BooleanField(default=False)
    has_charging_ports = models.BooleanField(default=False)
    has_reclining_seats = models.BooleanField(default=False)
    
    # Reference to the vehicle subtype code
    subtype_code = models.CharField(max_length=20, unique=True, help_text="Code used in Vehicle.subtype field")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.vehicle_type.name} - {self.name}"
    
    class Meta:
        verbose_name = 'Vehicle Subtype'
        verbose_name_plural = 'Vehicle Subtypes'
        ordering = ['vehicle_type', 'name']


class Vehicle(models.Model):
    """Model representing a vehicle in the system."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    registration_number = models.CharField(max_length=50, unique=True)
    
    # Replace simple capacity with more detailed seat layout configuration
    row_count = models.PositiveIntegerField(help_text="Number of regular rows (excluding back row)")
    has_back_row = models.BooleanField(default=True, help_text="Whether the vehicle has a back row of 5 seats")
   
    vehicle_subtype = models.ForeignKey('VehicleSubtype', on_delete=models.CASCADE, 
                                      related_name='vehicles', verbose_name="Vehicle Subtype")
    
    # Vehicle status
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('INACTIVE', 'Inactive'),
        ('RESERVED', 'Specially Reserved'),  # Added status for special reservations
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def capacity(self):
        """Calculate total seat capacity based on row count and back row"""
        regular_seats = self.row_count * 2  # 2 seats per row (A and B)
        back_row_seats = 5 if self.has_back_row else 0
        return regular_seats + back_row_seats
    
    def is_available(self, start_time, end_time, exclude_reservation_id=None):
        """
        Check if the vehicle is available during the specified time period
        
        Args:
            start_time: Datetime for the start of the period to check
            end_time: Datetime for the end of the period to check
            exclude_reservation_id: Optional ID of a reservation to exclude from the check
                                    (useful when updating an existing reservation)
        
        Returns:
            tuple: (is_available, conflicting_item, conflict_type)
                - is_available: Boolean indicating if the vehicle is available
                - conflicting_item: The conflicting Schedule or SpecialReservation object, if any
                - conflict_type: String indicating the type of conflict ('schedule' or 'special_reservation')
        """
        if self.status in ['MAINTENANCE', 'INACTIVE']:
            return False, None, 'vehicle_status'
        
        # Check for conflicts with regular schedules
        from django.db.models import Q
        
        # Schedule conflicts occur if:
        # 1. The schedule's departure time is between our start and end times, OR
        # 2. The schedule's arrival time is between our start and end times, OR
        # 3. Our start time is between the schedule's departure and arrival times
        schedule_conflicts = self.schedules.filter(
            Q(status__in=['SCHEDULED', 'DELAYED', 'IN_PROGRESS']) &
            (
                (Q(departure_time__gte=start_time) & Q(departure_time__lt=end_time)) |
                (Q(arrival_time__gt=start_time) & Q(arrival_time__lte=end_time)) |
                (Q(departure_time__lte=start_time) & Q(arrival_time__gte=end_time))
            )
        )
        
        if schedule_conflicts.exists():
            return False, schedule_conflicts.first(), 'schedule'
        
        # Check for conflicts with special reservations
        special_reservation_query = Q(
            status__in=['REQUESTED', 'APPROVED', 'IN_PROGRESS']
        ) & (
            (Q(departure_time__gte=start_time) & Q(departure_time__lt=end_time)) |
            (Q(estimated_arrival_time__gt=start_time) & Q(estimated_arrival_time__lte=end_time)) |
            (Q(departure_time__lte=start_time) & Q(estimated_arrival_time__gte=end_time))
        )
        
        # Exclude the current reservation if provided
        if exclude_reservation_id:
            special_reservation_query &= ~Q(id=exclude_reservation_id)
            
        special_conflicts = self.special_reservations.filter(special_reservation_query)
        
        if special_conflicts.exists():
            return False, special_conflicts.first(), 'special_reservation'
            
        return True, None, None
    
    def __str__(self):
        return f"{self.name} ({self.registration_number})"
    
    class Meta:
        verbose_name = 'Vehicle'
        verbose_name_plural = 'Vehicles'
        ordering = ['name']

class Route(models.Model):
    """Model representing a vehicle route."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2)
    estimated_duration_minutes = models.PositiveIntegerField()    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.source} to {self.destination}"

    class Meta:
        verbose_name = 'Route'
        verbose_name_plural = 'Routes'

class Schedule(models.Model):
    """Model representing a scheduled journey for a vehicle on a route."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='schedules')
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='schedules')
    
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    
    # Schedule status
    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
        ('DELAYED', 'Delayed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def calculate_base_price(self):
        """Calculate base price based on distance and rate_per_km"""
        vehicle_subtype = self.vehicle.vehicle_subtype
        if not vehicle_subtype or not self.route:
            return 0
        
        # Base calculation: Distance * Rate per km
        calculated_price = self.route.distance_km * vehicle_subtype.rate_per_km
        
        # Ensure minimum price is respected
        return max(calculated_price, vehicle_subtype.min_price)

    def save(self, *args, **kwargs):
        """Auto-set base price before saving"""
        self.base_price = self.calculate_base_price()
        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.vehicle.name} - {self.route.source} to {self.route.destination} on {self.departure_time.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        verbose_name = 'Schedule'
        verbose_name_plural = 'Schedules'

class Seat(models.Model):
    """Model representing a seat in a vehicle."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='seats')
    
    # Updated seat numbering system to match Nepali vechile layout
    # Format: row number + seat group (e.g., 1A, 1B, 2A, 2B)
    row_number = models.PositiveIntegerField()
    
    # Seat group (A or B) where A is window side, B is aisle side
    SEAT_GROUP_CHOICES = [
        ('A', 'Group A - Window Side'),
        ('B', 'Group B - Aisle Side'),
        ('BACK', 'Back Row'),
    ]
    seat_group = models.CharField(max_length=5, choices=SEAT_GROUP_CHOICES)
    
    # For back row seats, we use position (1-5 from left to right)
    position = models.PositiveIntegerField(null=True, blank=True)
    
    # Seat type (removed VIP and kept only standard seat types)
    SEAT_TYPE_CHOICES = [
        ('WINDOW', 'Window'),
        ('AISLE', 'Aisle'),
        ('BACK', 'Back Row'),
    ]
    seat_type = models.CharField(max_length=20, choices=SEAT_TYPE_CHOICES)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('vehicle', 'row_number', 'seat_group', 'position')
        verbose_name = 'Seat'
        verbose_name_plural = 'Seats'
    
    @property
    def seat_number(self):
        """Generate a formatted seat number like 1A, 2B, or BACK-1"""
        if self.seat_group == 'BACK':
            return f"BACK-{self.position}"
        return f"{self.row_number}{self.seat_group}"
    
    def __str__(self):
        return f"{self.vehicle.name} - Seat {self.seat_number}"

class Customer(models.Model):
    """Model representing a customer."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Remove User foreign key and add direct authentication fields
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=15)
    password = models.CharField(max_length=128)  # For storing hashed password
    
    # Customer verification status
    VERIFICATION_STATUS_CHOICES = [
        ('UNVERIFIED', 'Unverified'),
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
    ]
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='UNVERIFIED')
    
    # Additional fields for authentication
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    def set_password(self, raw_password):
        """Set the customer's password using Django's password hashing"""
        self.password = make_password(raw_password)
        
    def check_password(self, raw_password):
        """Check if the provided password matches the stored hash"""
        return check_password(raw_password, self.password)
    
    class Meta:
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

class Offer(models.Model):
    """Model representing promotional offers and coupons."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField()
    
    # Discount type
    DISCOUNT_TYPE_CHOICES = [
        ('PERCENTAGE', 'Percentage'),
        ('FIXED', 'Fixed Amount'),
    ]
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Limits
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Validity
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    
    # Usage limits
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.code} - {self.discount_type}: {self.discount_value}"

    class Meta:
        verbose_name = 'Offer'
        verbose_name_plural = 'Offers'

class Ticket(models.Model):
    """Model representing a ticket booking."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='tickets')
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='tickets')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, related_name='tickets')
    
    # Pricing details
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    offer = models.ForeignKey(Offer, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    
    # Ticket status
    STATUS_CHOICES = [
        ('RESERVED', 'Reserved'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='RESERVED')
    
    # Booking and cancellation details
    booking_time = models.DateTimeField(auto_now_add=True)
    cancellation_time = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('schedule', 'seat')
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
    
    def __str__(self):
        return f"Ticket {self.id} - {self.customer.first_name} {self.customer.last_name} - {self.schedule}"

class SpecialReservation(models.Model):
    """Model representing special custom destination reservations."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='special_reservations')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='special_reservations')
    
    # Custom journey details
    source = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Duration fields
    departure_time = models.DateTimeField()
    estimated_arrival_time = models.DateTimeField()
    return_time = models.DateTimeField(null=True, blank=True, help_text="For round trips, when the vehicle will return")
    duration_days = models.PositiveIntegerField(default=1, help_text="Number of days for the reservation")
    is_round_trip = models.BooleanField(default=False, help_text="Whether this is a round trip reservation")
    
    # Trip details
    trip_purpose = models.CharField(max_length=100, blank=True, help_text="Purpose of the trip (e.g., Tour, Picnic, Wedding)")
    passenger_count = models.PositiveIntegerField(default=1, help_text="Estimated number of passengers")
    has_multiple_stops = models.BooleanField(default=False, help_text="Whether the trip includes multiple stops")
    stops = models.TextField(blank=True, help_text="Comma-separated list of stops along the way")
    
    # Pricing factors
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    distance_surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    time_surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    demand_surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    multi_day_surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Extra charge for multi-day trips")
    season_factor = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, help_text="Multiplier based on high/low season")
    driver_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Daily allowance for driver(s)")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Payment tracking
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Initial deposit paid")
    deposit_paid_date = models.DateTimeField(null=True, blank=True)
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Remaining balance to be paid")
    is_fully_paid = models.BooleanField(default=False)
    
    # Reservation status
    STATUS_CHOICES = [
        ('REQUESTED', 'Requested'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='REQUESTED')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Special Reservation: {self.source} to {self.destination} on {self.departure_time.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        verbose_name = 'Special Reservation'
        verbose_name_plural = 'Special Reservations'
        
    def calculate_price(self):
        """Calculate the final price based on all factors"""
        # Base calculation from vehicle rate and distance
        if not hasattr(self, 'vehicle') or not self.vehicle or not self.distance_km:
            return 0
            
        vehicle_subtype = self.vehicle.vehicle_subtype
        base_price = float(self.distance_km) * float(vehicle_subtype.rate_per_km)
        
        # Apply minimum price check
        base_price = max(base_price, float(vehicle_subtype.min_price))
        
        # Apply multi-day factor
        base_price = base_price * self.duration_days
        
        # Add multi-day surcharge for overnight stays
        if self.duration_days > 1:
            multi_day_surcharge = float(self.driver_allowance) * (self.duration_days - 1)
            self.multi_day_surcharge = multi_day_surcharge
        else:
            self.multi_day_surcharge = 0
            
        # Apply season factor (e.g., 1.2 for high season, 0.9 for low season)
        base_price = base_price * float(self.season_factor)
        
        # Round trip calculation
        if self.is_round_trip:
            base_price = base_price * 1.8  # 20% discount on return journey
            
        # Set the base price
        self.base_price = base_price
        
        # Calculate final price
        final_price = (base_price + 
                      float(self.distance_surcharge) + 
                      float(self.time_surcharge) + 
                      float(self.demand_surcharge) + 
                      float(self.multi_day_surcharge) - 
                      float(self.discount_amount))
        
        # Calculate the balance
        if self.deposit_amount:
            self.balance_amount = final_price - float(self.deposit_amount)
            self.is_fully_paid = self.balance_amount <= 0
            
        return final_price
        
    def save(self, *args, **kwargs):
        """Update pricing before saving"""
        self.final_price = self.calculate_price()
        super().save(*args, **kwargs)

class SeatAvailability(models.Model):
    """Model tracking the real-time availability of seats for specific schedules."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='seat_availabilities')
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE, related_name='availabilities')
    
    # Availability status
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Reserved'),
        ('BOOKED', 'Booked'),
        ('UNAVAILABLE', 'Unavailable'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('schedule', 'seat')
        verbose_name = 'Seat Availability'
        verbose_name_plural = 'Seat Availabilities'
    
    def __str__(self):
        return f"{self.schedule} - Seat {self.seat.seat_number} ({self.status})"

class Dashboard(models.Model):
    """
    Dashboard model - just a placeholder for admin integration
    Used to create an admin view that will show the dashboard
    The model itself does nothing and no database table is created for it
    """
    name = models.CharField(max_length=255, default="Dashboard")
    
    class Meta:
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboard'
        # This prevents Django from creating a migration
        managed = False
        # Point to the auth_user table which definitely exists
        db_table = 'auth_user'
        
    def __str__(self):
        return self.name
