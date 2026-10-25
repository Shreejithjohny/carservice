from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Avg, Q
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

import re
from .models import (
    User,
    CustomerProfile,
    UserRole,
    CarBrand,
    CarModel,
    CarVariant,
    Vehicle,
    ServiceType,
    ServiceCenter,
    ServiceBooking,
    BookingStatus,
    DriverLocation,
    ServiceInspection,
    RepairEvidence,
    RepairRequest,
    RepairRequestStatus,
    VehicleConditionPhoto,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    CarHealthScore,
    RepairCostEstimate,
    Notification,
    NotificationType,
    Employee,
    CostModel,
    ServiceReview,
)
from .serializers import (
    SendOTPSerializer,
    VerifyOTPSerializer,
    UserSerializer,
    CarBrandSerializer,
    CarModelSerializer,
    CarVariantSerializer,
    VehicleSerializer,
    ServiceTypeSerializer,
    ServiceCenterSerializer,
    ServiceBookingSerializer,
    DriverLocationSerializer,
    ServiceInspectionSerializer,
    RepairEvidenceSerializer,
    RepairRequestSerializer,
    VehicleConditionPhotoSerializer,
    RepairCostEstimateInputSerializer,
    RepairCostEstimateSerializer,
    InvoiceItemSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    CarHealthScoreSerializer,
    NotificationSerializer,
    ServiceReviewSerializer,
)
from .otp_service import generate_otp_code, send_otp_to_identifier, normalize_phone_number
from .ai_cost_service import estimate_repair_cost
from .invoice_service import InvoiceError, generate_invoice_for_booking
from .invoice_pdf import build_invoice_pdf, invoice_from_token
from .health_service import recalculate_car_health_score
from .notification_service import send_notification
from .payment_service import PaymentError, pay_invoice, payment_gateway
from .plate_service import LIKELY, MATCH, check_plate
from .reminder_service import service_due
from .analytics_service import center_analytics
from .ml_cost_model import (
    MIN_TRAINING_SAMPLES, SYNTHETIC_HISTORY_EMAIL, SYNTHETIC_MARKER, train_cost_model, training_rows,
)
from .slot_service import SlotError, reserve_slot, slot_availability, validate_slot_choice


# Permissions come from the app role. is_staff only controls access to the Django admin site,
# so a staff flag on a manager or mechanic must not grant platform-wide admin powers.
def is_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == UserRole.ADMIN))


def is_manager(user):
    return bool(user and (is_admin(user) or user.role == UserRole.SERVICE_CENTER_MANAGER))


def is_driver(user):
    return bool(user and user.role == UserRole.DRIVER)


def is_mechanic(user):
    return bool(user and (user.role == UserRole.MECHANIC or is_admin(user)))


def is_customer(user):
    return bool(user and user.role == UserRole.CUSTOMER and not is_admin(user))


def manager_center(user):
    """The service center a manager runs (or works at); None if not linked to one."""
    center = getattr(user, "service_center_profile", None)
    if center:
        return center
    employee = getattr(user, "employee_profile", None)
    return employee.service_center if employee else None


def manager_scope_error(user, booking=None):
    """403 unless the user is an admin, or a manager linked to a center that owns this booking."""
    if is_admin(user):
        return None
    if user.role != UserRole.SERVICE_CENTER_MANAGER:
        return Response({"error": "Manager permissions required."}, status=status.HTTP_403_FORBIDDEN)
    center = manager_center(user)
    if not center:
        return Response({"error": "Your account is not linked to a service center."}, status=status.HTTP_403_FORBIDDEN)
    if booking is not None and booking.service_center_id != center.id:
        return Response({"error": "This booking belongs to another service center."}, status=status.HTTP_403_FORBIDDEN)
    return None


CUSTOMER_EDITABLE_BOOKING_FIELDS = {
    "pickup_address", "pickup_latitude", "pickup_longitude", "preferred_date", "preferred_time", "customer_notes", "status",
}

# Every status the workflow uses (model choices plus the intermediate pickup/workshop steps).
KNOWN_BOOKING_STATUSES = set(BookingStatus.values) | {
    "Driver Assigned", "En Route for Pickup", "Arrived at Pickup", "Inspection", "Repair Approval Required",
}


# Statuses while the car is at the workshop, and the ones a mechanic may set.
WORKSHOP_STATUSES = {BookingStatus.VEHICLE_PICKED_UP, BookingStatus.IN_SERVICE, "Inspection", "Repair Approval Required"}
MECHANIC_SETTABLE_STATUSES = {BookingStatus.IN_SERVICE, "Inspection", "Repair Approval Required", BookingStatus.READY_FOR_DELIVERY}


# Driver stages: before the handover OTP, and while driving the car to the workshop.
PICKUP_STAGE_STATUSES = {
    BookingStatus.CONFIRMED, BookingStatus.PICKUP_SCHEDULED, "Driver Assigned", "En Route for Pickup", "Arrived at Pickup",
}
# Return trip: the car is ready at the workshop, then on its way back to the customer.
DELIVERY_STAGE_STATUSES = {BookingStatus.READY_FOR_DELIVERY, BookingStatus.OUT_FOR_DELIVERY}
# Status a driver may set -> the statuses the booking may be in at that moment.
DRIVER_STATUS_MOVES = {
    "En Route for Pickup": PICKUP_STAGE_STATUSES,
    "Arrived at Pickup": PICKUP_STAGE_STATUSES,
    BookingStatus.OUT_FOR_DELIVERY: {BookingStatus.READY_FOR_DELIVERY},
}
DRIVER_SETTABLE_STATUSES = set(DRIVER_STATUS_MOVES)
DRIVER_GPS_STATUSES = PICKUP_STAGE_STATUSES | {BookingStatus.VEHICLE_PICKED_UP, BookingStatus.OUT_FOR_DELIVERY}


def driver_job_error(user, booking, allowed_statuses):
    """Returns an error Response unless the user is an admin, or the assigned driver at an allowed stage."""
    if is_admin(user):
        return None
    if not is_driver(user) or booking.assigned_driver_id != user.id:
        return Response({"error": "This pickup is not assigned to you."}, status=status.HTTP_403_FORBIDDEN)
    if booking.status not in allowed_statuses:
        return Response({"error": f"Not available while the booking is '{booking.status}'."}, status=status.HTTP_400_BAD_REQUEST)
    return None


# The pickup handover and the return delivery each use their own one-time code, stored in
# fields named handover_otp* and delivery_otp* on the booking.


def issue_booking_otp(booking, kind):
    code = generate_otp_code()
    setattr(booking, f"{kind}_otp", code)
    setattr(booking, f"{kind}_otp_verified", False)
    setattr(booking, f"{kind}_otp_attempts", 0)
    setattr(booking, f"{kind}_otp_expires_at", timezone.now() + timedelta(minutes=10))
    booking.save()
    resp_data = {"booking_reference": booking.booking_reference, "expires_in_minutes": 10}
    if getattr(settings, "OTP_BYPASS", False):
        resp_data["bypass_code"] = "123456"
    return resp_data


def booking_otp_error(booking, kind, otp_code):
    """Checks the code the driver typed in. Returns an error Response, or None when it matches."""
    if not otp_code:
        return Response({"error": "OTP code is required."}, status=status.HTTP_400_BAD_REQUEST)
    expected = getattr(booking, f"{kind}_otp")
    bypass_active = getattr(settings, "OTP_BYPASS", False)
    if bypass_active and (otp_code in ["123456", "000000", "999999"] or otp_code.lower() == "bypass" or otp_code == expected):
        return None

    attempts = getattr(booking, f"{kind}_otp_attempts")
    if attempts >= 5:
        return Response({"error": "Maximum OTP verification attempts exceeded. Please request a new OTP."}, status=status.HTTP_400_BAD_REQUEST)
    setattr(booking, f"{kind}_otp_attempts", attempts + 1)
    booking.save()

    expires_at = getattr(booking, f"{kind}_otp_expires_at")
    if not expected:
        return Response({"error": f"No {kind} OTP has been requested yet."}, status=status.HTTP_400_BAD_REQUEST)
    if expires_at and timezone.now() > expires_at:
        return Response({"error": f"OTP has expired. Please request a new {kind} OTP."}, status=status.HTTP_400_BAD_REQUEST)
    if expected != otp_code:
        remaining = 5 - (attempts + 1)
        return Response({"error": f"Invalid {kind} OTP code. {remaining} attempt(s) remaining."}, status=status.HTTP_400_BAD_REQUEST)
    return None


def notify_ready_for_delivery(booking):
    send_notification(
        user=booking.customer,
        booking=booking,
        notification_type=NotificationType.READY_FOR_DELIVERY,
        title="Vehicle Ready for Delivery",
        message=f"Servicing complete! Vehicle {booking.vehicle.registration_number} is ready for doorstep delivery.",
    )
    if booking.assigned_driver:
        send_notification(
            user=booking.assigned_driver,
            booking=booking,
            notification_type=NotificationType.READY_FOR_DELIVERY,
            title="Return Delivery Ready",
            message=f"Vehicle {booking.vehicle.registration_number} is ready to be delivered back to {booking.pickup_address}.",
        )


