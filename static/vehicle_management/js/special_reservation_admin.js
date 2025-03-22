document.addEventListener("DOMContentLoaded", function() {
    console.log("✅ Special Reservation Admin JS loaded!");
    
    // Form fields
    const vehicleField = document.querySelector("#id_vehicle");
    const distanceField = document.querySelector("#id_distance_km");
    const durationField = document.querySelector("#id_duration_days");
    const roundTripField = document.querySelector("#id_is_round_trip");
    const seasonFactorField = document.querySelector("#id_season_factor");
    const driverAllowanceField = document.querySelector("#id_driver_allowance");
    const basePriceField = document.querySelector("#id_base_price");
    const multiDaySurchargeField = document.querySelector("#id_multi_day_surcharge");
    const distanceSurchargeField = document.querySelector("#id_distance_surcharge");
    const timeSurchargeField = document.querySelector("#id_time_surcharge");
    const demandSurchargeField = document.querySelector("#id_demand_surcharge");
    const discountField = document.querySelector("#id_discount_amount");
    const finalPriceField = document.querySelector("#id_final_price");
    const depositField = document.querySelector("#id_deposit_amount");
    const balanceField = document.querySelector("#id_balance_amount");
    const isPaidField = document.querySelector("#id_is_fully_paid");
    
    // Make price fields read-only
    const readOnlyFields = [basePriceField, multiDaySurchargeField, finalPriceField, balanceField, isPaidField];
    readOnlyFields.forEach(field => {
        if (field) {
            field.addEventListener("focus", (e) => e.target.blur());
        }
    });
    
    // Calculate prices
    function calculatePrices() {
        if (!vehicleField || !distanceField || !durationField || !finalPriceField) {
            console.warn("⚠️ Missing required fields for price calculation");
            return;
        }
        
        // Get vehicle subtype data (this requires backend modification to include data attributes)
        const vehicleOption = vehicleField.options[vehicleField.selectedIndex];
        if (!vehicleOption || !vehicleOption.value) {
            console.warn("⚠️ No vehicle selected");
            return;
        }
        
        const ratePerKm = parseFloat(vehicleOption.getAttribute("data-rate-per-km") || 0);
        const minPrice = parseFloat(vehicleOption.getAttribute("data-min-price") || 0);
        const vehicleType = vehicleOption.getAttribute("data-vehicle-type") || '';
        
        console.log(`Vehicle data: Rate=${ratePerKm}, MinPrice=${minPrice}, Type=${vehicleType}`);
        
        if (ratePerKm === 0) {
            console.warn("⚠️ Rate per km is 0 or not found. Check if vehicle has rate data.");
        }
        
        const distance = parseFloat(distanceField.value) || 0;
        const duration = parseInt(durationField.value) || 1;
        const isRoundTrip = roundTripField && roundTripField.checked;
        const seasonFactor = parseFloat(seasonFactorField.value) || 1.0;
        const driverAllowance = parseFloat(driverAllowanceField.value) || 0;
        
        // Calculate base price
        let basePrice = distance * ratePerKm;
        basePrice = Math.max(basePrice, minPrice);
        
        // Apply duration factor
        basePrice = basePrice * duration;
        
        // Apply season factor
        basePrice = basePrice * seasonFactor;
        
        // Round trip calculation (80% for return journey)
        if (isRoundTrip) {
            basePrice = basePrice * 1.8;
        }
        
        // Update base price field
        basePriceField.value = basePrice.toFixed(2);
        
        // Calculate multi-day surcharge
        let multiDaySurcharge = 0;
        if (duration > 1) {
            multiDaySurcharge = driverAllowance * (duration - 1);
            multiDaySurchargeField.value = multiDaySurcharge.toFixed(2);
        } else {
            multiDaySurchargeField.value = "0.00";
        }
        
        // Gather surcharges and discount
        const distanceSurcharge = parseFloat(distanceSurchargeField.value) || 0;
        const timeSurcharge = parseFloat(timeSurchargeField.value) || 0;
        const demandSurcharge = parseFloat(demandSurchargeField.value) || 0;
        const discount = parseFloat(discountField.value) || 0;
        
        // Calculate final price
        const finalPrice = basePrice + 
                          multiDaySurcharge + 
                          distanceSurcharge + 
                          timeSurcharge + 
                          demandSurcharge - 
                          discount;
        
        finalPriceField.value = finalPrice.toFixed(2);
        
        // Update balance and payment status
        if (depositField) {
            const deposit = parseFloat(depositField.value) || 0;
            const balance = finalPrice - deposit;
            
            if (balanceField) {
                balanceField.value = Math.max(0, balance).toFixed(2);
            }
            
            if (isPaidField) {
                isPaidField.checked = balance <= 0;
            }
        }
        
        console.log(`✅ Prices calculated: Base=${basePrice.toFixed(2)}, Final=${finalPrice.toFixed(2)}`);
    }
    
    // Event listeners for fields that affect pricing
    const priceFactorFields = [
        vehicleField, distanceField, durationField, roundTripField, 
        seasonFactorField, driverAllowanceField, distanceSurchargeField,
        timeSurchargeField, demandSurchargeField, discountField, depositField
    ];
    
    priceFactorFields.forEach(field => {
        if (field) {
            if (field.type === 'checkbox') {
                field.addEventListener('change', calculatePrices);
            } else {
                field.addEventListener('input', calculatePrices);
                field.addEventListener('change', calculatePrices);
            }
        }
    });
    
    // Initial calculation
    function initializeForm() {
        console.log("Initializing form...");
        if (vehicleField && vehicleField.selectedIndex > 0) {
            calculatePrices();
        } else {
            console.log("No vehicle selected yet. Price calculation deferred.");
        }
    }
    
    // Run initialization after a delay to ensure all elements are loaded
    setTimeout(initializeForm, 500);
}); 