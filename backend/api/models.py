from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import uuid


class UserRole(models.TextChoices):
    CUSTOMER = "CUSTOMER", _("Customer")
    SERVICE_CENTER_MANAGER = "SERVICE_CENTER_MANAGER", _("Service Center Manager")
    DRIVER = "DRIVER", _("Driver / Valet")
    MECHANIC = "MECHANIC", _("Mechanic")
    ADMIN = "ADMIN", _("Admin")


class User(AbstractUser):
    role = models.CharField(
        max_length=30, choices=UserRole.choices, default=UserRole.CUSTOMER
    )
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True)

    # OTP Details
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    otp_attempts = models.PositiveIntegerField(default=0)
    otp_last_sent_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.email} ({self.role})"


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="customer_profile"
    )
    address = models.TextField(blank=True, default="")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Customer Profile: {self.user.email}"


class CarBrand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    logo = models.ImageField(upload_to="brand_logos/", null=True, blank=True)
    logo_url = models.CharField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["name"], name="unique_car_brand_name")
        ]

    def __str__(self):
        return self.name


class CarModel(models.Model):
    class BodyType(models.TextChoices):
        HATCHBACK = "Hatchback", _("Hatchback")
        SEDAN = "Sedan", _("Sedan")
        SUV = "SUV", _("SUV")
        MUV = "MUV", _("MUV")
        COUPE = "Coupe", _("Coupe")
        CONVERTIBLE = "Convertible", _("Convertible")
        EV = "EV", _("Electric Vehicle")

    brand = models.ForeignKey(CarBrand, on_delete=models.CASCADE, related_name="models")
    name = models.CharField(max_length=100)
    body_type = models.CharField(
        max_length=30, choices=BodyType.choices, default=BodyType.HATCHBACK
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["brand", "name"], name="unique_car_model_per_brand")
        ]

    def __str__(self):
        return f"{self.brand.name} {self.name}"


class CarVariant(models.Model):
    class FuelType(models.TextChoices):
        PETROL = "Petrol", _("Petrol")
        DIESEL = "Diesel", _("Diesel")
        CNG = "CNG", _("CNG")
        ELECTRIC = "Electric", _("Electric")
        HYBRID = "Hybrid", _("Hybrid")

    class Transmission(models.TextChoices):
        MANUAL = "Manual", _("Manual")
        AUTOMATIC = "Automatic", _("Automatic")
        AMT = "AMT", _("AMT")
        CVT = "CVT", _("CVT")
        DCT = "DCT", _("DCT")

    model = models.ForeignKey(CarModel, on_delete=models.CASCADE, related_name="variants")
    name = models.CharField(max_length=100)
    fuel_type = models.CharField(
        max_length=20, choices=FuelType.choices, default=FuelType.PETROL
    )
    transmission = models.CharField(
        max_length=20, choices=Transmission.choices, default=Transmission.MANUAL
    )
    engine = models.CharField(max_length=50, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["model", "name"], name="unique_car_variant_per_model")
        ]

    def __str__(self):
        return f"{self.model.brand.name} {self.model.name} {self.name}"


class Vehicle(models.Model):
    class FuelType(models.TextChoices):
        PETROL = "Petrol", _("Petrol")
        DIESEL = "Diesel", _("Diesel")
        CNG = "CNG", _("CNG")
        ELECTRIC = "Electric", _("Electric")
        HYBRID = "Hybrid", _("Hybrid")

    customer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="vehicles"
    )
    car_brand = models.ForeignKey(
        CarBrand, on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_vehicles"
    )
    car_model = models.ForeignKey(
        CarModel, on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_vehicles"
    )
    car_variant = models.ForeignKey(
        CarVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="customer_vehicles"
    )
    brand = models.CharField(max_length=100, blank=True, default="")
    model = models.CharField(max_length=100, blank=True, default="")
    variant_name = models.CharField(max_length=100, blank=True, default="")
    nickname = models.CharField(max_length=100, blank=True, default="")
    year = models.PositiveIntegerField(default=2021)
    fuel_type = models.CharField(
        max_length=20, choices=FuelType.choices, default=FuelType.PETROL
    )
    registration_number = models.CharField(max_length=20, unique=True)
    color = models.CharField(max_length=30, blank=True, default="")
    # Latest odometer reading we know of (from the customer or a driver's pickup/delivery reading).
    odometer_km = models.PositiveIntegerField(null=True, blank=True)
    image = models.ImageField(upload_to="vehicle_images/", null=True, blank=True)
    image_url = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.car_brand and not self.brand:
            self.brand = self.car_brand.name
        if self.car_model and not self.model:
            self.model = self.car_model.name
        if self.car_variant:
            if not self.variant_name:
                self.variant_name = self.car_variant.name
            if not self.fuel_type or self.fuel_type == Vehicle.FuelType.PETROL:
                self.fuel_type = self.car_variant.fuel_type
        if not self.nickname:
            self.nickname = f"{self.brand} {self.model}".strip() or "My Vehicle"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.brand} {self.model} ({self.registration_number})"


