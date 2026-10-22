"""
Service reminders: a car is due for service 6 months or 10,000 km after its last completed service,
whichever comes first (the usual interval Indian manufacturers recommend for petrol and diesel cars).
"""
from datetime import date, timedelta

from django.utils import timezone

from .models import BookingStatus, Notification, NotificationType, ServiceBooking, Vehicle

SERVICE_INTERVAL_DAYS = 180
SERVICE_INTERVAL_KM = 10_000
DUE_SOON_DAYS = 14
DUE_SOON_KM = 1_000
# Don't remind about the same car more often than this.
REMINDER_GAP_DAYS = 7

OK = "OK"
DUE_SOON = "DUE_SOON"
OVERDUE = "OVERDUE"
BOOKED = "BOOKED"

CLOSED_STATUSES = [BookingStatus.COMPLETED, BookingStatus.CANCELLED]


def service_due(vehicle: Vehicle, today: date) -> dict:
    bookings = ServiceBooking.objects.filter(vehicle=vehicle)
    last = bookings.filter(status=BookingStatus.COMPLETED).order_by("-completed_at", "-updated_at").first()

    if last:
        last_date = timezone.localtime(last.completed_at or last.updated_at).date()
        last_km = last.delivery_odometer_km if last.delivery_odometer_km is not None else last.pickup_odometer_km
    else:
        # Never serviced with us: count from when the car was added.
        last_date = timezone.localtime(vehicle.created_at).date()
        last_km = None

    due_date = last_date + timedelta(days=SERVICE_INTERVAL_DAYS)
    days_left = (due_date - today).days
    km_left = None
    if last_km is not None and vehicle.odometer_km is not None:
        km_left = last_km + SERVICE_INTERVAL_KM - vehicle.odometer_km

    reasons = []
    if days_left < 0:
        reasons.append(f"{-days_left} day(s) past the 6-month service date")
    elif days_left <= DUE_SOON_DAYS:
        reasons.append(f"6-month service date in {days_left} day(s)")
    if km_left is not None:
        if km_left < 0:
            reasons.append(f"{-km_left:,} km past the 10,000 km interval")
        elif km_left <= DUE_SOON_KM:
            reasons.append(f"{km_left:,} km left in the 10,000 km interval")

    if bookings.exclude(status__in=CLOSED_STATUSES).exists():
        state = BOOKED
    elif days_left < 0 or (km_left is not None and km_left < 0):
        state = OVERDUE
    elif reasons:
        state = DUE_SOON
    else:
        state = OK

    return {
        "vehicle": vehicle.id,
        "registration_number": vehicle.registration_number,
        "name": vehicle.nickname or f"{vehicle.brand} {vehicle.model}".strip(),
        "status": state,
        "last_service_date": last_date.isoformat() if last else None,
        "due_date": due_date.isoformat(),
        "days_left": days_left,
        "km_left": km_left,
        "odometer_km": vehicle.odometer_km,
        "reasons": reasons,
    }


def send_service_reminders(today: date) -> int:
    """Notifies owners of cars that are due or overdue. Returns how many reminders were sent."""
    sent = 0
    recent = timezone.now() - timedelta(days=REMINDER_GAP_DAYS)
    for vehicle in Vehicle.objects.select_related("customer"):
        due = service_due(vehicle, today)
        if due["status"] not in (DUE_SOON, OVERDUE):
            continue
        already = Notification.objects.filter(
            user=vehicle.customer,
            notification_type=NotificationType.SERVICE_REMINDER,
            metadata__vehicle_id=vehicle.id,
            created_at__gte=recent,
        ).exists()
        if already:
            continue
        title = f"{'Service overdue' if due['status'] == OVERDUE else 'Service due soon'}: {due['name']}"
        message = f"{vehicle.registration_number}: {'; '.join(due['reasons'])}. Book a doorstep pickup in the app."
        Notification.objects.create(
            user=vehicle.customer,
            notification_type=NotificationType.SERVICE_REMINDER,
            title=title,
            message=message,
            body=message,
            metadata={"vehicle_id": vehicle.id, "status": due["status"]},
        )
        sent += 1
    return sent
