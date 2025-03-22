# Bus Management System

A comprehensive Django-based system for managing bus operations, including scheduling, ticketing, reservations, and reporting.

## Features

- **Vehicle Management**: Track buses, their types, and maintenance status
- **Route Management**: Define routes with source, destination, and estimated travel times
- **Scheduling**: Create and manage bus schedules on different routes
- **Booking System**: Book tickets for regular routes
- **Special Reservations**: Book entire buses for special occasions
- **User Management**: Different access levels for admins and customers
- **Dashboard**: Real-time analytics and reporting
- **Notifications**: In-app notifications for status updates

## Project Structure

```
bus-system/
├── bus_management/           # Main app for bus operations
│   ├── migrations/           # Database migrations
│   ├── management/           # Custom management commands
│   ├── models.py             # Data models for buses, routes, tickets, etc.
│   ├── views.py              # API views for bus management
│   ├── serializers.py        # Serializers for REST API
│   ├── forms.py              # Forms for data input
│   ├── urls.py               # URL routing for bus management
│   ├── utils.py              # Helper functions and utilities
│   ├── consumers.py          # WebSocket consumers for real-time updates
│   ├── signals.py            # Django signals for event handling
│   ├── routing.py            # WebSocket routing
│   ├── apps.py               # App configuration
│   ├── admin.py              # Admin interface configuration
│   └── tests.py              # Tests for the app
│
├── notifications/            # App for handling notifications
│   ├── migrations/           # Database migrations
│   ├── templates/            # Notification-specific templates
│   ├── models.py             # Notification data models
│   ├── views.py              # Views for notifications
│   ├── services.py           # Services for notification handling
│   ├── urls.py               # URL routing for notifications
│   ├── consumers.py          # WebSocket consumers for real-time notifications
│   ├── signals.py            # Signals for notification events
│   ├── routing.py            # WebSocket routing for notifications
│   ├── apps.py               # App configuration
│   ├── admin.py              # Admin interface for notifications
│   └── tests.py              # Tests for notifications
│
├── BusManagement/            # Project settings and configuration
│   ├── settings.py           # Django settings
│   ├── urls.py               # Main URL routing
│   ├── api.py                # Centralized API endpoints
│   ├── asgi.py               # ASGI configuration for WebSockets
│   └── wsgi.py               # WSGI configuration
│
├── templates/                # Global templates
│   └── dashboard/            # Dashboard templates
│       └── dashboard.html    # Main dashboard
│
├── static/                   # Static files (CSS, JS, images)
│
├── staticfiles/              # Collected static files
│
├── venv/                     # Virtual environment
│
├── manage.py                 # Django management script
└── requirements.txt          # Project dependencies
```

## API Endpoints

### Dashboard API

- `GET /api/v1/dashboard/` - Dashboard statistics and recent reservation data
- `GET /api/v1/dashboard/charts/` - Chart data for dashboard visualizations
- `GET /api/v1/notifications/` - Recent notifications for the current user

### Bus Management API

- `GET /api/vehicles/` - List all vehicles
- `GET /api/routes/` - List all routes
- `GET /api/schedules/` - List all schedules
- `GET /api/seat-availabilities/` - Check seat availability
- `GET /api/tickets/` - List all tickets
- `GET /api/special-reservations/` - List all special reservations
- `POST /api/special-reservations/` - Create a new special reservation
- `GET /api/special-reservations/my-reservations/` - Get current user's reservations

### Notification API

- `GET /notifications/api/notifications/` - List all notifications for current user
- `POST /notifications/api/notifications/{id}/mark_read/` - Mark a notification as read
- `POST /notifications/api/notifications/mark_all_read/` - Mark all notifications as read

## Setup

1. Clone the repository:
```
git clone https://github.com/username/bus-system.git
cd bus-system
```

2. Create a virtual environment and install dependencies:
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Run migrations:
```
python manage.py migrate
```

4. Create a superuser:
```
python manage.py createsuperuser
```

5. Run the development server:
```
python manage.py runserver
```

6. Access the admin interface at http://localhost:8000/admin/
7. Access the dashboard at http://localhost:8000/dashboard/

## Development

### Dependencies

- Django 4.2
- Django REST Framework
- Channels (for WebSockets)
- Django Filter
- drf-yasg (for API docs)
- Django Jazzmin (for admin theme)

### Key Components

1. **Models**: Defined in `bus_management/models.py` and `notifications/models.py`
2. **APIs**: 
   - REST APIs in app-specific views
   - Centralized dashboard APIs in `BusManagement/api.py`
3. **Admin Interface**: Customized in `bus_management/admin.py`
4. **Dashboard**: HTML/JS in `templates/dashboard/dashboard.html`

## License

MIT
