document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ Ticket Admin JS Loaded!");

    const basePriceField = document.querySelector("#id_base_price");
    const discountField = document.querySelector("#id_discount_amount");
    const finalPriceField = document.querySelector("#id_final_price");
    const scheduleField = document.querySelector("#id_schedule");
    const offerField = document.querySelector("#id_offer");

    if (!basePriceField || !discountField || !finalPriceField || !scheduleField) {
        console.error("⚠️ Missing form fields. Check IDs.");
        return;
    }

    function calculateFinalPrice() {
        let basePrice = parseFloat(basePriceField.value) || 0;
        let discount = parseFloat(discountField.value) || 0;
        finalPriceField.value = (basePrice - discount).toFixed(2);
        console.log(`✅ Final Price Updated: ${finalPriceField.value}`);
    }

    function fetchBasePrice() {
        let selectedOption = scheduleField.options[scheduleField.selectedIndex];
        if (!selectedOption || !selectedOption.value) return; // Prevent running before selection

        let basePrice = selectedOption.getAttribute("data-base-price") || 0;
        basePriceField.value = parseFloat(basePrice).toFixed(2);
        console.log(`✅ Base Price Fetched: ${basePriceField.value}`);
        calculateFinalPrice();
        
        // If there's an offer selected, recalculate the discount
        if (offerField && offerField.selectedIndex > 0) {
            applyDiscountFromOffer();
        }
    }

    function applyDiscountFromOffer() {
        let selectedOffer = offerField.options[offerField.selectedIndex];
        if (!selectedOffer || !selectedOffer.value) {
            discountField.value = "0.00";
            calculateFinalPrice();
            return;
        }
        
        let discountType = selectedOffer.getAttribute("data-discount-type");
        let discountValue = parseFloat(selectedOffer.getAttribute("data-discount-value")) || 0;
        let basePrice = parseFloat(basePriceField.value) || 0;
        let discountAmount = 0;
        
        if (discountType === "PERCENTAGE") {
            // Calculate percentage discount
            discountAmount = (basePrice * discountValue / 100);
            console.log(`✅ Percentage Discount (${discountValue}%): ${discountAmount}`);
        } else {
            // Fixed discount
            discountAmount = discountValue;
            console.log(`✅ Fixed Discount: ${discountAmount}`);
        }
        
        // Don't allow discount to exceed base price
        if (discountAmount > basePrice) {
            discountAmount = basePrice;
        }
        
        discountField.value = discountAmount.toFixed(2);
        console.log(`✅ Discount Applied: ${discountField.value}`);
        calculateFinalPrice();
    }

    // Prevent manual edits
    basePriceField.addEventListener("focus", (e) => e.target.blur());
    finalPriceField.addEventListener("focus", (e) => e.target.blur());

    // Fix Select2 issue: Wait for Select2 to initialize, then attach event
    function attachScheduleChangeListener() {
        if (window.jQuery && jQuery.fn.select2) {
            console.log("✅ Select2 detected. Attaching change event.");
            jQuery(scheduleField).on("select2:select", fetchBasePrice);
        } else {
            console.log("⚠️ Select2 not detected. Using fallback event listener.");
            scheduleField.addEventListener("change", fetchBasePrice);
        }
    }

    // Attach event listeners
    discountField.addEventListener("input", calculateFinalPrice);
    offerField.addEventListener("change", applyDiscountFromOffer);

    // Delay event binding for Select2
    setTimeout(attachScheduleChangeListener, 500);
});
