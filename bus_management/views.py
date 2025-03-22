from django.shortcuts import render
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime
from django.db.models import F, Case, When, Value, IntegerField
from django.utils.dateparse import parse_datetime

from .models import (
    Vehicle, Route, Schedule, Seat, Customer, Offer,
    Ticket, SpecialReservation, SeatAvailability, VehicleType, VehicleSubtype
)
from .serializers import (
    VehicleSerializer, RouteSerializer, ScheduleSerializer, SeatSerializer,
    CustomerSerializer, OfferSerializer, TicketSerializer,
    SpecialReservationSerializer, SeatAvailabilitySerializer,
    CustomerRegistrationSerializer, VehicleTypeSerializer, VehicleSubtypeSerializer
)


class VehicleTypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing vehicle types.
    """
    queryset = VehicleType.objects.all()
    serializer_class = VehicleTypeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'description']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]


class VehicleSubtypeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing vehicle subtypes.
    """
    queryset = VehicleSubtype.objects.all()
    serializer_class = VehicleSubtypeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['vehicle_type', 'has_ac', 'has_wifi', 'has_entertainment', 'has_charging_ports', 'has_reclining_seats']
    search_fields = ['name', 'description', 'subtype_code']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]


class VehicleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing vehicles.
    """
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['type', 'status', 'is_active', 'subtype']
    search_fields = ['name', 'registration_number', 'color']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'check_availability', 'available_vehicles', 'dashboard', 'dashboard_charts']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['post'])
    def check_availability(self, request, pk=None):
        """
        Check if a vehicle is available during a specific time period
        """
        vehicle = self.get_object()
        
        # Validate input parameters
        try:
            start_time = parse_datetime(request.data.get('start_time'))
            end_time = parse_datetime(request.data.get('end_time'))
            
            if not start_time or not end_time:
                return Response(
                    {"error": "Both start_time and end_time are required in ISO format (YYYY-MM-DDTHH:MM:SS)"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if start_time >= end_time:
                return Response(
                    {"error": "End time must be after start time"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Check vehicle availability
            is_available, conflict, conflict_type = vehicle.is_available(start_time, end_time)
            
            if is_available:
                return Response(
                    {"available": True, "message": "Vehicle is available for the specified time period"}
                )
            else:
                if conflict_type == 'vehicle_status':
                    message = f"Vehicle is not available due to its status: {vehicle.get_status_display()}"
                elif conflict_type == 'schedule':
                    message = (f"Vehicle is already scheduled for a regular route from "
                              f"{conflict.route.source} to {conflict.route.destination} "
                              f"({conflict.departure_time} to {conflict.arrival_time})")
                elif conflict_type == 'special_reservation':
                    message = (f"Vehicle is already reserved for a special trip from "
                              f"{conflict.source} to {conflict.destination} "
                              f"({conflict.departure_time} to {conflict.estimated_arrival_time})")
                else:
                    message = "Vehicle is not available for the specified time period"
                    
                return Response(
                    {"available": False, "message": message, "conflict_type": conflict_type},
                    status=status.HTTP_200_OK
                )
                
        except ValueError as e:
            return Response(
                {"error": f"Invalid date format: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except TypeError as e:
            return Response(
                {"error": f"Invalid parameter type: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except AttributeError as e:
            return Response(
                {"error": f"Attribute error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            # For unexpected errors
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in check_availability: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred while checking availability"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def available_vehicles(self, request):
        """
        Find all available vehicles for a specific time period
        """
        try:
            # Parse date parameters
            start_time = parse_datetime(request.query_params.get('start_time'))
            end_time = parse_datetime(request.query_params.get('end_time'))
            
            if not start_time or not end_time:
                return Response(
                    {"error": "Both start_time and end_time parameters are required in ISO format (YYYY-MM-DDThh:mm:ss)"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if start_time >= end_time:
                return Response(
                    {"error": "start_time must be before end_time"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Get optional filter parameters
            vehicle_type = request.query_params.get('vehicle_type')
            min_capacity = request.query_params.get('min_capacity')
            
            # Start with all vehicles
            queryset = Vehicle.objects.filter(is_active=True)
            
            # Apply optional filters
            if vehicle_type:
                queryset = queryset.filter(vehicle_type=vehicle_type)
                
            if min_capacity:
                try:
                    min_capacity = int(min_capacity)
                    queryset = queryset.filter(capacity__gte=min_capacity)
                except ValueError:
                    return Response(
                        {"error": "min_capacity must be a valid integer"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Filter out vehicles with conflicting schedules
            # Vehicles with schedules where: 
            # 1. The start time of the schedule is before the end time of our period AND
            # 2. The end time of the schedule is after the start time of our period
            conflicts_with_schedules = Schedule.objects.filter(
                Q(start_time__lt=end_time) & Q(end_time__gt=start_time),
                is_active=True
            ).values_list('vehicle_id', flat=True)
            
            # Filter out vehicles with conflicting special reservations
            # Similar logic as schedules
            conflicts_with_reservations = SpecialReservation.objects.filter(
                Q(start_time__lt=end_time) & Q(end_time__gt=start_time),
                status__in=['approved', 'pending'],
                vehicle__isnull=False
            ).values_list('vehicle_id', flat=True)
            
            # Exclude all vehicles with conflicts
            queryset = queryset.exclude(
                id__in=list(conflicts_with_schedules) + list(conflicts_with_reservations)
            )
            
            # Serialize and return the filtered list
            serializer = VehicleSerializer(queryset, many=True)
            return Response(serializer.data)
            
        except (ValueError, TypeError) as e:
            return Response(
                {"error": f"Invalid date format: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in available_vehicles: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred while finding available vehicles"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """
        Get dashboard statistics and data for the admin dashboard
        """
        from django.utils import timezone
        from django.db.models import Sum, Count, Q
        import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info("Dashboard API called")
        
        # Get current date in Nepal timezone
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        try:
            # Total vehicles count
            total_vehicles = Vehicle.objects.count()
            logger.info(f"Total vehicles: {total_vehicles}")
            
            # Total active routes count
            total_routes = Route.objects.filter(is_active=True).count()
            logger.info(f"Total active routes: {total_routes}")
            
            # Tickets sold today
            tickets_today = Ticket.objects.filter(
                created_at__date=today
            ).count()
            logger.info(f"Tickets sold today: {tickets_today}")
            
            # Total special reservations
            special_reservations = SpecialReservation.objects.count()
            logger.info(f"Total special reservations: {special_reservations}")
            
            # Recent special reservations
            recent_reservations_data = []
            recent_special_reservations = SpecialReservation.objects.all().order_by('-created_at')[:10]
            
            for reservation in recent_special_reservations:
                try:
                    reservation_data = {
                        'id': str(reservation.id),
                        'customer_name': str(reservation.customer) if reservation.customer else 'Anonymous',
                        'vehicle_name': str(reservation.vehicle) if reservation.vehicle else 'Not assigned',
                        'start_time': reservation.departure_time.isoformat() if reservation.departure_time else None,
                        'status': reservation.status,
                        'final_price': float(reservation.final_price) if reservation.final_price else 0,
                    }
                    recent_reservations_data.append(reservation_data)
                except Exception as e:
                    logger.error(f"Error processing reservation {reservation.id}: {str(e)}")
            
            logger.info(f"Processed {len(recent_reservations_data)} recent reservations")
            
            response_data = {
                'total_vehicles': total_vehicles,
                'total_routes': total_routes,
                'tickets_today': tickets_today,
                'special_reservations': special_reservations,
                'recent_reservations': recent_reservations_data
            }
            
            logger.info("Dashboard API completed successfully")
            return Response(response_data)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in dashboard API: {str(e)}")
            return Response(
                {"error": "An error occurred while retrieving dashboard data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='dashboard/charts')
    def dashboard_charts(self, request):
        """
        Get chart data for the admin dashboard
        """
        from django.utils import timezone
        from django.db.models import Count, Sum
        import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        logger.info("Dashboard charts API called")
        
        try:
            # Get current date in Nepal timezone
            today = timezone.now().date()
            
            # Revenue chart - last 7 days
            revenue_labels = []
            revenue_data = []
            
            for i in range(6, -1, -1):
                day = today - datetime.timedelta(days=i)
                day_name = day.strftime('%a')
                revenue_labels.append(day_name)
                
                # Calculate revenue for this day from tickets and special reservations
                day_revenue = 0
                
                # Revenue from tickets
                tickets_revenue = Ticket.objects.filter(
                    created_at__date=day
                ).aggregate(total=Sum('final_price'))['total'] or 0
                
                # Revenue from special reservations
                reservations_revenue = SpecialReservation.objects.filter(
                    deposit_paid_date=day
                ).aggregate(total=Sum('deposit_amount'))['total'] or 0
                
                day_revenue = float(tickets_revenue) + float(reservations_revenue)
                revenue_data.append(day_revenue)
                
                logger.info(f"Revenue for {day_name}: {day_revenue} (Tickets: {tickets_revenue}, Reservations: {reservations_revenue})")
            
            # Ticket distribution by type
            ticket_types = ['Regular', 'Special', 'Student', 'Senior', 'Group']
            ticket_counts = []
            
            # Regular tickets
            regular_count = Ticket.objects.filter(
                created_at__gte=today - datetime.timedelta(days=30)
            ).count()
            ticket_counts.append(regular_count)
            logger.info(f"Regular tickets in last 30 days: {regular_count}")
            
            # Special reservations
            special_count = SpecialReservation.objects.filter(
                created_at__gte=today - datetime.timedelta(days=30)
            ).count()
            ticket_counts.append(special_count)
            logger.info(f"Special reservations in last 30 days: {special_count}")
            
            # Other ticket types (placeholders)
            ticket_counts.extend([0, 0, 0])  # Student, Senior, Group tickets
            
            response_data = {
                'revenue_chart': {
                    'labels': revenue_labels,
                    'data': revenue_data
                },
                'ticket_distribution': {
                    'labels': ticket_types,
                    'data': ticket_counts
                }
            }
            
            logger.info("Dashboard charts API completed successfully")
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error in dashboard charts API: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return Response(
                {"error": "An error occurred while retrieving chart data"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RouteViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing routes.
    """
    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source', 'destination']
    search_fields = ['name', 'source', 'destination']
    ordering_fields = ['name', 'distance_km', 'estimated_duration_minutes']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]


class ScheduleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing schedules.
    """
    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'vehicle', 'route']
    search_fields = ['vehicle__name', 'route__name', 'route__source', 'route__destination']
    ordering_fields = ['departure_time', 'arrival_time', 'base_price']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def available_schedules(self, request):
        """Get all available future schedules"""
        now = timezone.now()
        schedules = Schedule.objects.filter(
            departure_time__gt=now,
            status='SCHEDULED'
        ).order_by('departure_time')
        
        source = request.query_params.get('source')
        if source:
            schedules = schedules.filter(route__source__icontains=source)
            
        destination = request.query_params.get('destination')
        if destination:
            schedules = schedules.filter(route__destination__icontains=destination)
        
        date = request.query_params.get('date')
        if date:
            schedules = schedules.filter(departure_time__date=date)
            
        serializer = self.get_serializer(schedules, many=True)
        return Response(serializer.data)


class SeatViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing seats.
    """
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['vehicle', 'seat_type']
    search_fields = ['seat_number', 'vehicle__name']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]


class SeatAvailabilityViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing seat availability.
    """
    queryset = SeatAvailability.objects.all()
    serializer_class = SeatAvailabilitySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['schedule', 'seat', 'status']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def available_seats(self, request):
        """Get all available seats for a specific schedule"""
        schedule_id = request.query_params.get('schedule_id')
        if not schedule_id:
            return Response(
                {"error": "Schedule ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        available_seats = SeatAvailability.objects.filter(
            schedule_id=schedule_id,
            status='AVAILABLE'
        )
        
        serializer = self.get_serializer(available_seats, many=True)
        return Response(serializer.data)


class CustomerViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing customers.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['verification_status', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone_number']
    
    def get_permissions(self):
        if self.action == 'me':
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get the current user's customer profile"""
        try:
            # We need to extract the customer_id from the token
            customer_id = request.auth.payload.get('customer_id')
            if not customer_id:
                return Response(
                    {"error": "Invalid authentication token"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
            customer = Customer.objects.get(id=customer_id)
            serializer = self.get_serializer(customer)
            return Response(serializer.data)
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class OfferViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing offers and coupons.
    """
    queryset = Offer.objects.all()
    serializer_class = OfferSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['discount_type', 'is_active']
    search_fields = ['code', 'description']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'validate_coupon']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['post'])
    def validate_coupon(self, request):
        """Validate a coupon code"""
        code = request.data.get('code')
        amount = request.data.get('amount')
        
        if not code or not amount:
            return Response(
                {"error": "Coupon code and amount are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = float(amount)
        except ValueError:
            return Response(
                {"error": "Amount must be a valid number"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            now = timezone.now()
            offer = Offer.objects.get(
                code=code,
                is_active=True,
                valid_from__lte=now,
                valid_until__gte=now,
                min_purchase_amount__lte=amount
            )
            
            if offer.usage_limit and offer.usage_count >= offer.usage_limit:
                return Response(
                    {"error": "This coupon has reached its usage limit"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            discount_amount = 0
            if offer.discount_type == 'PERCENTAGE':
                discount_amount = amount * (offer.discount_value / 100)
                if offer.max_discount_amount and discount_amount > offer.max_discount_amount:
                    discount_amount = offer.max_discount_amount
            else:  # FIXED
                discount_amount = offer.discount_value
                if discount_amount > amount:
                    discount_amount = amount
            
            return Response({
                "offer": self.get_serializer(offer).data,
                "discount_amount": discount_amount,
                "final_amount": amount - discount_amount
            })
            
        except Offer.DoesNotExist:
            return Response(
                {"error": "Invalid or expired coupon code"},
                status=status.HTTP_400_BAD_REQUEST
            )


class TicketViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing tickets.
    """
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'schedule', 'customer']
    search_fields = ['customer__username', 'customer__email', 'schedule__vehicle__name', 
                    'schedule__route__source', 'schedule__route__destination']
    ordering_fields = ['booking_time', 'final_price']
    
    def get_permissions(self):
        if self.action in ['create', 'my_tickets', 'cancel_ticket']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['list', 'retrieve', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
    
    def create(self, request, *args, **kwargs):
        """Create a new ticket booking"""
        try:
            # Extract customer_id from token
            customer_id = request.auth.payload.get('customer_id')
            if not customer_id:
                return Response(
                    {"error": "Invalid authentication token"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
            # Get customer
            customer = Customer.objects.get(id=customer_id)
            
            # Get schedule and seat
            schedule_id = request.data.get('schedule')
            seat_id = request.data.get('seat')
            
            if not schedule_id or not seat_id:
                return Response(
                    {"error": "Schedule and seat are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if there's already a ticket for this seat and schedule
            existing_ticket = Ticket.objects.filter(
                schedule_id=schedule_id,
                seat_id=seat_id,
                status__in=['RESERVED', 'CONFIRMED']  # Only active tickets
            ).exists()
            
            if existing_ticket:
                return Response(
                    {"error": "This seat is already booked"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check seat availability using select_for_update to prevent race conditions
            with transaction.atomic():
                try:
                    seat_availability = SeatAvailability.objects.select_for_update().get(
                        schedule_id=schedule_id,
                        seat_id=seat_id
                    )
                    
                    if seat_availability.status != 'AVAILABLE':
                        return Response(
                            {"error": "This seat is not available"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                        
                    # Get schedule for pricing
                    schedule = Schedule.objects.get(id=schedule_id)
                    base_price = schedule.base_price
                    
                    # Check for offer/coupon
                    offer_id = request.data.get('offer')
                    discount_amount = 0
                    offer = None
                    
                    if offer_id:
                        try:
                            now = timezone.now()
                            offer = Offer.objects.select_for_update().get(
                                id=offer_id,
                                is_active=True,
                                valid_from__lte=now,
                                valid_until__gte=now,
                                min_purchase_amount__lte=base_price
                            )
                            
                            if offer.usage_limit and offer.usage_count >= offer.usage_limit:
                                return Response(
                                    {"error": "This coupon has reached its usage limit"},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                            
                            if offer.discount_type == 'PERCENTAGE':
                                discount_amount = base_price * (offer.discount_value / 100)
                                if offer.max_discount_amount and discount_amount > offer.max_discount_amount:
                                    discount_amount = offer.max_discount_amount
                            else:  # FIXED
                                discount_amount = offer.discount_value
                                if discount_amount > base_price:
                                    discount_amount = base_price
                            
                            # Update offer usage count
                            offer.usage_count += 1
                            offer.save()
                            
                        except Offer.DoesNotExist:
                            return Response(
                                {"error": "Invalid or expired coupon"},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    
                    # Calculate final price
                    final_price = base_price - discount_amount
                    
                    # Create ticket
                    ticket = Ticket.objects.create(
                        customer=customer,
                        schedule=schedule,
                        seat_id=seat_id,
                        base_price=base_price,
                        discount_amount=discount_amount,
                        final_price=final_price,
                        offer=offer,
                        status='RESERVED'
                    )
                    
                    # Update seat availability
                    seat_availability.status = 'RESERVED'
                    seat_availability.save()
                    
                except SeatAvailability.DoesNotExist:
                    return Response(
                        {"error": "Seat availability record not found"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Return ticket data
            serializer = self.get_serializer(ticket)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Schedule.DoesNotExist:
            return Response(
                {"error": "Schedule not found"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def my_tickets(self, request):
        """Get current user's tickets"""
        try:
            # Extract customer_id from token
            customer_id = request.auth.payload.get('customer_id')
            if not customer_id:
                return Response(
                    {"error": "Invalid authentication token"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
            customer = Customer.objects.get(id=customer_id)
            tickets = Ticket.objects.filter(customer=customer).order_by('-booking_time')
            
            # Filter by status if provided
            status_param = request.query_params.get('status')
            if status_param:
                tickets = tickets.filter(status=status_param)
                
            serializer = self.get_serializer(tickets, many=True)
            return Response(serializer.data)
            
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def cancel_ticket(self, request, pk=None):
        """Cancel a ticket"""
        try:
            ticket = self.get_object()
            
            # Extract customer_id from token
            customer_id = request.auth.payload.get('customer_id')
            if not customer_id:
                return Response(
                    {"error": "Invalid authentication token"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
            # Check if the ticket belongs to the current user
            customer = Customer.objects.get(id=customer_id)
            if ticket.customer.id != customer.id and not request.user.is_staff:
                return Response(
                    {"error": "You don't have permission to cancel this ticket"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if the ticket can be cancelled
            if ticket.status != 'RESERVED' and ticket.status != 'CONFIRMED':
                return Response(
                    {"error": f"Cannot cancel ticket with status '{ticket.status}'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update ticket status
            ticket.status = 'CANCELLED'
            ticket.cancellation_time = timezone.now()
            ticket.cancellation_reason = request.data.get('reason', 'Cancelled by user')
            ticket.save()
            
            # Update seat availability
            try:
                seat_availability = SeatAvailability.objects.get(
                    schedule=ticket.schedule,
                    seat=ticket.seat
                )
                seat_availability.status = 'AVAILABLE'
                seat_availability.save()
            except SeatAvailability.DoesNotExist:
                pass
            
            serializer = self.get_serializer(ticket)
            return Response(serializer.data)
            
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class SpecialReservationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing special reservations.
    """
    queryset = SpecialReservation.objects.all()
    serializer_class = SpecialReservationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'vehicle', 'customer']
    search_fields = ['source', 'destination', 'customer__username', 'customer__email', 'vehicle__name']
    ordering_fields = ['departure_time', 'final_price', 'created_at']
    
    def get_permissions(self):
        if self.action in ['create', 'my_reservations', 'make_payment']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'approve_reservation', 'reject_reservation', 'mark_completed']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
    
    def create(self, request, *args, **kwargs):
        """Create a new special reservation request"""
        try:
            # Extract customer_id from token
            customer_id = request.auth.payload.get('customer_id')
            if not customer_id:
                return Response(
                    {"error": "Invalid authentication token"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
            # Get customer
            customer = Customer.objects.get(id=customer_id)
            
            # Get required data
            vehicle_id = request.data.get('vehicle')
            source = request.data.get('source')
            destination = request.data.get('destination')
            departure_time = request.data.get('departure_time')
            distance_km = request.data.get('distance_km')
            
            if not all([vehicle_id, source, destination, departure_time, distance_km]):
                return Response(
                    {"error": "Vehicle, source, destination, departure time, and distance are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if the vehicle is already assigned to another special reservation for the requested time
            with transaction.atomic():
                # Parse the departure time
                try:
                    dept_time = timezone.datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
                except:
                    return Response(
                        {"error": "Invalid departure time format"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Estimated arrival time (simple calculation)
                try:
                    distance_km = float(distance_km)
                except ValueError:
                    return Response(
                        {"error": "Distance must be a valid number"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Calculate estimated arrival time
                avg_speed = 60  # km/h
                duration_hours = distance_km / avg_speed
                duration_minutes = int(duration_hours * 60)
                est_arrival_time = dept_time + timezone.timedelta(minutes=duration_minutes)
                
                # Check vehicle status and availability
                vehicle = Vehicle.objects.select_for_update().get(id=vehicle_id)
                
                # Check if vehicle is available (not in maintenance or inactive)
                if vehicle.status not in ['ACTIVE', 'RESERVED']:
                    return Response(
                        {"error": f"Vehicle is not available. Current status: {vehicle.get_status_display()}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check for overlapping special reservations
                overlapping_reservations = SpecialReservation.objects.filter(
                    vehicle_id=vehicle_id,
                    status__in=['REQUESTED', 'APPROVED'],
                    # Check if requested time overlaps with existing reservations
                    # Either: 1) New departure is during existing reservation
                    #        2) New arrival is during existing reservation
                    #        3) New reservation completely encompasses existing one
                    departure_time__lte=est_arrival_time,
                    estimated_arrival_time__gte=dept_time
                ).exists()
                
                if overlapping_reservations:
                    return Response(
                        {"error": "This vehicle is already reserved for the requested time period"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Check for regular schedules during the requested time
                overlapping_schedules = Schedule.objects.filter(
                    vehicle_id=vehicle_id,
                    status__in=['SCHEDULED', 'IN_PROGRESS'],
                    departure_time__lte=est_arrival_time,
                    arrival_time__gte=dept_time
                ).exists()
                
                if overlapping_schedules:
                    return Response(
                        {"error": "This vehicle has regular schedules during the requested time period"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Base pricing logic
                base_price = distance_km * 5  # $5 per km
                
                # Apply surcharges based on factors
                
                # 1. Distance surcharge - longer distances get bulk discount
                distance_surcharge = 0
                if distance_km > 200:
                    distance_surcharge = -base_price * 0.1  # 10% discount for long trips
                
                # 2. Time surcharge - peak hours cost more
                time_surcharge = 0
                hour = dept_time.hour
                if 6 <= hour <= 9 or 16 <= hour <= 19:  # Peak hours
                    time_surcharge = base_price * 0.2  # 20% extra for peak hours
                
                # 3. Demand surcharge - this would be calculated based on real demand
                # Here we're just using a placeholder value
                demand_surcharge = 0
                
                # Calculate final price
                final_price = base_price + distance_surcharge + time_surcharge + demand_surcharge
                
                # Create special reservation
                reservation = SpecialReservation.objects.create(
                    customer=customer,
                    vehicle=vehicle,
                    source=source,
                    destination=destination,
                    distance_km=distance_km,
                    departure_time=dept_time,
                    estimated_arrival_time=est_arrival_time,
                    base_price=base_price,
                    distance_surcharge=distance_surcharge,
                    time_surcharge=time_surcharge,
                    demand_surcharge=demand_surcharge,
                    final_price=final_price,
                    status='REQUESTED'
                )
            
            serializer = self.get_serializer(reservation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Vehicle.DoesNotExist:
            return Response(
                {"error": "Vehicle not found"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def my_reservations(self, request):
        """Get current user's special reservations"""
        try:
            # Extract customer_id from token
            customer_id = request.auth.payload.get('customer_id')
            if not customer_id:
                return Response(
                    {"error": "Invalid authentication token"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
            customer = Customer.objects.get(id=customer_id)
            reservations = SpecialReservation.objects.filter(customer=customer).order_by('-created_at')
            
            # Filter by status if provided
            status_param = request.query_params.get('status')
            if status_param:
                reservations = reservations.filter(status=status_param)
                
            serializer = self.get_serializer(reservations, many=True)
            return Response(serializer.data)
            
        except Customer.DoesNotExist:
            return Response(
                {"error": "Customer profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def approve_reservation(self, request, pk=None):
        """Approve a special reservation (admin only)"""
        reservation = self.get_object()
        
        if reservation.status != 'REQUESTED':
            return Response(
                {"error": f"Cannot approve reservation with status '{reservation.status}'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reservation.status = 'APPROVED'
        reservation.save()
        
        serializer = self.get_serializer(reservation)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject_reservation(self, request, pk=None):
        """Reject a special reservation (admin only)"""
        reservation = self.get_object()
        
        if reservation.status != 'REQUESTED':
            return Response(
                {"error": f"Cannot reject reservation with status '{reservation.status}'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reservation.status = 'REJECTED'
        reservation.save()
        
        serializer = self.get_serializer(reservation)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def make_payment(self, request, pk=None):
        """
        Record a payment for a special reservation
        """
        special_reservation = self.get_object()
        
        # Verify this is the customer's own reservation
        if request.user.is_staff or getattr(request.auth.payload.get('customer_id'), None) == str(special_reservation.customer.id):
            try:
                amount = float(request.data.get('amount', 0))
                if amount <= 0:
                    return Response(
                        {"error": "Payment amount must be greater than zero"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Record the payment
                special_reservation.deposit_amount += amount
                special_reservation.deposit_paid_date = timezone.now()
                
                # Update balance and payment status
                special_reservation.balance_amount = max(0, special_reservation.final_price - special_reservation.deposit_amount)
                special_reservation.is_fully_paid = special_reservation.balance_amount <= 0
                
                special_reservation.save()
                
                return Response({
                    "message": f"Payment of {amount} recorded successfully",
                    "deposit_amount": special_reservation.deposit_amount,
                    "balance_amount": special_reservation.balance_amount,
                    "is_fully_paid": special_reservation.is_fully_paid
                })
                
            except ValueError as e:
                return Response(
                    {"error": f"Invalid payment amount: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except (TypeError, AttributeError) as e:
                return Response(
                    {"error": f"Parameter error: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Unexpected error in make_payment: {str(e)}")
                return Response(
                    {"error": "An unexpected error occurred while processing payment"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            return Response(
                {"error": "You do not have permission to make a payment for this reservation"},
                status=status.HTTP_403_FORBIDDEN
            )
    
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """
        Mark a special reservation as completed and update vehicle status
        """
        special_reservation = self.get_object()
        
        if special_reservation.status != 'APPROVED':
            return Response(
                {"error": "Only approved reservations can be marked as completed"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update reservation status
        special_reservation.status = 'COMPLETED'
        special_reservation.save()
        
        # Update vehicle status back to ACTIVE
        vehicle = special_reservation.vehicle
        vehicle.status = 'ACTIVE'
        vehicle.save()
        
        return Response({
            "message": f"Reservation marked as completed. Vehicle {vehicle.name} is now available."
        })


# User registration view
class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = CustomerRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            customer = serializer.save()
            
            # Generate tokens
            refresh = RefreshToken()
            refresh['customer_id'] = str(customer.id)
            refresh['username'] = customer.username
            
            # Update last login
            customer.last_login = timezone.now()
            customer.save(update_fields=['last_login'])
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'customer': CustomerSerializer(customer).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Custom token authentication view
class TokenObtainPairForCustomerView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({'error': 'Please provide both username and password'},
                            status=status.HTTP_400_BAD_REQUEST)
        
        try:
            customer = Customer.objects.get(username=username)
        except Customer.DoesNotExist:
            return Response({'error': 'No customer with this username was found.'},
                            status=status.HTTP_404_NOT_FOUND)
        
        if not customer.check_password(password):
            return Response({'error': 'Invalid credentials.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        
        if not customer.is_active:
            return Response({'error': 'This account is not active.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        
        # Generate tokens
        refresh = RefreshToken()
        refresh['customer_id'] = str(customer.id)
        refresh['username'] = customer.username
        
        # Update last login
        customer.last_login = timezone.now()
        customer.save(update_fields=['last_login'])
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'customer': CustomerSerializer(customer).data
        })
