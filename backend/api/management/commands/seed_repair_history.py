"""
Creates SYNTHETIC completed bookings with approved repairs so the learned cost model can be
demonstrated before real repair history exists. Every generated booking's notes start with
"[synthetic]", and the trained model reports what share of its data was synthetic.

The prices come from the made-up process below, so a model trained on them can only show that it
recovers this process. It says nothing about real workshop prices.
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.ml_cost_model import SYNTHETIC_HISTORY_EMAIL, SYNTHETIC_MARKER
from api.models import (
    BookingStatus, RepairRequest, RepairRequestStatus, ServiceBooking, ServiceCenter, ServiceInspection,
    ServiceType, User, UserRole, Vehicle,
)

FUELS = ["Petrol", "Petrol", "Petrol", "Diesel", "Diesel", "CNG", "Electric", "Hybrid"]
SEVERITY_FACTOR = {"LOW": 0.7, "MEDIUM": 1.0, "HIGH": 1.6, "CRITICAL": 2.5}
FUEL_FACTOR = {"Petrol": 1.0, "Diesel": 1.15, "CNG": 1.05, "Electric": 1.3, "Hybrid": 1.25}
REPAIRS = ["Brake pads", "Clutch plate", "Suspension bush", "Battery", "AC compressor", "Wiper motor", "Radiator hose"]


class Command(BaseCommand):
    help = "Generates synthetic repair history for demonstrating the learned cost model (demo only)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=200)
        parser.add_argument("--seed", type=int, default=7)

    def handle(self, *args, **options):
        # A seeded, non-cryptographic generator is deliberate: the demo data must be reproducible and
        # nothing secret is derived from it (OTPs use the secrets module). Hence the NOSONAR markers.
        rng = random.Random(options["seed"])
        service_types = list(ServiceType.objects.all())
        if not service_types:
            self.stderr.write("Run `npm run seed` first so service packages exist.")
            return
        # A hidden center keeps the fake jobs out of real centers' booking lists and analytics
        center, _ = ServiceCenter.objects.get_or_create(
            name="Synthetic history (demo data)",
            defaults={"address": "Not a real center", "phone": "0000000000", "email": "synthetic@smartdoorstep.local", "is_active": False},
        )
        customer, _ = User.objects.get_or_create(
            email=SYNTHETIC_HISTORY_EMAIL,
            defaults={"username": "synthetic_history", "role": UserRole.CUSTOMER, "first_name": "Synthetic"},
        )
        mechanic = User.objects.filter(role=UserRole.MECHANIC).first() or customer
        now = timezone.now()

        for i in range(options["count"]):
            fuel = rng.choice(FUELS)  # NOSONAR
            year = rng.randint(2010, 2025)  # NOSONAR
            vehicle = Vehicle.objects.create(
                customer=customer, brand="Synthetic", model=f"Car {i}", fuel_type=fuel, year=year,
                registration_number=f"SY{options['seed']:02d}{i:06d}",
            )
            st = rng.choice(service_types)  # NOSONAR
            severity = rng.choices(list(SEVERITY_FACTOR), weights=[3, 4, 2, 1])[0]  # NOSONAR
            hours = rng.randint(1, 6)  # NOSONAR
            age = now.year - year
            # Hidden "true" price process plus ±20%-ish log-normal noise
            parts = 900 * SEVERITY_FACTOR[severity] * FUEL_FACTOR[fuel] * (1 + 0.03 * age) * (float(st.base_price) / 2000) ** 0.5
            cost = round(parts * rng.lognormvariate(0, 0.2) + 350 * hours * rng.lognormvariate(0, 0.1), -1)  # NOSONAR
            done = now - timedelta(days=rng.randint(1, 330))  # NOSONAR
            booking = ServiceBooking.objects.create(
                customer=customer, vehicle=vehicle, service_type=st, service_center=center,
                pickup_address="Synthetic", status=BookingStatus.COMPLETED, completed_at=done,
                customer_notes=f"{SYNTHETIC_MARKER} generated demo history",
            )
            ServiceInspection.objects.create(booking=booking, mechanic=mechanic, inspection_notes="Synthetic", severity=severity)
            RepairRequest.objects.create(
                booking=booking, mechanic=mechanic, issue_title=rng.choice(REPAIRS), description="Synthetic",  # NOSONAR
                additional_cost=cost, estimated_extra_hours=hours, status=RepairRequestStatus.APPROVED,
            )
        self.stdout.write(self.style.WARNING(f"Created {options['count']} SYNTHETIC repairs. Do not report model accuracy on them as real."))
