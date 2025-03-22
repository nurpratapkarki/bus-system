import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from .models import Schedule, SeatAvailability, Vehicle


class VehicleStatusConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time vehicle status updates.
    Clients can subscribe to a specific vehicle or schedule.
    """
    async def connect(self):
        try:
            self.vehicle_id = self.scope['url_route']['kwargs'].get('vehicle_id')
            self.schedule_id = self.scope['url_route']['kwargs'].get('schedule_id')
            
            if not self.vehicle_id and not self.schedule_id:
                await self.close(code=4000, reason="Either vehicle_id or schedule_id is required")
                return
                
            if self.vehicle_id:
                # Verify vehicle exists
                vehicle = await self.get_vehicle(self.vehicle_id)
                if not vehicle:
                    await self.close(code=4004, reason="Vehicle not found")
                    return
                    
                self.group_name = f'vehicle_{self.vehicle_id}'
                await self.channel_layer.group_add(
                    self.group_name,
                    self.channel_name
                )
                await self.accept()
                
            elif self.schedule_id:
                # Verify schedule exists
                schedule = await self.get_schedule(self.schedule_id)
                if not schedule:
                    await self.close(code=4004, reason="Schedule not found")
                    return
                    
                self.group_name = f'schedule_{self.schedule_id}'
                await self.channel_layer.group_add(
                    self.group_name,
                    self.channel_name
                )
                await self.accept()
                
        except Exception as e:
            await self.close(code=4000, reason=str(e))
    
    @database_sync_to_async
    def get_vehicle(self, vehicle_id):
        try:
            return Vehicle.objects.get(id=vehicle_id)
        except ObjectDoesNotExist:
            return None
    
    @database_sync_to_async
    def get_schedule(self, schedule_id):
        try:
            return Schedule.objects.get(id=schedule_id)
        except ObjectDoesNotExist:
            return None
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """
        Receive message from WebSocket.
        Only admins can send updates.
        """
        data = json.loads(text_data)
        
        # Check if user is authenticated and has permission (would be validated in a real app)
        # For this example, we'll proceed without authentication
        
        if self.vehicle_id:
            await self.update_vehicle_status(self.vehicle_id, data.get('status'))
        elif self.schedule_id:
            await self.update_schedule_status(self.schedule_id, data.get('status'))
    
    @database_sync_to_async
    def update_vehicle_status(self, vehicle_id, status):
        if not status:
            return
            
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
            vehicle.status = status
            vehicle.save()
            
            # Broadcast to all clients
            return {
                'type': 'status_update',
                'vehicle_id': str(vehicle_id),
                'status': status,
                'timestamp': timezone.now().isoformat()
            }
        except Vehicle.DoesNotExist:
            return None
    
    @database_sync_to_async
    def update_schedule_status(self, schedule_id, status):
        if not status:
            return
            
        try:
            schedule = Schedule.objects.get(id=schedule_id)
            schedule.status = status
            schedule.save()
            
            # Broadcast to all clients
            return {
                'type': 'status_update',
                'schedule_id': str(schedule_id),
                'status': status,
                'timestamp': timezone.now().isoformat()
            }
        except Schedule.DoesNotExist:
            return None
    
    async def status_update(self, event):
        """
        Send status update to WebSocket.
        """
        await self.send(text_data=json.dumps(event))


class SeatAvailabilityConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time seat availability updates.
    Clients can subscribe to a specific schedule to get seat updates.
    """
    async def connect(self):
        self.schedule_id = self.scope['url_route']['kwargs'].get('schedule_id')
        
        if self.schedule_id:
            self.group_name = f'seat_availability_{self.schedule_id}'
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            # Send initial seat availability data
            seats = await self.get_seat_availability(self.schedule_id)
            await self.accept()
            await self.send(text_data=json.dumps({
                'type': 'initial_data',
                'seats': seats
            }))
        else:
            await self.close()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """
        Receive updates for seat availability.
        """
        # In a real app, we'd validate if the user has permission to update
        # For this example, we'll proceed without validation
        data = json.loads(text_data)
        seat_id = data.get('seat_id')
        status = data.get('status')
        
        if seat_id and status and self.schedule_id:
            result = await self.update_seat_availability(self.schedule_id, seat_id, status)
            if result:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        'type': 'seat_update',
                        'seat_id': str(seat_id),
                        'status': status,
                        'timestamp': timezone.now().isoformat()
                    }
                )
    
    @database_sync_to_async
    def get_seat_availability(self, schedule_id):
        """Get current seat availability data for a schedule"""
        try:
            seat_availability = SeatAvailability.objects.filter(schedule_id=schedule_id)
            return [
                {
                    'id': str(sa.id),
                    'seat_id': str(sa.seat.id),
                    'seat_number': sa.seat.seat_number,
                    'status': sa.status,
                    'seat_type': sa.seat.seat_type
                }
                for sa in seat_availability
            ]
        except Exception:
            return []
    
    @database_sync_to_async
    def update_seat_availability(self, schedule_id, seat_id, status):
        """Update seat availability status"""
        try:
            seat_availability = SeatAvailability.objects.get(
                schedule_id=schedule_id,
                seat_id=seat_id
            )
            seat_availability.status = status
            seat_availability.save()
            return True
        except SeatAvailability.DoesNotExist:
            return False
    
    async def seat_update(self, event):
        """
        Send seat availability update to WebSocket.
        """
        await self.send(text_data=json.dumps(event)) 