class ServiceType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_duration = models.CharField(max_length=50, default="2 hours")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (₹{self.base_price})"


class ServiceCenter(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_center_profile",
    )
    name = models.CharField(max_length=150)
    address = models.TextField()
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    latitude = models.FloatField(default=12.9716)
    longitude = models.FloatField(default=77.5946)
    rating = models.FloatField(default=4.8)
    # Pickups the center can handle in each time slot (roughly its number of drivers).
    slot_capacity = models.PositiveIntegerField(default=3)
    is_active = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.active = self.is_active
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Employee(models.Model):
    class EmployeeType(models.TextChoices):
        VALET = "VALET", _("Pickup Valet")
        MECHANIC = "MECHANIC", _("Mechanic")
        MANAGER = "MANAGER", _("Manager")

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="employee_profile"
    )
    service_center = models.ForeignKey(
        ServiceCenter, on_delete=models.CASCADE, related_name="employees"
    )
    employee_type = models.CharField(
        max_length=20, choices=EmployeeType.choices, default=EmployeeType.VALET
    )
    speciality = models.CharField(max_length=100, blank=True, default="")
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} - {self.employee_type}"


class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_duration_hours = models.PositiveIntegerField(default=2)
    service_center = models.ForeignKey(
        ServiceCenter,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="services",
    )

    def __str__(self):
        return f"{self.name} (₹{self.base_price})"


class BookingStatus(models.TextChoices):
    PENDING = "Pending", _("Pending")
    CONFIRMED = "Confirmed", _("Confirmed")
    PICKUP_SCHEDULED = "Pickup Scheduled", _("Pickup Scheduled")
    VEHICLE_PICKED_UP = "Vehicle Picked Up", _("Vehicle Picked Up")
    IN_SERVICE = "In Service", _("In Service")
    READY_FOR_DELIVERY = "Ready for Delivery", _("Ready for Delivery")
    OUT_FOR_DELIVERY = "Out for Delivery", _("Out for Delivery")
    COMPLETED = "Completed", _("Completed")
    CANCELLED = "Cancelled", _("Cancelled")


class ServiceBooking(models.Model):
    booking_reference = models.CharField(max_length=30, unique=True, null=True, blank=True, editable=False)
    booking_id = models.CharField(max_length=30, unique=True, editable=False)
    customer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="bookings"
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="bookings"
    )
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    service_center = models.ForeignKey(
        ServiceCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )
    service_type_name = models.CharField(max_length=100, blank=True, default="")
    problem_description = models.TextField(blank=True, default="")
    pickup_address = models.TextField()
    pickup_latitude = models.FloatField(null=True, blank=True)
    pickup_longitude = models.FloatField(null=True, blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.CharField(max_length=30, blank=True, default="10:00 AM")
    customer_notes = models.TextField(blank=True, default="")
    pickup_scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=35, choices=BookingStatus.choices, default=BookingStatus.PENDING
    )
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_cost_min = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_cost_max = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    assigned_driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_bookings",
    )
    assigned_mechanic = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mechanic_bookings",
    )
    handover_otp = models.CharField(max_length=6, blank=True, default="")
    handover_otp_verified = models.BooleanField(default=False)
    handover_otp_expires_at = models.DateTimeField(null=True, blank=True)
    handover_otp_attempts = models.PositiveIntegerField(default=0)
    # Return trip: the customer gives this code to the driver when the car is handed back.
    delivery_otp = models.CharField(max_length=6, blank=True, default="")
    delivery_otp_verified = models.BooleanField(default=False)
    delivery_otp_expires_at = models.DateTimeField(null=True, blank=True)
    delivery_otp_attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Odometer readings taken by the driver, so the customer can see how far the car was driven.
    pickup_odometer_km = models.PositiveIntegerField(null=True, blank=True)
    delivery_odometer_km = models.PositiveIntegerField(null=True, blank=True)
    # Set when the driver's photo of the number plate matched the registration on the booking.
    plate_verified = models.BooleanField(default=False)
    plate_detected = models.CharField(max_length=20, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.booking_reference:
            year = timezone.now().year
            last_booking = ServiceBooking.objects.filter(
                booking_reference__startswith=f"SDV-{year}-"
            ).order_by("-id").first()
            if last_booking and last_booking.booking_reference:
                try:
                    last_num = int(last_booking.booking_reference.split("-")[-1])
                    seq = last_num + 1
                except ValueError:
                    seq = ServiceBooking.objects.count() + 1
            else:
                seq = 1
            self.booking_reference = f"SDV-{year}-{seq:06d}"
        if not self.booking_id:
            self.booking_id = self.booking_reference
        if self.service_type:
            if not self.service_type_name:
                self.service_type_name = self.service_type.name
            if not self.estimated_cost or self.estimated_cost == 0:
                self.estimated_cost = self.service_type.base_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_reference} - {self.status}"


