from django.urls import re_path
from . import consumers

# Empty websocket_urlpatterns for now
# We'll add actual consumers when implementing real-time features for bus_management
websocket_urlpatterns = []

# WebSocket connection for vehicle status updates
re_path(r'ws/vehicle/(?P<vehicle_id>[0-9a-f-]+)/$', consumers.VehicleStatusConsumer.as_asgi()),

# WebSocket connection for schedule status updates
re_path(r'ws/schedule/(?P<schedule_id>[0-9a-f-]+)/$', consumers.VehicleStatusConsumer.as_asgi()),

# WebSocket connection for seat availability updates
re_path(r'ws/seats/(?P<schedule_id>[0-9a-f-]+)/$', consumers.SeatAvailabilityConsumer.as_asgi()), 