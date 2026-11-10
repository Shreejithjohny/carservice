"""
Razorpay payments for invoices (PAYMENT_GATEWAY=razorpay).

Flow:
  1. create_order()      - our server asks Razorpay for an order for the invoice total
  2. the browser opens Razorpay Checkout with that order; card/UPI details go only to Razorpay
  3. confirm_checkout()  - the browser returns payment id + signature; we verify the signature,
                           then ask Razorpay for the payment itself and check order, amount, status
  4. handle_webhook()    - Razorpay also tells our server directly, which covers a customer who
                           closes the tab right after paying
Steps 3 and 4 both end in record_payment(), which is safe to run twice for the same payment.
Talks to Razorpay's REST API with `requests`; no SDK needed.
"""
import hashlib
import hmac
import json
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from django.conf import settings
from django.db import transaction

from .models import Invoice, InvoiceStatus, NotificationType, Payment
from .notification_service import send_notification
from .payment_service import PaymentError, notify_invoice_paid, payable_invoice

logger = logging.getLogger(__name__)

API_URL = "https://api.razorpay.com/v1"

METHODS = {
    "upi": Payment.Method.UPI,
    "card": Payment.Method.CARD,
    "emi": Payment.Method.CARD,
    "netbanking": Payment.Method.NETBANKING,
    "wallet": Payment.Method.WALLET,
}


def razorpay_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def _api(method: str, path: str, body: Optional[dict] = None) -> dict:
    if not razorpay_configured():
        raise PaymentError("Online payment is not set up yet. Please pay at the service center.", 503)
    try:
        response = requests.request(
            method, f"{API_URL}{path}", json=body, auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET), timeout=15
        )
    except requests.RequestException as exc:
        logger.error("Razorpay request failed: %s", exc)
        raise PaymentError("Couldn't reach the payment service. Please try again.", 503) from exc
    if response.status_code >= 400:
        logger.error("Razorpay %s %s answered %s: %s", method, path, response.status_code, response.text[:300])
        raise PaymentError("The payment service refused the request. Please try again.", 502)
    return response.json()


def to_paise(amount: Decimal) -> int:
    return int((Decimal(str(amount)) * 100).to_integral_value())


