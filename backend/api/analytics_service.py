"""Numbers for the service-center manager's analytics page (or platform-wide for an admin)."""
from collections import Counter, defaultdict
from datetime import date, datetime
from statistics import median

from django.db.models import Avg, Count
from django.utils import timezone

from .ml_cost_model import SYNTHETIC_MARKER
from .models import BookingStatus, Invoice, RepairRequest, RepairRequestStatus, ServiceBooking, ServiceReview


def _month_keys(today: date, months: int):
    """The last `months` calendar months as (year, month), oldest first, ending with the current one."""
    keys = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return keys[::-1]


def _month_of(dt):
    local = timezone.localtime(dt)
    return local.year, local.month


def center_analytics(center=None, months: int = 6) -> dict:
    """`center=None` means every center (admin view)."""
    # Generated demo history (seed_repair_history) is never business data
    bookings = ServiceBooking.objects.exclude(customer_notes__startswith=SYNTHETIC_MARKER)
    invoices = Invoice.objects.exclude(booking__customer_notes__startswith=SYNTHETIC_MARKER)
    repairs = RepairRequest.objects.exclude(booking__customer_notes__startswith=SYNTHETIC_MARKER)
    reviews = ServiceReview.objects.all()
    if center is not None:
        bookings = bookings.filter(service_center=center)
        invoices = invoices.filter(service_center=center)
        repairs = repairs.filter(booking__service_center=center)
        reviews = reviews.filter(service_center=center)

    today = timezone.localdate()
    keys = _month_keys(today, months)
    # A datetime bound (not a __date lookup) so MySQL needs no time zone tables.
    first = timezone.make_aware(datetime(keys[0][0], keys[0][1], 1))

    created = Counter(_month_of(b) for b in bookings.filter(created_at__gte=first).values_list("created_at", flat=True))
    completed = Counter(
        _month_of(c) for c in bookings.filter(completed_at__gte=first).values_list("completed_at", flat=True)
    )
    revenue = defaultdict(float)
    for issued, total in invoices.filter(payment_status=Invoice.PaymentStatus.PAID, issued_at__gte=first).values_list(
        "issued_at", "grand_total"
    ):
        revenue[_month_of(issued)] += float(total or 0)

    monthly = [
        {
            "month": f"{y}-{m:02d}",
            "label": date(y, m, 1).strftime("%b %Y"),
            "bookings": created[(y, m)],
            "completed": completed[(y, m)],
            "revenue": round(revenue[(y, m)], 2),
        }
        for y, m in keys
    ]

    # Turnaround: from booking to the car being back with the customer (completed_at).
    durations = [
        (done - start).total_seconds() / 3600
        for start, done in bookings.filter(completed_at__isnull=False).values_list("created_at", "completed_at")
        if done >= start
    ]

    # Most requested extra repairs, grouping titles that differ only in case or spacing.
    titles = defaultdict(list)
    for title, cost in repairs.values_list("issue_title", "additional_cost"):
        key = " ".join(title.lower().split())
        titles[key].append(float(cost or 0))
    display = {}
    for title in repairs.values_list("issue_title", flat=True):
        display.setdefault(" ".join(title.lower().split()), title.strip())
    top_repairs = sorted(
        (
            {"title": display[k], "count": len(v), "average_cost": round(sum(v) / len(v), 2)}
            for k, v in titles.items()
        ),
        key=lambda r: (-r["count"], r["title"]),
    )[:5]

    approved = repairs.filter(status=RepairRequestStatus.APPROVED).count()
    rejected = repairs.filter(status=RepairRequestStatus.REJECTED).count()
    pending = repairs.filter(status=RepairRequestStatus.PENDING).count()
    answered = approved + rejected

    rating = reviews.aggregate(n=Count("id"), avg=Avg("center_rating"))
    distribution = Counter(reviews.values_list("center_rating", flat=True))

    status_counts = Counter(bookings.values_list("status", flat=True))

    paid_total = sum(float(t or 0) for t in invoices.filter(payment_status=Invoice.PaymentStatus.PAID).values_list("grand_total", flat=True))
    outstanding = sum(
        float(t or 0)
        for t in invoices.exclude(payment_status=Invoice.PaymentStatus.PAID)
        .exclude(invoice_status="CANCELLED")
        .values_list("grand_total", flat=True)
    )

    return {
        "scope": center.name if center is not None else "All service centers",
        "monthly": monthly,
        "totals": {
            "bookings": bookings.count(),
            "completed": bookings.filter(status=BookingStatus.COMPLETED).count(),
            "cancelled": bookings.filter(status=BookingStatus.CANCELLED).count(),
            "revenue_paid": round(paid_total, 2),
            "outstanding": round(outstanding, 2),
        },
        "turnaround_hours": {
            "count": len(durations),
            "average": round(sum(durations) / len(durations), 1) if durations else None,
            "median": round(median(durations), 1) if durations else None,
        },
        "repairs": {
            "approved": approved,
            "rejected": rejected,
            "pending": pending,
            "approval_rate": round(100 * approved / answered, 1) if answered else None,
            "top": top_repairs,
        },
        "ratings": {
            "count": rating["n"],
            "average": round(rating["avg"], 2) if rating["avg"] is not None else None,
            "distribution": [{"stars": s, "count": distribution.get(s, 0)} for s in range(5, 0, -1)],
            "recent": [
                {"rating": r.center_rating, "comment": r.comment, "created_at": r.created_at}
                for r in reviews.exclude(comment="")[:5]
            ],
        },
        "status_breakdown": [{"status": s, "count": n} for s, n in status_counts.most_common()],
    }
