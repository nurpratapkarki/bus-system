document.addEventListener("DOMContentLoaded", function () {
    console.log("Ticket Admin JS Loaded!");  // Debugging

    const basePriceField = document.querySelector("#id_base_price");
    const discountField = document.querySelector("#id_discount_amount");
    const finalPriceField = document.querySelector("#id_final_price");
    const scheduleField = document.querySelector("#id_schedule");
    const offerField = document.querySelector("#id_offer");

    if (!basePriceField || !discountField || !finalPriceField || !scheduleField) {
        console.error("Form fields not found! Check your field IDs.");
        return;
    }

    function calculateFinalPrice() {
        let basePrice = parseFloat(basePriceField.value) || 0;
        let discount = parseFloat(discountField.value) || 0;
        finalPriceField.value = (basePrice - discount).toFixed(2);
        console.log(`Final Price Updated: ${finalPriceField.value}`);
    }

    function fetchBasePrice() {
        let selectedOption = scheduleField.options[scheduleField.selectedIndex];
        if (selectedOption) {
            let basePrice = selectedOption.getAttribute("data-base-price") || 0;
            basePriceField.value = parseFloat(basePrice).toFixed(2);
            console.log(`Base Price Fetched: ${basePriceField.value}`);
            calculateFinalPrice();
        }
    }

    function applyDiscountFromOffer() {
        let selectedOffer = offerField.options[offerField.selectedIndex];
        if (selectedOffer && selectedOffer.dataset.discount) {
            let discountValue = parseFloat(selectedOffer.dataset.discount) || 0;
            discountField.value = discountValue.toFixed(2);
            console.log(`Discount Applied: ${discountField.value}`);
            calculateFinalPrice();
        }
    }

    // Prevent manual edits (but allow calculations)
    basePriceField.addEventListener("focus", (e) => e.target.blur());
    finalPriceField.addEventListener("focus", (e) => e.target.blur());

    discountField.addEventListener("input", calculateFinalPrice);
    scheduleField.addEventListener("change", fetchBasePrice);
    offerField.addEventListener("change", applyDiscountFromOffer);

    // Initialize calculations on page load
    fetchBasePrice();
    calculateFinalPrice();
});
