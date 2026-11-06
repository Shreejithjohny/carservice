"""
Rate limits for the OTP endpoints, so nobody can run up the SMS/email bill or brute-force codes.

Limits (all configurable in settings / .env):
  * codes sent to one email or number        OTP_SEND_LIMIT_PER_IDENTIFIER per hour
  * codes requested from one IP address      OTP_SEND_LIMIT_PER_IP per hour
  * codes sent by the whole server           OTP_SEND_DAILY_LIMIT per 24 hours (0 = no cap)
  * codes checked from one IP address        OTP_VERIFY_LIMIT_PER_IP per hour
They are skipped when OTP_BYPASS (local demo mode) is on, like the 60-second resend cooldown.
"""
import math
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle

from .models import OtpRequestLog
from .otp_service import normalize_phone_number

HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
KEEP_LOGS_FOR = timedelta(days=2)


def client_ip(request):
    """The caller's IP. Honours REST_FRAMEWORK["NUM_PROXIES"] when running behind a proxy."""
    return (BaseThrottle().get_ident(request) or "")[:64]


def identifier_key(identifier):
    identifier = (identifier or "").strip()
    if "@" in identifier:
        return identifier.lower()[:255]
    return normalize_phone_number(identifier)[:255]


def _limit_response(oldest, window, message):
    retry_after = max(1, math.ceil((oldest + window - timezone.now()).total_seconds())) if oldest else 60
    minutes = max(1, math.ceil(retry_after / 60))
    response = Response(
        {"error": f"{message} Please try again in {minutes} minute(s).", "retry_after_seconds": retry_after},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )
    response["Retry-After"] = str(retry_after)
    return response


def _over_limit(queryset, limit, window):
    """Returns (True, oldest timestamp in the window) when `limit` rows already exist in `window`."""
    if not limit or limit <= 0:
        return False, None
    recent = queryset.filter(created_at__gte=timezone.now() - window)
    if recent.count() < limit:
        return False, None
    return True, recent.order_by("created_at").values_list("created_at", flat=True).first()


def _record(action, identifier, ip):
    now = timezone.now()
    OtpRequestLog.objects.filter(created_at__lt=now - KEEP_LOGS_FOR).delete()
    OtpRequestLog.objects.create(action=action, identifier=identifier, ip_address=ip, created_at=now)


def otp_send_limit_error(request, identifier):
    """
    Call before sending a code (and before any account lookup, so the answer is the same whether or
    not an account exists). Returns a 429 Response when a limit is reached, otherwise None.
    Call record_otp_send() once the code is actually being sent.
    """
    if getattr(settings, "OTP_BYPASS", False):
        return None
    sends = OtpRequestLog.objects.filter(action=OtpRequestLog.SEND)

    hit, oldest = _over_limit(sends.filter(identifier=identifier_key(identifier)), settings.OTP_SEND_LIMIT_PER_IDENTIFIER, HOUR)
    if hit:
        return _limit_response(oldest, HOUR, "Too many codes have been sent to this email or number.")
    hit, oldest = _over_limit(sends.filter(ip_address=client_ip(request)), settings.OTP_SEND_LIMIT_PER_IP, HOUR)
    if hit:
        return _limit_response(oldest, HOUR, "Too many code requests from your network.")
    hit, oldest = _over_limit(sends, settings.OTP_SEND_DAILY_LIMIT, DAY)
    if hit:
        return _limit_response(oldest, DAY, "We can't send more codes right now.")
    return None


def record_otp_send(request, identifier):
    if not getattr(settings, "OTP_BYPASS", False):
        _record(OtpRequestLog.SEND, identifier_key(identifier), client_ip(request))


def otp_verify_limit_error(request, identifier):
    """Call before checking a code. Returns a 429 Response when the IP checked too many codes."""
    if getattr(settings, "OTP_BYPASS", False):
        return None
    ip = client_ip(request)
    checks = OtpRequestLog.objects.filter(action=OtpRequestLog.VERIFY, ip_address=ip)
    hit, oldest = _over_limit(checks, settings.OTP_VERIFY_LIMIT_PER_IP, HOUR)
    if hit:
        return _limit_response(oldest, HOUR, "Too many code attempts from your network.")
    _record(OtpRequestLog.VERIFY, identifier_key(identifier), ip)
    return None
