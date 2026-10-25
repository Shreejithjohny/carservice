from datetime import date

from django.db import transaction

from .models import BookingStatus, ServiceBooking, ServiceCenter

# Pickup windows offered each day. The value is what bookings store in preferred_time.
PICKUP_SLOTS = [
    ("09:00:00", "09:00 AM - 11:00 AM"),
    ("11:00:00", "11:00 AM - 01:00 PM"),
    ("14:00:00", "02:00 PM - 04:00 PM"),
    ("16:00:00", "04:00 PM - 06:00 PM"),
]
SLOT_VALUES = {value for value, _ in PICKUP_SLOTS}

# How far ahead customers may book.
MAX_DAYS_AHEAD = 30


class SlotError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _booked_counts(center: ServiceCenter, day: date) -> dict:
    """Number of live (non-cancelled) bookings per slot for a center on a day."""
    counts = {value: 0 for value in SLOT_VALUES}
    rows = (
        ServiceBooking.objects.filter(service_center=center, preferred_date=day)
        .exclude(status=BookingStatus.CANCELLED)
        .values_list("preferred_time", flat=True)
    )
    for slot in rows:
        if slot in counts:
            counts[slot] += 1
    return counts


def slot_availability(center: ServiceCenter, day: date) -> list:
    counts = _booked_counts(center, day)
    capacity = center.slot_capacity
    return [
        {
            "time": value,
            "label": label,
            "capacity": capacity,
            "booked": counts[value],
            "available": max(0, capacity - counts[value]),
            "is_full": counts[value] >= capacity,
        }
        for value, label in PICKUP_SLOTS
    ]


def validate_slot_choice(center: ServiceCenter, day, slot: str, today: date) -> None:
    """Raises SlotError unless the date is bookable and the slot still has room."""
    if not day:
        raise SlotError("Choose a pickup date.")
    if slot not in SLOT_VALUES:
        raise SlotError("Choose one of the offered pickup time slots.")
    if day < today:
        raise SlotError("The pickup date cannot be in the past.")
    if (day - today).days > MAX_DAYS_AHEAD:
        raise SlotError(f"Bookings open at most {MAX_DAYS_AHEAD} days ahead.")
    if _booked_counts(center, day)[slot] >= center.slot_capacity:
        raise SlotError("That time slot is fully booked. Please pick another slot.")


def reserve_slot(center: ServiceCenter, day, slot: str, today: date, create_booking):
    """
    Checks capacity and creates the booking in one transaction. On MySQL, locking the center row
    makes two customers racing for the last place in a slot queue up, so the slot cannot be
    overbooked. SQLite ignores row locks, which is acceptable for local development only.
    """
    with transaction.atomic():
        ServiceCenter.objects.select_for_update().filter(pk=center.pk).first()
        validate_slot_choice(center, day, slot, today)
        return create_booking()