class PickupAssignment(models.Model):
    class AssignmentStatus(models.TextChoices):
        ASSIGNED = "ASSIGNED", _("Assigned")
        EN_ROUTE_PICKUP = "EN_ROUTE_PICKUP", _("En Route for Pickup")
        PICKED_UP = "PICKED_UP", _("Picked Up")
        EN_ROUTE_DELIVERY = "EN_ROUTE_DELIVERY", _("En Route for Delivery")
        DELIVERED = "DELIVERED", _("Delivered")

    booking = models.OneToOneField(
        ServiceBooking, on_delete=models.CASCADE, related_name="pickup_assignment"
    )
    employee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="assigned_pickups"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=25, choices=AssignmentStatus.choices, default=AssignmentStatus.ASSIGNED
    )

    def __str__(self):
        return f"Assignment for {self.booking.booking_reference} to {self.employee.email}"


class DriverLocation(models.Model):
    driver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="driver_locations"
    )
    booking = models.ForeignKey(
        ServiceBooking, on_delete=models.CASCADE, related_name="driver_locations"
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Loc for {self.booking.booking_reference} by {self.driver.email} at {self.timestamp}"


# Alias for backward compatibility
LocationTracking = DriverLocation


class ServiceInspection(models.Model):
    class SeverityLevel(models.TextChoices):
        LOW = "LOW", _("Low")
        MEDIUM = "MEDIUM", _("Medium")
        HIGH = "HIGH", _("High")
        CRITICAL = "CRITICAL", _("Critical")

    booking = models.ForeignKey(
        ServiceBooking, on_delete=models.CASCADE, related_name="inspections"
    )
    mechanic = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="conducted_inspections"
    )
    inspection_notes = models.TextField()
    issue_description = models.TextField(blank=True, default="")
    severity = models.CharField(
        max_length=15, choices=SeverityLevel.choices, default=SeverityLevel.MEDIUM
    )
    estimated_additional_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Inspection for {self.booking.booking_reference} by {self.mechanic.email}"


class RepairEvidence(models.Model):
    class MediaType(models.TextChoices):
        PHOTO = "PHOTO", _("Photo")
        VIDEO = "VIDEO", _("Video")

    booking = models.ForeignKey(
        ServiceBooking, on_delete=models.CASCADE, related_name="evidence_items"
    )
    mechanic = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="uploaded_evidence"
    )
    issue_title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    media_type = models.CharField(
        max_length=10, choices=MediaType.choices, default=MediaType.PHOTO
    )
    file = models.FileField(upload_to="repair_evidence/", null=True, blank=True)
    file_url = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Evidence {self.issue_title} for {self.booking.booking_reference}"


class VehicleConditionPhoto(models.Model):
    """Photos the driver takes at pickup and again at delivery, so any new damage is visible."""

    class Stage(models.TextChoices):
        PICKUP = "PICKUP", _("Pickup")
        DELIVERY = "DELIVERY", _("Delivery")

    class Angle(models.TextChoices):
        FRONT = "FRONT", _("Front")
        REAR = "REAR", _("Rear")
        LEFT = "LEFT", _("Left side")
        RIGHT = "RIGHT", _("Right side")
        INTERIOR = "INTERIOR", _("Interior")
        ODOMETER = "ODOMETER", _("Odometer")
        OTHER = "OTHER", _("Other / close-up")

    booking = models.ForeignKey(
        ServiceBooking, on_delete=models.CASCADE, related_name="condition_photos"
    )
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="condition_photos"
    )
    stage = models.CharField(max_length=10, choices=Stage.choices)
    angle = models.CharField(max_length=10, choices=Angle.choices, default=Angle.OTHER)
    file = models.FileField(upload_to="condition_photos/")
    notes = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.stage} {self.angle} photo for {self.booking.booking_reference}"


class RepairRequestStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    REJECTED = "REJECTED", _("Rejected")


class RepairRequest(models.Model):
    booking = models.ForeignKey(
        ServiceBooking, on_delete=models.CASCADE, related_name="repair_requests"
    )
    mechanic = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_repair_requests"
    )
    issue_title = models.CharField(max_length=150)
    description = models.TextField()
    additional_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_extra_hours = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=15, choices=RepairRequestStatus.choices, default=RepairRequestStatus.PENDING
    )
    customer_response = models.TextField(blank=True, default="")
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.estimated_cost or self.estimated_cost == 0:
            self.estimated_cost = self.additional_cost
        elif not self.additional_cost or self.additional_cost == 0:
            self.additional_cost = self.estimated_cost
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Repair: {self.issue_title} for {self.booking.booking_reference} ({self.status})"



class EstimationSource(models.TextChoices):
    AI = "AI", _("AI")
    RULE_BASED = "RULE_BASED", _("Rule-Based")
    MANUAL = "MANUAL", _("Manual")


class RepairCostEstimate(models.Model):
    booking = models.ForeignKey(
        ServiceBooking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cost_estimates",
    )
    repair_request = models.ForeignKey(
        RepairRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cost_estimates",
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="repair_cost_estimates"
    )
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repair_cost_estimates",
    )
    issue_description = models.TextField()
    severity = models.CharField(max_length=20, default="MEDIUM")
    estimated_min_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_max_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estimated_labor_hours = models.DecimalField(max_digits=5, decimal_places=1, default=1.0)
    estimation_source = models.CharField(
        max_length=20, choices=EstimationSource.choices, default=EstimationSource.AI
    )
    explanation = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Estimate for {self.vehicle}: ₹{self.estimated_min_cost}–₹{self.estimated_max_cost} ({self.estimation_source})"


class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    ISSUED = "ISSUED", _("Issued")
    PAID = "PAID", _("Paid")
    CANCELLED = "CANCELLED", _("Cancelled")


class Invoice(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        PAID = "PAID", _("Paid")
        FAILED = "FAILED", _("Failed")
        REFUNDED = "REFUNDED", _("Refunded")

    invoice_number = models.CharField(max_length=40, unique=True, editable=False)
    booking = models.OneToOneField(
        ServiceBooking, on_delete=models.CASCADE, related_name="invoice"
    )
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="invoices",
        null=True,
        blank=True,
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="invoices",
        null=True,
        blank=True,
    )
    service_center = models.ForeignKey(
        ServiceCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )

    # Breakdown fields
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    additional_repairs_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    labor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Legacy alias fields for backward compatibility
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    additional_repairs_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    invoice_status = models.CharField(
        max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.ISSUED
    )
    issued_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.booking:
            if not self.customer_id:
                self.customer = self.booking.customer
            if not self.vehicle_id:
                self.vehicle = self.booking.vehicle
            if not self.service_center_id:
                self.service_center = self.booking.service_center

        if not self.invoice_number:
            year = timezone.now().year
            last_inv = Invoice.objects.filter(
                invoice_number__startswith=f"SDV-INV-{year}-"
            ).order_by("-id").first()
            if last_inv and last_inv.invoice_number:
                try:
                    last_num = int(last_inv.invoice_number.split("-")[-1])
                    seq = last_num + 1
                except ValueError:
                    seq = Invoice.objects.count() + 1
            else:
                seq = 1
            self.invoice_number = f"SDV-INV-{year}-{seq:06d}"

        # Keep synchronized
        if self.subtotal and not self.base_amount:
            self.base_amount = self.subtotal
        elif self.base_amount and not self.subtotal:
            self.subtotal = self.base_amount

        if self.additional_repairs_total and not self.additional_repairs_amount:
            self.additional_repairs_amount = self.additional_repairs_total
        elif self.additional_repairs_amount and not self.additional_repairs_total:
            self.additional_repairs_total = self.additional_repairs_amount

        if self.tax and not self.tax_amount:
            self.tax_amount = self.tax
        elif self.tax_amount and not self.tax:
            self.tax = self.tax_amount

        if self.discount and not self.discount_amount:
            self.discount_amount = self.discount
        elif self.discount_amount and not self.discount:
            self.discount = self.discount_amount

        if self.grand_total and not self.total_amount:
            self.total_amount = self.grand_total
        elif self.total_amount and not self.grand_total:
            self.grand_total = self.total_amount

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} (₹{self.grand_total})"


