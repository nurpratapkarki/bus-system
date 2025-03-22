from django import forms
from .models import Ticket, Schedule, SpecialReservation, Vehicle

class ScheduleAdminForm(forms.ModelForm):
    """Form for Schedule to calculate base price dynamically."""
    
    class Meta:
        model = Schedule
        fields = "__all__"

    def clean_base_price(self):
        """Ensure base_price is recalculated before saving"""
        schedule = self.instance
        return schedule.calculate_base_price() if schedule else self.cleaned_data.get('base_price')


class TicketAdminForm(forms.ModelForm):
    """Ticket Form that updates price fields automatically"""

    class Meta:
        model = Ticket
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make base_price and final_price non-editable
        if 'base_price' in self.fields:
            self.fields['base_price'].widget.attrs['readonly'] = True
            self.fields['base_price'].widget.attrs['style'] = 'background-color: #f1f1f1;'
        if 'final_price' in self.fields:
            self.fields['final_price'].widget.attrs['readonly'] = True
            self.fields['final_price'].widget.attrs['style'] = 'background-color: #f1f1f1;'
            
        # Add data-base-price attribute to schedule options
        if 'schedule' in self.fields:
            from django.forms.widgets import Select
            original_widget = self.fields['schedule'].widget
            
            # Create a custom widget with data attributes
            class ScheduleSelectWithPrices(Select):
                def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
                    option = super().create_option(name, value, label, selected, index, subindex, attrs)
                    if value and str(value) != '':
                        from .models import Schedule
                        try:
                            # Convert value to string to handle ModelChoiceIteratorValue
                            schedule = Schedule.objects.get(pk=str(value))
                            option['attrs']['data-base-price'] = schedule.base_price
                        except (Schedule.DoesNotExist, ValueError, TypeError):
                            pass
                    return option
            
            # Replace the widget while preserving any existing attributes
            self.fields['schedule'].widget = ScheduleSelectWithPrices(
                attrs=original_widget.attrs,
                choices=original_widget.choices
            )
            
            # Add data-discount attribute to offer options
            if 'offer' in self.fields:
                original_widget = self.fields['offer'].widget
                
                # Create a custom widget with data attributes
                class OfferSelectWithDiscount(Select):
                    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
                        option = super().create_option(name, value, label, selected, index, subindex, attrs)
                        if value and str(value) != '':
                            from .models import Offer
                            try:
                                # Convert value to string to handle ModelChoiceIteratorValue
                                offer = Offer.objects.get(pk=str(value))
                                if offer.discount_type == 'FIXED':
                                    option['attrs']['data-discount'] = offer.discount_value
                                # For percentage, we'll calculate the actual amount in JS
                                option['attrs']['data-discount-type'] = offer.discount_type
                                option['attrs']['data-discount-value'] = offer.discount_value
                            except (Offer.DoesNotExist, ValueError, TypeError):
                                pass
                        return option
                
                # Replace the widget while preserving any existing attributes
                self.fields['offer'].widget = OfferSelectWithDiscount(
                    attrs=original_widget.attrs,
                    choices=original_widget.choices
                )

    def clean(self):
        """Auto-fill price fields based on schedule selection & discounts"""
        cleaned_data = super().clean()
        schedule = cleaned_data.get("schedule")
        offer = cleaned_data.get("offer")
        discount_amount = cleaned_data.get("discount_amount", 0)

        if schedule:
            # Set base price from schedule
            cleaned_data["base_price"] = schedule.base_price

            # Calculate discount if offer is selected
            if offer:
                if offer.discount_type == "PERCENTAGE":
                    discount_amount = (schedule.base_price * offer.discount_value) / 100
                    # Apply maximum discount if set
                    if offer.max_discount_amount and discount_amount > offer.max_discount_amount:
                        discount_amount = offer.max_discount_amount
                else:
                    discount_amount = offer.discount_value
                    # Don't allow discount to exceed base price
                    if discount_amount > schedule.base_price:
                        discount_amount = schedule.base_price

            # Ensure discount is not negative
            discount_amount = max(0, discount_amount)
            cleaned_data["discount_amount"] = discount_amount

            # Calculate final price
            cleaned_data["final_price"] = schedule.base_price - discount_amount

        return cleaned_data

    def clean_discount_amount(self):
        """Validate discount amount"""
        discount_amount = self.cleaned_data.get('discount_amount', 0)
        base_price = self.cleaned_data.get('base_price', 0)
        
        # Ensure discount is not negative
        discount_amount = max(0, discount_amount)
        
        # Ensure discount doesn't exceed base price
        if discount_amount > base_price:
            discount_amount = base_price
            
        return discount_amount

