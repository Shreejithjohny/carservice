import secrets
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Avg, Q
from django.db import transaction
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from rest_framework import status
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
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
    Payment,
    PushSubscription,
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
    valid_contact_phone,
    PasswordRegisterSerializer,
    StaffCreateSerializer,
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
from .otp_service import generate_otp_code, normalize_phone_number
from .google_auth_service import GoogleSignInError, GoogleUnavailableError, verify_google_credential
from .ai_cost_service import estimate_repair_cost
from .invoice_service import InvoiceError, generate_invoice_for_booking
from .invoice_pdf import build_invoice_pdf, invoice_from_token
from .health_service import recalculate_car_health_score
from .notification_service import notify_admins, send_notification
from .payment_service import PaymentError, pay_invoice, payment_gateway
from . import razorpay_service
from .coupon_service import CouponError, coupon_discount, find_coupon
from .push_service import push_enabled
from .dispatch_service import best_driver, best_mechanic, rank_drivers, rank_mechanics
from .geocoding_service import GeocodingError, reverse_geocode, search_address
from .routing_service import RoutingError, driving_route
from .avatar_service import AvatarError, process_avatar
from .plate_service import LIKELY, MATCH, check_plate
from .reminder_service import service_due
from .analytics_service import center_analytics
from .ml_cost_model import (
    MIN_TRAINING_SAMPLES, SYNTHETIC_HISTORY_EMAIL, SYNTHETIC_MARKER, train_cost_model, training_rows,
)
from .slot_service import PICKUP_SLOTS, SlotError, reserve_slot, slot_availability, validate_slot_choice


# Permissions come from the app role. is_staff only controls access to the Django admin site,
# so a staff flag on a driver or mechanic must not grant platform-wide admin powers.
def is_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role == UserRole.ADMIN))


def is_driver(user):
    return bool(user and user.role == UserRole.DRIVER)


def is_mechanic(user):
    return bool(user and (user.role == UserRole.MECHANIC or is_admin(user)))


def is_customer(user):
    return bool(user and user.role == UserRole.CUSTOMER and not is_admin(user))


def admin_required_error(user):
    """
    403 unless the user is an admin. Admins run the service centers: they confirm bookings, assign
    drivers and mechanics, manage staff and issue invoices. (The separate manager role was retired.)
    """
    if is_admin(user):
        return None
    return Response({"error": "Admin permissions required."}, status=status.HTTP_403_FORBIDDEN)


CUSTOMER_EDITABLE_BOOKING_FIELDS = {
    "pickup_address", "pickup_latitude", "pickup_longitude", "preferred_date", "preferred_time", "customer_notes", "status",
    "contact_phone",
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
    """The customer, an admin, or the assigned driver or mechanic."""
    if booking.customer_id == user.id or is_admin(user):
        return True
    return user.id in (booking.assigned_driver_id, booking.assigned_mechanic_id)


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
        "google_client_id": settings.GOOGLE_CLIENT_ID or None,
        "push_public_key": settings.VAPID_PUBLIC_KEY if push_enabled() else None,
    })


# ==========================================
# AUTHENTICATION VIEWS (PHASE 2)
# ==========================================

@api_view(["POST"])
@permission_classes([AllowAny])
def bypass_login(request):
    """
    POST /api/auth/bypass-login/
    Demo login without a password. Only available when settings.OTP_BYPASS is enabled.
    Existing accounts keep their own role; new accounts may take any non-admin role.
    """
    if not getattr(settings, "OTP_BYPASS", False):
        return Response({"error": "Demo login is disabled. Please sign in with your password or Google."}, status=status.HTTP_403_FORBIDDEN)

    identifier = str(request.data.get("identifier") or "").strip()
    requested_role = str(request.data.get("role") or UserRole.CUSTOMER).upper()
    provided_name = str(request.data.get("name") or "").strip()

    if requested_role not in UserRole.values or requested_role == UserRole.SERVICE_CENTER_MANAGER:
        requested_role = UserRole.CUSTOMER

    if not identifier:
        role_defaults = {
            UserRole.ADMIN: "admin@smartdoorstep.com",
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

    retired = retired_role_error(user)
    if retired:
        return retired

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
        "message": f"Successfully signed in as {user.role.lower()}.",
        "token": access_token,
        "access": access_token,
        "refresh": refresh_token,
        "user": user_data,
        "bypass": True,
    }, status=status.HTTP_200_OK)


