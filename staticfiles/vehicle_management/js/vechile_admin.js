document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".delete-vehicle").forEach(button => {
        button.addEventListener("click", function (e) {
            e.preventDefault();
            let deleteUrl = this.getAttribute("data-url");

            if (confirm("Are you sure you want to delete this vehicle?")) {
                fetch(deleteUrl, {
                    method: "DELETE",
                    headers: { "X-CSRFToken": getCookie("csrftoken") }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert("Failed to delete vehicle: " + (data.error || "Unknown error"));
                    }
                })
                .catch(error => alert("Error deleting vehicle: " + error));
            }
        });
    });

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            document.cookie.split(';').forEach(cookie => {
                let trimmedCookie = cookie.trim();
                if (trimmedCookie.startsWith(name + '=')) {
                    cookieValue = decodeURIComponent(trimmedCookie.substring(name.length + 1));
                }
            });
        }
        return cookieValue;
    }
});