class SpecialReservationAdminForm(forms.ModelForm):
    """Form for managing special vehicle reservations with dynamic pricing."""
    
    class Meta:
        model = SpecialReservation
        fields = "__all__"
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make calculated price fields read-only
        read_only_fields = [
            'base_price', 'final_price', 'multi_day_surcharge', 
            'balance_amount', 'is_fully_paid'
        ]
        
        for field_name in read_only_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'readonly': True,
                    'style': 'background-color: #f1f1f1;'
                })
                
        # Add data attributes to vehicle field
        if 'vehicle' in self.fields:
            from django.forms.widgets import Select
            original_widget = self.fields['vehicle'].widget
            
            # Custom widget to add vehicle subtype data
            class VehicleSelectWithRates(Select):
                def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
                    option = super().create_option(name, value, label, selected, index, subindex, attrs)
                    if value and str(value) != '':
                        from .models import Vehicle
                        try:
                            # Convert value to string to handle ModelChoiceIteratorValue
                            vehicle = Vehicle.objects.get(pk=str(value))
                            if vehicle.vehicle_subtype:
                                option['attrs']['data-rate-per-km'] = vehicle.vehicle_subtype.rate_per_km
                                option['attrs']['data-min-price'] = vehicle.vehicle_subtype.min_price
                                option['attrs']['data-vehicle-type'] = vehicle.vehicle_subtype.vehicle_type.name
                        except (Vehicle.DoesNotExist, ValueError, TypeError):
                            pass
                    return option
            
            # Replace widget
            self.fields['vehicle'].widget = VehicleSelectWithRates(
                attrs=original_widget.attrs,
                choices=original_widget.choices
            )
                
        # Set default values
        if not self.instance.pk:  # For new reservations
            self.fields['season_factor'].initial = 1.0
            self.fields['driver_allowance'].initial = 1500.00  # Default driver daily allowance (in NPR)
            
        # Add help texts
        self.fields['distance_km'].help_text = "Distance in kilometers affects the base price"
        if 'duration_days' in self.fields:
            self.fields['duration_days'].help_text = "Number of days affects the pricing calculation"
        self.fields['season_factor'].help_text = "E.g., 1.2 for high season, 0.9 for low season"
        
    def clean(self):
        """Validate form data and update calculated fields."""
        cleaned_data = super().clean()
        
        # Ensure return time is after departure for round trips
        is_round_trip = cleaned_data.get('is_round_trip')
        departure_time = cleaned_data.get('departure_time')
        return_time = cleaned_data.get('return_time')
        estimated_arrival_time = cleaned_data.get('estimated_arrival_time')
        vehicle = cleaned_data.get('vehicle')
        
        if not departure_time or not estimated_arrival_time or not vehicle:
            # Skip validation if essential fields are missing - they'll be caught by field validators
            return cleaned_data
        
        if is_round_trip and departure_time and not return_time:
            self.add_error('return_time', 'Return time is required for round trips')
            
        if is_round_trip and departure_time and return_time:
            if return_time <= departure_time:
                self.add_error('return_time', 'Return time must be after departure time')
                
        # Validate multi-day reservations
        duration_days = cleaned_data.get('duration_days', 1)
        if duration_days < 1:
            self.add_error('duration_days', 'Duration must be at least 1 day')
        
        # Check vehicle availability for the specified timeframe
        end_time = return_time if is_round_trip and return_time else estimated_arrival_time
        
        # If we're editing an existing reservation, exclude it from the availability check
        exclude_id = self.instance.pk if self.instance and self.instance.pk else None
        
        is_available, conflict, conflict_type = vehicle.is_available(
            departure_time, end_time, exclude_reservation_id=exclude_id
        )
        
        if not is_available:
            if conflict_type == 'vehicle_status':
                self.add_error('vehicle', f"Vehicle is not available (status: {vehicle.get_status_display()})")
            elif conflict_type == 'schedule':
                conflict_detail = f"({conflict.route.source} to {conflict.route.destination}, " \
                                 f"{conflict.departure_time.strftime('%Y-%m-%d %H:%M')} to " \
                                 f"{conflict.arrival_time.strftime('%Y-%m-%d %H:%M')})"
                self.add_error('vehicle', f"Vehicle is already scheduled for a regular route {conflict_detail}")
            elif conflict_type == 'special_reservation':
                conflict_detail = f"({conflict.source} to {conflict.destination}, " \
                                 f"{conflict.departure_time.strftime('%Y-%m-%d %H:%M')} to " \
                                 f"{conflict.estimated_arrival_time.strftime('%Y-%m-%d %H:%M')})"
                self.add_error('vehicle', f"Vehicle is already reserved for a special trip {conflict_detail}")
            
        # Instead of checking against the instance's final_price (which may not be calculated yet),
        # calculate what the final price would be based on the submitted data
        distance_km = cleaned_data.get('distance_km')
        deposit_amount = cleaned_data.get('deposit_amount', 0)
        
        if vehicle and distance_km and deposit_amount > 0:
            # Create a temporary instance with the form data to calculate the price
            temp_instance = self.instance.__class__(
                vehicle=vehicle,
                distance_km=distance_km,
                duration_days=duration_days,
                is_round_trip=is_round_trip,
                season_factor=cleaned_data.get('season_factor', 1.0),
                driver_allowance=cleaned_data.get('driver_allowance', 0),
                distance_surcharge=cleaned_data.get('distance_surcharge', 0),
                time_surcharge=cleaned_data.get('time_surcharge', 0),
                demand_surcharge=cleaned_data.get('demand_surcharge', 0),
                multi_day_surcharge=cleaned_data.get('multi_day_surcharge', 0),
                discount_amount=cleaned_data.get('discount_amount', 0)
            )
            
            estimated_price = temp_instance.calculate_price()
            
            if deposit_amount > estimated_price:
                self.add_error('deposit_amount', f'Deposit amount ({deposit_amount}) cannot exceed the estimated total price ({estimated_price:.2f})')
            
        return cleaned_data
