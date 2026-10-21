import re
import secrets
from typing import Any, Dict

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Invoice, InvoiceStatus, NotificationType, Payment
from .notification_service import send_notification

UPI_ID_PATTERN = re.compile(r"^[\w.\-]{2,256}@[a-zA-Z][a-zA-Z0-9]{1,63}$")

# Test values understood by the mock gateway (shown to users in test mode).
MOCK_FAILING_UPI_ID = "failure@mock"
MOCK_FAILING_CARD = "4000000000000002"


class PaymentError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def payment_gateway() -> str:
    """Configured gateway name, or "" when online payment is disabled."""
    return (getattr(settings, "PAYMENT_GATEWAY", "") or "").strip().lower()


def _luhn_valid(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _validate_payer(method: str, data: Dict[str, Any]) -> Dict[str, str]:
    """Returns the masked payer reference and the raw value the gateway needs."""
    if method == Payment.Method.UPI:
        upi_id = str(data.get("upi_id") or "").strip().lower()
        if not UPI_ID_PATTERN.match(upi_id):
            raise PaymentError("Enter a valid UPI ID, e.g. name@okbank.", 400)
        return {"reference": upi_id, "raw": upi_id}

    if method == Payment.Method.CARD:
        number = re.sub(r"[\s-]", "", str(data.get("card_number") or ""))
        if not number.isdigit() or not 12 <= len(number) <= 19 or not _luhn_valid(number):
            raise PaymentError("Enter a valid card number.", 400)
        expiry = str(data.get("card_expiry") or "").strip()
        match = re.match(r"^(0[1-9]|1[0-2])/(\d{2})$", expiry)
        if not match:
            raise PaymentError("Enter the card expiry as MM/YY.", 400)
        month, year = int(match.group(1)), 2000 + int(match.group(2))
        now = timezone.now()
        if (year, month) < (now.year, now.month):
            raise PaymentError("This card has expired.", 400)
        return {"reference": f"Card ending {number[-4:]}", "raw": number}

    raise PaymentError("Choose UPI or Card as the payment method.", 400)


def _mock_charge(method: str, raw_payer: str) -> Dict[str, Any]:
    """Mock gateway: approves everything except the documented failing test values."""
    if (method == Payment.Method.UPI and raw_payer == MOCK_FAILING_UPI_ID) or (
        method == Payment.Method.CARD and raw_payer == MOCK_FAILING_CARD
    ):
        return {"success": False, "reason": "Payment declined by the bank (test failure)."}
    return {"success": True, "reason": ""}


def pay_invoice(invoice_id: int, user, data: Dict[str, Any]) -> Payment:
    """
    Charges the full invoice amount. Raises PaymentError with an HTTP status code
    for anything the caller should report to the user.
    """
    gateway = payment_gateway()
    if gateway != "mock":
        raise PaymentError("Online payment is not available. Please pay at the service center.", 503)

    method = str(data.get("method") or "").upper()

    with transaction.atomic():
        # Row lock so two simultaneous requests cannot both pay the same invoice.
        invoice = Invoice.objects.select_for_update().filter(pk=invoice_id).first()
        if not invoice:
            raise PaymentError("Invoice not found.", 404)
        if invoice.customer_id != user.id:
            raise PaymentError("Only the customer on this invoice can pay it.", 403)
        if invoice.payment_status == Invoice.PaymentStatus.PAID:
            raise PaymentError("This invoice is already paid.", 409)
        if invoice.invoice_status == InvoiceStatus.CANCELLED:
            raise PaymentError("This invoice was cancelled and cannot be paid.", 400)
        if invoice.grand_total <= 0:
            raise PaymentError("This invoice has nothing to pay.", 400)

        payer = _validate_payer(method, data)

        result = _mock_charge(method, payer["raw"])
        payment = Payment.objects.create(
            invoice=invoice,
            customer=user,
            amount=invoice.grand_total,
            method=method,
            status=Payment.Status.SUCCESS if result["success"] else Payment.Status.FAILED,
            provider=gateway.upper(),
            transaction_id=f"SDVPAY-{timezone.now():%Y%m%d}-{secrets.token_hex(5).upper()}",
            payer_reference=payer["reference"],
            failure_reason=result["reason"],
        )

        if result["success"]:
            invoice.payment_status = Invoice.PaymentStatus.PAID
            invoice.invoice_status = InvoiceStatus.PAID
        else:
            invoice.payment_status = Invoice.PaymentStatus.FAILED
        invoice.save(update_fields=["payment_status", "invoice_status", "updated_at"])

    if result["success"]:
        amount = f"₹{invoice.grand_total:,.2f}"
        send_notification(
            user=user,
            booking=invoice.booking,
            notification_type=NotificationType.PAYMENT_RECEIVED,
            title="Payment successful",
            message=f"{amount} paid for invoice {invoice.invoice_number}. Transaction {payment.transaction_id}.",
        )
        manager = invoice.service_center.user if invoice.service_center else None
        if manager:
            send_notification(
                user=manager,
                booking=invoice.booking,
                notification_type=NotificationType.PAYMENT_RECEIVED,
                title="Invoice paid",
                message=f"{invoice.invoice_number} was paid online ({amount}).",
            )
    return payment
