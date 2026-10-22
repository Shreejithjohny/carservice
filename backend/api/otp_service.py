import os
import re
import secrets
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

OTP_SMS_TEMPLATE = (
    "Smart Doorstep Vehicle Service:\n"
    "Your OTP is {otp_code}.\n"
    "It is valid for 5 minutes.\n"
    "Do not share this OTP with anyone."
)


def normalize_phone_number(raw_phone: str) -> str:
    """
    Normalize phone numbers into standard E.164 format.
    - Preserves existing E.164 numbers (e.g. '+919876543210', '+14155552671').
    - Converts 10-digit Indian numbers (e.g. '9876543210') to '+919876543210'.
    - Converts numbers with leading '0' (e.g. '09876543210') to '+919876543210'.
    - Converts 12-digit Indian numbers starting with '91' (e.g. '919876543210') to '+919876543210'.
    - Strips spaces, hyphens, and parentheses.
    - Prevents duplicate '+91'.
    """
    if not raw_phone:
        return ""

    cleaned = re.sub(r"[\s\-\(\)\.]+", "", str(raw_phone).strip())

    # Handle leading '+'
    if cleaned.startswith("+"):
        cleaned = "+" + re.sub(r"^\++", "", cleaned)
        if cleaned.startswith("+91+91"):
            cleaned = "+91" + cleaned[6:]
        elif cleaned.startswith("+9191") and len(cleaned) == 15 and cleaned[1:].isdigit():
            cleaned = "+91" + cleaned[5:]
        return cleaned

    # Leading 00 international prefix: e.g. 00919876543210 -> +919876543210
    if cleaned.startswith("00"):
        return "+" + cleaned[2:]

    # Leading 0 followed by 10 digits: e.g. 09876543210 -> +919876543210
    if cleaned.startswith("0") and len(cleaned) == 11 and cleaned[1:].isdigit():
        return f"+91{cleaned[1:]}"

    # 10-digit Indian number: 9876543210 -> +919876543210
    if len(cleaned) == 10 and cleaned.isdigit():
        return f"+91{cleaned}"

    # 12-digit Indian number without '+': 919876543210 -> +919876543210
    if len(cleaned) == 12 and cleaned.startswith("91") and cleaned.isdigit():
        return f"+{cleaned}"

    # Default fallback: if numeric and >= 10 digits, prefix '+'
    if cleaned.isdigit() and len(cleaned) >= 10:
        return f"+{cleaned}"

    return cleaned


def generate_otp_code() -> str:
    """Generate a cryptographically secure 6-digit numeric OTP code."""
    return f"{secrets.randbelow(900000) + 100000}"


def send_otp_to_identifier(identifier: str, otp_code: str) -> dict:
    """
    Send OTP via Twilio Programmable SMS / Email or fallback to console mode for development.
    NEVER expose the OTP to API caller output.
    """
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    twilio_from = os.getenv("TWILIO_PHONE_NUMBER", "").strip()

    is_email = "@" in identifier

    # 1. Twilio Programmable SMS Mode (When all three Twilio variables are configured)
    if not is_email and twilio_sid and twilio_token and twilio_from:
        normalized_to = normalize_phone_number(identifier)
        try:
            from twilio.rest import Client

            client = Client(twilio_sid, twilio_token)
            sms_body = OTP_SMS_TEMPLATE.format(otp_code=otp_code)
            message = client.messages.create(
                body=sms_body,
                from_=twilio_from,
                to=normalized_to,
            )
            logger.info(f"Twilio Programmable SMS dispatched to {normalized_to}. SID: {getattr(message, 'sid', 'N/A')}")
            return {
                "success": True,
                "provider": "twilio_sms",
                "message_sid": getattr(message, "sid", None),
            }
        except Exception as e:
            logger.error(f"Failed to send OTP via Twilio SMS to {normalized_to}: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": "Unable to send OTP. Please try again.",
                "provider": "twilio_sms",
            }

    # 2. Email SMTP (if identifier is email and SMTP host is configured)
    if is_email:
        if settings.EMAIL_HOST:
            try:
                from django.core.mail import send_mail

                send_mail(
                    subject="Smart Doorstep Vehicle Service - Verification Code",
                    message=OTP_SMS_TEMPLATE.format(otp_code=otp_code),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[identifier],
                    fail_silently=False,
                )
                logger.info(f"OTP email sent to {identifier}")
                return {"success": True, "provider": "email"}
            except Exception as e:
                logger.error(f"Failed to send OTP email to {identifier}: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "error": "Unable to send OTP. Please try again.",
                    "provider": "email",
                }

    # 3. Development / Console Fallback (When Twilio credentials or SMTP are missing)
    if not settings.OTP_CONSOLE_FALLBACK:
        logger.error(f"No OTP delivery provider configured for {'email' if is_email else 'SMS'}; cannot send OTP.")
        return {
            "success": False,
            "error": "OTP delivery is not configured. Please contact support.",
            "provider": "none",
        }

    expires_at = (timezone.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("\n==========================================")
    print("[SECURE BACKEND OTP DISPATCH - DEV FALLBACK]")
    print(f"Target: {identifier}")
    print(f"OTP Code: {otp_code}")
    print(f"Expires At: {expires_at}")
    print("SMS Message Preview:")
    print("Smart Doorstep Vehicle Service:")
    print(f"Your OTP is {otp_code}.")
    print("It is valid for 5 minutes.")
    print("Do not share this OTP with anyone.")
    print("==========================================\n")
    logger.info(f"[DEV MODE] OTP generated for {identifier} (Twilio credentials not configured)")
    return {"success": True, "provider": "console"}

