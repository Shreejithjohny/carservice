from datetime import date
from django.utils import timezone
from .models import Vehicle, CarHealthScore, ServiceBooking, ServiceInspection, RepairRequest, RepairRequestStatus


def recalculate_car_health_score(vehicle: Vehicle) -> CarHealthScore:
    """
    Computes a deterministic Car Health Score (0-100) based on:
    - Completed service history (+5 per service up to +15)
    - Unresolved critical issues from inspections (-25 per critical issue; fixed once the booking
      is completed with an approved repair)
    - Unresolved high/warning severity issues (-10 per warning issue)
    - Resolved / approved repairs (+3 per resolved item)
    - Vehicle age deduction (-2 per year over 3 years old)
    """
    bookings = ServiceBooking.objects.filter(vehicle=vehicle)
    completed_bookings = bookings.filter(status="Completed")
    service_count = completed_bookings.count()

    # Inspection findings count until fixed: a finding on a completed booking whose repair the
    # customer approved has been resolved, so it no longer lowers the score.
    fixed_bookings = completed_bookings.filter(repair_requests__status=RepairRequestStatus.APPROVED)
    inspections = ServiceInspection.objects.filter(booking__vehicle=vehicle).exclude(booking__in=fixed_bookings)
    critical_issues = inspections.filter(severity="CRITICAL").count()
    warning_issues = inspections.filter(severity="HIGH").count()

    # Repair requests
    repairs = RepairRequest.objects.filter(booking__vehicle=vehicle)
    resolved_repairs = repairs.filter(status=RepairRequestStatus.APPROVED).count()
    pending_repairs = repairs.filter(status=RepairRequestStatus.PENDING).count()

    # Calculation logic
    base_score = 90  # Default starting benchmark for healthy vehicle

    # Rewards
    service_bonus = min(service_count * 5, 15)
    resolved_bonus = min(resolved_repairs * 3, 10)

    # Penalties
    critical_penalty = critical_issues * 25
    warning_penalty = (warning_issues + pending_repairs) * 10

    # Age penalty
    current_year = date.today().year
    vehicle_year = vehicle.year or current_year
    age = max(0, current_year - vehicle_year)
    age_penalty = max(0, (age - 3) * 2)

    raw_score = base_score + service_bonus + resolved_bonus - critical_penalty - warning_penalty - age_penalty
    final_score = max(0, min(100, raw_score))

    # Interpret compliance
    if final_score >= 90:
        compliance = "Excellent"
    elif final_score >= 75:
        compliance = "Good"
    elif final_score >= 60:
        compliance = "Fair"
    elif final_score >= 40:
        compliance = "Needs Attention"
    else:
        compliance = "Critical"

    # Explanation construction
    factors = []
    if service_count > 0:
        factors.append(f"✓ {service_count} service(s) successfully logged")
    else:
        factors.append("ℹ No completed service history logged yet")

    if critical_issues == 0 and warning_issues == 0:
        factors.append("✓ No unresolved critical or high-risk mechanical issues")
    else:
        if critical_issues > 0:
            factors.append(f"⚠ {critical_issues} critical issue(s) detected during inspection")
        if warning_issues > 0:
            factors.append(f"⚠ {warning_issues} high-risk warning(s) flagged")

    if resolved_repairs > 0:
        factors.append(f"✓ {resolved_repairs} recommended repair(s) approved and completed")

    if age > 3:
        factors.append(f"ℹ Vehicle age ({age} yrs) factored into baseline wear estimate")

    explanation = "; ".join(factors) + ". Note: Health score is a maintenance guidance index and not a certified statutory diagnosis."

    # Update or create CarHealthScore
    health_record, created = CarHealthScore.objects.get_or_create(
        vehicle=vehicle,
        defaults={
            "score": final_score,
            "previous_score": final_score,
            "service_count": service_count,
            "recent_service_count": service_count,
            "maintenance_compliance": compliance,
            "critical_issue_count": critical_issues,
            "warning_issue_count": warning_issues,
            "resolved_issue_count": resolved_repairs,
            "explanation": explanation,
        },
    )

    if not created:
        health_record.previous_score = health_record.score
        health_record.score = final_score
        health_record.service_count = service_count
        health_record.recent_service_count = service_count
        health_record.maintenance_compliance = compliance
        health_record.critical_issue_count = critical_issues
        health_record.warning_issue_count = warning_issues
        health_record.resolved_issue_count = resolved_repairs
        health_record.explanation = explanation
        health_record.save()

    return health_record
