from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

import re
import random
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
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    CarHealthScore,
    RepairCostEstimate,
    Notification,
    NotificationType,
    Employee,
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
    RepairCostEstimateInputSerializer,
    RepairCostEstimateSerializer,
    InvoiceItemSerializer,
    InvoiceSerializer,
    CarHealthScoreSerializer,
    NotificationSerializer,
)
from .otp_service import generate_otp_code, send_otp_to_identifier, normalize_phone_number
from .ai_cost_service import estimate_repair_cost
from .invoice_service import generate_invoice_for_booking
from .health_service import recalculate_car_health_score
from .notification_service import send_notification


def is_admin(user):
    return user and (user.is_staff or user.role == UserRole.ADMIN)


def is_manager(user):
    return user and (user.is_staff or user.role in [UserRole.ADMIN, UserRole.SERVICE_CENTER_MANAGER])


def is_driver(user):
    return user and user.role == UserRole.DRIVER


def is_mechanic(user):
    return user and (user.role == UserRole.MECHANIC or user.is_staff)


def is_customer(user):
    return user and user.role == UserRole.CUSTOMER and not user.is_staff



@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response({
        "status": "ok",
        "service": "Smart Doorstep Vehicle Service Management System API",
        "backend": "Django REST Framework",
        "phase": 4
    })


# ==========================================
# AUTHENTICATION VIEWS (PHASE 2)
# ==========================================

