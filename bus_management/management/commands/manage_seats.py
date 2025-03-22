from django.core.management.base import BaseCommand, CommandError
from bus_management.models import Bus, Schedule, Seat, SeatAvailability
import uuid

class Command(BaseCommand):
    help = 'Manage seats and seat availability for buses and schedules'

    def add_arguments(self, parser):
        # Create subcommands
        subparsers = parser.add_subparsers(dest='command', help='Command to run')
        
        # Command to create seats for a bus
        create_seats = subparsers.add_parser('create_seats', help='Create seats for a bus')
        create_seats.add_argument('bus_id', type=str, help='Bus ID')
        
        # Command to initialize seat availability for a schedule
        init_availability = subparsers.add_parser('init_availability', help='Initialize seat availability for a schedule')
        init_availability.add_argument('schedule_id', type=str, help='Schedule ID')
        
        # Command to update seat status
        update_seat = subparsers.add_parser('update_seat', help='Update seat status')
        update_seat.add_argument('schedule_id', type=str, help='Schedule ID')
        update_seat.add_argument('seat_id', type=str, help='Seat ID')
        update_seat.add_argument('status', type=str, choices=['AVAILABLE', 'RESERVED', 'BOOKED', 'UNAVAILABLE'], help='New status')
        
        # Command to list seats for a bus
        list_seats = subparsers.add_parser('list_seats', help='List seats for a bus')
        list_seats.add_argument('bus_id', type=str, help='Bus ID')
        
        # Command to list seat availability for a schedule
        list_availability = subparsers.add_parser('list_availability', help='List seat availability for a schedule')
        list_availability.add_argument('schedule_id', type=str, help='Schedule ID')
        list_availability.add_argument('--status', type=str, choices=['AVAILABLE', 'RESERVED', 'BOOKED', 'UNAVAILABLE'], help='Filter by status')
        
        # Command to update bus configuration
        update_bus = subparsers.add_parser('update_bus', help='Update bus seating configuration')
        update_bus.add_argument('bus_id', type=str, help='Bus ID')
        update_bus.add_argument('--row_count', type=int, help='Number of rows')
        update_bus.add_argument('--has_back_row', type=bool, help='Whether the bus has a back row of 5 seats')
        update_bus.add_argument('--regenerate', action='store_true', help='Force regeneration of seats')

    def handle(self, *args, **options):
        command = options['command']
        
        if command == 'create_seats':
            self.create_seats(options['bus_id'])
        elif command == 'init_availability':
            self.init_availability(options['schedule_id'])
        elif command == 'update_seat':
            self.update_seat(options['schedule_id'], options['seat_id'], options['status'])
        elif command == 'list_seats':
            self.list_seats(options['bus_id'])
        elif command == 'list_availability':
            self.list_availability(options['schedule_id'], options.get('status'))
        elif command == 'update_bus':
            self.update_bus(
                options['bus_id'], 
                options.get('row_count'), 
                options.get('has_back_row'),
                options.get('regenerate', False)
            )
        else:
            self.stdout.write(self.style.ERROR("Please specify a command"))
            return
    
    def create_seats(self, bus_id):
        """Create seats for a bus"""
        try:
            bus = Bus.objects.get(id=bus_id)
            
            # Check if bus already has seats
            existing_seats = Seat.objects.filter(bus=bus).count()
            if existing_seats > 0:
                self.stdout.write(
                    self.style.WARNING(f"Bus already has {existing_seats} seats. Use 'update_bus --regenerate' to recreate.")
                )
                return
            
            # Create seats for the bus
            seats = []
            
            # Create regular row seats (A and B groups)
            for row in range(1, bus.row_count + 1):
                # Group A - Window Side
                seats.append(
                    Seat(
                        bus=bus,
                        row_number=row,
                        seat_group='A',
                        seat_type='WINDOW',
                        position=None
                    )
                )
                
                # Group B - Aisle Side
                seats.append(
                    Seat(
                        bus=bus,
                        row_number=row,
                        seat_group='B',
                        seat_type='AISLE',
                        position=None
                    )
                )
            
            # Create back row if the bus has one
            if bus.has_back_row:
                for position in range(1, 6):  # 5 seats in the back row
                    seats.append(
                        Seat(
                            bus=bus,
                            row_number=0,  # Using 0 to indicate back row
                            seat_group='BACK',
                            seat_type='BACK',
                            position=position
                        )
                    )
            
            # Bulk create all seats
            Seat.objects.bulk_create(seats)
            self.stdout.write(
                self.style.SUCCESS(f"Created {len(seats)} seats for bus {bus.name}")
            )
            
        except Bus.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Bus with ID {bus_id} does not exist"))
    
    def init_availability(self, schedule_id):
        """Initialize seat availability for a schedule"""
        try:
            schedule = Schedule.objects.get(id=schedule_id)
            
            # Check if schedule already has seat availability records
            existing_records = SeatAvailability.objects.filter(schedule=schedule).count()
            if existing_records > 0:
                self.stdout.write(
                    self.style.WARNING(f"Schedule already has {existing_records} seat availability records")
                )
                return
            
            # Get all seats for this bus
            bus = schedule.bus
            seats = Seat.objects.filter(bus=bus)
            
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
            SeatAvailability.objects.bulk_create(seat_availabilities)
            
            # Count how many records were created
            created_records = SeatAvailability.objects.filter(schedule=schedule).count()
            self.stdout.write(
                self.style.SUCCESS(f"Created {created_records} seat availability records for schedule {schedule}")
            )
            
        except Schedule.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Schedule with ID {schedule_id} does not exist"))
    
    def update_seat(self, schedule_id, seat_id, status):
        """Update seat status"""
        try:
            seat_availability = SeatAvailability.objects.get(
                schedule_id=schedule_id,
                seat_id=seat_id
            )
            
            old_status = seat_availability.status
            seat_availability.status = status
            seat_availability.save()
            
            self.stdout.write(
                self.style.SUCCESS(f"Updated seat {seat_availability.seat.seat_number} status from {old_status} to {status}")
            )
            
        except SeatAvailability.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Seat availability record for schedule {schedule_id} and seat {seat_id} does not exist")
            )
    
    def list_seats(self, bus_id):
        """List seats for a bus"""
        try:
            bus = Bus.objects.get(id=bus_id)
            seats = Seat.objects.filter(bus=bus).order_by('row_number', 'seat_group', 'position')
            
            if not seats.exists():
                self.stdout.write(self.style.WARNING(f"No seats found for bus {bus.name}"))
                return
            
            self.stdout.write(self.style.SUCCESS(f"Seats for bus {bus.name} (ID: {bus.id}):"))
            self.stdout.write("=" * 70)
            self.stdout.write(f"{'ID':<36} | {'Seat #':<6} | {'Row':<4} | {'Group':<5} | {'Position':<8} | {'Type':<10}")
            self.stdout.write("-" * 70)
            
            for seat in seats:
                position = seat.position if seat.position is not None else '-'
                self.stdout.write(
                    f"{str(seat.id):<36} | {seat.seat_number:<6} | {seat.row_number:<4} | {seat.seat_group:<5} | {position:<8} | {seat.seat_type:<10}"
                )
            
            self.stdout.write(f"\nTotal: {seats.count()} seats")
            
            # Group by type for summary
            seat_types = {}
            for seat in seats:
                if seat.seat_type not in seat_types:
                    seat_types[seat.seat_type] = 0
                seat_types[seat.seat_type] += 1
                
            self.stdout.write("\nSeat Types:")
            for seat_type, count in seat_types.items():
                self.stdout.write(f"- {seat_type}: {count} seats")
            
        except Bus.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Bus with ID {bus_id} does not exist"))
    
    def list_availability(self, schedule_id, status=None):
        """List seat availability for a schedule"""
        try:
            schedule = Schedule.objects.get(id=schedule_id)
            query = SeatAvailability.objects.filter(schedule=schedule)
            
            if status:
                query = query.filter(status=status)
                
            availabilities = query.order_by('seat__row_number', 'seat__seat_group', 'seat__position')
            
            if not availabilities.exists():
                self.stdout.write(self.style.WARNING(f"No seat availability records found for schedule {schedule}"))
                return
            
            self.stdout.write(self.style.SUCCESS(f"Seat availability for schedule {schedule} (ID: {schedule.id}):"))
            self.stdout.write("=" * 70)
            self.stdout.write(f"{'Seat #':<6} | {'Row':<4} | {'Group':<5} | {'Position':<8} | {'Status':<10}")
            self.stdout.write("-" * 70)
            
            for availability in availabilities:
                seat = availability.seat
                position = seat.position if seat.position is not None else '-'
                self.stdout.write(
                    f"{seat.seat_number:<6} | {seat.row_number:<4} | {seat.seat_group:<5} | {position:<8} | {availability.status:<10}"
                )
            
            self.stdout.write(f"\nTotal: {availabilities.count()} seat records")
            
            # Show statistics
            status_counts = {}
            for availability in availabilities:
                if availability.status not in status_counts:
                    status_counts[availability.status] = 0
                status_counts[availability.status] += 1
            
            self.stdout.write("\nStatus breakdown:")
            for status, count in status_counts.items():
                self.stdout.write(f"- {status}: {count}")
            
        except Schedule.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Schedule with ID {schedule_id} does not exist"))
    
    def update_bus(self, bus_id, row_count=None, has_back_row=None, regenerate=False):
        """Update bus seating configuration"""
        try:
            bus = Bus.objects.get(id=bus_id)
            
            # Display current configuration
            self.stdout.write(f"Current bus configuration:")
            self.stdout.write(f"- Row count: {bus.row_count}")
            self.stdout.write(f"- Has back row: {bus.has_back_row}")
            self.stdout.write(f"- Total capacity: {bus.capacity}")
            
            # Count existing seats
            existing_seats = Seat.objects.filter(bus=bus).count()
            self.stdout.write(f"- Existing seats: {existing_seats}")
            
            # Update configuration if specified
            changed = False
            if row_count is not None and row_count != bus.row_count:
                bus.row_count = row_count
                changed = True
                self.stdout.write(f"Updated row count to {row_count}")
            
            if has_back_row is not None and has_back_row != bus.has_back_row:
                bus.has_back_row = has_back_row
                changed = True
                self.stdout.write(f"Updated has_back_row to {has_back_row}")
            
            if changed:
                bus.save()
                self.stdout.write(f"New total capacity: {bus.capacity}")
            
            # Regenerate seats if requested or if configuration changed
            if regenerate or (changed and existing_seats > 0):
                # Delete existing seats
                Seat.objects.filter(bus=bus).delete()
                
                # Create seats based on new configuration
                self.create_seats(bus_id)
                
                # Update seat availability for all schedules using this bus
                schedules = Schedule.objects.filter(bus=bus)
                for schedule in schedules:
                    # Delete existing availability records
                    SeatAvailability.objects.filter(schedule=schedule).delete()
                    # Create new availability records
                    self.init_availability(str(schedule.id))
            
            if not changed and not regenerate:
                self.stdout.write(self.style.WARNING("No changes made. Use --regenerate to force seat regeneration."))
            
        except Bus.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Bus with ID {bus_id} does not exist"))