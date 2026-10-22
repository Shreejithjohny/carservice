from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from api.otp_service import generate_otp_code
from api.models import (
    User,
    UserRole,
    CustomerProfile,
    ServiceCenter,
    ServiceType,
    CarBrand,
    CarModel,
    Vehicle,
    ServiceBooking,
    BookingStatus,
    Employee,
    CarHealthScore,
)


class Command(BaseCommand):
    help = "Seeds demo users for each role and sample booking/vehicle data for UI testing."

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo accounts for all roles...")

        # 1. Admin
        admin, _ = User.objects.get_or_create(
            email="admin@smartdoorstep.com",
            defaults={
                "username": "admin_demo",
                "role": UserRole.ADMIN,
                "first_name": "Admin",
                "last_name": "DoorStep",
                "is_staff": True,
                "is_superuser": True,
                "is_verified": True,
            },
        )
        admin.role = UserRole.ADMIN
        admin.is_staff = True
        admin.is_superuser = True
        admin.is_verified = True
        admin.save()

        # 2. Service Center
        center = ServiceCenter.objects.first()
        if not center:
            center = ServiceCenter.objects.create(
                name="DoorStep Central Workshop",
                address="12, 100 Feet Road, Indiranagar, Bengaluru, Karnataka 560038",
                phone="+91 80 2525 1111",
                email="central@smartdoorstep.com",
                latitude=12.9784,
                longitude=77.6408,
                rating=4.9,
                is_active=True,
            )

        # 3. Manager
        manager, _ = User.objects.get_or_create(
            email="manager@smartdoorstep.com",
            defaults={
                "username": "manager_demo",
                "role": UserRole.SERVICE_CENTER_MANAGER,
                "first_name": "Vikram",
                "last_name": "Manager",
                "is_verified": True,
            },
        )
        manager.role = UserRole.SERVICE_CENTER_MANAGER
        manager.is_staff = False  # app permissions come from the role; staff would expose the Django admin site
        manager.is_verified = True
        manager.save()
        center.user = manager
        center.save()

        # 4. Driver / Valet
        driver, _ = User.objects.get_or_create(
            email="driver@smartdoorstep.com",
            defaults={
                "username": "driver_demo",
                "role": UserRole.DRIVER,
                "first_name": "Ramesh",
                "last_name": "Kumar",
                "phone": "+919876543201",
                "is_verified": True,
            },
        )
        driver.role = UserRole.DRIVER
        driver.is_verified = True
        driver.save()
        Employee.objects.get_or_create(
            user=driver,
            defaults={
                "service_center": center,
                "employee_type": Employee.EmployeeType.VALET,
                "speciality": "Express Doorstep Pickup & Inspection",
            },
        )

        # 5. Mechanic
        mechanic, _ = User.objects.get_or_create(
            email="mechanic@smartdoorstep.com",
            defaults={
                "username": "mechanic_demo",
                "role": UserRole.MECHANIC,
                "first_name": "Suresh",
                "last_name": "Sharma",
                "phone": "+919876543202",
                "is_verified": True,
            },
        )
        mechanic.role = UserRole.MECHANIC
        mechanic.is_verified = True
        mechanic.save()
        Employee.objects.get_or_create(
            user=mechanic,
            defaults={
                "service_center": center,
                "employee_type": Employee.EmployeeType.MECHANIC,
                "speciality": "Engine & Diagnostics Specialist",
            },
        )

        # 6. Customer
        customer, _ = User.objects.get_or_create(
            email="customer@smartdoorstep.com",
            defaults={
                "username": "customer_demo",
                "role": UserRole.CUSTOMER,
                "first_name": "Rahul",
                "last_name": "Verma",
                "phone": "+919876543200",
                "is_verified": True,
            },
        )
        customer.role = UserRole.CUSTOMER
        customer.is_verified = True
        customer.save()
        CustomerProfile.objects.get_or_create(
            user=customer,
            defaults={
                "address": "Flat 402, Green Glen Layout, Bellandur, Bengaluru",
                "latitude": 12.9260,
                "longitude": 77.6762,
            },
        )

        # 7. Customer Vehicle
        brand = CarBrand.objects.filter(name__icontains="Hyundai").first() or CarBrand.objects.first()
        model = CarModel.objects.filter(brand=brand).first() if brand else None

        vehicle, _ = Vehicle.objects.get_or_create(
            registration_number="KA-01-MJ-5500",
            defaults={
                "customer": customer,
                "car_brand": brand,
                "car_model": model,
                "brand": brand.name if brand else "Hyundai",
                "model": model.name if model else "Creta",
                "nickname": "Rahul's Creta",
                "year": 2022,
                "fuel_type": Vehicle.FuelType.PETROL,
                "color": "Polar White",
            },
        )

        CarHealthScore.objects.get_or_create(
            vehicle=vehicle,
            defaults={
                "score": 88,
                "previous_score": 82,
                "service_count": 3,
                "recent_service_count": 1,
                "maintenance_compliance": "Excellent",
                "critical_issue_count": 0,
                "warning_issue_count": 1,
                "resolved_issue_count": 2,
                "explanation": "Vehicle in very good overall health. Brake pads may require replacement in next 5,000 km.",
            },
        )

        # 8. Sample Active Booking
        service_type = ServiceType.objects.filter(name__icontains="General").first() or ServiceType.objects.first()
        existing = ServiceBooking.objects.filter(vehicle=vehicle).first()
        if not existing:
            booking = ServiceBooking.objects.create(
                customer=customer,
                vehicle=vehicle,
                service_type=service_type,
                service_center=center,
                status=BookingStatus.PICKUP_SCHEDULED,
                problem_description="Scheduled 30,000km general service and brake inspection",
                pickup_address="Flat 402, Green Glen Layout, Bellandur, Bengaluru",
                pickup_latitude=12.9260,
                pickup_longitude=77.6762,
                preferred_date=timezone.now().date(),
                preferred_time="10:30 AM",
                assigned_driver=driver,
                assigned_mechanic=mechanic,
                handover_otp=generate_otp_code(),
                handover_otp_verified=False,
                handover_otp_expires_at=timezone.now() + timedelta(days=1),
                estimated_cost=2999.00,
            )
        else:
            booking = existing

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded demo accounts & active booking!\n"
                f"Admin:    admin@smartdoorstep.com (Role: ADMIN)\n"
                f"Manager:  manager@smartdoorstep.com (Role: SERVICE_CENTER_MANAGER)\n"
                f"Driver:   driver@smartdoorstep.com (Role: DRIVER)\n"
                f"Mechanic: mechanic@smartdoorstep.com (Role: MECHANIC)\n"
                f"Customer: customer@smartdoorstep.com (Role: CUSTOMER)\n"
                f"Vehicle:  {vehicle.registration_number} ({vehicle.brand} {vehicle.model})\n"
                f"Booking:  {booking.booking_reference or booking.booking_id} (Status: {booking.status})"
            )
        )
