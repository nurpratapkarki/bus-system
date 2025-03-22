from django.core.management.base import BaseCommand
from bus_management.models import BusType

class Command(BaseCommand):
    help = 'Initialize bus types for the system'

    def handle(self, *args, **options):
        # Define default bus types
        bus_types = [
            {
                'name': 'Air Conditioned',
                'description': 'Comfortable bus with air conditioning',
                'default_rows': 15,
                'default_columns': 2,
                'rate_per_km': 3.50,
                'min_price': 200.00,
                'has_ac': True,
                'has_wifi': True,
                'has_entertainment': True,
                'has_charging_ports': True,
                'has_reclining_seats': True,
            },
            {
                'name': 'Non Air Conditioned',
                'description': 'Standard bus without air conditioning',
                'default_rows': 16,
                'default_columns': 2, 
                'rate_per_km': 2.00,
                'min_price': 150.00,
                'has_ac': False,
                'has_wifi': False,
                'has_entertainment': False,
                'has_charging_ports': False,
                'has_reclining_seats': False,
            },
            {
                'name': 'Deluxe',
                'description': 'Premium bus with extra amenities',
                'default_rows': 12,
                'default_columns': 2,
                'rate_per_km': 4.50,
                'min_price': 300.00,
                'has_ac': True,
                'has_wifi': True,
                'has_entertainment': True,
                'has_charging_ports': True,
                'has_reclining_seats': True,
            },
            {
                'name': 'Super Deluxe',
                'description': 'Ultra premium bus with luxury features',
                'default_rows': 10,
                'default_columns': 2,
                'rate_per_km': 6.00,
                'min_price': 400.00,
                'has_ac': True,
                'has_wifi': True,
                'has_entertainment': True,
                'has_charging_ports': True,
                'has_reclining_seats': True,
            },
        ]
        
        # Create bus types
        created_count = 0
        for bus_type_data in bus_types:
            bus_type, created = BusType.objects.get_or_create(
                name=bus_type_data['name'],
                defaults=bus_type_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created bus type: {bus_type.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Bus type already exists: {bus_type.name}'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} bus types')) 