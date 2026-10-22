"""
Invoice PDF with a QR code. The QR holds a signed link to the public /verify page, so anyone holding
the paper copy can check that the invoice is genuine and see whether it has been paid.
"""
from io import BytesIO
from xml.sax.saxutils import escape

import qrcode
from django.conf import settings
from django.core import signing
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Invoice

VERIFY_SALT = "invoice-verify"
ACCENT = colors.HexColor("#ff4d2e")


def verification_token(invoice: Invoice) -> str:
    # The signature makes the token unguessable and tamper-proof without storing anything extra.
    return signing.Signer(salt=VERIFY_SALT).sign(invoice.invoice_number)


def invoice_from_token(token: str):
    try:
        number = signing.Signer(salt=VERIFY_SALT).unsign(token)
    except signing.BadSignature:
        return None
    return Invoice.objects.filter(invoice_number=number).first()


def verification_url(invoice: Invoice) -> str:
    return f"{settings.FRONTEND_URL}/verify/{verification_token(invoice)}"


def _e(value) -> str:
    """Paragraph text is parsed as markup, so names and descriptions must be escaped."""
    return escape(str(value or ""))


def _money(value) -> str:
    # Built-in PDF fonts have no rupee glyph, so amounts are written "Rs."
    return f"Rs. {float(value or 0):,.2f}"


def _qr_image(data: str, size_mm: float = 32) -> Image:
    buf = BytesIO()
    qrcode.make(data, box_size=8, border=1).save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=size_mm * mm, height=size_mm * mm)


def build_invoice_pdf(invoice: Invoice) -> bytes:
    styles = getSampleStyleSheet()
    small = styles["Normal"].clone("small", fontSize=8.5, leading=11)
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=invoice.invoice_number, author="DoorStep",
    )
    center = invoice.service_center
    booking = invoice.booking
    vehicle = invoice.vehicle
    customer = invoice.customer
    issued = timezone.localtime(invoice.issued_at).strftime("%d %b %Y")

    header = Table(
        [[
            Paragraph(
                f"<font size=18 color='#ff4d2e'><b>DoorStep</b></font><br/>"
                f"<b>{_e(center.name) if center else 'DoorStep Service'}</b><br/>"
                f"{_e(center.address) if center else ''}<br/>{_e(center.phone) if center else ''}",
                small,
            ),
            Paragraph(
                f"<para align=right><font size=14><b>INVOICE</b></font><br/>"
                f"<b>{_e(invoice.invoice_number)}</b><br/>Issued: {issued}<br/>Booking: {_e(booking.booking_reference)}</para>",
                small,
            ),
        ]],
        colWidths=[100 * mm, 74 * mm],
    )

    customer_name = (customer.get_full_name() or customer.email) if customer else ""
    vehicle_line = f"{vehicle.brand} {vehicle.model} ({vehicle.registration_number})" if vehicle else ""
    parties = Table(
        [[
            Paragraph(f"<b>Billed to</b><br/>{_e(customer_name)}<br/>{_e(customer.phone) if customer else ''}", small),
            Paragraph(f"<b>Vehicle</b><br/>{_e(vehicle_line)}<br/>{_e(vehicle.fuel_type) if vehicle else ''}", small),
        ]],
        colWidths=[87 * mm, 87 * mm],
    )

    rows = [["Description", "Qty", "Unit price", "Amount"]]
    for item in invoice.items.all():
        rows.append([Paragraph(_e(item.description), small), str(item.quantity), _money(item.unit_price), _money(item.total_price)])
    items = Table(rows, colWidths=[96 * mm, 14 * mm, 32 * mm, 32 * mm], repeatRows=1)
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f5")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e4e4e7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    paid = invoice.payment_status == Invoice.PaymentStatus.PAID
    totals = Table(
        [
            ["Service", _money(invoice.subtotal)],
            ["Approved repairs", _money(invoice.additional_repairs_total)],
            ["Repair labour", _money(invoice.labor_total)],
            ["GST (18%)", _money(invoice.tax)],
            ["Grand total", _money(invoice.grand_total)],
            ["Status", "PAID" if paid else "UNPAID"],
        ],
        colWidths=[40 * mm, 34 * mm],
    )
    totals.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
        ("LINEABOVE", (0, 4), (-1, 4), 0.75, colors.black),
        ("TEXTCOLOR", (1, 5), (1, 5), colors.HexColor("#059669") if paid else ACCENT),
        ("FONTNAME", (1, 5), (1, 5), "Helvetica-Bold"),
    ]))

    qr_block = Table(
        [[_qr_image(verification_url(invoice))], [Paragraph("<para align=center>Scan to verify this invoice</para>", small)]],
        colWidths=[40 * mm],
    )
    footer = Table([[qr_block, totals]], colWidths=[100 * mm, 74 * mm])
    footer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    doc.build([
        header, Spacer(1, 8 * mm), parties, Spacer(1, 6 * mm), items, Spacer(1, 6 * mm), footer, Spacer(1, 8 * mm),
        Paragraph("Computer-generated invoice; no signature required.", small),
    ])
    return buf.getvalue()
