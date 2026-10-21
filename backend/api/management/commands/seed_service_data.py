from django.core.management.base import BaseCommand
from api.models import ServiceType, ServiceCenter

INITIAL_SERVICES = [
    {
        "name": "General Service",
        "description": "Comprehensive multi-point vehicle inspection, fluid top-ups, air filter cleaning, and safety checks.",
        "base_price": 2999.00,
        "estimated_duration": "4 hours",
    },
    {
        "name": "Oil Change",
        "description": "Premium engine oil replacement, oil filter change, and engine health scan.",
        "base_price": 1499.00,
        "estimated_duration": "1 hour",
    },
    {
        "name": "AC Service",
        "description": "AC refrigerant top-up, cabin filter cleaning, and condenser inspection.",
        "base_price": 1999.00,
        "estimated_duration": "2 hours",
    },
    {
        "name": "Brake Service",
        "description": "Brake pad inspection, brake fluid flush, and disc rotor cleaning.",
        "base_price": 1899.00,
        "estimated_duration": "2 hours",
    },
    {
        "name": "Engine Service",
        "description": "Full engine diagnostic scan, spark plug check, fuel injector cleaning, and tuning.",
        "base_price": 3499.00,
        "estimated_duration": "5 hours",
    },
    {
        "name": "Battery Service",
        "description": "Battery health testing, terminal cleaning, voltage test, and doorstep replacement.",
        "base_price": 2499.00,
        "estimated_duration": "1 hour",
    },
    {
        "name": "Tyre Service",
        "description": "Wheel alignment, balancing, tyre rotation, and pressure calibration.",
        "base_price": 1299.00,
        "estimated_duration": "1 hour",
    },
    {
        "name": "Full Inspection",
        "description": "71-point digital job card evaluation covering mechanical, electrical, and body condition.",
        "base_price": 999.00,
        "estimated_duration": "2 hours",
    },
]

INITIAL_CENTERS = [
    {
        "name": "DoorStep Central Workshop",
        "address": "12, 100 Feet Road, Indiranagar, Bengaluru, Karnataka 560038",
        "phone": "+91 80 2525 1111",
        "email": "central@smartdoorstep.com",
        "latitude": 12.9784,
        "longitude": 77.6408,
        "rating": 4.9,
    },
    {
        "name": "DoorStep North Hub",
        "address": "45, Major Unnikrishnan Road, Yelahanka, Bengaluru, Karnataka 560064",
        "phone": "+91 80 2525 2222",
        "email": "north@smartdoorstep.com",
        "latitude": 13.1007,
        "longitude": 77.5963,
        "rating": 4.8,
    },
    {
        "name": "DoorStep South Hub",
        "address": "88, 80 Feet Road, Koramangala 4th Block, Bengaluru, Karnataka 560034",
        "phone": "+91 80 2525 3333",
        "email": "south@smartdoorstep.com",
        "latitude": 12.9352,
        "longitude": 77.6245,
        "rating": 4.85,
    },
]


class Command(BaseCommand):
    help = "Seeds initial ServiceType items and sample ServiceCenter records."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding service types and service centers..."))

        services_created = 0
        for s in INITIAL_SERVICES:
            obj, created = ServiceType.objects.get_or_create(
                name=s["name"],
                defaults={
                    "description": s["description"],
                    "base_price": s["base_price"],
                    "estimated_duration": s["estimated_duration"],
                    "active": True,
                },
            )
            if created:
                services_created += 1

        centers_created = 0
        for c in INITIAL_CENTERS:
            obj, created = ServiceCenter.objects.get_or_create(
                name=c["name"],
                defaults={
                    "address": c["address"],
                    "phone": c["phone"],
                    "email": c["email"],
                    "latitude": c["latitude"],
                    "longitude": c["longitude"],
                    "rating": c["rating"],
                    "is_active": True,
                    "active": True,
                },
            )
            if created:
                centers_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded service data!\n"
                f"ServiceTypes total: {ServiceType.objects.count()} (new: {services_created})\n"
                f"ServiceCenters total: {ServiceCenter.objects.count()} (new: {centers_created})"
            )
        )
