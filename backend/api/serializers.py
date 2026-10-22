import re
import uuid
from rest_framework import serializers
from .models import (
    UserRole,
    User,
    CustomerProfile,
    CarBrand,
    CarModel,
    CarVariant,
    Vehicle,
    ServiceType,
    ServiceCenter,
    ServiceBooking,
    DriverLocation,
    ServiceInspection,
    RepairEvidence,
    RepairRequest,
    Invoice,
    InvoiceItem,
    Payment,
    CarHealthScore,
    RepairCostEstimate,
    Notification,
)


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "phone", "role", "is_verified", "name"]

    def get_name(self, obj):
        return obj.get_full_name() or obj.username or obj.email.split("@")[0]


class SendOTPSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)

    def validate_identifier(self, value):
        val = value.strip()
        is_email = "@" in val
        cleaned_num = re.sub(r"[\s\-\(\)\.]+", "", val)
        is_phone = bool(re.match(r"^\+?[0-9]{10,15}$", cleaned_num))
        if not is_email and not is_phone:
            raise serializers.ValidationError("Please provide a valid email address or mobile phone number.")
        return val


class VerifyOTPSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)
    otp_code = serializers.CharField(required=True, min_length=6, max_length=6)
    name = serializers.CharField(required=False, allow_blank=True)


class CarVariantSerializer(serializers.ModelSerializer):
    model_name = serializers.CharField(source="model.name", read_only=True)
    brand_name = serializers.CharField(source="model.brand.name", read_only=True)

    class Meta:
        model = CarVariant
        fields = [
            "id",
            "model",
            "model_name",
            "brand_name",
            "name",
            "fuel_type",
            "transmission",
            "engine",
            "is_active",
            "created_at",
            "updated_at",
        ]


class CarModelSerializer(serializers.ModelSerializer):
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    variants_count = serializers.IntegerField(source="variants.count", read_only=True)

    class Meta:
        model = CarModel
        fields = [
            "id",
            "brand",
            "brand_name",
            "name",
            "body_type",
            "is_active",
            "variants_count",
            "created_at",
            "updated_at",
        ]


class CarBrandSerializer(serializers.ModelSerializer):
    models_count = serializers.IntegerField(source="models.count", read_only=True)

    class Meta:
        model = CarBrand
        fields = [
            "id",
            "name",
            "logo",
            "logo_url",
            "is_active",
            "models_count",
            "created_at",
            "updated_at",
        ]


class VehicleSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    car_brand_details = CarBrandSerializer(source="car_brand", read_only=True)
    car_model_details = CarModelSerializer(source="car_model", read_only=True)
    car_variant_details = CarVariantSerializer(source="car_variant", read_only=True)

    car_brand_id = serializers.PrimaryKeyRelatedField(
        queryset=CarBrand.objects.all(), source="car_brand", write_only=True, required=False, allow_null=True
    )
    car_model_id = serializers.PrimaryKeyRelatedField(
        queryset=CarModel.objects.all(), source="car_model", write_only=True, required=False, allow_null=True
    )
    car_variant_id = serializers.PrimaryKeyRelatedField(
        queryset=CarVariant.objects.all(), source="car_variant", write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "customer",
            "customer_email",
            "car_brand",
            "car_brand_id",
            "car_brand_details",
            "car_model",
            "car_model_id",
            "car_model_details",
            "car_variant",
            "car_variant_id",
            "car_variant_details",
            "brand",
            "model",
            "variant_name",
            "nickname",
            "year",
            "fuel_type",
            "registration_number",
            "color",
            "image",
            "image_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["customer", "created_at", "updated_at"]

    def validate_registration_number(self, value):
        val = value.strip().upper()
        if not val:
            raise serializers.ValidationError("Registration number is required.")
        instance = getattr(self, "instance", None)
        qs = Vehicle.objects.filter(registration_number=val)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A vehicle with this registration number already exists.")
        return val


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = [
            "id",
            "name",
            "description",
            "base_price",
            "estimated_duration",
            "active",
            "created_at",
            "updated_at",
        ]


class ServiceCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCenter
        fields = [
            "id",
            "name",
            "address",
            "phone",
            "email",
            "latitude",
            "longitude",
            "rating",
            "is_active",
            "active",
            "created_at",
        ]


class ServiceBookingSerializer(serializers.ModelSerializer):
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    vehicle_details = VehicleSerializer(source="vehicle", read_only=True)
    service_type_details = ServiceTypeSerializer(source="service_type", read_only=True)
    service_center_details = ServiceCenterSerializer(source="service_center", read_only=True)
    assigned_driver_details = UserSerializer(source="assigned_driver", read_only=True)
    assigned_mechanic_details = UserSerializer(source="assigned_mechanic", read_only=True)

    class Meta:
        model = ServiceBooking
        fields = [
            "id",
            "booking_reference",
            "booking_id",
            "customer",
            "customer_email",
            "customer_phone",
            "customer_name",
            "vehicle",
            "vehicle_details",
            "service_type",
            "service_type_details",
            "service_center",
            "service_center_details",
            "assigned_driver",
            "assigned_driver_details",
            "assigned_mechanic",
            "assigned_mechanic_details",
            "pickup_address",
            "pickup_latitude",
            "pickup_longitude",
            "preferred_date",
            "preferred_time",
            "customer_notes",
            "estimated_cost",
            "status",
            "handover_otp_verified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "booking_reference",
            "booking_id",
            "customer",
            "handover_otp_verified",
            "created_at",
            "updated_at",
        ]

    def validate_vehicle(self, value):
        request = self.context.get("request")
        if request and request.user and request.user.role != UserRole.ADMIN and not request.user.is_superuser:
            if value.customer != request.user:
                raise serializers.ValidationError("Selected vehicle does not belong to you.")
        return value

    def validate_pickup_latitude(self, value):
        if value is not None:
            if value < -90.0 or value > 90.0:
                raise serializers.ValidationError("Latitude must be between -90.0 and 90.0 degrees.")
        return value

    def validate_pickup_longitude(self, value):
        if value is not None:
            if value < -180.0 or value > 180.0:
                raise serializers.ValidationError("Longitude must be between -180.0 and 180.0 degrees.")
        return value


class DriverLocationSerializer(serializers.ModelSerializer):
    driver_email = serializers.CharField(source="driver.email", read_only=True)

    class Meta:
        model = DriverLocation
        fields = ["id", "booking", "driver", "driver_email", "latitude", "longitude", "timestamp"]
        read_only_fields = ["id", "driver", "timestamp"]


class ServiceInspectionSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(source="mechanic.get_full_name", read_only=True)

    class Meta:
        model = ServiceInspection
        fields = [
            "id",
            "booking",
            "mechanic",
            "mechanic_name",
            "inspection_notes",
            "issue_description",
            "severity",
            "estimated_additional_cost",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "mechanic", "created_at", "updated_at"]


MAX_EVIDENCE_BYTES = 25 * 1024 * 1024
EVIDENCE_CONTENT_TYPES = {
    "image/jpeg": "PHOTO",
    "image/png": "PHOTO",
    "image/webp": "PHOTO",
    "video/mp4": "VIDEO",
    "video/quicktime": "VIDEO",
    "video/webm": "VIDEO",
}

EVIDENCE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}


def _evidence_content_matches(upload, content_type: str) -> bool:
    """Checks the bytes, not just the browser-supplied content type."""
    try:
        if content_type.startswith("image/"):
            from PIL import Image

            with Image.open(upload) as img:
                img.verify()
                return Image.MIME.get(img.format) == content_type
        head = upload.read(12)
        if content_type == "video/webm":
            return head[:4] == b"\x1a\x45\xdf\xa3"
        return head[4:8] == b"ftyp"  # MP4 / QuickTime
    except Exception:
        return False
    finally:
        upload.seek(0)


class RepairEvidenceSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(source="mechanic.get_full_name", read_only=True)

    class Meta:
        model = RepairEvidence
        fields = [
            "id",
            "booking",
            "mechanic",
            "mechanic_name",
            "issue_title",
            "description",
            "media_type",
            "file",
            "file_url",
            "created_at",
        ]
        read_only_fields = ["id", "mechanic", "created_at"]

    def validate(self, attrs):
        upload = attrs.get("file")
        url = (attrs.get("file_url") or "").strip()
        if not upload and not url:
            raise serializers.ValidationError({"file": "Attach a photo or video of the fault."})
        if upload:
            content_type = getattr(upload, "content_type", "") or ""
            if content_type not in EVIDENCE_CONTENT_TYPES:
                raise serializers.ValidationError({"file": "Upload a JPEG, PNG or WebP photo, or an MP4, MOV or WebM video."})
            if upload.size > MAX_EVIDENCE_BYTES:
                raise serializers.ValidationError({"file": "File is too large (max 25 MB)."})
            if not _evidence_content_matches(upload, content_type):
                raise serializers.ValidationError({"file": "The file content does not match its type."})
            # Never keep the uploaded name: a fixed extension stops e.g. "x.html" being served as a page.
            upload.name = f"{uuid.uuid4().hex}{EVIDENCE_EXTENSIONS[content_type]}"
            attrs["media_type"] = EVIDENCE_CONTENT_TYPES[content_type]
        elif not url.startswith(("https://", "http://")):
            raise serializers.ValidationError({"file_url": "Enter a full http(s) link to the media."})
        return attrs


class RepairRequestSerializer(serializers.ModelSerializer):
    mechanic_name = serializers.CharField(source="mechanic.get_full_name", read_only=True)

    class Meta:
        model = RepairRequest
        fields = [
            "id",
            "booking",
            "mechanic",
            "mechanic_name",
            "issue_title",
            "description",
            "additional_cost",
            "estimated_cost",
            "estimated_extra_hours",
            "status",
            "customer_response",
            "responded_at",
            "created_at",
        ]
        read_only_fields = ["id", "mechanic", "status", "responded_at", "created_at"]


class RepairCostEstimateInputSerializer(serializers.Serializer):
    vehicle = serializers.IntegerField(required=True)
    service_type = serializers.IntegerField(required=False, allow_null=True)
    issue_description = serializers.CharField(required=True, min_length=5)
    severity = serializers.ChoiceField(
        choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"], default="MEDIUM"
    )
    estimated_labor_hours = serializers.DecimalField(
        max_digits=5, decimal_places=1, required=False, default=1.5
    )


class RepairCostEstimateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairCostEstimate
        fields = [
            "id",
            "booking",
            "repair_request",
            "vehicle",
            "service_type",
            "issue_description",
            "severity",
            "estimated_min_cost",
            "estimated_max_cost",
            "estimated_labor_hours",
            "estimation_source",
            "explanation",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            "description",
            "item_type",
            "quantity",
            "unit_price",
            "total_price",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "method",
            "status",
            "provider",
            "transaction_id",
            "payer_reference",
            "failure_reason",
            "created_at",
        ]
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    booking_reference = serializers.CharField(source="booking.booking_reference", read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    service_center_name = serializers.CharField(source="service_center.name", read_only=True)
    vehicle_details = VehicleSerializer(source="vehicle", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "booking",
            "booking_reference",
            "customer",
            "customer_name",
            "customer_email",
            "customer_phone",
            "vehicle",
            "vehicle_details",
            "service_center",
            "service_center_name",
            "subtotal",
            "additional_repairs_total",
            "labor_total",
            "tax",
            "discount",
            "grand_total",
            "base_amount",
            "additional_repairs_amount",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "payment_status",
            "invoice_status",
            "issued_at",
            "created_at",
            "updated_at",
            "items",
            "payments",
        ]
        read_only_fields = ["id", "invoice_number", "issued_at", "created_at", "updated_at"]

    def get_customer_name(self, obj):
        if obj.customer:
            return obj.customer.get_full_name() or obj.customer.username or obj.customer.email.split("@")[0]
        return ""


class CarHealthScoreSerializer(serializers.ModelSerializer):
    vehicle_details = VehicleSerializer(source="vehicle", read_only=True)

    class Meta:
        model = CarHealthScore
        fields = [
            "id",
            "vehicle",
            "vehicle_details",
            "score",
            "previous_score",
            "service_count",
            "recent_service_count",
            "maintenance_compliance",
            "critical_issue_count",
            "warning_issue_count",
            "resolved_issue_count",
            "explanation",
            "calculated_at",
        ]
        read_only_fields = ["id", "calculated_at"]


class NotificationSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="notification_type", read_only=True)
    body = serializers.CharField(source="message", read_only=True)
    read = serializers.BooleanField(source="is_read", read_only=True)
    booking_reference = serializers.CharField(source="booking.booking_reference", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "user",
            "booking",
            "booking_reference",
            "notification_type",
            "type",
            "title",
            "message",
            "body",
            "read",
            "is_read",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]