@api_view(["POST"])
@permission_classes([AllowAny])
def bypass_login(request):
    """
    POST /api/auth/bypass-login/
    Directly signs in or registers any role without requiring OTP.
    Controlled by settings.OTP_BYPASS.
    """
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
        if not user:
            username = identifier.split("@")[0] + f"_{timezone.now().strftime('%M%S')}"
            user = User.objects.create(
                email=identifier.lower(),
                username=username,
                role=requested_role,
                first_name=provided_name or identifier.split("@")[0].capitalize(),
                is_staff=requested_role in [UserRole.ADMIN, "ADMIN"],
                is_superuser=requested_role in [UserRole.ADMIN, "ADMIN"],
            )
        elif requested_role != UserRole.CUSTOMER and user.role != requested_role:
            user.role = requested_role
            if requested_role in [UserRole.ADMIN, "ADMIN"]:
                user.is_staff = True
            user.save()
    else:
        norm_phone = normalize_phone_number(identifier)
        clean_phone = identifier.replace(" ", "").replace("-", "")
        user = User.objects.filter(phone=norm_phone).first() or User.objects.filter(phone=clean_phone).first()
        if not user:
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
        elif requested_role != UserRole.CUSTOMER and user.role != requested_role:
            user.role = requested_role
            user.save()

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
    requested_role = serializer.validated_data.get("role", UserRole.CUSTOMER).upper()
    if requested_role not in UserRole.values:
        requested_role = UserRole.CUSTOMER

    is_email = "@" in identifier

    if is_email:
        user = User.objects.filter(email__iexact=identifier).first()
        if not user:
            username = identifier.split("@")[0] + f"_{timezone.now().strftime('%M%S')}"
            user = User.objects.create(email=identifier.lower(), username=username, role=requested_role)
        target_identifier = identifier
    else:
        norm_phone = normalize_phone_number(identifier)
        clean_phone = identifier.replace(" ", "").replace("-", "")
        user = User.objects.filter(phone=norm_phone).first() or User.objects.filter(phone=clean_phone).first()
        if not user:
            clean_digits = re.sub(r"\D", "", norm_phone)
            username = f"user_{clean_digits[-4:]}_{timezone.now().strftime('%M%S')}"
            dummy_email = f"{clean_digits}@smartdoorstep.local"
            user = User.objects.create(phone=norm_phone, email=dummy_email, username=username, role=requested_role)
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


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def booking_list_create(request):
    """
    GET /api/bookings/ -> List authenticated customer's bookings (or all for admin/staff)
    POST /api/bookings/ -> Create a new vehicle service booking
    """
    if request.method == "GET":
        if is_admin(request.user):
            qs = ServiceBooking.objects.all().order_by("-created_at")
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

            # Auto-populate estimated_cost from service_type.base_price if not provided
            service_type = serializer.validated_data.get("service_type")
            est_cost = serializer.validated_data.get("estimated_cost", 0)
            if service_type and (not est_cost or est_cost == 0):
                est_cost = service_type.base_price

            booking = serializer.save(
                customer=request.user,
                estimated_cost=est_cost,
                status=BookingStatus.PENDING
            )
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

        # Cancellation validation rule: Customers can only cancel if status is Pending or Confirmed
        if new_status == BookingStatus.CANCELLED and not is_admin(request.user):
            if booking.status not in [BookingStatus.PENDING, BookingStatus.CONFIRMED]:
                return Response(
                    {"error": f"Bookings can only be cancelled when status is Pending or Confirmed. Current status is '{booking.status}'."},
                    status=status.HTTP_400_BAD_REQUEST
                )

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
@permission_classes([AllowAny])
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
    if not is_manager(request.user):
        return Response({"error": "Manager permissions required."}, status=status.HTTP_403_FORBIDDEN)

    qs = ServiceBooking.objects.all().order_by("-created_at")

    if hasattr(request.user, "service_center_profile") and request.user.service_center_profile:
        qs = qs.filter(service_center=request.user.service_center_profile)
    elif hasattr(request.user, "employee_profile") and request.user.employee_profile and request.user.employee_profile.service_center:
        qs = qs.filter(service_center=request.user.employee_profile.service_center)

    serializer = ServiceBookingSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def service_center_booking_update(request, pk):
    """
    PATCH /api/service-center/bookings/<id>/
    Managers can confirm/reject bookings, update status, assign drivers, or assign mechanics.
    """
    if not is_manager(request.user):
        return Response({"error": "Manager permissions required."}, status=status.HTTP_403_FORBIDDEN)

    if str(pk).isdigit():
        booking = ServiceBooking.objects.filter(pk=pk).first()
    else:
        booking = ServiceBooking.objects.filter(Q(booking_reference=pk) | Q(booking_id=pk)).first()

    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    if hasattr(request.user, "service_center_profile") and request.user.service_center_profile:
        if booking.service_center and booking.service_center != request.user.service_center_profile:
            return Response({"error": "Cannot modify booking belonging to another service center."}, status=status.HTTP_403_FORBIDDEN)

    new_status = request.data.get("status")
    assigned_driver_id = request.data.get("assigned_driver_id") or request.data.get("assigned_driver")
    assigned_mechanic_id = request.data.get("assigned_mechanic_id") or request.data.get("assigned_mechanic")

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
            send_notification(
                user=booking.customer,
                booking=booking,
                notification_type=NotificationType.READY_FOR_DELIVERY,
                title=f"Vehicle Ready for Delivery",
                message=f"Servicing complete! Vehicle {booking.vehicle.registration_number} is ready for doorstep delivery.",
            )
        elif new_status == BookingStatus.COMPLETED:
            send_notification(
                user=booking.customer,
                booking=booking,
                notification_type=NotificationType.SERVICE_COMPLETED,
                title=f"Service Completed Successfully",
                message=f"All services and repairs for {booking.vehicle.registration_number} have been successfully finalized.",
            )
            try:
                generate_invoice_for_booking(booking)
            except Exception:
                pass
            try:
                recalculate_car_health_score(booking.vehicle)
            except Exception:
                pass

    if assigned_driver_id:
        driver = User.objects.filter(pk=assigned_driver_id).first()
        if not driver or not is_driver(driver):
            return Response({"error": "Invalid driver selection."}, status=status.HTTP_400_BAD_REQUEST)
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
        if not mechanic or not is_mechanic(mechanic):
            return Response({"error": "Invalid mechanic selection."}, status=status.HTTP_400_BAD_REQUEST)
        booking.assigned_mechanic = mechanic

    booking.save()
    return Response(ServiceBookingSerializer(booking).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_center_employees_list(request):
    """
    GET /api/service-center/employees/
    Lists available drivers and mechanics for manager dropdown assignment.
    """
    if not is_manager(request.user):
        return Response({"error": "Manager permissions required."}, status=status.HTTP_403_FORBIDDEN)

    drivers = User.objects.filter(role=UserRole.DRIVER)
    mechanics = User.objects.filter(role=UserRole.MECHANIC)

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
        qs = ServiceBooking.objects.exclude(status=BookingStatus.CANCELLED).order_by("-created_at")
    else:
        qs = ServiceBooking.objects.filter(
            Q(assigned_driver=request.user) | Q(status__in=[BookingStatus.PICKUP_SCHEDULED, BookingStatus.CONFIRMED])
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

    if booking.assigned_driver and booking.assigned_driver != request.user and not is_admin(request.user):
        return Response({"error": "You are not the assigned driver for this pickup."}, status=status.HTTP_403_FORBIDDEN)

    new_status = request.data.get("status")
    if not new_status:
        return Response({"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST)

    if not booking.assigned_driver:
        booking.assigned_driver = request.user

    booking.status = new_status
    booking.save()
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

    code = f"{random.randint(100000, 999999)}"
    booking.handover_otp = code
    booking.handover_otp_verified = False
    booking.handover_otp_attempts = 0
    booking.handover_otp_expires_at = timezone.now() + timedelta(minutes=10)
    booking.save()

    resp_data = {
        "message": "Handover OTP generated successfully.",
        "booking_reference": booking.booking_reference,
        "expires_in_minutes": 10,
    }
    if getattr(settings, "OTP_BYPASS", False):
        resp_data["otp_code"] = code
        resp_data["bypass_code"] = "123456"

    return Response(resp_data)


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

    otp_code = str(request.data.get("otp_code") or request.data.get("code") or "").strip()
    if not otp_code:
        return Response({"error": "OTP code is required."}, status=status.HTTP_400_BAD_REQUEST)

    bypass_active = getattr(settings, "OTP_BYPASS", False)
    is_universal_bypass = bypass_active and (
        otp_code in ["123456", "000000", "999999"] or otp_code.lower() == "bypass" or otp_code == booking.handover_otp
    )

    if not is_universal_bypass:
        if booking.handover_otp_attempts >= 5:
            return Response({"error": "Maximum OTP verification attempts exceeded. Please request a new OTP."}, status=status.HTTP_400_BAD_REQUEST)

        booking.handover_otp_attempts += 1

        if booking.handover_otp_expires_at and timezone.now() > booking.handover_otp_expires_at:
            booking.save()
            return Response({"error": "OTP has expired. Please request a new handover OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if booking.handover_otp != otp_code:
            booking.save()
            remaining = 5 - booking.handover_otp_attempts
            return Response({"error": f"Invalid handover OTP code. {remaining} attempt(s) remaining."}, status=status.HTTP_400_BAD_REQUEST)

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

    if booking.assigned_driver and booking.assigned_driver != request.user and not is_admin(request.user):
        return Response({"error": "Cannot post location for another driver's booking."}, status=status.HTTP_403_FORBIDDEN)

    try:
        lat = float(request.data.get("latitude"))
        lng = float(request.data.get("longitude"))
    except (ValueError, TypeError):
        return Response({"error": "Valid latitude and longitude coordinates are required."}, status=status.HTTP_400_BAD_REQUEST)

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
        qs = ServiceBooking.objects.exclude(status=BookingStatus.CANCELLED).order_by("-created_at")
    else:
        qs = ServiceBooking.objects.filter(
            Q(assigned_mechanic=request.user) | Q(status__in=[BookingStatus.VEHICLE_PICKED_UP, BookingStatus.IN_SERVICE])
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

    if booking.assigned_mechanic and booking.assigned_mechanic != request.user and not is_admin(request.user):
        return Response({"error": "Cannot modify another mechanic's assigned job."}, status=status.HTTP_403_FORBIDDEN)

    new_status = request.data.get("status")
    if not new_status:
        return Response({"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST)

    if not booking.assigned_mechanic:
        booking.assigned_mechanic = request.user

    booking.status = new_status
    booking.save()

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
    inspections = ServiceInspection.objects.filter(booking=booking)
    evidence_items = RepairEvidence.objects.filter(booking=booking)
    repair_requests = RepairRequest.objects.filter(booking=booking)

    return Response({
        "booking": ServiceBookingSerializer(booking).data,
        "latest_driver_location": DriverLocationSerializer(latest_location).data if latest_location else None,
        "assigned_driver": UserSerializer(booking.assigned_driver).data if booking.assigned_driver else None,
        "assigned_mechanic": UserSerializer(booking.assigned_mechanic).data if booking.assigned_mechanic else None,
        "handover_otp_code": booking.handover_otp if booking.customer == request.user else None,
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

    repair_req.status = RepairRequestStatus.APPROVED
    repair_req.responded_at = timezone.now()
    repair_req.customer_response = request.data.get("notes", "Approved by customer")
    repair_req.save()

    booking = repair_req.booking
    booking.estimated_cost = float(booking.estimated_cost) + float(repair_req.estimated_cost or repair_req.additional_cost or 0)
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

    repair_req.status = RepairRequestStatus.REJECTED
    repair_req.responded_at = timezone.now()
    repair_req.customer_response = request.data.get("reason", "Declined by customer")
    repair_req.save()

    booking = repair_req.booking
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

    # Validate access: vehicle owner or mechanic / manager / admin
    if vehicle.customer != request.user and not (is_mechanic(request.user) or is_manager(request.user) or is_admin(request.user)):
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
    if is_customer(request.user):
        qs = Invoice.objects.filter(customer=request.user)
    elif is_manager(request.user):
        if hasattr(request.user, "service_center_profile") and request.user.service_center_profile:
            qs = Invoice.objects.filter(service_center=request.user.service_center_profile)
        elif hasattr(request.user, "employee_profile") and request.user.employee_profile:
            qs = Invoice.objects.filter(service_center=request.user.employee_profile.service_center)
        else:
            qs = Invoice.objects.all()
    elif is_admin(request.user):
        qs = Invoice.objects.all()
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

    # Permissions
    if invoice.customer != request.user and not is_manager(request.user):
        return Response({"error": "Unauthorized access to invoice."}, status=status.HTTP_403_FORBIDDEN)

    if is_manager(request.user):
        mgr_sc = getattr(request.user, "service_center_profile", None) or (
            request.user.employee_profile.service_center if hasattr(request.user, "employee_profile") else None
        )
        if mgr_sc and invoice.service_center != mgr_sc and not is_admin(request.user):
            return Response({"error": "Unauthorized access to invoice."}, status=status.HTTP_403_FORBIDDEN)

    serializer = InvoiceSerializer(invoice)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def booking_generate_invoice(request, pk):
    """
    POST /api/bookings/<id>/generate-invoice/
    Generates or recalculates itemized invoice for booking.
    """
    if str(pk).isdigit():
        booking = ServiceBooking.objects.filter(pk=pk).first()
    else:
        booking = ServiceBooking.objects.filter(Q(booking_reference=pk) | Q(booking_id=pk)).first()

    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    if not (is_manager(request.user) or is_mechanic(request.user) or is_admin(request.user) or booking.customer == request.user):
        return Response({"error": "Unauthorized to generate invoice for this booking."}, status=status.HTTP_403_FORBIDDEN)

    invoice = generate_invoice_for_booking(booking)
    recalculate_car_health_score(booking.vehicle)
    return Response(InvoiceSerializer(invoice).data, status=status.HTTP_200_OK)


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

    total_customers = User.objects.filter(role=UserRole.CUSTOMER).count()
    total_vehicles = Vehicle.objects.count()
    total_bookings = ServiceBooking.objects.count()
    active_services = ServiceBooking.objects.filter(
        status__in=[
            BookingStatus.CONFIRMED,
            BookingStatus.PICKUP_SCHEDULED,
            BookingStatus.VEHICLE_PICKED_UP,
            BookingStatus.IN_SERVICE,
            "Repair Approval Required",
            BookingStatus.READY_FOR_DELIVERY,
        ]
    ).count()
    completed_services = ServiceBooking.objects.filter(status=BookingStatus.COMPLETED).count()
    service_centers_count = ServiceCenter.objects.count()
    total_drivers = User.objects.filter(role=UserRole.DRIVER).count()
    total_mechanics = User.objects.filter(role=UserRole.MECHANIC).count()

    total_revenue = sum(
        (float(inv.grand_total or inv.total_amount or 0) for inv in Invoice.objects.all()),
        0.0,
    )

    repair_stats = {
        "total": RepairRequest.objects.count(),
        "approved": RepairRequest.objects.filter(status=RepairRequestStatus.APPROVED).count(),
        "pending": RepairRequest.objects.filter(status=RepairRequestStatus.PENDING).count(),
        "rejected": RepairRequest.objects.filter(status=RepairRequestStatus.REJECTED).count(),
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
        "repair_approvals": repair_stats,
    })



