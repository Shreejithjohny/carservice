from decimal import Decimal
from django.utils import timezone
from .models import BookingStatus, Invoice, InvoiceItem, ServiceBooking, RepairRequestStatus


class InvoiceError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def generate_invoice_for_booking(booking: ServiceBooking) -> Invoice:
    """
    Generates or recalculates an itemized server-side Invoice for a ServiceBooking.
    Includes base service fee, approved additional repairs, labor hours, and 18% GST tax.
    Only completed bookings are invoiced, and a paid invoice is never recalculated.
    """
    if booking.status != BookingStatus.COMPLETED:
        raise InvoiceError("Invoices can only be generated once the service is completed.", 400)
    existing = Invoice.objects.filter(booking=booking).first()
    if existing and existing.payment_status == Invoice.PaymentStatus.PAID:
        raise InvoiceError("This invoice is already paid and can no longer be changed.", 409)

    # 1. Base service charge
    if booking.service_type and hasattr(booking.service_type, "base_price"):
        subtotal = Decimal(str(booking.service_type.base_price))
    elif booking.estimated_cost and booking.estimated_cost > 0:
        subtotal = Decimal(str(booking.estimated_cost))
    else:
        subtotal = Decimal("1499.00")

    # 2. Approved additional repairs
    approved_repairs = booking.repair_requests.filter(status=RepairRequestStatus.APPROVED)
    additional_repairs_total = sum(
        (Decimal(str(r.additional_cost or r.estimated_cost or "0")) for r in approved_repairs),
        Decimal("0.00"),
    )

    # 3. Labor total
    extra_labor_hours = sum((r.estimated_extra_hours for r in approved_repairs), 0)
    labor_total = Decimal(str(extra_labor_hours)) * Decimal("400.00")

    # 4. Tax (18% GST) & Totals
    taxable_amount = subtotal + additional_repairs_total + labor_total
    tax = (taxable_amount * Decimal("0.18")).quantize(Decimal("0.01"))
    discount = Decimal("0.00")
    grand_total = (taxable_amount + tax - discount).quantize(Decimal("0.01"))

    # 5. Create or Update Invoice
    invoice, created = Invoice.objects.get_or_create(
        booking=booking,
        defaults={
            "customer": booking.customer,
            "vehicle": booking.vehicle,
            "service_center": booking.service_center,
            "subtotal": subtotal,
            "additional_repairs_total": additional_repairs_total,
            "labor_total": labor_total,
            "tax": tax,
            "discount": discount,
            "grand_total": grand_total,
            "base_amount": subtotal,
            "additional_repairs_amount": additional_repairs_total,
            "tax_amount": tax,
            "discount_amount": discount,
            "total_amount": grand_total,
            "payment_status": Invoice.PaymentStatus.PENDING,
            "invoice_status": "ISSUED",
            "issued_at": timezone.now(),
        },
    )

    if not created:
        invoice.customer = booking.customer
        invoice.vehicle = booking.vehicle
        invoice.service_center = booking.service_center
        invoice.subtotal = subtotal
        invoice.additional_repairs_total = additional_repairs_total
        invoice.labor_total = labor_total
        invoice.tax = tax
        invoice.discount = discount
        invoice.grand_total = grand_total
        invoice.base_amount = subtotal
        invoice.additional_repairs_amount = additional_repairs_total
        invoice.tax_amount = tax
        invoice.discount_amount = discount
        invoice.total_amount = grand_total
        invoice.save()

    # 6. Rebuild itemized items
    invoice.items.all().delete()

    # Primary Service item
    service_name = booking.service_type_name or (booking.service_type.name if booking.service_type else "Doorstep Vehicle Service")
    InvoiceItem.objects.create(
        invoice=invoice,
        description=f"Primary Service: {service_name}",
        item_type=InvoiceItem.ItemType.SERVICE,
        quantity=1,
        unit_price=subtotal,
        total_price=subtotal,
    )

    # Approved repairs items
    for repair in approved_repairs:
        rep_cost = Decimal(str(repair.additional_cost or repair.estimated_cost or "0"))
        InvoiceItem.objects.create(
            invoice=invoice,
            description=f"Approved Repair: {repair.issue_title}",
            item_type=InvoiceItem.ItemType.ADDITIONAL_REPAIR,
            quantity=1,
            unit_price=rep_cost,
            total_price=rep_cost,
        )

    # Extra labor item
    if labor_total > 0:
        InvoiceItem.objects.create(
            invoice=invoice,
            description=f"Specialized Repair Labor ({extra_labor_hours} hrs)",
            item_type=InvoiceItem.ItemType.LABOR,
            quantity=extra_labor_hours,
            unit_price=Decimal("400.00"),
            total_price=labor_total,
        )

    # Tax item
    InvoiceItem.objects.create(
        invoice=invoice,
        description="Goods and Services Tax (GST 18%)",
        item_type=InvoiceItem.ItemType.OTHER,
        quantity=1,
        unit_price=tax,
        total_price=tax,
    )

    # 7. Notify customer of invoice generation
    try:
        from .notification_service import send_notification
        from .models import NotificationType
        send_notification(
            user=booking.customer,
            booking=booking,
            notification_type=NotificationType.INVOICE_GENERATED,
            title=f"Invoice #{invoice.invoice_number} Generated",
            message=f"Your service invoice of ₹{grand_total:.2f} has been generated for vehicle {booking.vehicle.registration_number}.",
        )
    except Exception:
        pass

    return invoice
