from django.core.management.base import BaseCommand
from django.utils import timezone
import random
from datetime import timedelta
import uuid

from bus_management.models import (
    Bus, Route, Schedule, Seat, Customer, Offer,
    Ticket, SpecialReservation, SeatAvailability, BusType, VehicleType, VehicleSubtype
)
from bus_management.utils import initialize_seat_availability, create_bus_with_seats, create_vehicle_with_seats


class Command(BaseCommand):
    help = 'Seeds the database with sample data for testing'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting to seed database...'))
        
        # Create admin customer if it doesn't exist
        if not Customer.objects.filter(username='admin').exists():
            admin_customer = Customer(
                username='admin',
                email='admin@example.com',
                first_name='Admin',
                last_name='User',
                phone_number='555-ADMIN',
                verification_status='VERIFIED',
                is_active=True,
                date_joined=timezone.now()
            )
            admin_customer.set_password('adminpassword')
            admin_customer.save()
            self.stdout.write(self.style.SUCCESS('Admin customer created'))
        
        # Create test customers
        self.create_users_and_customers()
        
        # Create buses with seats
        self.create_buses()
        
        # Create routes
        self.create_routes()
        
        # Create schedules and seat availability
        self.create_schedules()
        
        # Create offers
        self.create_offers()
        
        # Create some tickets
        self.create_tickets()
        
        # Create some special reservations
        self.create_special_reservations()
        
        # Create vehicles
        self.create_vehicles()
        
        self.stdout.write(self.style.SUCCESS('Database seeding completed successfully!'))
    
    def create_users_and_customers(self):
        # Create 10 test customers directly (no Django User)
        for i in range(1, 11):
            username = f'user{i}'
            
            if not Customer.objects.filter(username=username).exists():
                # Create customer with hashed password
                customer = Customer(
                    username=username,
                    email=f'user{i}@example.com',
                    first_name=f'Test{i}',
                    last_name='User',
                    phone_number=f'555-{i:03d}-{i*1111}',
                    verification_status=random.choice(['UNVERIFIED', 'PENDING', 'VERIFIED']),
                    is_active=True,
                    date_joined=timezone.now()
                )
                # Set password (this will hash it)
                customer.set_password('password123')
                customer.save()
        
        self.stdout.write(self.style.SUCCESS('Created 10 test customers'))
    
    def create_buses(self):
        # Create bus types first
        bus_types = [
            {
                'name': 'AC Deluxe',
                'description': 'Air conditioned deluxe bus with reclining seats',
                'default_rows': 15,
                'default_columns': 2,
                'rate_per_km': 5.00,
                'min_price': 500.00,
                'has_ac': True,
                'has_wifi': True,
                'has_entertainment': True,
                'has_charging_ports': True,
                'has_reclining_seats': True,
                'bus_type_code': 'AC_DELUXE'
            },
            {
                'name': 'AC Standard',
                'description': 'Air conditioned standard bus',
                'default_rows': 15,
                'default_columns': 2,
                'rate_per_km': 4.00,
                'min_price': 400.00,
                'has_ac': True,
                'has_wifi': False,
                'has_entertainment': False,
                'has_charging_ports': True,
                'has_reclining_seats': False,
                'bus_type_code': 'AC'
            },
            {
                'name': 'Non-AC',
                'description': 'Standard non-air conditioned bus',
                'default_rows': 15,
                'default_columns': 2,
                'rate_per_km': 3.00,
                'min_price': 300.00,
                'has_ac': False,
                'has_wifi': False,
                'has_entertainment': False,
                'has_charging_ports': False,
                'has_reclining_seats': False,
                'bus_type_code': 'NON_AC'
            },
            {
                'name': 'Super Deluxe',
                'description': 'Premium bus with all amenities',
                'default_rows': 12,
                'default_columns': 2,
                'rate_per_km': 6.00,
                'min_price': 600.00,
                'has_ac': True,
                'has_wifi': True,
                'has_entertainment': True,
                'has_charging_ports': True,
                'has_reclining_seats': True,
                'bus_type_code': 'SUPER_DELUXE'
            }
        ]
        
        created_bus_types = []
        for bus_type_data in bus_types:
            bus_type, created = BusType.objects.get_or_create(
                bus_type_code=bus_type_data['bus_type_code'],
                defaults=bus_type_data
            )
            created_bus_types.append(bus_type)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created bus type: {bus_type.name}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Using existing bus type: {bus_type.name}'))
        
        # Create 5 buses with different types
        for i in range(1, 6):
            bus_type = random.choice(created_bus_types)
            capacity = random.choice([30, 40, 50, 60])
            
            # The capacity will be converted to row_count and has_back_row in create_bus_with_seats
            create_bus_with_seats(
                name=f'Bus {i}',
                registration_number=f'REG-{i:03d}-{random.randint(1000, 9999)}',
                capacity=capacity,  # This function handles the conversion
                bus_type_model=bus_type
            )
        
        self.stdout.write(self.style.SUCCESS('Created 5 buses with seats'))
    
    def create_routes(self):
        # Create 10 routes between different cities
        cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 
                 'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'San Jose']
        
        for i in range(10):
            source = cities[i]
            destination = cities[(i + 1) % 10]  # Circular routes
            distance = random.randint(50, 500)
            duration = distance * 1.2  # Rough estimate: 1.2 minutes per km
            
            Route.objects.create(
                name=f'{source} to {destination}',
                source=source,
                destination=destination,
                distance_km=distance,
                estimated_duration_minutes=int(duration)
            )
        
        self.stdout.write(self.style.SUCCESS('Created 10 routes'))
    
    def create_schedules(self):
        # Create schedules for the next 7 days
        buses = list(Bus.objects.all())
        routes = list(Route.objects.all())
        
        now = timezone.now()
        
        for day in range(7):
            for i in range(5):  # 5 schedules per day
                bus = random.choice(buses)
                route = random.choice(routes)
                
                # Random departure time during the day
                hour = random.randint(6, 20)
                minute = random.choice([0, 15, 30, 45])
                
                departure_time = now.replace(hour=hour, minute=minute) + timedelta(days=day)
                
                # Calculate arrival time based on route duration
                duration_minutes = route.estimated_duration_minutes
                arrival_time = departure_time + timedelta(minutes=duration_minutes)
                
                # Random base price based on distance
                base_price = route.distance_km * random.uniform(0.8, 1.2)
                
                schedule = Schedule.objects.create(
                    bus=bus,
                    route=route,
                    departure_time=departure_time,
                    arrival_time=arrival_time,
                    status='SCHEDULED',
                    base_price=round(base_price, 2)
                )
                
                # Initialize seat availability for this schedule
                initialize_seat_availability(schedule)
        
        self.stdout.write(self.style.SUCCESS('Created schedules for the next 7 days with seat availability'))
    
    def create_offers(self):
        # Create 5 different offers
        now = timezone.now()
        
        # Percentage discount
        Offer.objects.create(
            code='SAVE20',
            description='20% off on all tickets',
            discount_type='PERCENTAGE',
            discount_value=20,
            min_purchase_amount=50,
            max_discount_amount=200,
            valid_from=now,
            valid_until=now + timedelta(days=30),
            usage_limit=100,
            is_active=True
        )
        
        # Fixed amount discount
        Offer.objects.create(
            code='FLAT50',
            description='$50 off on tickets above $200',
            discount_type='FIXED',
            discount_value=50,
            min_purchase_amount=200,
            valid_from=now,
            valid_until=now + timedelta(days=15),
            usage_limit=50,
            is_active=True
        )
        
        # Weekend special
        Offer.objects.create(
            code='WEEKEND25',
            description='25% off on weekend trips',
            discount_type='PERCENTAGE',
            discount_value=25,
            min_purchase_amount=100,
            max_discount_amount=150,
            valid_from=now,
            valid_until=now + timedelta(days=60),
            usage_limit=200,
            is_active=True
        )
        
        # New user discount
        Offer.objects.create(
            code='NEWUSER',
            description='15% off for new users',
            discount_type='PERCENTAGE',
            discount_value=15,
            min_purchase_amount=0,
            max_discount_amount=100,
            valid_from=now,
            valid_until=now + timedelta(days=90),
            is_active=True
        )
        
        # Special route discount
        Offer.objects.create(
            code='SPECIAL10',
            description='10% off on special routes',
            discount_type='PERCENTAGE',
            discount_value=10,
            min_purchase_amount=75,
            valid_from=now,
            valid_until=now + timedelta(days=45),
            usage_limit=150,
            is_active=True
        )
        
        self.stdout.write(self.style.SUCCESS('Created 5 offers'))
    
    def create_tickets(self):
        # Create some sample tickets
        customers = list(Customer.objects.all())
        schedules = list(Schedule.objects.all())
        offers = list(Offer.objects.all())
        
        for _ in range(20):
            customer = random.choice(customers)
            schedule = random.choice(schedules)
            
            # Find available seats for this schedule
            available_seats = SeatAvailability.objects.filter(
                schedule=schedule,
                status='AVAILABLE'
            )
            
            if not available_seats.exists():
                continue
                
            seat_availability = random.choice(available_seats)
            seat = seat_availability.seat
            
            # Decide if we'll use an offer
            use_offer = random.choice([True, False])
            offer = random.choice(offers) if use_offer else None
            
            base_price = schedule.base_price
            discount_amount = 0
            
            if offer:
                if offer.discount_type == 'PERCENTAGE':
                    discount_amount = base_price * (offer.discount_value / 100)
                    if offer.max_discount_amount and discount_amount > offer.max_discount_amount:
                        discount_amount = offer.max_discount_amount
                else:  # FIXED
                    discount_amount = offer.discount_value
                    if discount_amount > base_price:
                        discount_amount = base_price
            
            final_price = base_price - discount_amount
            
            # Create the ticket
            ticket = Ticket.objects.create(
                customer=customer,
                schedule=schedule,
                seat=seat,
                base_price=base_price,
                discount_amount=discount_amount,
                final_price=final_price,
                offer=offer,
                status=random.choice(['RESERVED', 'CONFIRMED', 'CANCELLED', 'COMPLETED'])
            )
            
            # Update seat availability
            if ticket.status in ['RESERVED', 'CONFIRMED']:
                seat_availability.status = 'BOOKED'
                seat_availability.save()
        
        self.stdout.write(self.style.SUCCESS('Created sample tickets'))
    
    def create_special_reservations(self):
        # Create some sample special reservations
        customers = list(Customer.objects.all())
        buses = list(Bus.objects.all())
        
        cities = ['Boston', 'Seattle', 'Miami', 'Denver', 'Atlanta', 
                 'Nashville', 'Portland', 'Las Vegas', 'Austin', 'Orlando']
        
        for _ in range(10):
            customer = random.choice(customers)
            bus = random.choice(buses)
            
            source = random.choice(cities)
            destination = random.choice([city for city in cities if city != source])
            
            distance_km = random.randint(100, 800)
            
            # Random departure time in the next 30 days
            days_ahead = random.randint(1, 30)
            hour = random.randint(6, 20)
            minute = random.choice([0, 15, 30, 45])
            
            departure_time = timezone.now().replace(hour=hour, minute=minute) + timedelta(days=days_ahead)
            
            # Calculate arrival time
            avg_speed = 60  # km/h
            duration_hours = distance_km / avg_speed
            duration_minutes = int(duration_hours * 60)
            estimated_arrival_time = departure_time + timedelta(minutes=duration_minutes)
            
            # Calculate price components
            base_price = distance_km * 5  # $5 per km
            
            # Distance surcharge
            distance_surcharge = 0
            if distance_km > 200:
                distance_surcharge = -base_price * 0.1  # 10% discount for long trips
            
            # Time surcharge
            time_surcharge = 0
            hour = departure_time.hour
            if 6 <= hour <= 9 or 16 <= hour <= 19:  # Peak hours
                time_surcharge = base_price * 0.2  # 20% extra for peak hours
            
            # Demand surcharge (random for demo)
            demand_surcharge = base_price * random.uniform(0, 0.15)
            
            # Final price
            final_price = base_price + distance_surcharge + time_surcharge + demand_surcharge
            
            # Create the special reservation
            SpecialReservation.objects.create(
                customer=customer,
                bus=bus,
                source=source,
                destination=destination,
                distance_km=distance_km,
                departure_time=departure_time,
                estimated_arrival_time=estimated_arrival_time,
                base_price=round(base_price, 2),
                distance_surcharge=round(distance_surcharge, 2),
                time_surcharge=round(time_surcharge, 2),
                demand_surcharge=round(demand_surcharge, 2),
                final_price=round(final_price, 2),
                status=random.choice(['REQUESTED', 'APPROVED', 'REJECTED', 'CANCELLED', 'COMPLETED'])
            )
        
        self.stdout.write(self.style.SUCCESS('Created sample special reservations'))
    
    def create_vehicles(self):
        # Create vehicle types first
        vehicle_types = [
            {
                'name': 'Bus',
                'description': 'Large passenger vehicle with multiple rows of seats',
            },
            {
                'name': 'Van',
                'description': 'Medium-sized passenger vehicle with flexible seating',
            },
            {
                'name': 'Car',
                'description': 'Small passenger vehicle with limited seating',
            },
        ]
        
        created_vehicle_types = []
        for vehicle_type_data in vehicle_types:
            vehicle_type, created = VehicleType.objects.get_or_create(
                name=vehicle_type_data['name'],
                defaults=vehicle_type_data
            )
            created_vehicle_types.append(vehicle_type)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created vehicle type: {vehicle_type.name}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Using existing vehicle type: {vehicle_type.name}'))
        
        # Create vehicle subtypes
        vehicle_subtypes = [
            {
                'name': 'AC Deluxe Bus',
                'description': 'Air conditioned deluxe bus with reclining seats',
                'vehicle_type': 'Bus',
                'default_rows': 15,
                'default_columns': 2,
                'rate_per_km': 5.00,
                'min_price': 500.00,
                'has_ac': True,
                'has_wifi': True,
                'has_entertainment': True,
                'has_charging_ports': True,
                'has_reclining_seats': True,
                'subtype_code': 'BUS_AC_DELUXE'
            },
            {
                'name': 'AC Standard Bus',
                'description': 'Air conditioned standard bus',
                'vehicle_type': 'Bus',
                'default_rows': 15,
                'default_columns': 2,
                'rate_per_km': 4.00,
                'min_price': 400.00,
                'has_ac': True,
                'has_wifi': False,
                'has_entertainment': False,
                'has_charging_ports': True,
                'has_reclining_seats': False,
                'subtype_code': 'BUS_AC_STANDARD'
            },
            {
                'name': 'Non-AC Bus',
                'description': 'Standard non-air conditioned bus',
                'vehicle_type': 'Bus',
                'default_rows': 15,
                'default_columns': 2,
                'rate_per_km': 3.00,
                'min_price': 300.00,
                'has_ac': False,
                'has_wifi': False,
                'has_entertainment': False,
                'has_charging_ports': False,
                'has_reclining_seats': False,
                'subtype_code': 'BUS_NON_AC'
            },
            {
                'name': 'Luxury Van',
                'description': 'Premium van with comfortable seating',
                'vehicle_type': 'Van',
                'default_rows': 5,
                'default_columns': 2,
                'rate_per_km': 4.50,
                'min_price': 350.00,
                'has_ac': True,
                'has_wifi': True,
                'has_entertainment': True,
                'has_charging_ports': True,
                'has_reclining_seats': True,
                'subtype_code': 'VAN_LUXURY'
            },
            {
                'name': 'Standard Van',
                'description': 'Standard van with basic amenities',
                'vehicle_type': 'Van',
                'default_rows': 5,
                'default_columns': 2,
                'rate_per_km': 3.50,
                'min_price': 250.00,
                'has_ac': True,
                'has_wifi': False,
                'has_entertainment': False,
                'has_charging_ports': True,
                'has_reclining_seats': False,
                'subtype_code': 'VAN_STANDARD'
            },
            {
                'name': 'Luxury Car',
                'description': 'Premium car with extra comfort',
                'vehicle_type': 'Car',
                'default_rows': 2,
                'default_columns': 2,
                'rate_per_km': 4.00,
                'min_price': 300.00,
                'has_ac': True,
                'has_wifi': True,
                'has_entertainment': True,
                'has_charging_ports': True,
                'has_reclining_seats': True,
                'subtype_code': 'CAR_LUXURY'
            },
            {
                'name': 'Standard Car',
                'description': 'Standard car with basic features',
                'vehicle_type': 'Car',
                'default_rows': 2,
                'default_columns': 2,
                'rate_per_km': 3.00,
                'min_price': 200.00,
                'has_ac': True,
                'has_wifi': False,
                'has_entertainment': False,
                'has_charging_ports': True,
                'has_reclining_seats': False,
                'subtype_code': 'CAR_STANDARD'
            },
        ]
        
        created_subtypes = []
        for subtype_data in vehicle_subtypes:
            vehicle_type = next(vt for vt in created_vehicle_types if vt.name == subtype_data['vehicle_type'])
            subtype_data.pop('vehicle_type')  # Remove vehicle_type from data before creating
            
            subtype, created = VehicleSubtype.objects.get_or_create(
                subtype_code=subtype_data['subtype_code'],
                defaults={**subtype_data, 'vehicle_type': vehicle_type}
            )
            created_subtypes.append(subtype)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created vehicle subtype: {subtype.name}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Using existing vehicle subtype: {subtype.name}'))
        
        # Create 5 vehicles with different types
        for i in range(1, 6):
            subtype = random.choice(created_subtypes)
            capacity = random.choice([30, 40, 50, 60])
            
            # The capacity will be converted to row_count and has_back_row in create_vehicle_with_seats
            create_vehicle_with_seats(
                name=f'Vehicle {i}',
                registration_number=f'REG-{i:03d}-{random.randint(1000, 9999)}',
                capacity=capacity,  # This function handles the conversion
                vehicle_subtype=subtype
            )
        
        self.stdout.write(self.style.SUCCESS('Created 5 vehicles with seats')) 