def complete_booking(booking):
    """Closes a booking: records the time, notifies the customer, issues the invoice, updates car health."""
    booking.status = BookingStatus.COMPLETED
    booking.completed_at = booking.completed_at or timezone.now()
    booking.save()
    send_notification(
        user=booking.customer,
        booking=booking,
        notification_type=NotificationType.SERVICE_COMPLETED,
        title="Service Completed Successfully",
        message=f"All services and repairs for {booking.vehicle.registration_number} have been successfully finalized.",
    )
    try:
        generate_invoice_for_booking(booking)
    except InvoiceError:
        pass  # e.g. already paid; completing the booking still succeeds
    try:
        recalculate_car_health_score(booking.vehicle)
    except Exception:
        pass


def find_booking(pk):
    """Looks a booking up by its numeric id or its reference (e.g. SDV-2026-000001)."""
    if str(pk).isdigit():
        return ServiceBooking.objects.filter(pk=pk).first()
    return ServiceBooking.objects.filter(Q(booking_reference=pk) | Q(booking_id=pk)).first()


def can_view_booking(user, booking):
    """The customer, an admin, the assigned driver or mechanic, or the manager of the booking's center."""
    if booking.customer_id == user.id or is_admin(user):
        return True
    if user.id in (booking.assigned_driver_id, booking.assigned_mechanic_id):
        return True
    return manager_scope_error(user, booking) is None


def condition_stage(booking):
    """Which set of condition photos the driver is taking right now, or None outside those stages."""
    if booking.status in PICKUP_STAGE_STATUSES:
        return VehicleConditionPhoto.Stage.PICKUP
    if booking.status == BookingStatus.OUT_FOR_DELIVERY:
        return VehicleConditionPhoto.Stage.DELIVERY
    return None


def repair_response_error(repair_req):
    """A repair request can be answered once, while the car is still at the workshop."""
    if repair_req.status != RepairRequestStatus.PENDING:
        return Response({"error": f"This repair request was already {repair_req.status.lower()}."}, status=status.HTTP_409_CONFLICT)
    if repair_req.booking.status not in WORKSHOP_STATUSES:
        return Response({"error": "The vehicle is no longer at the workshop."}, status=status.HTTP_400_BAD_REQUEST)
    return None


def mechanic_job_error(user, booking):
    """Returns a 403 Response unless the user is an admin or the mechanic assigned to this open booking."""
    if is_admin(user):
        return None
    if not is_mechanic(user) or booking.assigned_mechanic_id != user.id:
        return Response({"error": "This job is not assigned to you."}, status=status.HTTP_403_FORBIDDEN)
    if booking.status in (BookingStatus.COMPLETED, BookingStatus.CANCELLED):
        return Response({"error": "This job is already closed."}, status=status.HTTP_400_BAD_REQUEST)
    return None



@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({
        "status": "ok",
        "service": "Smart Doorstep Vehicle Service Management System API",
        "backend": "Django REST Framework",
        "demo_login": getattr(settings, "OTP_BYPASS", False),
        "payment_gateway": payment_gateway() or None,
    })


# ==========================================
# AUTHENTICATION VIEWS (PHASE 2)
# ==========================================

