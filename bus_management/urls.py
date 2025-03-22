from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    VehicleViewSet, RouteViewSet, ScheduleViewSet, SeatViewSet,
    CustomerViewSet, OfferViewSet, TicketViewSet, SpecialReservationViewSet,
    SeatAvailabilityViewSet, RegisterView, TokenObtainPairForCustomerView,
    VehicleTypeViewSet
)

# Setup the router for REST API viewsets
router = DefaultRouter()
router.register(r'vehicle-types', VehicleTypeViewSet)
router.register(r'vehicles', VehicleViewSet)
router.register(r'routes', RouteViewSet)
router.register(r'schedules', ScheduleViewSet)
router.register(r'seats', SeatViewSet)
router.register(r'seat-availabilities', SeatAvailabilityViewSet)
router.register(r'customers', CustomerViewSet)
router.register(r'offers', OfferViewSet)

# The Ticket model uses UUID as primary key instead of regular auto-incrementing ID
# This provides several benefits:
# 1. Security - UUIDs are not sequential and harder to guess
# 2. Distributed systems - UUIDs can be generated without a central authority
# 3. Uniqueness - UUIDs are globally unique across systems
# 4. URL-friendly - UUIDs can be used in URLs without encoding
router.register(r'tickets', TicketViewSet)
router.register(r'special-reservations', SpecialReservationViewSet)

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Authentication endpoints
    path('api/token/', TokenObtainPairForCustomerView.as_view(), name='token_obtain_pair'),
    path('api/register/', RegisterView.as_view(), name='register'),
    
    # Dashboard endpoints
    path('api/dashboard/', 
         VehicleViewSet.as_view({'get': 'dashboard'}), 
         name='api_dashboard'),
    path('api/dashboard/charts/', 
         VehicleViewSet.as_view({'get': 'dashboard_charts'}), 
         name='dashboard-charts'),
    
    # Custom Vehicle availability endpoints
    path('api/vehicles/<uuid:pk>/check-availability/', 
         VehicleViewSet.as_view({'post': 'check_availability'}), 
         name='vehicle-check-availability'),
    path('api/vehicles/available/', 
         VehicleViewSet.as_view({'get': 'available_vehicles'}), 
         name='available-vehicles'),
    
    # Special Reservation specific endpoints
    path('api/special-reservations/my-reservations/', 
         SpecialReservationViewSet.as_view({'get': 'my_reservations'}), 
         name='my-special-reservations'),
    path('api/special-reservations/<uuid:pk>/approve/', 
         SpecialReservationViewSet.as_view({'post': 'approve_reservation'}), 
         name='approve-special-reservation'),
    path('api/special-reservations/<uuid:pk>/reject/', 
         SpecialReservationViewSet.as_view({'post': 'reject_reservation'}), 
         name='reject-special-reservation'),
    path('api/special-reservations/<uuid:pk>/payment/', 
         SpecialReservationViewSet.as_view({'post': 'make_payment'}), 
         name='make-special-reservation-payment'),
    path('api/special-reservations/<uuid:pk>/complete/', 
         SpecialReservationViewSet.as_view({'post': 'mark_completed'}), 
         name='complete-special-reservation'),
    
    # Add custom ticket endpoints  
    path('api/tickets/my-tickets/', 
         TicketViewSet.as_view({'get': 'my_tickets'}), 
         name='my-tickets'),
    path('api/tickets/<uuid:pk>/cancel/', 
         TicketViewSet.as_view({'post': 'cancel_ticket'}), 
         name='cancel-ticket'),
] 