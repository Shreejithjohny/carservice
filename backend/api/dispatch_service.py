"""
Automatic staff assignment for a confirmed booking.

Driver: among drivers of the booking's service center who are available and free in the booking's
pickup slot, pick the lowest score

    score = distance to the customer (km) + WORKLOAD_PENALTY_KM x pickups already that day

so a nearby driver usually wins, but one who already has a full day loses to a slightly farther
driver who is free. A driver's position is their latest GPS point if it is recent, otherwise their
service center (an idle driver waits at the workshop).

Mechanic: the available mechanic of the center with the fewest open jobs.
"""
from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

from django.db.models import Q
from django.utils import timezone

from .models import BookingStatus, DriverLocation, ServiceBooking, User, UserRole

WORKLOAD_PENALTY_KM = 3.0
GPS_FRESH_FOR = timedelta(hours=2)
CLOSED_STATUSES = [BookingStatus.COMPLETED, BookingStatus.CANCELLED]


def haversine_km(lat1, lng1, lat2, lng2):
    dlat, dlng = radians(lat2 - lat1), radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def center_staff(booking, role):
    """Staff of the booking's center, plus the shared pool of staff not attached to any center."""
    return User.objects.filter(role=role, is_active=True).filter(
        Q(employee_profile__service_center=booking.service_center)
        | Q(employee_profile__isnull=True)
        | Q(employee_profile__service_center__isnull=True)
    )


def _is_available(user):
    employee = getattr(user, "employee_profile", None)
    return employee is None or employee.is_available


def _driver_position(driver, booking):
    """(lat, lng, where-from text) or None when nothing is known."""
    latest = DriverLocation.objects.filter(driver=driver).order_by("-timestamp").first()
    if latest and timezone.now() - latest.timestamp <= GPS_FRESH_FOR:
        return latest.latitude, latest.longitude, "live GPS"
    employee = getattr(driver, "employee_profile", None)
    center = employee.service_center if employee and employee.service_center_id else booking.service_center
    if center and center.latitude is not None and center.longitude is not None:
        return center.latitude, center.longitude, f"at {center.name}"
    return None


def rank_drivers(booking):
    """Every candidate driver, best first, with the reasoning shown to the manager."""
    day = booking.preferred_date or timezone.localdate()
    has_pickup_point = booking.pickup_latitude is not None and booking.pickup_longitude is not None
    rows = []
    for driver in center_staff(booking, UserRole.DRIVER):
        jobs = ServiceBooking.objects.filter(assigned_driver=driver, preferred_date=day).exclude(
            status__in=CLOSED_STATUSES
        ).exclude(pk=booking.pk)
        jobs_today = jobs.count()
        slot_taken = bool(booking.preferred_time) and jobs.filter(preferred_time=booking.preferred_time).exists()

        position = _driver_position(driver, booking)
        distance = None
        if position and has_pickup_point:
            distance = round(haversine_km(position[0], position[1], booking.pickup_latitude, booking.pickup_longitude), 1)

        if not _is_available(driver):
            reason = "Marked unavailable"
        elif slot_taken:
            reason = "Already has a pickup in this time slot"
        else:
            reason = None

        score = (distance or 0.0) + WORKLOAD_PENALTY_KM * jobs_today
        rows.append({
            "driver_id": driver.id,
            "name": driver.get_full_name() or driver.username,
            "distance_km": distance,
            "position_source": position[2] if position else "unknown",
            "jobs_today": jobs_today,
            "score": round(score, 1),
            "eligible": reason is None,
            "reason": reason or (
                f"{distance} km away ({position[2]}), {jobs_today} pickup(s) that day"
                if distance is not None
                else f"{jobs_today} pickup(s) that day; distance unknown"
            ),
        })
    rows.sort(key=lambda r: (not r["eligible"], r["score"], r["jobs_today"], r["driver_id"]))
    return rows


def rank_mechanics(booking):
    rows = []
    for mechanic in center_staff(booking, UserRole.MECHANIC):
        open_jobs = ServiceBooking.objects.filter(assigned_mechanic=mechanic).exclude(status__in=CLOSED_STATUSES).exclude(pk=booking.pk).count()
        available = _is_available(mechanic)
        rows.append({
            "mechanic_id": mechanic.id,
            "name": mechanic.get_full_name() or mechanic.username,
            "open_jobs": open_jobs,
            "eligible": available,
            "reason": f"{open_jobs} open job(s)" if available else "Marked unavailable",
        })
    rows.sort(key=lambda r: (not r["eligible"], r["open_jobs"], r["mechanic_id"]))
    return rows


def best_driver(booking):
    ranked = [r for r in rank_drivers(booking) if r["eligible"]]
    return (User.objects.get(pk=ranked[0]["driver_id"]), ranked[0]) if ranked else (None, None)


def best_mechanic(booking):
    ranked = [r for r in rank_mechanics(booking) if r["eligible"]]
    return (User.objects.get(pk=ranked[0]["mechanic_id"]), ranked[0]) if ranked else (None, None)
