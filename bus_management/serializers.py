from rest_framework import serializers
from .models import (
    Vehicle, Route, Schedule, Seat, Customer, Offer,
    Ticket, SpecialReservation, SeatAvailability, VehicleType, VehicleSubtype
)


class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class VehicleSubtypeSerializer(serializers.ModelSerializer):
    vehicle_type_name = serializers.CharField(source='vehicle_type.name', read_only=True)
    
    class Meta:
        model = VehicleSubtype
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class VehicleSerializer(serializers.ModelSerializer):
    capacity = serializers.IntegerField(read_only=True)
    vehicle_subtype_details = VehicleSubtypeSerializer(source='vehicle_subtype', read_only=True)
    
    class Meta:
        model = Vehicle
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'capacity', 'vehicle_subtype_details')


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at')


class SeatSerializer(serializers.ModelSerializer):
    seat_number = serializers.CharField(read_only=True)
    
    class Meta:
        model = Seat
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'seat_number')


class ScheduleSerializer(serializers.ModelSerializer):
    vehicle_details = VehicleSerializer(source='vehicle', read_only=True)
    route_details = RouteSerializer(source='route', read_only=True)
    
    class Meta:
        model = Schedule
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'vehicle_details', 'route_details')


class SeatAvailabilitySerializer(serializers.ModelSerializer):
    seat_details = SeatSerializer(source='seat', read_only=True)
    
    class Meta:
        model = SeatAvailability
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'seat_details')


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 
                 'phone_number', 'verification_status', 'is_active',
                 'date_joined', 'last_login', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at', 'date_joined', 'last_login')
        extra_kwargs = {
            'password': {'write_only': True}
        }


class OfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'usage_count')


class TicketSerializer(serializers.ModelSerializer):
    customer_details = CustomerSerializer(source='customer', read_only=True)
    schedule_details = ScheduleSerializer(source='schedule', read_only=True)
    seat_details = SeatSerializer(source='seat', read_only=True)
    
    class Meta:
        model = Ticket
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 'booking_time', 
                           'customer_details', 'schedule_details', 'seat_details')


class SpecialReservationSerializer(serializers.ModelSerializer):
    customer_details = CustomerSerializer(source='customer', read_only=True)
    vehicle_details = VehicleSerializer(source='vehicle', read_only=True)
    
    class Meta:
        model = SpecialReservation
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'updated_at', 
                           'customer_details', 'vehicle_details')


# Registration Serializer
class CustomerRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    password2 = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    
    class Meta:
        model = Customer
        fields = ('username', 'password', 'password2', 'email', 'first_name', 'last_name', 'phone_number')
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        
        customer = Customer.objects.create(**validated_data)
        customer.set_password(password)
        customer.save()
        
        return customer