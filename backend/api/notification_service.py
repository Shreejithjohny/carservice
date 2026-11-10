from typing import Optional, Dict, Any
from django.utils import timezone
from datetime import timedelta
import logging

from .models import User, ServiceBooking, Notification, NotificationType, UserRole

logger = logging.getLogger(__name__)

# Page a push notification opens when clicked
_CUSTOMER_PAGES = {
    NotificationType.REPAIR_APPROVAL_REQUIRED: "/app/approvals",
    NotificationType.INVOICE_GENERATED: "/app/invoices",
    NotificationType.PAYMENT_RECEIVED: "/app/invoices",
}
_STAFF_HOME = {
    UserRole.DRIVER: "/driver",
    UserRole.MECHANIC: "/mechanic",
    UserRole.SERVICE_CENTER_MANAGER: "/service-center",
    UserRole.ADMIN: "/admin",
}


def _notification_url(user, notification_type) -> str:
    if user.role == UserRole.CUSTOMER:
        return _CUSTOMER_PAGES.get(notification_type, "/app/track")
    return _STAFF_HOME.get(user.role, "/")


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

    notification = Notification.objects.create(
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
    # Also to the user's browsers, if they turned on alerts (no-op when push is not configured)
    try:
        from .push_service import push_to_user

        push_to_user(user, title, message, _notification_url(user, notification_type))
    except Exception:  # noqa: BLE001 - the in-app notification must never fail because of push
        logger.exception("Could not queue a push notification")
    return notification
