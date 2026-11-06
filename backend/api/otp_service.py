"""
Helpers for phone numbers and the 6-digit codes drivers check at pickup and delivery.
(Sign-in no longer uses one-time codes: customers use a password or Google.)
"""
import re
import secrets


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
