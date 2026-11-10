"""Coupon rules: who may use a code, and how much it takes off a package price."""
from decimal import Decimal

from django.utils import timezone

from .models import BookingStatus, Coupon, ServiceBooking


class CouponError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def find_coupon(code: str, lock: bool = False) -> Coupon:
    code = (code or "").strip().upper()
    if not code:
        raise CouponError("Enter a coupon code.")
    qs = Coupon.objects.select_for_update() if lock else Coupon.objects
    coupon = qs.filter(code=code).first()
    if not coupon or not coupon.active:
        raise CouponError("This coupon code is not valid.")
    return coupon


def coupon_discount(coupon: Coupon, user, price) -> Decimal:
    """Rupees off `price` (the package price) for this customer; raises CouponError when not usable."""
    price = Decimal(str(price))
    today = timezone.localdate()
    if coupon.valid_from and today < coupon.valid_from:
        raise CouponError("This coupon is not active yet.")
    if coupon.valid_until and today > coupon.valid_until:
        raise CouponError("This coupon has expired.")
    if price < coupon.min_order:
        raise CouponError(f"This coupon needs a package of ₹{coupon.min_order:,.0f} or more.")

    # Cancelled bookings give the use back
    used = ServiceBooking.objects.filter(coupon=coupon).exclude(status=BookingStatus.CANCELLED)
    if coupon.usage_limit is not None and used.count() >= coupon.usage_limit:
        raise CouponError("This coupon has been fully used.")
    if coupon.per_customer_limit and used.filter(customer=user).count() >= coupon.per_customer_limit:
        raise CouponError("You have already used this coupon.")

    if coupon.discount_type == Coupon.DiscountType.PERCENT:
        discount = price * min(coupon.value, Decimal("100")) / Decimal("100")
        if coupon.max_discount is not None:
            discount = min(discount, coupon.max_discount)
    else:
        discount = coupon.value
    return min(discount, price).quantize(Decimal("0.01"))