class InvoiceItem(models.Model):
    class ItemType(models.TextChoices):
        SERVICE = "SERVICE", _("Service")
        PART = "PART", _("Part")
        LABOR = "LABOR", _("Labor")
        LABOUR = "LABOUR", _("Labour")
        ADDITIONAL_REPAIR = "ADDITIONAL_REPAIR", _("Additional Repair")
        EXTRA_REPAIR = "EXTRA_REPAIR", _("Extra Repair")
        DISCOUNT = "DISCOUNT", _("Discount")
        OTHER = "OTHER", _("Other")

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="items"
    )
    description = models.CharField(max_length=200)
    item_type = models.CharField(
        max_length=25, choices=ItemType.choices, default=ItemType.SERVICE
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.description} - ₹{self.total_price}"


class Payment(models.Model):
    """One payment attempt against an invoice (successful or failed)."""

    class Method(models.TextChoices):
        UPI = "UPI", _("UPI")
        CARD = "CARD", _("Card")

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", _("Success")
        FAILED = "FAILED", _("Failed")

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices)
    status = models.CharField(max_length=10, choices=Status.choices)
    provider = models.CharField(max_length=20, default="MOCK")
    transaction_id = models.CharField(max_length=40, unique=True)
    # Masked payer reference only (UPI ID or card last 4); full card numbers are never stored.
    payer_reference = models.CharField(max_length=60, blank=True)
    failure_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.transaction_id} {self.status} ₹{self.amount}"


class CarHealthScore(models.Model):
    vehicle = models.OneToOneField(
        Vehicle, on_delete=models.CASCADE, related_name="health_score"
    )
    score = models.IntegerField(default=100)
    previous_score = models.IntegerField(default=100)
    service_count = models.IntegerField(default=0)
    recent_service_count = models.IntegerField(default=0)
    maintenance_compliance = models.CharField(max_length=30, default="Good")
    critical_issue_count = models.IntegerField(default=0)
    warning_issue_count = models.IntegerField(default=0)
    resolved_issue_count = models.IntegerField(default=0)
    explanation = models.TextField(blank=True, default="")
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-calculated_at"]

    def __str__(self):
        return f"Health Score for {self.vehicle}: {self.score}/100"


class NotificationType(models.TextChoices):
    BOOKING_CREATED = "BOOKING_CREATED", _("Booking Created")
    BOOKING_CONFIRMED = "BOOKING_CONFIRMED", _("Booking Confirmed")
    PICKUP_SCHEDULED = "PICKUP_SCHEDULED", _("Pickup Scheduled")
    DRIVER_ASSIGNED = "DRIVER_ASSIGNED", _("Driver Assigned")
    VEHICLE_PICKED_UP = "VEHICLE_PICKED_UP", _("Vehicle Picked Up")
    SERVICE_STARTED = "SERVICE_STARTED", _("Service Started")
    REPAIR_APPROVAL_REQUIRED = "REPAIR_APPROVAL_REQUIRED", _("Repair Approval Required")
    REPAIR_APPROVED = "REPAIR_APPROVED", _("Repair Approved")
    REPAIR_REJECTED = "REPAIR_REJECTED", _("Repair Rejected")
    SERVICE_COMPLETED = "SERVICE_COMPLETED", _("Service Completed")
    READY_FOR_DELIVERY = "READY_FOR_DELIVERY", _("Ready for Delivery")
    DELIVERY_COMPLETED = "DELIVERY_COMPLETED", _("Delivery Completed")
    INVOICE_GENERATED = "INVOICE_GENERATED", _("Invoice Generated")
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED", _("Payment Received")
    GENERAL = "GENERAL", _("General")


class Notification(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    booking = models.ForeignKey(
        ServiceBooking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=50, choices=NotificationType.choices, default=NotificationType.GENERAL
    )
    title = models.CharField(max_length=150)
    message = models.TextField(blank=True, default="")
    body = models.TextField(blank=True, default="")
    read = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.message and not self.body:
            self.body = self.message
        elif self.body and not self.message:
            self.message = self.body
        if self.read != self.is_read:
            if self.read:
                self.is_read = True
            elif self.is_read:
                self.read = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Notification to {self.user.email}: {self.title}"


class ServiceHistory(models.Model):
    customer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="service_histories"
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="service_histories"
    )
    booking = models.ForeignKey(
        ServiceBooking, on_delete=models.SET_NULL, null=True, blank=True
    )
    service_summary = models.CharField(max_length=200)
    completed_at = models.DateTimeField()
    health_impact_score = models.IntegerField(default=0)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["-completed_at"]

    def __str__(self):
        return f"History for {self.vehicle.registration_number} on {self.completed_at.strftime('%Y-%m-%d')}"