@api_view(["POST"])
@permission_classes([AllowAny])
def bypass_login(request):
    """
    POST /api/auth/bypass-login/
    Demo login without OTP. Only available when settings.OTP_BYPASS is enabled.
    Existing accounts keep their own role; new accounts may take any non-admin role.
    """
    if not getattr(settings, "OTP_BYPASS", False):
        return Response({"error": "Demo login is disabled. Please sign in with an OTP."}, status=status.HTTP_403_FORBIDDEN)

    identifier = str(request.data.get("identifier") or "").strip()
    requested_role = str(request.data.get("role") or UserRole.CUSTOMER).upper()
    provided_name = str(request.data.get("name") or "").strip()

    if requested_role not in UserRole.values:
        requested_role = UserRole.CUSTOMER

    if not identifier:
        role_defaults = {
            UserRole.ADMIN: "admin@smartdoorstep.com",
            UserRole.SERVICE_CENTER_MANAGER: "manager@smartdoorstep.com",
            UserRole.DRIVER: "driver@smartdoorstep.com",
            UserRole.MECHANIC: "mechanic@smartdoorstep.com",
            UserRole.CUSTOMER: "customer@smartdoorstep.com",
        }
        identifier = role_defaults.get(requested_role, "customer@smartdoorstep.com")

    is_email = "@" in identifier

    if is_email:
        user = User.objects.filter(email__iexact=identifier).first()
    else:
        norm_phone = normalize_phone_number(identifier)
        clean_phone = identifier.replace(" ", "").replace("-", "")
        user = User.objects.filter(phone=norm_phone).first() or User.objects.filter(phone=clean_phone).first()

    if not user and requested_role == UserRole.ADMIN:
        return Response({"error": "Admin accounts cannot be created through demo login."}, status=status.HTTP_403_FORBIDDEN)

    if not user:
        if is_email:
            username = identifier.split("@")[0] + f"_{timezone.now().strftime('%M%S')}"
            user = User.objects.create(
                email=identifier.lower(),
                username=username,
                role=requested_role,
                first_name=provided_name or identifier.split("@")[0].capitalize(),
            )
        else:
            clean_digits = re.sub(r"\D", "", norm_phone) or "0000"
            username = f"user_{clean_digits[-4:]}_{timezone.now().strftime('%M%S')}"
            dummy_email = f"{clean_digits}@smartdoorstep.local"
            user = User.objects.create(
                phone=norm_phone,
                email=dummy_email,
                username=username,
                role=requested_role,
                first_name=provided_name or f"User {clean_digits[-4:]}",
            )

    user.is_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    if provided_name:
        user.first_name = provided_name
    user.save()

    if user.role == UserRole.CUSTOMER and not hasattr(user, "customer_profile"):
        CustomerProfile.objects.create(user=user)

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)
    user_data = UserSerializer(user).data

    return Response({
        "message": f"Successfully signed in as {user.role.lower()}.",
        "token": access_token,
        "access": access_token,
        "refresh": refresh_token,
        "user": user_data,
        "bypass": True,
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def send_otp(request):
    serializer = SendOTPSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors.get("identifier", ["Invalid request"])[0]}, status=status.HTTP_400_BAD_REQUEST)

    identifier = serializer.validated_data["identifier"]
    # Self sign-up always creates a customer; staff accounts are created by an admin.
    is_email = "@" in identifier

    if is_email:
        user = User.objects.filter(email__iexact=identifier).first()
        if not user:
            username = identifier.split("@")[0] + f"_{timezone.now().strftime('%M%S')}"
            user = User.objects.create(email=identifier.lower(), username=username, role=UserRole.CUSTOMER)
        target_identifier = identifier
    else:
        norm_phone = normalize_phone_number(identifier)
        clean_phone = identifier.replace(" ", "").replace("-", "")
        user = User.objects.filter(phone=norm_phone).first() or User.objects.filter(phone=clean_phone).first()
        if not user:
            clean_digits = re.sub(r"\D", "", norm_phone)
            username = f"user_{clean_digits[-4:]}_{timezone.now().strftime('%M%S')}"
            dummy_email = f"{clean_digits}@smartdoorstep.local"
            user = User.objects.create(phone=norm_phone, email=dummy_email, username=username, role=UserRole.CUSTOMER)
        else:
            if user.phone != norm_phone:
                user.phone = norm_phone
                user.save(update_fields=["phone"])
        target_identifier = norm_phone

    bypass_active = getattr(settings, "OTP_BYPASS", False)

    # In production, check cooldown. In bypass/dev mode, allow instant resend.
    if not bypass_active and user.otp_last_sent_at:
        elapsed = (timezone.now() - user.otp_last_sent_at).total_seconds()
        if elapsed < 60:
            remaining = int(60 - elapsed)
            return Response(
                {"error": f"Please wait {remaining} seconds before requesting a new OTP.", "cooldown_seconds": remaining},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

    otp_code = generate_otp_code()
    user.otp_code = otp_code
    user.otp_expires_at = timezone.now() + timedelta(minutes=5)
    user.otp_attempts = 0
    user.otp_last_sent_at = timezone.now()
    user.save()

    send_result = send_otp_to_identifier(target_identifier, otp_code)

    if not send_result.get("success", False) and not bypass_active:
        user.otp_last_sent_at = None
        user.save(update_fields=["otp_last_sent_at"])
        return Response(
            {"error": send_result.get("error", "Unable to send OTP. Please try again.")},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    resp_data = {
        "message": f"Verification code sent to {identifier}.",
        "identifier": identifier,
        "cooldown_seconds": 0 if bypass_active else 60,
        "expires_in_minutes": 5,
        "provider": send_result.get("provider", "console"),
    }
    if bypass_active:
        resp_data["otp_code"] = otp_code
        resp_data["bypass_code"] = "123456"

    return Response(resp_data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request):
    serializer = VerifyOTPSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Invalid request payload. Please provide identifier and 6-digit OTP code."}, status=status.HTTP_400_BAD_REQUEST)

    identifier = serializer.validated_data["identifier"]
    otp_code = serializer.validated_data["otp_code"].strip()
    provided_name = serializer.validated_data.get("name", "").strip()

    bypass_active = getattr(settings, "OTP_BYPASS", False)
    is_universal_bypass = bypass_active and (
        otp_code in ["123456", "000000", "999999", "111111"] or otp_code.lower() == "bypass"
    )

    is_email = "@" in identifier
    if is_email:
        user = User.objects.filter(email__iexact=identifier).first()
    else:
        norm_phone = normalize_phone_number(identifier)
        clean_phone = identifier.replace(" ", "").replace("-", "")
        user = User.objects.filter(phone=norm_phone).first() or User.objects.filter(phone=clean_phone).first()

    if not user:
        if bypass_active:
            # Auto-create user on the fly in bypass mode
            if is_email:
                username = identifier.split("@")[0] + f"_{timezone.now().strftime('%M%S')}"
                user = User.objects.create(email=identifier.lower(), username=username, role=UserRole.CUSTOMER)
            else:
                clean_digits = re.sub(r"\D", "", norm_phone) or "0000"
                username = f"user_{clean_digits[-4:]}_{timezone.now().strftime('%M%S')}"
                dummy_email = f"{clean_digits}@smartdoorstep.local"
                user = User.objects.create(phone=norm_phone, email=dummy_email, username=username, role=UserRole.CUSTOMER)
        else:
            return Response({"error": "No user found with this identifier. Please request an OTP first."}, status=status.HTTP_400_BAD_REQUEST)

    # Verification checks
    if not is_universal_bypass:
        if not user.otp_code or not user.otp_expires_at:
            if not bypass_active:
                return Response({"error": "No active OTP request found. Please request a new OTP code."}, status=status.HTTP_400_BAD_REQUEST)

        elif timezone.now() > user.otp_expires_at:
            if not bypass_active:
                user.otp_code = None
                user.otp_expires_at = None
                user.save()
                return Response({"error": "OTP has expired. Please request a new code."}, status=status.HTTP_400_BAD_REQUEST)

        elif user.otp_attempts >= 5:
            if not bypass_active:
                user.otp_code = None
                user.otp_expires_at = None
                user.save()
                return Response({"error": "Maximum verification attempts exceeded. Please request a new OTP."}, status=status.HTTP_400_BAD_REQUEST)

        elif user.otp_code != otp_code:
            if not bypass_active:
                user.otp_attempts += 1
                user.save()
                remaining_attempts = 5 - user.otp_attempts
                if remaining_attempts <= 0:
                    user.otp_code = None
                    user.otp_expires_at = None
                    user.save()
                    return Response({"error": "Maximum verification attempts exceeded. Please request a new OTP."}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"error": f"Invalid OTP code. {remaining_attempts} attempt(s) remaining.", "remaining_attempts": remaining_attempts}, status=status.HTTP_400_BAD_REQUEST)

    user.otp_code = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    user.is_verified = True

    if provided_name:
        user.first_name = provided_name
    user.save()

    if user.role == UserRole.CUSTOMER and not hasattr(user, "customer_profile"):
        CustomerProfile.objects.create(user=user)

    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    user_data = UserSerializer(user).data

    return Response({
        "message": "OTP verified successfully.",
        "token": access_token,
        "access": access_token,
        "refresh": refresh_token,
        "user": user_data
    }, status=status.HTTP_200_OK)



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


# ==========================================
# VEHICLE CATALOG VIEWS (PHASE 3)
# ==========================================

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def car_brand_list_create(request):
    if request.method == "GET":
        qs = CarBrand.objects.filter(is_active=True)
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        serializer = CarBrandSerializer(qs, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        if not is_admin(request.user):
            return Response({"error": "Admin access required to modify the vehicle catalog."}, status=status.HTTP_403_FORBIDDEN)
        serializer = CarBrandSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def car_brand_detail(request, pk):
    try:
        brand = CarBrand.objects.get(pk=pk)
    except CarBrand.DoesNotExist:
        return Response({"error": "Car brand not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(CarBrandSerializer(brand).data)

    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    if request.method in ["PUT", "PATCH"]:
        serializer = CarBrandSerializer(brand, data=request.data, partial=(request.method == "PATCH"))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        brand.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([AllowAny])
def car_brand_models(request, pk):
    try:
        brand = CarBrand.objects.get(pk=pk)
    except CarBrand.DoesNotExist:
        return Response({"error": "Car brand not found."}, status=status.HTTP_404_NOT_FOUND)

    models = CarModel.objects.filter(brand=brand, is_active=True)
    search = request.query_params.get("search", "").strip()
    if search:
        models = models.filter(name__icontains=search)
    return Response(CarModelSerializer(models, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def car_model_list_create(request):
    if request.method == "GET":
        qs = CarModel.objects.filter(is_active=True)
        brand_id = request.query_params.get("brand")
        if brand_id:
            qs = qs.filter(brand_id=brand_id)
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(brand__name__icontains=search))
        return Response(CarModelSerializer(qs, many=True).data)

    elif request.method == "POST":
        if not is_admin(request.user):
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        serializer = CarModelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def car_model_detail(request, pk):
    try:
        model_obj = CarModel.objects.get(pk=pk)
    except CarModel.DoesNotExist:
        return Response({"error": "Car model not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(CarModelSerializer(model_obj).data)

    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    if request.method in ["PUT", "PATCH"]:
        serializer = CarModelSerializer(model_obj, data=request.data, partial=(request.method == "PATCH"))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        model_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([AllowAny])
def car_model_variants(request, pk):
    try:
        model_obj = CarModel.objects.get(pk=pk)
    except CarModel.DoesNotExist:
        return Response({"error": "Car model not found."}, status=status.HTTP_404_NOT_FOUND)

    variants = CarVariant.objects.filter(model=model_obj, is_active=True)
    search = request.query_params.get("search", "").strip()
    if search:
        variants = variants.filter(name__icontains=search)
    return Response(CarVariantSerializer(variants, many=True).data)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def car_variant_list_create(request):
    if request.method == "GET":
        qs = CarVariant.objects.filter(is_active=True)
        model_id = request.query_params.get("model")
        if model_id:
            qs = qs.filter(model_id=model_id)
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(name__icontains=search)
        return Response(CarVariantSerializer(qs, many=True).data)

    elif request.method == "POST":
        if not is_admin(request.user):
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        serializer = CarVariantSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def car_variant_detail(request, pk):
    try:
        variant = CarVariant.objects.get(pk=pk)
    except CarVariant.DoesNotExist:
        return Response({"error": "Car variant not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(CarVariantSerializer(variant).data)

    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    if request.method in ["PUT", "PATCH"]:
        serializer = CarVariantSerializer(variant, data=request.data, partial=(request.method == "PATCH"))
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        variant.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# CUSTOMER VEHICLE VIEWS (PHASE 3)
# ==========================================

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def vehicle_list_create(request):
    if request.method == "GET":
        if is_admin(request.user):
            qs = Vehicle.objects.all()
        else:
            qs = Vehicle.objects.filter(customer=request.user)
        serializer = VehicleSerializer(qs, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = VehicleSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(customer=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def vehicle_detail(request, pk):
    try:
        vehicle = Vehicle.objects.get(pk=pk)
    except Vehicle.DoesNotExist:
        return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

    if vehicle.customer != request.user and not is_admin(request.user):
        return Response({"error": "You do not have permission to access this vehicle."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        return Response(VehicleSerializer(vehicle).data)

    elif request.method in ["PUT", "PATCH"]:
        serializer = VehicleSerializer(vehicle, data=request.data, partial=(request.method == "PATCH"), context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        # Deleting a vehicle cascades to its bookings, invoices and payments, so keep that history.
        if vehicle.bookings.exclude(status=BookingStatus.CANCELLED).exists():
            return Response(
                {"error": "This vehicle has service bookings and invoices on record, so it cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        vehicle.delete()
        return Response({"message": "Vehicle deleted successfully."}, status=status.HTTP_200_OK)


# ==========================================
# SERVICE BOOKING VIEWS (PHASE 4)
# ==========================================

@api_view(["GET"])
@permission_classes([AllowAny])
def service_type_list(request):
    """
    GET /api/service-types/ -> List active service types
    """
    qs = ServiceType.objects.filter(active=True)
    serializer = ServiceTypeSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def service_center_list(request):
    """
    GET /api/service-centers/ -> List active service centers
    """
    qs = ServiceCenter.objects.filter(is_active=True)
    serializer = ServiceCenterSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def service_center_slots(request, pk):
    """
    GET /api/service-centers/<id>/slots/?date=YYYY-MM-DD -> pickup slots with remaining capacity
    """

    center = ServiceCenter.objects.filter(pk=pk, is_active=True).first()
    if not center:
        return Response({"error": "Service center not found."}, status=status.HTTP_404_NOT_FOUND)
    try:
        day = date.fromisoformat(request.query_params.get("date", ""))
    except ValueError:
        return Response({"error": "Pass the date as YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        "service_center": center.id,
        "date": day.isoformat(),
        "slots": slot_availability(center, day),
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def booking_list_create(request):
    """
    GET /api/bookings/ -> List authenticated customer's bookings (or all for admin/staff)
    POST /api/bookings/ -> Create a new vehicle service booking
    """
    if request.method == "GET":
        if is_admin(request.user):
            qs = ServiceBooking.objects.exclude(customer_notes__startswith=SYNTHETIC_MARKER).order_by("-created_at")
        else:
            qs = ServiceBooking.objects.filter(customer=request.user).order_by("-created_at")
        serializer = ServiceBookingSerializer(qs, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = ServiceBookingSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            # Validate vehicle ownership
            vehicle = serializer.validated_data.get("vehicle")
            if vehicle.customer != request.user and not is_admin(request.user):
                return Response(
                    {"error": "Selected vehicle does not belong to you."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # The price always comes from the chosen package, never from the client.
            service_type = serializer.validated_data.get("service_type")
            service_center = serializer.validated_data.get("service_center")
            if not service_type or not service_type.active:
                return Response({"error": "Choose an available service package."}, status=status.HTTP_400_BAD_REQUEST)
            if not service_center or not service_center.is_active:
                return Response({"error": "Choose an available service center."}, status=status.HTTP_400_BAD_REQUEST)
            est_cost = service_type.base_price

            try:
                booking = reserve_slot(
                    service_center,
                    serializer.validated_data.get("preferred_date"),
                    serializer.validated_data.get("preferred_time", ""),
                    timezone.localdate(),
                    lambda: serializer.save(
                        customer=request.user,
                        estimated_cost=est_cost,
                        status=BookingStatus.PENDING,
                    ),
                )
            except SlotError as exc:
                return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)
            send_notification(
                user=booking.customer,
                booking=booking,
                notification_type=NotificationType.BOOKING_CREATED,
                title=f"Booking {booking.booking_reference} Placed",
                message=f"Your service booking for vehicle {booking.vehicle.registration_number} has been created and is pending confirmation.",
            )
            return Response(ServiceBookingSerializer(booking).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def booking_detail(request, pk):
    """
    GET /api/bookings/<id>/
    PUT /api/bookings/<id>/
    PATCH /api/bookings/<id>/
    DELETE /api/bookings/<id>/
    """
    # Accept either integer primary key or booking_reference string (e.g. SDV-2026-000001)
    if str(pk).isdigit():
        qs = ServiceBooking.objects.filter(pk=pk)
    else:
        qs = ServiceBooking.objects.filter(Q(booking_reference=pk) | Q(booking_id=pk))

    booking = qs.first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    # Permission check: must belong to customer or be admin/staff
    if booking.customer != request.user and not is_admin(request.user):
        return Response({"error": "You do not have permission to access this booking."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        return Response(ServiceBookingSerializer(booking).data)

    elif request.method in ["PUT", "PATCH"]:
        new_status = request.data.get("status")

        if not is_admin(request.user):
            # Customers may only edit pickup details/notes or cancel, and only before pickup is underway.
            disallowed = sorted(set(request.data.keys()) - CUSTOMER_EDITABLE_BOOKING_FIELDS)
            if disallowed:
                return Response(
                    {"error": f"You cannot change: {', '.join(disallowed)}."}, status=status.HTTP_400_BAD_REQUEST
                )
            if new_status is not None and new_status != BookingStatus.CANCELLED:
                return Response({"error": "You can only cancel a booking."}, status=status.HTTP_400_BAD_REQUEST)
            if booking.status not in [BookingStatus.PENDING, BookingStatus.CONFIRMED]:
                return Response(
                    {"error": f"Bookings can only be changed or cancelled while Pending or Confirmed. Current status is '{booking.status}'."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            new_date = request.data.get("preferred_date")
            new_time = request.data.get("preferred_time")
            if new_date is not None or new_time is not None:
                # Rescheduling must land in a slot that still has room.

                try:
                    day = date.fromisoformat(str(new_date)) if new_date is not None else booking.preferred_date
                except ValueError:
                    return Response({"error": "Enter the pickup date as YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)
                slot = str(new_time) if new_time is not None else booking.preferred_time
                if (day, slot) != (booking.preferred_date, booking.preferred_time):
                    try:
                        validate_slot_choice(booking.service_center, day, slot, timezone.localdate())
                    except SlotError as exc:
                        return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ServiceBookingSerializer(booking, data=request.data, partial=(request.method == "PATCH"), context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        if not is_admin(request.user) and booking.customer != request.user:
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        # Non-admin customer deletion rule: can only delete if Pending or Confirmed
        if not is_admin(request.user) and booking.status not in [BookingStatus.PENDING, BookingStatus.CONFIRMED]:
            return Response(
                {"error": "Cannot delete active or completed booking."},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking.delete()
        return Response({"message": "Booking deleted successfully."}, status=status.HTTP_200_OK)


# ==========================================
# PHASE 5 LOCATION & DISTANCE VIEWS
# ==========================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])  # may call the paid Google Distance Matrix API
def calculate_distance_view(request):
    """
    GET /api/location/distance/?origin_lat=12.9716&origin_lng=77.5946&dest_lat=12.9784&dest_lng=77.6408
    Calculates distance in km and estimated travel time in minutes.
    """
    try:
        origin_lat = float(request.query_params.get("origin_lat", 0))
        origin_lng = float(request.query_params.get("origin_lng", 0))
        dest_lat = float(request.query_params.get("dest_lat", 0))
        dest_lng = float(request.query_params.get("dest_lng", 0))
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid or missing latitude/longitude parameters."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not (-90.0 <= origin_lat <= 90.0 and -90.0 <= dest_lat <= 90.0):
        return Response({"error": "Latitude values must be between -90.0 and 90.0."}, status=status.HTTP_400_BAD_REQUEST)
    if not (-180.0 <= origin_lng <= 180.0 and -180.0 <= dest_lng <= 180.0):
        return Response({"error": "Longitude values must be between -180.0 and 180.0."}, status=status.HTTP_400_BAD_REQUEST)

    from .location_service import get_route_info
    route_info = get_route_info(origin_lat, origin_lng, dest_lat, dest_lng)
    return Response(route_info)


# ==========================================
# PHASE 6 — SERVICE CENTER MANAGER VIEWS
# ==========================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_center_bookings_list(request):
    """
    GET /api/service-center/bookings/
    Lists bookings assigned to the manager's service center.
    Managers cannot view bookings of another service center.
    """
    error = manager_scope_error(request.user)
    if error:
        return error

    qs = ServiceBooking.objects.exclude(customer_notes__startswith=SYNTHETIC_MARKER).order_by("-created_at")
    if not is_admin(request.user):
        qs = qs.filter(service_center=manager_center(request.user))

    serializer = ServiceBookingSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def service_center_booking_update(request, pk):
    """
    PATCH /api/service-center/bookings/<id>/
    Managers can confirm/reject bookings, update status, assign drivers, or assign mechanics.
    """
    error = manager_scope_error(request.user)
    if error:
        return error

    if str(pk).isdigit():
        booking = ServiceBooking.objects.filter(pk=pk).first()
    else:
        booking = ServiceBooking.objects.filter(Q(booking_reference=pk) | Q(booking_id=pk)).first()

    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = manager_scope_error(request.user, booking)
    if error:
        return error

    new_status = request.data.get("status")
    assigned_driver_id = request.data.get("assigned_driver_id") or request.data.get("assigned_driver")
    assigned_mechanic_id = request.data.get("assigned_mechanic_id") or request.data.get("assigned_mechanic")

    if new_status and new_status not in KNOWN_BOOKING_STATUSES:
        return Response({"error": f"Unknown booking status '{new_status}'."}, status=status.HTTP_400_BAD_REQUEST)

    def works_at_this_center(staff):
        # Staff not yet attached to any center form a shared pool; staff of another center are off limits.
        employee = getattr(staff, "employee_profile", None)
        center_id = employee.service_center_id if employee else None
        return is_admin(request.user) or center_id in (None, booking.service_center_id)

    if new_status:
        booking.status = new_status
        if new_status == BookingStatus.CONFIRMED:
            send_notification(
                user=booking.customer,
                booking=booking,
                notification_type=NotificationType.BOOKING_CONFIRMED,
                title=f"Booking {booking.booking_reference} Confirmed",
                message="Your service booking has been accepted and confirmed by the service center.",
            )
        elif new_status == BookingStatus.READY_FOR_DELIVERY:
            notify_ready_for_delivery(booking)
        elif new_status == BookingStatus.COMPLETED:
            # e.g. the customer collected the car at the center instead of a doorstep delivery
            complete_booking(booking)

    if assigned_driver_id:
        driver = User.objects.filter(pk=assigned_driver_id).first()
        if not driver or not is_driver(driver):
            return Response({"error": "Invalid driver selection."}, status=status.HTTP_400_BAD_REQUEST)
        if not works_at_this_center(driver):
            return Response({"error": "That driver does not work at this service center."}, status=status.HTTP_400_BAD_REQUEST)
        booking.assigned_driver = driver
        send_notification(
            user=booking.customer,
            booking=booking,
            notification_type=NotificationType.DRIVER_ASSIGNED,
            title="Valet Assigned for Doorstep Pickup",
            message=f"Valet {driver.get_full_name() or driver.username} has been assigned to pick up your vehicle.",
        )
        send_notification(
            user=driver,
            booking=booking,
            notification_type=NotificationType.PICKUP_SCHEDULED,
            title="New Doorstep Pickup Assigned",
            message=f"You have been assigned to pick up vehicle {booking.vehicle.registration_number} at {booking.pickup_address}.",
        )

    if assigned_mechanic_id:
        mechanic = User.objects.filter(pk=assigned_mechanic_id).first()
        if not mechanic or mechanic.role != UserRole.MECHANIC:
            return Response({"error": "Invalid mechanic selection."}, status=status.HTTP_400_BAD_REQUEST)
        if not works_at_this_center(mechanic):
            return Response({"error": "That mechanic does not work at this service center."}, status=status.HTTP_400_BAD_REQUEST)
        booking.assigned_mechanic = mechanic

    booking.save()
    return Response(ServiceBookingSerializer(booking).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_center_analytics(request):
    """
    GET /api/service-center/analytics/?months=6
    Managers see their own center; admins see every center, or one with ?center=<id>.
    """
    error = manager_scope_error(request.user)
    if error:
        return error
    try:
        months = min(24, max(1, int(request.query_params.get("months", 6))))
    except ValueError:
        months = 6

    if is_admin(request.user):
        center_id = request.query_params.get("center")
        center = ServiceCenter.objects.filter(pk=center_id).first() if center_id else None
        if center_id and not center:
            return Response({"error": "Service center not found."}, status=status.HTTP_404_NOT_FOUND)
    else:
        center = manager_center(request.user)
    return Response(center_analytics(center, months))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_center_employees_list(request):
    """
    GET /api/service-center/employees/
    Lists available drivers and mechanics for manager dropdown assignment.
    """
    error = manager_scope_error(request.user)
    if error:
        return error

    drivers = User.objects.filter(role=UserRole.DRIVER)
    mechanics = User.objects.filter(role=UserRole.MECHANIC)
    if not is_admin(request.user):
        center = manager_center(request.user)
        in_scope = Q(employee_profile__service_center=center) | Q(employee_profile__isnull=True) | Q(
            employee_profile__service_center__isnull=True
        )
        drivers = drivers.filter(in_scope)
        mechanics = mechanics.filter(in_scope)

    return Response({
        "drivers": UserSerializer(drivers, many=True).data,
        "mechanics": UserSerializer(mechanics, many=True).data,
    })


# ==========================================
# PHASE 7 — DRIVER / VALET VIEWS
# ==========================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def driver_pickups_list(request):
    """
    GET /api/driver/pickups/
    Lists assigned pickup jobs for the authenticated driver.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    if is_admin(request.user):
        qs = ServiceBooking.objects.exclude(status=BookingStatus.CANCELLED).exclude(
            customer_notes__startswith=SYNTHETIC_MARKER
        ).order_by("-created_at")
    else:
        qs = ServiceBooking.objects.filter(assigned_driver=request.user).exclude(
            status=BookingStatus.CANCELLED
        ).order_by("-created_at")

    serializer = ServiceBookingSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def driver_pickup_status_update(request, pk):
    """
    POST /api/driver/pickups/<id>/status/
    Driver updates pickup workflow stage.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = driver_job_error(request.user, booking, PICKUP_STAGE_STATUSES | DELIVERY_STAGE_STATUSES)
    if error:
        return error

    new_status = request.data.get("status")
    if not new_status:
        return Response({"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not is_admin(request.user):
        if new_status not in DRIVER_SETTABLE_STATUSES:
            return Response(
                {"error": f"Drivers cannot set status '{new_status}'. The handover and delivery OTPs move the job on."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if booking.status not in DRIVER_STATUS_MOVES[new_status]:
            return Response(
                {"error": f"Cannot change to '{new_status}' while the booking is '{booking.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    booking.status = new_status
    booking.save()
    if new_status == BookingStatus.OUT_FOR_DELIVERY:
        send_notification(
            user=booking.customer,
            booking=booking,
            notification_type=NotificationType.READY_FOR_DELIVERY,
            title="Your Car Is On Its Way Back",
            message=f"Vehicle {booking.vehicle.registration_number} is out for delivery. Keep your delivery OTP ready.",
        )
    return Response(ServiceBookingSerializer(booking).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def driver_request_handover_otp(request, pk):
    """
    POST /api/driver/pickups/<id>/handover-otp/request/
    Driver requests vehicle handover OTP for customer verification.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = driver_job_error(request.user, booking, PICKUP_STAGE_STATUSES)
    if error:
        return error

    return Response({"message": "Handover OTP generated successfully.", **issue_booking_otp(booking, "handover")})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def driver_verify_handover_otp(request, pk):
    """
    POST /api/driver/pickups/<id>/handover-otp/verify/
    Driver submits OTP provided by customer. Verifies OTP, updates handover status.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = driver_job_error(request.user, booking, PICKUP_STAGE_STATUSES)
    if error:
        return error

    otp_code = str(request.data.get("otp_code") or request.data.get("code") or "").strip()
    error = booking_otp_error(booking, "handover", otp_code)
    if error:
        return error

    booking.handover_otp_verified = True
    booking.status = BookingStatus.VEHICLE_PICKED_UP
    booking.save()

    send_notification(
        user=booking.customer,
        booking=booking,
        notification_type=NotificationType.VEHICLE_PICKED_UP,
        title="Vehicle Handover Complete",
        message=f"Your vehicle {booking.vehicle.registration_number} has been picked up and is en route to the service center.",
    )

    return Response({
        "message": "Vehicle handover OTP verified successfully. Status updated to Vehicle Picked Up.",
        "booking": ServiceBookingSerializer(booking).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def driver_request_delivery_otp(request, pk):
    """
    POST /api/driver/pickups/<id>/delivery-otp/request/
    Driver at the customer's door asks for the return-delivery code, which the customer sees in the app.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = driver_job_error(request.user, booking, {BookingStatus.OUT_FOR_DELIVERY})
    if error:
        return error

    return Response({"message": "Delivery OTP generated successfully.", **issue_booking_otp(booking, "delivery")})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def driver_verify_delivery_otp(request, pk):
    """
    POST /api/driver/pickups/<id>/delivery-otp/verify/
    Driver enters the customer's delivery code. A match hands the car back and completes the booking.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = driver_job_error(request.user, booking, {BookingStatus.OUT_FOR_DELIVERY})
    if error:
        return error

    otp_code = str(request.data.get("otp_code") or request.data.get("code") or "").strip()
    error = booking_otp_error(booking, "delivery", otp_code)
    if error:
        return error

    booking.delivery_otp_verified = True
    booking.delivered_at = timezone.now()
    send_notification(
        user=booking.customer,
        booking=booking,
        notification_type=NotificationType.DELIVERY_COMPLETED,
        title="Vehicle Delivered",
        message=f"Vehicle {booking.vehicle.registration_number} has been handed back to you. Thank you for choosing DoorStep!",
    )
    complete_booking(booking)

    return Response({
        "message": "Delivery OTP verified. The vehicle is handed back and the booking is completed.",
        "booking": ServiceBookingSerializer(booking).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def driver_upload_condition_photo(request, pk):
    """
    POST /api/driver/pickups/<id>/condition-photos/  (multipart: file, angle, notes)
    Photos taken before pickup are the "before" set; photos taken at delivery are the "after" set.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = driver_job_error(request.user, booking, PICKUP_STAGE_STATUSES | {BookingStatus.OUT_FOR_DELIVERY})
    if error:
        return error

    serializer = VehicleConditionPhotoSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    photo = serializer.save(booking=booking, uploaded_by=request.user, stage=condition_stage(booking))
    return Response(VehicleConditionPhotoSerializer(photo).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def driver_plate_check(request, pk):
    """
    POST /api/driver/pickups/<id>/plate-check/  {"ocr_text": "KA 01 AB 1234"}
    The driver's phone reads the number plate (OCR in the browser); the server compares it with the
    registration on the booking so the driver cannot pick up the wrong car.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = driver_job_error(request.user, booking, PICKUP_STAGE_STATUSES)
    if error:
        return error

    ocr_text = str(request.data.get("ocr_text") or "")[:500]
    outcome = check_plate(ocr_text, booking.vehicle.registration_number)
    if outcome["result"] in (MATCH, LIKELY):
        booking.plate_verified = True
        booking.plate_detected = outcome["detected"][:20]
        booking.save(update_fields=["plate_verified", "plate_detected", "updated_at"])
    return Response({**outcome, "plate_verified": booking.plate_verified})


MAX_ODOMETER_KM = 2_000_000


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def driver_record_odometer(request, pk):
    """
    POST /api/driver/pickups/<id>/odometer/  {"reading_km": 45210}
    Recorded at pickup and again at delivery; the difference is the distance driven while we had the car.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = driver_job_error(request.user, booking, PICKUP_STAGE_STATUSES | {BookingStatus.OUT_FOR_DELIVERY})
    if error:
        return error

    try:
        reading = int(request.data.get("reading_km"))
    except (TypeError, ValueError):
        return Response({"error": "Enter the odometer reading in whole kilometres."}, status=status.HTTP_400_BAD_REQUEST)
    if not 0 <= reading <= MAX_ODOMETER_KM:
        return Response({"error": "That odometer reading is out of range."}, status=status.HTTP_400_BAD_REQUEST)

    if condition_stage(booking) == VehicleConditionPhoto.Stage.PICKUP:
        booking.pickup_odometer_km = reading
    else:
        if booking.pickup_odometer_km is not None and reading < booking.pickup_odometer_km:
            return Response(
                {"error": f"The delivery reading cannot be lower than the pickup reading ({booking.pickup_odometer_km} km)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        booking.delivery_odometer_km = reading
    booking.save()

    vehicle = booking.vehicle
    if vehicle.odometer_km is None or reading > vehicle.odometer_km:
        vehicle.odometer_km = reading
        vehicle.save(update_fields=["odometer_km", "updated_at"])
    return Response(ServiceBookingSerializer(booking).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def booking_condition_report(request, pk):
    """
    GET /api/bookings/<id>/condition-report/
    Before (pickup) and after (delivery) photos and odometer readings for one booking.
    """
    booking = find_booking(pk)
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
    if not can_view_booking(request.user, booking):
        return Response({"error": "You do not have permission to view this booking."}, status=status.HTTP_403_FORBIDDEN)

    photos = booking.condition_photos.all()
    km_driven = None
    if booking.pickup_odometer_km is not None and booking.delivery_odometer_km is not None:
        km_driven = booking.delivery_odometer_km - booking.pickup_odometer_km
    return Response({
        "booking": booking.id,
        "pickup_photos": VehicleConditionPhotoSerializer(photos.filter(stage=VehicleConditionPhoto.Stage.PICKUP), many=True).data,
        "delivery_photos": VehicleConditionPhotoSerializer(photos.filter(stage=VehicleConditionPhoto.Stage.DELIVERY), many=True).data,
        "pickup_odometer_km": booking.pickup_odometer_km,
        "delivery_odometer_km": booking.delivery_odometer_km,
        "km_driven": km_driven,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def driver_post_location(request, pk):
    """
    POST /api/driver/pickups/<id>/location/
    Driver posts periodic GPS coordinates during active pickup.
    """
    if not (is_driver(request.user) or is_admin(request.user)):
        return Response({"error": "Driver permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = driver_job_error(request.user, booking, DRIVER_GPS_STATUSES)
    if error:
        return error

    try:
        lat = float(request.data.get("latitude"))
        lng = float(request.data.get("longitude"))
    except (ValueError, TypeError):
        return Response({"error": "Valid latitude and longitude coordinates are required."}, status=status.HTTP_400_BAD_REQUEST)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return Response({"error": "Coordinates are out of range."}, status=status.HTTP_400_BAD_REQUEST)

    location = DriverLocation.objects.create(
        driver=request.user,
        booking=booking,
        latitude=lat,
        longitude=lng,
    )
    return Response(DriverLocationSerializer(location).data, status=status.HTTP_201_CREATED)


# ==========================================
# PHASE 8 — MECHANIC, EVIDENCE & REPAIR VIEWS
# ==========================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def mechanic_jobs_list(request):
    """
    GET /api/mechanic/jobs/
    Lists assigned service jobs for mechanic.
    """
    if not (is_mechanic(request.user) or is_admin(request.user)):
        return Response({"error": "Mechanic permissions required."}, status=status.HTTP_403_FORBIDDEN)

    if is_admin(request.user):
        qs = ServiceBooking.objects.exclude(status=BookingStatus.CANCELLED).exclude(
            customer_notes__startswith=SYNTHETIC_MARKER
        ).order_by("-created_at")
    else:
        qs = ServiceBooking.objects.filter(assigned_mechanic=request.user).exclude(
            status=BookingStatus.CANCELLED
        ).order_by("-created_at")

    serializer = ServiceBookingSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def mechanic_job_status_update(request, pk):
    """
    PATCH /api/mechanic/jobs/<id>/status/
    Mechanic updates service job status.
    """
    if not (is_mechanic(request.user) or is_admin(request.user)):
        return Response({"error": "Mechanic permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking = ServiceBooking.objects.filter(pk=pk).first()
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    error = mechanic_job_error(request.user, booking)
    if error:
        return error

    new_status = request.data.get("status")
    if not new_status:
        return Response({"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST)
    if not is_admin(request.user):
        if new_status not in MECHANIC_SETTABLE_STATUSES:
            return Response({"error": f"Mechanics cannot set status '{new_status}'."}, status=status.HTTP_400_BAD_REQUEST)
        if booking.status not in WORKSHOP_STATUSES:
            return Response({"error": "The vehicle is not at the workshop yet."}, status=status.HTTP_400_BAD_REQUEST)

    booking.status = new_status
    booking.save()

    if new_status == BookingStatus.READY_FOR_DELIVERY:
        notify_ready_for_delivery(booking)
    if new_status == BookingStatus.IN_SERVICE:
        send_notification(
            user=booking.customer,
            booking=booking,
            notification_type=NotificationType.SERVICE_STARTED,
            title="Vehicle Service Started",
            message=f"Mechanic {request.user.get_full_name() or request.user.username} has started servicing vehicle {booking.vehicle.registration_number}.",
        )
    return Response(ServiceBookingSerializer(booking).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_service_inspection(request):
    """
    POST /api/inspections/
    Mechanic records digital vehicle inspection report.
    """
    if not (is_mechanic(request.user) or is_admin(request.user)):
        return Response({"error": "Mechanic permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking_id = request.data.get("booking") or request.data.get("booking_id")
    booking = ServiceBooking.objects.filter(pk=booking_id).first()
    if not booking:
        return Response({"error": "Valid booking ID is required."}, status=status.HTTP_400_BAD_REQUEST)
    error = mechanic_job_error(request.user, booking)
    if error:
        return error

    serializer = ServiceInspectionSerializer(data=request.data)
    if serializer.is_valid():
        inspection = serializer.save(mechanic=request.user, booking=booking)
        try:
            recalculate_car_health_score(booking.vehicle)
        except Exception:
            pass
        return Response(ServiceInspectionSerializer(inspection).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_repair_evidence(request):
    """
    POST /api/repair-evidence/
    Mechanic uploads photo or short video evidence of damaged/worn parts.
    """
    if not (is_mechanic(request.user) or is_admin(request.user)):
        return Response({"error": "Mechanic permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking_id = request.data.get("booking") or request.data.get("booking_id")
    booking = ServiceBooking.objects.filter(pk=booking_id).first()
    if not booking:
        return Response({"error": "Valid booking ID is required."}, status=status.HTTP_400_BAD_REQUEST)
    error = mechanic_job_error(request.user, booking)
    if error:
        return error

    serializer = RepairEvidenceSerializer(data=request.data)
    if serializer.is_valid():
        evidence = serializer.save(mechanic=request.user, booking=booking)
        return Response(RepairEvidenceSerializer(evidence).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_repair_request(request):
    """
    POST /api/repair-requests/
    Mechanic creates an additional repair request for customer approval.
    Updates booking status to 'Repair Approval Required'.
    """
    if not (is_mechanic(request.user) or is_admin(request.user)):
        return Response({"error": "Mechanic permissions required."}, status=status.HTTP_403_FORBIDDEN)

    booking_id = request.data.get("booking") or request.data.get("booking_id")
    booking = ServiceBooking.objects.filter(pk=booking_id).first()
    if not booking:
        return Response({"error": "Valid booking ID is required."}, status=status.HTTP_400_BAD_REQUEST)
    error = mechanic_job_error(request.user, booking)
    if error:
        return error

    serializer = RepairRequestSerializer(data=request.data)
    if serializer.is_valid():
        repair_req = serializer.save(
            mechanic=request.user,
            booking=booking,
            status=RepairRequestStatus.PENDING,
        )
        booking.status = "Repair Approval Required"
        booking.save()

        send_notification(
            user=booking.customer,
            booking=booking,
            notification_type=NotificationType.REPAIR_APPROVAL_REQUIRED,
            title="Additional Repair Approval Required",
            message=f"Mechanic recommended repair: '{repair_req.issue_title}' (₹{repair_req.additional_cost}). Please inspect and approve or decline.",
        )

        return Response(RepairRequestSerializer(repair_req).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# PHASE 8 — CUSTOMER TRACKING & APPROVAL VIEWS
# ==========================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def customer_booking_tracking_detail(request, pk):
    """
    GET /api/bookings/<id>/tracking/
    Detailed customer tracking payload: booking info, timeline, driver GPS, evidence, repair requests.
    """
    if str(pk).isdigit():
        booking = ServiceBooking.objects.filter(pk=pk).first()
    else:
        booking = ServiceBooking.objects.filter(Q(booking_reference=pk) | Q(booking_id=pk)).first()

    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    if booking.customer != request.user and not is_admin(request.user):
        return Response({"error": "Unauthorized access to booking tracking."}, status=status.HTTP_403_FORBIDDEN)

    latest_location = DriverLocation.objects.filter(booking=booking).first()
    # Recent GPS trail, oldest first, for drawing the driver's route on the map
    recent_route = list(DriverLocation.objects.filter(booking=booking)[:50])[::-1]
    inspections = ServiceInspection.objects.filter(booking=booking)
    evidence_items = RepairEvidence.objects.filter(booking=booking)
    repair_requests = RepairRequest.objects.filter(booking=booking)

    return Response({
        "booking": ServiceBookingSerializer(booking).data,
        "latest_driver_location": DriverLocationSerializer(latest_location).data if latest_location else None,
        "driver_route": DriverLocationSerializer(recent_route, many=True).data,
        "assigned_driver": UserSerializer(booking.assigned_driver).data if booking.assigned_driver else None,
        "assigned_mechanic": UserSerializer(booking.assigned_mechanic).data if booking.assigned_mechanic else None,
        "handover_otp_code": booking.handover_otp if booking.customer == request.user else None,
        "delivery_otp_code": (
            booking.delivery_otp if booking.customer == request.user and not booking.delivery_otp_verified else None
        ),
        "inspections": ServiceInspectionSerializer(inspections, many=True).data,
        "evidence": RepairEvidenceSerializer(evidence_items, many=True).data,
        "repair_requests": RepairRequestSerializer(repair_requests, many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def customer_approve_repair_request(request, pk):
    """
    POST /api/repair-requests/<id>/approve/
    Customer approves an additional repair request.
    """
    repair_req = RepairRequest.objects.filter(pk=pk).first()
    if not repair_req:
        return Response({"error": "Repair request not found."}, status=status.HTTP_404_NOT_FOUND)

    if repair_req.booking.customer != request.user and not is_admin(request.user):
        return Response({"error": "Cannot approve repair request belonging to another customer."}, status=status.HTTP_403_FORBIDDEN)

    error = repair_response_error(repair_req)
    if error:
        return error

    repair_req.status = RepairRequestStatus.APPROVED
    repair_req.responded_at = timezone.now()
    repair_req.customer_response = request.data.get("notes", "Approved by customer")
    repair_req.save()

    booking = repair_req.booking
    booking.estimated_cost = float(booking.estimated_cost) + float(repair_req.estimated_cost or repair_req.additional_cost or 0)
    if not booking.repair_requests.filter(status=RepairRequestStatus.PENDING).exists():
        booking.status = BookingStatus.IN_SERVICE
    booking.save()

    if repair_req.mechanic:
        send_notification(
            user=repair_req.mechanic,
            booking=booking,
            notification_type=NotificationType.REPAIR_APPROVED,
            title="Repair Approved by Customer",
            message=f"Customer approved repair '{repair_req.issue_title}' for {booking.vehicle.registration_number}.",
        )

    return Response({
        "message": "Repair request approved successfully.",
        "repair_request": RepairRequestSerializer(repair_req).data,
        "booking": ServiceBookingSerializer(booking).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def customer_reject_repair_request(request, pk):
    """
    POST /api/repair-requests/<id>/reject/
    Customer rejects an additional repair request.
    """
    repair_req = RepairRequest.objects.filter(pk=pk).first()
    if not repair_req:
        return Response({"error": "Repair request not found."}, status=status.HTTP_404_NOT_FOUND)

    if repair_req.booking.customer != request.user and not is_admin(request.user):
        return Response({"error": "Cannot reject repair request belonging to another customer."}, status=status.HTTP_403_FORBIDDEN)

    error = repair_response_error(repair_req)
    if error:
        return error

    repair_req.status = RepairRequestStatus.REJECTED
    repair_req.responded_at = timezone.now()
    repair_req.customer_response = request.data.get("reason", "Declined by customer")
    repair_req.save()

    booking = repair_req.booking
    if not booking.repair_requests.filter(status=RepairRequestStatus.PENDING).exists():
        booking.status = BookingStatus.IN_SERVICE
        booking.save()

    if repair_req.mechanic:
        send_notification(
            user=repair_req.mechanic,
            booking=booking,
            notification_type=NotificationType.REPAIR_REJECTED,
            title="Repair Declined by Customer",
            message=f"Customer declined repair '{repair_req.issue_title}' for {booking.vehicle.registration_number}.",
        )

    return Response({
        "message": "Repair request rejected.",
        "repair_request": RepairRequestSerializer(repair_req).data,
        "booking": ServiceBookingSerializer(booking).data,
    })


# ==========================================
# PHASE 9 — AI REPAIR COST ESTIMATOR
# ==========================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def repair_cost_estimate(request):
    """
    POST /api/repair-cost/estimate/
    AI-assisted repair cost estimation endpoint.
    Calculates deterministic range based on brand, model, variant, severity, and labor.
    """
    serializer = RepairCostEstimateInputSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    vehicle_id = serializer.validated_data["vehicle"]
    vehicle = Vehicle.objects.filter(pk=vehicle_id).first()
    if not vehicle:
        return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

    # Validate access: vehicle owner, manager / admin, or a mechanic with an open job on this vehicle
    assigned_mechanic = (
        request.user.role == UserRole.MECHANIC
        and ServiceBooking.objects.filter(vehicle=vehicle, assigned_mechanic=request.user)
        .exclude(status__in=[BookingStatus.COMPLETED, BookingStatus.CANCELLED])
        .exists()
    )
    center = manager_center(request.user) if request.user.role == UserRole.SERVICE_CENTER_MANAGER else None
    center_manager = bool(center) and ServiceBooking.objects.filter(vehicle=vehicle, service_center=center).exists()
    if vehicle.customer != request.user and not (assigned_mechanic or center_manager or is_admin(request.user)):
        return Response({"error": "Unauthorized: You do not have permission to estimate for this vehicle."}, status=status.HTTP_403_FORBIDDEN)

    service_type = None
    service_type_id = serializer.validated_data.get("service_type")
    if service_type_id:
        service_type = ServiceType.objects.filter(pk=service_type_id).first()

    issue_description = serializer.validated_data["issue_description"]
    severity = serializer.validated_data.get("severity", "MEDIUM")
    estimated_labor_hours = serializer.validated_data.get("estimated_labor_hours", 1.5)

    estimation_data = estimate_repair_cost(
        vehicle=vehicle,
        service_type=service_type,
        issue_description=issue_description,
        severity=severity,
        estimated_labor_hours=estimated_labor_hours,
    )

    estimate_obj = RepairCostEstimate.objects.create(
        vehicle=vehicle,
        service_type=service_type,
        issue_description=issue_description,
        severity=severity,
        estimated_min_cost=estimation_data["estimated_min_cost"],
        estimated_max_cost=estimation_data["estimated_max_cost"],
        estimated_labor_hours=estimation_data["estimated_labor_hours"],
        estimation_source=estimation_data["estimation_source"],
        explanation=estimation_data["explanation"],
    )

    return Response(RepairCostEstimateSerializer(estimate_obj).data, status=status.HTTP_200_OK)


# ==========================================
# PHASE 10 — INVOICES & CAR HEALTH SCORE
# ==========================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoices_list(request):
    """
    GET /api/invoices/
    List invoices isolated by role (Customer sees own, Manager sees service center, Admin sees all).
    """
    if is_admin(request.user):
        qs = Invoice.objects.all()
    elif is_customer(request.user):
        qs = Invoice.objects.filter(customer=request.user)
    elif request.user.role == UserRole.SERVICE_CENTER_MANAGER:
        error = manager_scope_error(request.user)
        if error:
            return error
        qs = Invoice.objects.filter(service_center=manager_center(request.user))
    else:
        return Response({"error": "Unauthorized to view invoices."}, status=status.HTTP_403_FORBIDDEN)

    serializer = InvoiceSerializer(qs.order_by("-created_at"), many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoice_detail(request, pk):
    """
    GET /api/invoices/<id>/
    Retrieve single invoice detail with itemized breakdown.
    """
    if str(pk).isdigit():
        invoice = Invoice.objects.filter(pk=pk).first()
    else:
        invoice = Invoice.objects.filter(invoice_number=pk).first()

    if not invoice:
        return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
    if not can_view_invoice(request.user, invoice):
        return Response({"error": "Unauthorized access to invoice."}, status=status.HTTP_403_FORBIDDEN)

    serializer = InvoiceSerializer(invoice)
    return Response(serializer.data)


def can_view_invoice(user, invoice):
    """The customer billed, an admin, or the manager of the center that issued it."""
    if invoice.customer_id == user.id or is_admin(user):
        return True
    center = manager_center(user) if user.role == UserRole.SERVICE_CENTER_MANAGER else None
    return bool(center) and invoice.service_center_id == center.id


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoice_pdf(request, pk):
    """GET /api/invoices/<id>/pdf/ -> downloadable PDF with a verification QR code"""
    invoice = Invoice.objects.filter(pk=pk).first() if str(pk).isdigit() else Invoice.objects.filter(invoice_number=pk).first()
    if not invoice:
        return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)
    if not can_view_invoice(request.user, invoice):
        return Response({"error": "Unauthorized access to invoice."}, status=status.HTTP_403_FORBIDDEN)

    response = HttpResponse(build_invoice_pdf(invoice), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{invoice.invoice_number}.pdf"'
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def invoice_verify(request, token):
    """
    GET /api/invoices/verify/<token>/  (public; the token comes from the QR code on the PDF)
    Confirms an invoice is genuine. Shows only what is printed on it anyway, minus customer contact details.
    """
    invoice = invoice_from_token(token)
    if not invoice:
        return Response({"valid": False, "error": "This code does not match any invoice we issued."}, status=status.HTTP_404_NOT_FOUND)
    reg = invoice.vehicle.registration_number if invoice.vehicle else ""
    return Response({
        "valid": True,
        "invoice_number": invoice.invoice_number,
        "issued_at": invoice.issued_at,
        "service_center": invoice.service_center.name if invoice.service_center else None,
        # Partly hidden so a lost invoice does not reveal the full registration
        "vehicle": f"{reg[:4]}{'*' * max(0, len(reg) - 6)}{reg[-2:]}" if len(reg) > 6 else reg,
        "grand_total": invoice.grand_total,
        "payment_status": invoice.payment_status,
        "invoice_status": invoice.invoice_status,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invoice_pay(request, pk):
    """
    POST /api/invoices/<id>/pay/
    Customer pays their invoice. Body: {"method": "UPI", "upi_id": ...}
    or {"method": "CARD", "card_number": ..., "card_expiry": "MM/YY"}.
    """
    try:
        payment = pay_invoice(pk, request.user, request.data)
    except PaymentError as exc:
        return Response({"error": exc.message}, status=exc.status_code)

    invoice_data = InvoiceSerializer(payment.invoice).data
    if payment.status != payment.Status.SUCCESS:
        return Response(
            {"error": payment.failure_reason, "payment": PaymentSerializer(payment).data, "invoice": invoice_data},
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )
    return Response({"payment": PaymentSerializer(payment).data, "invoice": invoice_data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def booking_generate_invoice(request, pk):
    """
    POST /api/bookings/<id>/generate-invoice/
    Generates or recalculates the itemized invoice for a completed booking.
    Only admins and the manager of the booking's service center may do this.
    """
    if str(pk).isdigit():
        booking = ServiceBooking.objects.filter(pk=pk).first()
    else:
        booking = ServiceBooking.objects.filter(Q(booking_reference=pk) | Q(booking_id=pk)).first()

    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    if manager_scope_error(request.user, booking):
        return Response(
            {"error": "Only the service center manager for this booking can generate its invoice."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        invoice = generate_invoice_for_booking(booking)
    except InvoiceError as exc:
        return Response({"error": exc.message}, status=exc.status_code)
    recalculate_car_health_score(booking.vehicle)
    return Response(InvoiceSerializer(invoice).data, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def booking_review(request, pk):
    """
    GET  /api/bookings/<id>/review/ -> the review left for this booking (404 if none)
    POST /api/bookings/<id>/review/ -> customer rates a completed booking once:
         {"center_rating": 1-5, "driver_rating": 1-5 (optional), "comment": "..."}
    """
    booking = find_booking(pk)
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        if not can_view_booking(request.user, booking):
            return Response({"error": "You do not have permission to view this booking."}, status=status.HTTP_403_FORBIDDEN)
        review = ServiceReview.objects.filter(booking=booking).first()
        if not review:
            return Response({"error": "No review yet."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ServiceReviewSerializer(review).data)

    if booking.customer_id != request.user.id:
        return Response({"error": "Only the customer who booked this service can review it."}, status=status.HTTP_403_FORBIDDEN)
    if booking.status != BookingStatus.COMPLETED:
        return Response({"error": "You can review a service once it is completed."}, status=status.HTTP_400_BAD_REQUEST)
    if ServiceReview.objects.filter(booking=booking).exists():
        return Response({"error": "You have already reviewed this service."}, status=status.HTTP_409_CONFLICT)

    serializer = ServiceReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    driver_rating = serializer.validated_data.get("driver_rating")
    if driver_rating is not None and not booking.assigned_driver_id:
        return Response({"error": "This booking had no driver to rate."}, status=status.HTTP_400_BAD_REQUEST)

    review = serializer.save(
        booking=booking,
        customer=request.user,
        service_center=booking.service_center,
        driver=booking.assigned_driver if driver_rating is not None else None,
    )
    center = booking.service_center
    if center:
        # Keep the stored rating equal to the real average, so nothing shows a made-up score.
        center.rating = round(center.reviews.aggregate(avg=Avg("center_rating"))["avg"], 1)
        center.save(update_fields=["rating", "active"])
    return Response(ServiceReviewSerializer(review).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def service_center_reviews(request, pk):
    """GET /api/service-centers/<id>/reviews/ -> recent public reviews of a center"""
    center = ServiceCenter.objects.filter(pk=pk).first()
    if not center:
        return Response({"error": "Service center not found."}, status=status.HTTP_404_NOT_FOUND)
    reviews = center.reviews.select_related("customer", "booking")[:20]
    return Response({
        "service_center": ServiceCenterSerializer(center).data,
        "reviews": ServiceReviewSerializer(reviews, many=True).data,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_reminders(request):
    """
    GET /api/reminders/
    Next service due date / kilometres for each of the customer's vehicles.
    """
    today = timezone.localdate()
    return Response([service_due(v, today) for v in Vehicle.objects.filter(customer=request.user)])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def vehicle_health_score(request, pk):
    """
    GET /api/vehicles/<id>/health-score/
    Get and/or recalculate deterministic Car Health Score (0-100).
    """
    vehicle = Vehicle.objects.filter(pk=pk).first()
    if not vehicle:
        return Response({"error": "Vehicle not found."}, status=status.HTTP_404_NOT_FOUND)

    if vehicle.customer != request.user and not is_admin(request.user):
        return Response({"error": "Unauthorized to view health score for this vehicle."}, status=status.HTTP_403_FORBIDDEN)

    health_score = recalculate_car_health_score(vehicle)
    return Response(CarHealthScoreSerializer(health_score).data)


# ==========================================
# PHASE 11 — NOTIFICATIONS & ADMIN DASHBOARD
# ==========================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications_list(request):
    """
    GET /api/notifications/
    List authenticated user's notifications.
    """
    notifications = Notification.objects.filter(user=request.user).order_by("-created_at")
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)


@api_view(["PATCH", "POST"])
@permission_classes([IsAuthenticated])
def notification_mark_read(request, pk):
    """
    PATCH /api/notifications/<id>/read/
    Mark a single notification as read.
    """
    notification = Notification.objects.filter(pk=pk).first()
    if not notification:
        return Response({"error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)

    if notification.user != request.user and not is_admin(request.user):
        return Response({"error": "Unauthorized access to notification."}, status=status.HTTP_403_FORBIDDEN)

    notification.read = True
    notification.is_read = True
    notification.save()
    return Response({"success": True, "notification": NotificationSerializer(notification).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notifications_mark_all_read(request):
    """
    POST /api/notifications/mark-all-read/
    Mark all user's notifications as read.
    """
    updated_count = Notification.objects.filter(user=request.user, is_read=False).update(read=True, is_read=True)
    return Response({"success": True, "marked_read_count": updated_count})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_dashboard_stats(request):
    """
    GET /api/admin/dashboard-stats/
    Comprehensive platform analytics for administrators.
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    # Leave out generated demo history (seed_repair_history)
    real_bookings = ServiceBooking.objects.exclude(customer_notes__startswith=SYNTHETIC_MARKER)
    total_customers = User.objects.filter(role=UserRole.CUSTOMER).exclude(email=SYNTHETIC_HISTORY_EMAIL).count()
    total_vehicles = Vehicle.objects.exclude(customer__email=SYNTHETIC_HISTORY_EMAIL).count()
    total_bookings = real_bookings.count()
    active_services = real_bookings.filter(
        status__in=[
            BookingStatus.CONFIRMED,
            BookingStatus.PICKUP_SCHEDULED,
            BookingStatus.VEHICLE_PICKED_UP,
            BookingStatus.IN_SERVICE,
            "Repair Approval Required",
            BookingStatus.READY_FOR_DELIVERY,
            BookingStatus.OUT_FOR_DELIVERY,
        ]
    ).count()
    completed_services = real_bookings.filter(status=BookingStatus.COMPLETED).count()
    service_centers_count = ServiceCenter.objects.filter(is_active=True).count()
    total_drivers = User.objects.filter(role=UserRole.DRIVER).count()
    total_mechanics = User.objects.filter(role=UserRole.MECHANIC).count()

    # Revenue counts only paid invoices; unpaid invoice totals are reported separately.
    def invoice_sum(qs):
        return sum((float(inv.grand_total or inv.total_amount or 0) for inv in qs), 0.0)

    total_revenue = invoice_sum(Invoice.objects.filter(payment_status=Invoice.PaymentStatus.PAID))
    outstanding_amount = invoice_sum(
        Invoice.objects.exclude(payment_status=Invoice.PaymentStatus.PAID).exclude(invoice_status=InvoiceStatus.CANCELLED)
    )

    real_repairs = RepairRequest.objects.exclude(booking__customer_notes__startswith=SYNTHETIC_MARKER)
    repair_stats = {
        "total": real_repairs.count(),
        "approved": real_repairs.filter(status=RepairRequestStatus.APPROVED).count(),
        "pending": real_repairs.filter(status=RepairRequestStatus.PENDING).count(),
        "rejected": real_repairs.filter(status=RepairRequestStatus.REJECTED).count(),
    }

    return Response({
        "total_customers": total_customers,
        "total_vehicles": total_vehicles,
        "total_bookings": total_bookings,
        "active_services": active_services,
        "completed_services": completed_services,
        "service_centers": service_centers_count,
        "total_drivers": total_drivers,
        "total_mechanics": total_mechanics,
        "total_revenue": round(total_revenue, 2),
        "outstanding_amount": round(outstanding_amount, 2),
        "repair_approvals": repair_stats,
    })


def cost_model_summary(model):
    return {
        "id": model.id,
        "trained_at": model.trained_at,
        "n_samples": model.n_samples,
        "synthetic_share": model.synthetic_share,
        "metrics": model.metrics,
        "is_active": model.is_active,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_cost_model(request):
    """GET /api/admin/cost-model/ -> the active learned estimator (if any) and its cross-validated accuracy"""
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    model = CostModel.objects.filter(is_active=True).first()
    return Response({
        "active": cost_model_summary(model) if model else None,
        "available_samples": len(training_rows()),
        "min_samples": MIN_TRAINING_SAMPLES,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_train_cost_model(request):
    """POST /api/admin/cost-model/train/ -> retrain on all completed, approved repairs"""
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
    try:
        model = train_cost_model()
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(cost_model_summary(model), status=status.HTTP_201_CREATED)