def _signature(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def create_order(invoice_id: int, user) -> Dict[str, Any]:
    """Creates a Razorpay order for the invoice total and returns what Checkout needs."""
    with transaction.atomic():
        invoice = payable_invoice(invoice_id, user)
        order = _api("POST", "/orders", {
            "amount": to_paise(invoice.grand_total),
            "currency": "INR",
            "receipt": invoice.invoice_number,
            "notes": {"invoice_id": str(invoice.pk), "invoice_number": invoice.invoice_number},
        })
        invoice.razorpay_order_id = order["id"]
        invoice.save(update_fields=["razorpay_order_id", "updated_at"])
    return {
        "key_id": settings.RAZORPAY_KEY_ID,
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "invoice_number": invoice.invoice_number,
        "prefill": {
            "name": user.get_full_name(),
            "email": "" if user.email.endswith("@smartdoorstep.local") else user.email,
            "contact": user.phone or "",
        },
    }


def _invoice_id_for_order(order_id: str) -> Optional[int]:
    """Which invoice an order pays. Falls back to the order's own notes for an older order."""
    invoice = Invoice.objects.filter(razorpay_order_id=order_id).first()
    if invoice:
        return invoice.pk
    try:
        return int(_api("GET", f"/orders/{order_id}").get("notes", {}).get("invoice_id"))
    except (TypeError, ValueError):
        return None


def _payer_reference(entity: dict) -> str:
    method = entity.get("method")
    if method == "upi":
        return str(entity.get("vpa") or "UPI")[:60]
    if method in ("card", "emi"):
        last4 = (entity.get("card") or {}).get("last4")
        return f"Card ending {last4}" if last4 else "Card"
    return str(entity.get("bank") or entity.get("wallet") or method or "")[:60]


def record_payment(entity: dict) -> Optional[Payment]:
    """
    Stores a Razorpay payment (the `payment` object from their API or webhook) and marks the
    invoice paid. Returns None for a payment that isn't for one of our invoices. Idempotent.
    """
    payment_id, order_id = entity.get("id"), entity.get("order_id")
    if not payment_id or not order_id:
        return None
    existing = Payment.objects.filter(transaction_id=payment_id).first()
    if existing and existing.status == Payment.Status.SUCCESS:
        return existing
    invoice_id = _invoice_id_for_order(order_id)
    if invoice_id is None:
        logger.warning("Razorpay payment %s is for unknown order %s", payment_id, order_id)
        return None

    if entity.get("status") == "authorized":  # account not on auto-capture: take the money now
        entity = _api("POST", f"/payments/{payment_id}/capture", {"amount": entity["amount"], "currency": "INR"})
    captured = entity.get("status") == "captured"
    paid = Decimal(entity.get("amount", 0)) / 100

    problem = ""
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
        payment = Payment.objects.filter(transaction_id=payment_id).first() or Payment(transaction_id=payment_id)
        payment.invoice = invoice
        payment.customer = invoice.customer
        payment.amount = paid
        payment.method = METHODS.get(entity.get("method"), Payment.Method.OTHER)
        payment.provider = "RAZORPAY"
        payment.payer_reference = _payer_reference(entity)
        payment.status = Payment.Status.SUCCESS if captured else Payment.Status.FAILED
        payment.failure_reason = "" if captured else str(entity.get("error_description") or "Payment failed.")[:200]

        if captured:
            if invoice.payment_status == Invoice.PaymentStatus.PAID:
                problem = "was paid twice"
            elif to_paise(invoice.grand_total) != entity.get("amount") or entity.get("currency") != "INR":
                problem = f"was paid ₹{paid:,.2f} but the invoice total is ₹{invoice.grand_total:,.2f}"
            elif invoice.invoice_status == InvoiceStatus.CANCELLED:
                problem = "was paid after it was cancelled"
            else:
                invoice.payment_status = Invoice.PaymentStatus.PAID
                invoice.invoice_status = InvoiceStatus.PAID
                invoice.save(update_fields=["payment_status", "invoice_status", "updated_at"])
            if problem:
                payment.failure_reason = f"Needs review: invoice {problem}."[:200]
        elif invoice.payment_status != Invoice.PaymentStatus.PAID:
            invoice.payment_status = Invoice.PaymentStatus.FAILED
            invoice.save(update_fields=["payment_status", "updated_at"])
        payment.save()

    if captured and not problem:
        notify_invoice_paid(invoice, payment)
    elif problem:
        # Money was taken but the invoice can't simply be marked paid: a person must refund or settle it
        logger.error("Razorpay payment %s: invoice %s %s", payment_id, invoice.invoice_number, problem)
        manager = invoice.service_center.user if invoice.service_center else None
        if manager:
            send_notification(
                user=manager,
                booking=invoice.booking,
                notification_type=NotificationType.GENERAL,
                title="Payment needs review",
                message=f"Invoice {invoice.invoice_number} {problem} (Razorpay payment {payment_id}). Refund or settle it in the Razorpay dashboard.",
            )
    return payment


def confirm_checkout(invoice_id: int, user, data: Dict[str, Any]) -> Payment:
    """Called by the browser after Razorpay Checkout succeeds."""
    order_id = str(data.get("razorpay_order_id") or "")
    payment_id = str(data.get("razorpay_payment_id") or "")
    signature = str(data.get("razorpay_signature") or "")
    if not (order_id and payment_id and signature):
        raise PaymentError("Payment details are missing.", 400)
    if not razorpay_configured():
        raise PaymentError("Online payment is not set up yet. Please pay at the service center.", 503)

    invoice = Invoice.objects.filter(pk=invoice_id).first()
    if not invoice:
        raise PaymentError("Invoice not found.", 404)
    if invoice.customer_id != user.id:
        raise PaymentError("Only the customer on this invoice can pay it.", 403)

    expected = _signature(settings.RAZORPAY_KEY_SECRET, f"{order_id}|{payment_id}".encode())
    if not hmac.compare_digest(expected, signature):
        raise PaymentError("Payment could not be verified.", 400)

    # The signature proves Razorpay issued this pair; the payment itself says what was paid
    entity = _api("GET", f"/payments/{payment_id}")
    if entity.get("order_id") != order_id or _invoice_id_for_order(order_id) != invoice.pk:
        raise PaymentError("This payment is not for this invoice.", 400)
    payment = record_payment(entity)
    if payment is None:
        raise PaymentError("Payment could not be verified.", 400)
    return payment


def handle_webhook(raw_body: bytes, signature: str) -> str:
    """Verifies and processes a Razorpay webhook. Returns a short note of what was done."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        raise PaymentError("Webhook secret is not configured.", 503)
    if not signature or not hmac.compare_digest(_signature(secret, raw_body), signature):
        raise PaymentError("Invalid signature.", 400)
    try:
        event = json.loads(raw_body)
        name = event.get("event", "")
        entity = event["payload"]["payment"]["entity"]
    except (ValueError, KeyError, TypeError):
        return "ignored"
    if name not in ("payment.captured", "payment.failed", "order.paid"):
        return "ignored"
    payment = record_payment(entity)
    return "recorded" if payment else "ignored"
