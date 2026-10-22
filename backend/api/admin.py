from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    CustomerProfile,
    CarBrand,
    CarModel,
    CarVariant,
    Vehicle,
    ServiceType,
    ServiceCenter,
    Employee,
    Service,
    ServiceBooking,
    PickupAssignment,
    DriverLocation,
    ServiceInspection,
    RepairEvidence,
    RepairRequest,
    Invoice,
    InvoiceItem,
    Payment,
    Notification,
    ServiceHistory,
    RepairCostEstimate,
    CarHealthScore,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Custom Fields", {"fields": ("role", "phone", "otp_code", "otp_expires_at", "otp_attempts", "is_verified")}),
    )
    list_display = ["email", "username", "role", "phone", "is_verified", "is_staff"]
    list_filter = ["role", "is_verified", "is_staff"]


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "latitude", "longitude"]


@admin.register(CarBrand)
class CarBrandAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "created_at"]
    search_fields = ["name"]
    list_filter = ["is_active"]


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ["name", "brand", "body_type", "is_active"]
    search_fields = ["name", "brand__name"]
    list_filter = ["brand", "body_type", "is_active"]


@admin.register(CarVariant)
class CarVariantAdmin(admin.ModelAdmin):
    list_display = ["name", "model", "fuel_type", "transmission", "engine", "is_active"]
    search_fields = ["name", "model__name", "model__brand__name"]
    list_filter = ["fuel_type", "transmission", "is_active"]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ["registration_number", "brand", "model", "variant_name", "customer", "fuel_type", "year"]
    search_fields = ["registration_number", "brand", "model", "variant_name"]


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "base_price", "estimated_duration", "active", "created_at"]
    search_fields = ["name", "description"]
    list_filter = ["active"]


@admin.register(ServiceCenter)
class ServiceCenterAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "email", "rating", "is_active", "active"]
    search_fields = ["name", "email"]
    list_filter = ["is_active"]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["user", "service_center", "employee_type", "is_available"]
    list_filter = ["employee_type", "is_available"]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "base_price", "estimated_duration_hours", "service_center"]


@admin.register(ServiceBooking)
class ServiceBookingAdmin(admin.ModelAdmin):
    list_display = [
        "booking_reference",
        "customer",
        "vehicle",
        "service_type",
        "service_center",
        "preferred_date",
        "preferred_time",
        "estimated_cost",
        "status",
        "created_at",
    ]
    list_filter = ["status", "preferred_date", "created_at"]
    search_fields = [
        "booking_reference",
        "booking_id",
        "customer__email",
        "vehicle__registration_number",
    ]


@admin.register(PickupAssignment)
class PickupAssignmentAdmin(admin.ModelAdmin):
    list_display = ["booking", "employee", "status", "assigned_at"]


@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display = ["booking", "driver", "latitude", "longitude", "timestamp"]


@admin.register(ServiceInspection)
class ServiceInspectionAdmin(admin.ModelAdmin):
    list_display = ["booking", "mechanic", "severity", "estimated_additional_cost", "created_at"]


@admin.register(RepairEvidence)
class RepairEvidenceAdmin(admin.ModelAdmin):
    list_display = ["booking", "mechanic", "issue_title", "media_type", "created_at"]


@admin.register(RepairRequest)
class RepairRequestAdmin(admin.ModelAdmin):
    list_display = ["booking", "mechanic", "issue_title", "estimated_cost", "status", "created_at"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "booking", "total_amount", "payment_status", "created_at"]


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ["invoice", "description", "item_type", "quantity", "total_price"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["transaction_id", "invoice", "customer", "amount", "method", "status", "created_at"]
    list_filter = ["status", "method", "provider"]
    search_fields = ["transaction_id", "invoice__invoice_number", "customer__email"]
    readonly_fields = ["transaction_id", "amount", "payer_reference", "created_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "title", "notification_type", "is_read", "created_at"]


@admin.register(ServiceHistory)
class ServiceHistoryAdmin(admin.ModelAdmin):
    list_display = ["customer", "vehicle", "service_summary", "completed_at", "total_cost"]


@admin.register(RepairCostEstimate)
class RepairCostEstimateAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "service_type", "severity", "estimated_min_cost", "estimated_max_cost", "estimation_source", "created_at"]


@admin.register(CarHealthScore)
class CarHealthScoreAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "score", "maintenance_compliance", "critical_issue_count", "calculated_at"]