# ==========================================
# EMAIL + PASSWORD SIGN-IN
# ==========================================

MAX_PASSWORD_ATTEMPTS = 5
PASSWORD_LOCK_MINUTES = 15


# A Google sign-in less than this long ago may set a new password without the current one
# ("Forgot password?": prove you own the email with Google, then choose a new password).
GOOGLE_PASSWORD_RESET_WINDOW = timedelta(minutes=15)


def auth_tokens_response(user, message, status_code=status.HTTP_200_OK, google=False):
    refresh = RefreshToken.for_user(user)
    access = refresh.access_token
    if google:
        # Only on this access token, not the refresh token, so it can't be renewed past the window
        access["google_signin_at"] = int(timezone.now().timestamp())
    access_token = str(access)
    return Response({
        "message": message,
        "token": access_token,
        "access": access_token,
        "refresh": str(refresh),
        "user": UserSerializer(user).data,
    }, status=status_code)


def retired_role_error(user):
    """Accounts of the retired manager role can no longer sign in; an admin can give them another role."""
    if user.role == UserRole.SERVICE_CENTER_MANAGER and not user.is_superuser:
        return Response(
            {"error": "Manager accounts are no longer used. Ask an admin to change this account's role."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def wrong_sign_in_tab(request, user):
    """
    When the sign-in page sends the role of the tab used (e.g. DRIVER), an account of another role
    is refused and told which tab to use. Only call this once the user has proved who they are.
    """
    expected_role = str(request.data.get("role") or "").upper()
    account_role = UserRole.ADMIN if is_admin(user) else user.role
    if expected_role in UserRole.values and expected_role != account_role:
        label = UserRole(account_role).label
        return Response(
            {"error": f"This is a {label} account. Please use the {label} sign-in.", "account_role": account_role},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def find_user_by_identifier(identifier):
    """An email address or a mobile number, in any common format."""
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    if "@" in identifier:
        return User.objects.filter(email__iexact=identifier).first()
    clean_phone = identifier.replace(" ", "").replace("-", "")
    return User.objects.filter(phone=normalize_phone_number(identifier)).first() or User.objects.filter(phone=clean_phone).first()


def password_error(password, user):
    """Django's password rules (length, common passwords, all-numeric, too close to the name/email)."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        return Response({"error": " ".join(exc.messages), "password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
    return None


@api_view(["POST"])
@permission_classes([AllowAny])
def register_with_password(request):
    """
    POST /api/auth/register/  {"name", "email", "phone" (optional), "password"}
    Creates a customer account and signs it in. Staff accounts are still created by an admin.
    """
    serializer = PasswordRegisterSerializer(data=request.data)
    if not serializer.is_valid():
        errors = serializer.errors
        first = next(iter(errors.values()))[0] if errors else "Invalid details."
        return Response({"error": str(first), **errors}, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    first_name, _, last_name = data["name"].strip().partition(" ")
    user = User(
        email=data["email"],
        username=f"{data['email'].split('@')[0]}_{timezone.now().strftime('%M%S%f')[:8]}",
        phone=data.get("phone") or None,
        first_name=first_name,
        last_name=last_name,
        role=UserRole.CUSTOMER,
    )
    user.set_password(data["password"])
    user.save()
    CustomerProfile.objects.create(user=user)
    return auth_tokens_response(user, "Account created.", status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_login(request):
    """
    POST /api/auth/login/  {"identifier": email or mobile, "password", "role" (optional)}
    Five wrong passwords in a row lock the account for 15 minutes. When the sign-in page sends the
    role of the tab used (e.g. DRIVER), an account of another role is refused and told which tab to
    use; that is only revealed after the password was correct.
    """
    identifier = str(request.data.get("identifier") or request.data.get("email") or "").strip()
    password = str(request.data.get("password") or "")
    if not identifier or not password:
        return Response({"error": "Enter your email (or mobile number) and password."}, status=status.HTTP_400_BAD_REQUEST)

    invalid = Response({"error": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
    user = find_user_by_identifier(identifier)
    if user is None or not user.has_password():
        # Hash anyway, so a missing account answers as slowly as a wrong password
        User().set_password(password)
        return invalid

    now = timezone.now()
    if user.password_locked_until and user.password_locked_until > now:
        minutes = max(1, int((user.password_locked_until - now).total_seconds() // 60) + 1)
        return Response(
            {"error": f"Too many failed attempts. Try again in {minutes} minute(s), or reset your password."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if not user.check_password(password) or not user.is_active:
        user.password_attempts += 1
        if user.password_attempts >= MAX_PASSWORD_ATTEMPTS:
            user.password_attempts = 0
            user.password_locked_until = now + timedelta(minutes=PASSWORD_LOCK_MINUTES)
        user.save(update_fields=["password_attempts", "password_locked_until"])
        return invalid

    user.password_attempts = 0
    user.password_locked_until = None
    user.save(update_fields=["password_attempts", "password_locked_until"])

    wrong_tab = retired_role_error(user) or wrong_sign_in_tab(request, user)
    if wrong_tab:
        return wrong_tab

    if user.role == UserRole.CUSTOMER and not hasattr(user, "customer_profile"):
        CustomerProfile.objects.create(user=user)
    return auth_tokens_response(user, "Signed in successfully.")


@api_view(["POST"])
@permission_classes([AllowAny])
def google_login(request):
    """
    POST /api/auth/google/  {"credential": ID token from Google's sign-in button, "role" (optional)}
    Signs in the account with the Google account's (verified) email. With no such account, a
    customer account is created; staff accounts are still created by an admin.
    """
    client_id = settings.GOOGLE_CLIENT_ID
    if not client_id:
        return Response({"error": "Google sign-in is not set up on this server."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    credential = str(request.data.get("credential") or "").strip()
    if not credential:
        return Response({"error": "Missing Google credential."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        claims = verify_google_credential(credential, client_id)
    except GoogleUnavailableError:
        return Response({"error": "Couldn't reach Google. Please try again."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except GoogleSignInError:
        return Response({"error": "Google sign-in failed. Please try again."}, status=status.HTTP_400_BAD_REQUEST)

    email = claims["email"].strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        expected_role = str(request.data.get("role") or "").upper()
        if expected_role and expected_role != UserRole.CUSTOMER:
            return Response(
                {"error": "No staff account uses this Google email. Staff accounts are created by an admin."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User(
            email=email,
            username=f"{email.split('@')[0][:120]}_{timezone.now().strftime('%M%S%f')[:8]}",
            first_name=str(claims.get("given_name") or "")[:150],
            last_name=str(claims.get("family_name") or "")[:150],
            role=UserRole.CUSTOMER,
            is_verified=True,
        )
        user.set_unusable_password()
        user.save()
        CustomerProfile.objects.create(user=user)
        return auth_tokens_response(user, "Account created.", status.HTTP_201_CREATED, google=True)

    if not user.is_active:
        return Response({"error": "This account is disabled."}, status=status.HTTP_403_FORBIDDEN)
    wrong_tab = retired_role_error(user) or wrong_sign_in_tab(request, user)
    if wrong_tab:
        return wrong_tab

    # Google has just confirmed the email, which also clears a password lockout
    user.is_verified = True
    user.password_attempts = 0
    user.password_locked_until = None
    user.save(update_fields=["is_verified", "password_attempts", "password_locked_until"])
    if user.role == UserRole.CUSTOMER and not hasattr(user, "customer_profile"):
        CustomerProfile.objects.create(user=user)
    return auth_tokens_response(user, "Signed in successfully.", google=True)


def recent_google_sign_in(request):
    signed_in_at = request.auth.get("google_signin_at") if request.auth is not None else None
    if not signed_in_at:
        return False
    age = timezone.now().timestamp() - int(signed_in_at)
    return 0 <= age <= GOOGLE_PASSWORD_RESET_WINDOW.total_seconds()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    POST /api/auth/change-password/  {"current_password", "new_password"}
    The current password is not needed when the account has none yet (created with Google or the old
    OTP sign-in), or within 15 minutes of signing in with Google (how "Forgot password?" works).
    """
    user = request.user
    new_password = str(request.data.get("new_password") or "")
    current_needed = user.has_password() and not recent_google_sign_in(request)
    if current_needed and not user.check_password(str(request.data.get("current_password") or "")):
        return Response({"error": "Your current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
    error = password_error(new_password, user)
    if error:
        return error
    user.set_password(new_password)
    user.save(update_fields=["password"])
    return Response({"message": "Password updated.", "user": UserSerializer(user).data})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def my_avatar(request):
    """
    POST   /api/auth/avatar/  multipart "photo" -> sets the profile photo (any phone photo)
    DELETE /api/auth/avatar/                    -> removes it (initials are shown instead)
    """
    user = request.user
    if request.method == "DELETE":
        user.avatar, user.avatar_token = None, ""
        user.save(update_fields=["avatar", "avatar_token"])
        return Response(UserSerializer(user).data)

    upload = request.FILES.get("photo")
    if not upload:
        return Response({"error": "Choose a photo to upload."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user.avatar = process_avatar(upload)
    except AvatarError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    user.avatar_token = secrets.token_hex(16)
    user.save(update_fields=["avatar", "avatar_token"])
    return Response(UserSerializer(user).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def avatar_image(request, token):
    """
    GET /api/avatars/<token>.jpg -> a profile photo. Public so <img> tags can load it, but the
    32-character random token can't be guessed, and it changes with every upload.
    """
    user = User.objects.filter(avatar_token=token).exclude(avatar=None).only("avatar").first()
    if not user:
        return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    response = HttpResponse(bytes(user.avatar), content_type="image/jpeg")
    response["Cache-Control"] = "public, max-age=31536000, immutable"  # a new photo gets a new address
    return response


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


def notify_rescheduled(booking):
    """Tells everyone involved that the customer moved the pickup."""
    when = f"{booking.preferred_date:%d %b %Y}, {dict(PICKUP_SLOTS).get(booking.preferred_time, booking.preferred_time)}"
    recipients = [(booking.customer, f"Your pickup for {booking.vehicle.registration_number} is now on {when}.")]
    staff_message = f"Booking {booking.booking_reference} was moved by the customer to {when}."
    if booking.assigned_driver:
        recipients.append((booking.assigned_driver, staff_message))
    for user, message in recipients:
        send_notification(
            user=user,
            booking=booking,
            notification_type=NotificationType.PICKUP_SCHEDULED,
            title="Pickup rescheduled",
            message=message,
        )
    notify_admins(NotificationType.PICKUP_SCHEDULED, "Pickup rescheduled", staff_message, booking=booking)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def coupon_check(request):
    """
    POST /api/coupons/check/  {"code", "service_type": id}
    Previews a coupon on a package for the signed-in customer. The booking re-checks it.
    """
    service_type = ServiceType.objects.filter(pk=request.data.get("service_type") or 0, active=True).first()
    if not service_type:
        return Response({"error": "Choose a service package first."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        coupon = find_coupon(request.data.get("code"))
        discount = coupon_discount(coupon, request.user, service_type.base_price)
    except CouponError as exc:
        return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)
    return Response({
        "code": coupon.code,
        "description": coupon.description,
        "discount": discount,
        "price": service_type.base_price,
        "final_price": service_type.base_price - discount,
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

            # The driver calls this number at pickup: the one confirmed on the form, else the profile's
            contact_phone = serializer.validated_data.get("contact_phone") or ""
            if not contact_phone:
                try:
                    contact_phone = valid_contact_phone(request.user.phone)
                except drf_serializers.ValidationError:
                    return Response(
                        {"error": "Enter the mobile number our driver should call at pickup.", "field": "contact_phone"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            coupon_code = str(request.data.get("coupon_code") or "").strip()

            def create_booking():
                coupon, discount = None, 0
                if coupon_code:
                    # Locked so two bookings can't both take a coupon's last use
                    coupon = find_coupon(coupon_code, lock=True)
                    discount = coupon_discount(coupon, request.user, est_cost)
                return serializer.save(
                    customer=request.user,
                    estimated_cost=est_cost,
                    status=BookingStatus.PENDING,
                    contact_phone=contact_phone,
                    coupon=coupon,
                    coupon_discount=discount,
                )

            try:
                booking = reserve_slot(
                    service_center,
                    serializer.validated_data.get("preferred_date"),
                    serializer.validated_data.get("preferred_time", ""),
                    timezone.localdate(),
                    create_booking,
                )
            except SlotError as exc:
                return Response({"error": exc.message}, status=status.HTTP_400_BAD_REQUEST)
            except CouponError as exc:
                return Response({"error": exc.message, "field": "coupon_code"}, status=status.HTTP_400_BAD_REQUEST)

            # Remember the number on a profile that has none (unless another account already uses it)
            if not request.user.phone and not User.objects.filter(phone=contact_phone).exists():
                request.user.phone = contact_phone
                request.user.save(update_fields=["phone"])
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

        previous_slot = (booking.preferred_date, booking.preferred_time)
        serializer = ServiceBookingSerializer(booking, data=request.data, partial=(request.method == "PATCH"), context={"request": request})
        if serializer.is_valid():
            booking = serializer.save()
            if (booking.preferred_date, booking.preferred_time) != previous_slot and booking.status != BookingStatus.CANCELLED:
                notify_rescheduled(booking)
            return Response(serializer.data)
        first_error = next(iter(serializer.errors.values()))[0] if serializer.errors else "Invalid details."
        return Response({"error": str(first_error), **serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

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


GEOCODING_DOWN = "Address search is unavailable right now. Move the map or pick a preset area instead."


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def location_search(request):
    """GET /api/location/search/?q=koramangala -> up to 5 matching places (OpenStreetMap)"""
    query = str(request.query_params.get("q", "")).strip()
    if len(query) < 3:
        return Response({"error": "Type at least 3 characters to search."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        return Response({"results": search_address(query)})
    except GeocodingError:
        return Response({"error": GEOCODING_DOWN}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def location_reverse(request):
    """GET /api/location/reverse/?lat=12.97&lng=77.64 -> readable address for a map pin"""
    try:
        lat = float(request.query_params.get("lat"))
        lng = float(request.query_params.get("lng"))
    except (TypeError, ValueError):
        return Response({"error": "Valid lat and lng are required."}, status=status.HTTP_400_BAD_REQUEST)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return Response({"error": "Coordinates are out of range."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        return Response({"address": reverse_geocode(lat, lng)})
    except GeocodingError:
        return Response({"error": GEOCODING_DOWN}, status=status.HTTP_502_BAD_GATEWAY)


def _point(value):
    """'12.97,77.64' -> (12.97, 77.64), or None when it is not a valid point."""
    try:
        lat, lng = (float(part) for part in str(value or "").split(","))
    except ValueError:
        return None
    return (lat, lng) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def location_route(request):
    """GET /api/location/route/?from=12.97,77.64&to=12.93,77.62 -> driving route along roads (OSRM)"""
    start, end = _point(request.query_params.get("from")), _point(request.query_params.get("to"))
    if not start or not end:
        return Response({"error": "Valid from and to points (lat,lng) are required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        return Response(driving_route(*start, *end))
    except RoutingError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


# ==========================================
# PHASE 6 — SERVICE CENTER OPERATIONS (ADMIN)
# ==========================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_center_bookings_list(request):
    """
    GET /api/service-center/bookings/
    Admin only: lists the bookings of every service center.
    """
    error = admin_required_error(request.user)
    if error:
        return error

    qs = ServiceBooking.objects.exclude(customer_notes__startswith=SYNTHETIC_MARKER).order_by("-created_at")

    serializer = ServiceBookingSerializer(qs, many=True)
    return Response(serializer.data)


def assign_driver(booking, driver):
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


def auto_assign_staff(booking):
    """Fills in a driver and a mechanic if none were chosen; returns what was picked and why."""
    picked = {}
    if not booking.assigned_driver_id:
        driver, row = best_driver(booking)
        if driver:
            assign_driver(booking, driver)
            picked["driver"] = row
    if not booking.assigned_mechanic_id:
        mechanic, row = best_mechanic(booking)
        if mechanic:
            booking.assigned_mechanic = mechanic
            picked["mechanic"] = row
    return picked


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def service_center_booking_update(request, pk):
    """
    PATCH /api/service-center/bookings/<id>/
    Admin only: confirm/reject bookings, update status, assign drivers, or assign mechanics.
    """
    error = admin_required_error(request.user)
    if error:
        return error

    if str(pk).isdigit():
        booking = ServiceBooking.objects.filter(pk=pk).first()
    else:
        booking = ServiceBooking.objects.filter(Q(booking_reference=pk) | Q(booking_id=pk)).first()

    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    new_status = request.data.get("status")
    assigned_driver_id = request.data.get("assigned_driver_id") or request.data.get("assigned_driver")
    assigned_mechanic_id = request.data.get("assigned_mechanic_id") or request.data.get("assigned_mechanic")

    if new_status and new_status not in KNOWN_BOOKING_STATUSES:
        return Response({"error": f"Unknown booking status '{new_status}'."}, status=status.HTTP_400_BAD_REQUEST)

    def works_at_this_center(staff):
        # Staff not yet attached to any center form a shared pool; staff of another center are off limits.
        employee = getattr(staff, "employee_profile", None)
        center_id = employee.service_center_id if employee else None
        return center_id in (None, booking.service_center_id)

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
        assign_driver(booking, driver)

    if assigned_mechanic_id:
        mechanic = User.objects.filter(pk=assigned_mechanic_id).first()
        if not mechanic or mechanic.role != UserRole.MECHANIC:
            return Response({"error": "Invalid mechanic selection."}, status=status.HTTP_400_BAD_REQUEST)
        if not works_at_this_center(mechanic):
            return Response({"error": "That mechanic does not work at this service center."}, status=status.HTTP_400_BAD_REQUEST)
        booking.assigned_mechanic = mechanic

    # Confirming a booking fills in any staff the admin did not pick (they can still change it)
    auto_assigned = auto_assign_staff(booking) if new_status == BookingStatus.CONFIRMED else {}

    booking.save()
    data = dict(ServiceBookingSerializer(booking).data)
    data["auto_assigned"] = auto_assigned
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_center_staff_suggestions(request, pk):
    """
    GET /api/service-center/bookings/<id>/staff-suggestions/
    Drivers ranked by distance and that day's workload, and mechanics by open jobs, with reasons.
    """
    booking = find_booking(pk)
    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)
    error = admin_required_error(request.user)
    if error:
        return error
    return Response({"drivers": rank_drivers(booking), "mechanics": rank_mechanics(booking)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_center_analytics(request):
    """
    GET /api/service-center/analytics/?months=6
    Admin only: every center together, or one with ?center=<id>.
    """
    error = admin_required_error(request.user)
    if error:
        return error
    try:
        months = min(24, max(1, int(request.query_params.get("months", 6))))
    except ValueError:
        months = 6

    center_id = request.query_params.get("center")
    center = ServiceCenter.objects.filter(pk=center_id).first() if center_id else None
    if center_id and not center:
        return Response({"error": "Service center not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(center_analytics(center, months))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def service_center_employees_list(request):
    """
    GET /api/service-center/employees/
    Admin only: drivers and mechanics for the assignment dropdowns.
    """
    error = admin_required_error(request.user)
    if error:
        return error

    drivers = User.objects.filter(role=UserRole.DRIVER)
    mechanics = User.objects.filter(role=UserRole.MECHANIC)

    return Response({
        "drivers": UserSerializer(drivers, many=True).data,
        "mechanics": UserSerializer(mechanics, many=True).data,
    })


def _staff_row(user):
    employee = getattr(user, "employee_profile", None)
    center = employee.service_center if employee else None
    return {
        "id": user.id,
        "name": user.get_full_name() or user.username,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "service_center": {"id": center.id, "name": center.name} if center else None,
        "speciality": employee.speciality if employee else "",
        "is_available": employee.is_available if employee else True,
    }


def _all_staff():
    """Every driver and mechanic."""
    return User.objects.filter(role__in=[UserRole.DRIVER, UserRole.MECHANIC]).select_related("employee_profile__service_center")


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def staff_list_create(request):
    """
    Admin only.
    GET  /api/staff/  -> every driver and mechanic
    POST /api/staff/  {"name", "email", "phone"?, "password", "role": DRIVER|MECHANIC, "service_center", "speciality"?}
    Staff then sign in on their own tab with that email and password, and can change the password.
    """
    error = admin_required_error(request.user)
    if error:
        return error

    if request.method == "GET":
        return Response([_staff_row(u) for u in _all_staff().order_by("role", "first_name", "id")])

    serializer = StaffCreateSerializer(data=request.data)
    if not serializer.is_valid():
        errors = serializer.errors
        first = next(iter(errors.values()))[0] if errors else "Invalid details."
        return Response({"error": str(first), **errors}, status=status.HTTP_400_BAD_REQUEST)
    data = serializer.validated_data

    center = data.get("service_center")
    if not center:
        return Response({"error": "Choose the service center this person works at."}, status=status.HTTP_400_BAD_REQUEST)

    first_name, _, last_name = data["name"].strip().partition(" ")
    with transaction.atomic():
        user = User(
            email=data["email"],
            username=f"{data['email'].split('@')[0]}_{timezone.now().strftime('%M%S%f')[:8]}",
            phone=data.get("phone") or None,
            first_name=first_name,
            last_name=last_name,
            role=data["role"],
            is_verified=True,
        )
        user.set_password(data["password"])
        user.save()
        Employee.objects.create(
            user=user,
            service_center=center,
            employee_type=Employee.EmployeeType.VALET if data["role"] == UserRole.DRIVER else Employee.EmployeeType.MECHANIC,
            speciality=data.get("speciality", ""),
        )
    return Response(_staff_row(user), status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def staff_update(request, pk):
    """PATCH /api/staff/<id>/ {"is_available": false} -> off duty (auto-assignment skips them)"""
    error = admin_required_error(request.user)
    if error:
        return error
    member = _all_staff().filter(pk=pk).first()
    employee = getattr(member, "employee_profile", None) if member else None
    if not employee:
        return Response({"error": "Staff member not found."}, status=status.HTTP_404_NOT_FOUND)
    if "is_available" in request.data:
        employee.is_available = str(request.data["is_available"]).lower() in ("true", "1")
        employee.save(update_fields=["is_available"])
    return Response(_staff_row(member))


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

    # Validate access: vehicle owner, an admin, or a mechanic with an open job on this vehicle
    assigned_mechanic = (
        request.user.role == UserRole.MECHANIC
        and ServiceBooking.objects.filter(vehicle=vehicle, assigned_mechanic=request.user)
        .exclude(status__in=[BookingStatus.COMPLETED, BookingStatus.CANCELLED])
        .exists()
    )
    if vehicle.customer != request.user and not (assigned_mechanic or is_admin(request.user)):
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
    List invoices by role (a customer sees their own, an admin sees all).
    """
    if is_admin(request.user):
        qs = Invoice.objects.all()
    elif is_customer(request.user):
        qs = Invoice.objects.filter(customer=request.user)
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
    """The customer billed, or an admin."""
    return invoice.customer_id == user.id or is_admin(user)


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
def invoice_razorpay_order(request, pk):
    """POST /api/invoices/<id>/razorpay/order/ -> a Razorpay order for the invoice total, for Checkout."""
    if payment_gateway() != "razorpay":
        return Response({"error": "Razorpay payments are not enabled."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        return Response(razorpay_service.create_order(pk, request.user))
    except PaymentError as exc:
        return Response({"error": exc.message}, status=exc.status_code)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invoice_razorpay_verify(request, pk):
    """
    POST /api/invoices/<id>/razorpay/verify/
    Body: what Razorpay Checkout returned (razorpay_order_id, razorpay_payment_id, razorpay_signature).
    """
    if payment_gateway() != "razorpay":
        return Response({"error": "Razorpay payments are not enabled."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        payment = razorpay_service.confirm_checkout(pk, request.user, request.data)
    except PaymentError as exc:
        return Response({"error": exc.message}, status=exc.status_code)
    payment.invoice.refresh_from_db()
    body = {"payment": PaymentSerializer(payment).data, "invoice": InvoiceSerializer(payment.invoice).data}
    if payment.status != Payment.Status.SUCCESS or payment.invoice.payment_status != Invoice.PaymentStatus.PAID:
        message = payment.failure_reason or "Payment failed."
        if payment.status == Payment.Status.SUCCESS:
            message = "Your payment was received but needs a manual check. The service center will contact you."
        return Response({"error": message, **body}, status=status.HTTP_402_PAYMENT_REQUIRED)
    return Response(body)


@api_view(["POST"])
@permission_classes([AllowAny])
@authentication_classes([])
def razorpay_webhook(request):
    """POST /api/payments/razorpay/webhook/ -> called by Razorpay's servers; trusted only by its signature."""
    try:
        result = razorpay_service.handle_webhook(request.body, request.headers.get("X-Razorpay-Signature", ""))
    except PaymentError as exc:
        return Response({"error": exc.message}, status=exc.status_code)
    return Response({"status": result})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def push_subscription(request):
    """
    POST   /api/push/subscription/  {"endpoint", "keys": {"p256dh", "auth"}}  (a browser PushSubscription)
    DELETE /api/push/subscription/  {"endpoint"}
    """
    endpoint = str(request.data.get("endpoint") or "").strip()
    if request.method == "DELETE":
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response({"subscribed": False})

    if not push_enabled():
        return Response({"error": "Browser alerts are not set up on this server."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    keys = request.data.get("keys") if isinstance(request.data.get("keys"), dict) else {}
    p256dh, auth = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
    if not endpoint.startswith("https://") or len(endpoint) > 1000 or not p256dh or not auth or len(p256dh) > 200 or len(auth) > 100:
        return Response({"error": "Invalid push subscription."}, status=status.HTTP_400_BAD_REQUEST)
    # A browser has one subscription; if someone else signed in on it before, it becomes this user's
    PushSubscription.objects.update_or_create(
        endpoint=endpoint, defaults={"user": request.user, "p256dh": p256dh, "auth": auth}
    )
    return Response({"subscribed": True}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def booking_generate_invoice(request, pk):
    """
    POST /api/bookings/<id>/generate-invoice/
    Generates or recalculates the itemized invoice for a completed booking.
    Only admins may do this.
    """
    if str(pk).isdigit():
        booking = ServiceBooking.objects.filter(pk=pk).first()
    else:
        booking = ServiceBooking.objects.filter(Q(booking_reference=pk) | Q(booking_id=pk)).first()

    if not booking:
        return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

    if admin_required_error(request.user):
        return Response(
            {"error": "Only an admin can generate an invoice."},
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
