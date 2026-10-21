from typing import Optional, Dict, Any
from django.utils import timezone
from datetime import timedelta
from .models import User, ServiceBooking, Notification, NotificationType


def send_notification(
    user: User,
    notification_type: str,
    title: str,
    message: str,
    booking: Optional[ServiceBooking] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Notification]:
    """
    Creates an internal notification with duplicate suppression.
    Avoids sending identical alerts for the same booking and event within a 1-minute window.
    """
    if not user:
        return None

    recent_cutoff = timezone.now() - timedelta(minutes=1)
    duplicate_exists = Notification.objects.filter(
        user=user,
        booking=booking,
        notification_type=notification_type,
        created_at__gte=recent_cutoff,
    ).exists()

    if duplicate_exists:
        return None

    return Notification.objects.create(
        user=user,
        booking=booking,
        notification_type=notification_type,
        title=title,
        message=message,
        body=message,
        metadata=metadata or {},
        read=False,
        is_read=False,
    )
