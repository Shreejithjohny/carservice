from datetime import timedelta
from django.utils import timezone
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from api.models import (
    UserRole,
    CarBrand,
    CarModel,
    CarVariant,
    Vehicle,
    ServiceType,
    ServiceCenter,
    ServiceBooking,
    BookingStatus,
    Invoice,
    Payment,
    Notification,
)

User = get_user_model()

# Bookings can only be made for upcoming dates, so API payloads use a date a few days out.
FUTURE_DATE = (timezone.localdate() + timedelta(days=3)).isoformat()


class Phase4ServiceBookingTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.user1 = User.objects.create_user(
            username="cust1",
            email="cust1@example.com",
            phone="+919876543210",
            role=UserRole.CUSTOMER,
        )
        self.user2 = User.objects.create_user(
            username="cust2",
            email="cust2@example.com",
            phone="+919876543211",
            role=UserRole.CUSTOMER,
        )

        # Vehicle Catalog
        self.brand = CarBrand.objects.create(name="Hyundai")
        self.model = CarModel.objects.create(brand=self.brand, name="i20")
        self.variant = CarVariant.objects.create(model=self.model, name="Asta")

        # Vehicles
        self.vehicle1 = Vehicle.objects.create(
            customer=self.user1,
            car_brand=self.brand,
            car_model=self.model,
            car_variant=self.variant,
            brand="Hyundai",
            model="i20",
            registration_number="KA01AB1234",
            year=2022,
        )
        self.vehicle2 = Vehicle.objects.create(
            customer=self.user2,
            car_brand=self.brand,
            car_model=self.model,
            car_variant=self.variant,
            brand="Hyundai",
            model="i20",
            registration_number="KA01CD5678",
            year=2023,
        )

        # Service Types & Centers
        self.service_type = ServiceType.objects.create(
            name="General Service",
            description="Full oil, fluid and brake checkup",
            base_price=2499.00,
            estimated_duration="3 hours",
        )
        self.service_center = ServiceCenter.objects.create(
            name="Doorstep Motors Indiranagar",
            address="100ft Road, Indiranagar, Bengaluru",
            phone="+918025000000",
            email="indiranagar@doorstepmotors.com",
        )

    def test_list_service_types_and_centers(self):
        # Service Types
        res_types = self.client.get("/api/service-types/")
        self.assertEqual(res_types.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res_types.data), 1)

        # Service Centers
        res_centers = self.client.get("/api/service-centers/")
        self.assertEqual(res_centers.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res_centers.data), 1)

    def test_create_booking_unauthenticated(self):
        payload = {
            "vehicle": self.vehicle1.id,
            "service_type": self.service_type.id,
            "service_center": self.service_center.id,
            "pickup_address": "123 Street",
            "preferred_date": FUTURE_DATE,
            "preferred_time": "09:00:00",
        }
        res = self.client.post("/api/bookings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_booking_success(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "vehicle": self.vehicle1.id,
            "service_type": self.service_type.id,
            "service_center": self.service_center.id,
            "pickup_address": "456 MG Road, Indiranagar, Bengaluru",
            "preferred_date": FUTURE_DATE,
            "preferred_time": "09:00:00",
            "customer_notes": "Please check brake squeal.",
        }
        res = self.client.post("/api/bookings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("booking_reference", res.data)
        self.assertTrue(res.data["booking_reference"].startswith("SDV-"))
        self.assertEqual(res.data["status"], BookingStatus.PENDING)
        self.assertEqual(float(res.data["estimated_cost"]), 2499.00)

    def test_create_booking_other_user_vehicle_fails(self):
        # User 1 tries to book with User 2's vehicle
        self.client.force_authenticate(user=self.user1)
        payload = {
            "vehicle": self.vehicle2.id,
            "service_type": self.service_type.id,
            "service_center": self.service_center.id,
            "pickup_address": "789 Brigade Road",
            "preferred_date": FUTURE_DATE,
            "preferred_time": "11:00:00",
        }
        res = self.client.post("/api/bookings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_booking_isolation(self):
        b1 = ServiceBooking.objects.create(
            customer=self.user1,
            vehicle=self.vehicle1,
            service_type=self.service_type,
            service_center=self.service_center,
            pickup_address="Address 1",
            preferred_date="2026-10-01",
            preferred_time="10:00:00",
            estimated_cost=2499,
        )
        b2 = ServiceBooking.objects.create(
            customer=self.user2,
            vehicle=self.vehicle2,
            service_type=self.service_type,
            service_center=self.service_center,
            pickup_address="Address 2",
            preferred_date="2026-10-01",
            preferred_time="11:00:00",
            estimated_cost=2499,
        )

        # Authenticate as User 1
        self.client.force_authenticate(user=self.user1)
        res = self.client.get("/api/bookings/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        booking_ids = [item["id"] for item in res.data]
        self.assertIn(b1.id, booking_ids)
        self.assertNotIn(b2.id, booking_ids)

        # Access detail of User 2's booking should be HTTP 403
        res_detail = self.client.get(f"/api/bookings/{b2.id}/")
        self.assertEqual(res_detail.status_code, status.HTTP_403_FORBIDDEN)

    def test_booking_cancellation_rules(self):
        b1 = ServiceBooking.objects.create(
            customer=self.user1,
            vehicle=self.vehicle1,
            service_type=self.service_type,
            service_center=self.service_center,
            pickup_address="Address 1",
            preferred_date="2026-10-01",
            preferred_time="10:00:00",
            estimated_cost=2499,
            status=BookingStatus.PENDING,
        )

        self.client.force_authenticate(user=self.user1)

        # Cancel PENDING booking -> allowed
        res = self.client.patch(f"/api/bookings/{b1.id}/", {"status": BookingStatus.CANCELLED}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], BookingStatus.CANCELLED)

        # Update to IN_SERVICE and attempt cancel -> blocked
        b1.status = BookingStatus.IN_SERVICE
        b1.save()

        res_blocked = self.client.patch(f"/api/bookings/{b1.id}/", {"status": BookingStatus.CANCELLED}, format="json")
        self.assertEqual(res_blocked.status_code, status.HTTP_400_BAD_REQUEST)

    # ==========================================
    # PHASE 5 GOOGLE MAPS & LOCATION TESTS
    # ==========================================

    def test_create_booking_with_valid_coordinates(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "vehicle": self.vehicle1.id,
            "service_type": self.service_type.id,
            "service_center": self.service_center.id,
            "pickup_address": "100 Feet Road, Indiranagar, Bengaluru",
            "pickup_latitude": 12.9784,
            "pickup_longitude": 77.6408,
            "preferred_date": FUTURE_DATE,
            "preferred_time": "09:00:00",
        }
        res = self.client.post("/api/bookings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(res.data["pickup_latitude"]), 12.9784)
        self.assertEqual(float(res.data["pickup_longitude"]), 77.6408)

    def test_create_booking_without_coordinates_backward_compatible(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "vehicle": self.vehicle1.id,
            "service_type": self.service_type.id,
            "service_center": self.service_center.id,
            "pickup_address": "Text address only without map coordinates",
            "preferred_date": FUTURE_DATE,
            "preferred_time": "11:00:00",
        }
        res = self.client.post("/api/bookings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(res.data.get("pickup_latitude"))
        self.assertIsNone(res.data.get("pickup_longitude"))

    def test_create_booking_invalid_latitude_fails(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "vehicle": self.vehicle1.id,
            "service_type": self.service_type.id,
            "service_center": self.service_center.id,
            "pickup_address": "Invalid latitude test",
            "pickup_latitude": 120.0,  # Invalid: > 90
            "pickup_longitude": 77.6408,
            "preferred_date": FUTURE_DATE,
            "preferred_time": "09:00:00",
        }
        res = self.client.post("/api/bookings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pickup_latitude", res.data)

    def test_create_booking_invalid_longitude_fails(self):
        self.client.force_authenticate(user=self.user1)
        payload = {
            "vehicle": self.vehicle1.id,
            "service_type": self.service_type.id,
            "service_center": self.service_center.id,
            "pickup_address": "Invalid longitude test",
            "pickup_latitude": 12.9784,
            "pickup_longitude": -200.0,  # Invalid: < -180
            "preferred_date": FUTURE_DATE,
            "preferred_time": "09:00:00",
        }
        res = self.client.post("/api/bookings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pickup_longitude", res.data)

    def test_calculate_distance_api(self):
        url = "/api/location/distance/?origin_lat=12.9784&origin_lng=77.6408&dest_lat=12.9352&dest_lng=77.6245"
        # Requires login, since it can call the paid Google Distance Matrix API
        self.assertEqual(self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.force_authenticate(user=self.user1)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("distance_km", res.data)
        self.assertIn("duration_minutes", res.data)
        self.assertGreater(float(res.data["distance_km"]), 0)

    # ==========================================
    # COMBINED PHASE 6–8 TESTS
    # ==========================================

    def test_admin_confirms_and_assigns_and_nobody_else_can(self):
        ops_admin = User.objects.create_user(username="adm1", email="adm1@example.com", role=UserRole.ADMIN)
        driver = User.objects.create_user(username="drv1", email="drv1@example.com", role=UserRole.DRIVER)
        mechanic = User.objects.create_user(username="mech1", email="mech1@example.com", role=UserRole.MECHANIC)

        booking = ServiceBooking.objects.create(
            customer=self.user1,
            vehicle=self.vehicle1,
            service_type=self.service_type,
            service_center=self.service_center,
            pickup_address="Admin test address",
            preferred_date="2026-10-10",
        )

        # Only an admin runs the service centers: customers, drivers and mechanics are refused
        for outsider in (self.user1, driver, mechanic):
            self.client.force_authenticate(user=outsider)
            refused = self.client.patch(f"/api/service-center/bookings/{booking.id}/", {"status": "Confirmed"}, format="json")
            self.assertEqual(refused.status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(self.client.get("/api/service-center/bookings/").status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=ops_admin)
        res = self.client.patch(
            f"/api/service-center/bookings/{booking.id}/",
            {"status": "Confirmed", "assigned_driver_id": driver.id, "assigned_mechanic_id": mechanic.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "Confirmed")
        self.assertEqual(res.data["assigned_driver"], driver.id)
        self.assertEqual(res.data["assigned_mechanic"], mechanic.id)

    def test_driver_workflow_and_handover_otp(self):
        driver = User.objects.create_user(username="drv2", email="drv2@example.com", role=UserRole.DRIVER)
        booking = ServiceBooking.objects.create(
            customer=self.user1,
            vehicle=self.vehicle1,
            service_type=self.service_type,
            service_center=self.service_center,
            assigned_driver=driver,
            pickup_address="Driver workflow test address",
            preferred_date="2026-10-10",
            status="Pickup Scheduled",
        )

        self.client.force_authenticate(user=driver)

        res_status = self.client.post(f"/api/driver/pickups/{booking.id}/status/", {"status": "En Route for Pickup"}, format="json")
        self.assertEqual(res_status.status_code, status.HTTP_200_OK)

        res_otp_req = self.client.post(f"/api/driver/pickups/{booking.id}/handover-otp/request/")
        self.assertEqual(res_otp_req.status_code, status.HTTP_200_OK)

        booking.refresh_from_db()
        otp = booking.handover_otp
        self.assertTrue(len(otp) == 6)

        res_wrong_otp = self.client.post(f"/api/driver/pickups/{booking.id}/handover-otp/verify/", {"otp_code": "000000"}, format="json")
        self.assertEqual(res_wrong_otp.status_code, status.HTTP_400_BAD_REQUEST)

        res_verify_otp = self.client.post(f"/api/driver/pickups/{booking.id}/handover-otp/verify/", {"otp_code": otp}, format="json")
        self.assertEqual(res_verify_otp.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertTrue(booking.handover_otp_verified)
        self.assertEqual(booking.status, BookingStatus.VEHICLE_PICKED_UP)

    def test_driver_location_tracking(self):
        driver = User.objects.create_user(username="drv3", email="drv3@example.com", role=UserRole.DRIVER)
        other_driver = User.objects.create_user(username="drv4", email="drv4@example.com", role=UserRole.DRIVER)
        booking = ServiceBooking.objects.create(
            customer=self.user1,
            vehicle=self.vehicle1,
            service_type=self.service_type,
            service_center=self.service_center,
            assigned_driver=driver,
            pickup_address="GPS test address",
            status=BookingStatus.PICKUP_SCHEDULED,
        )

        self.client.force_authenticate(user=driver)
        res_gps = self.client.post(f"/api/driver/pickups/{booking.id}/location/", {"latitude": 12.9784, "longitude": 77.6408}, format="json")
        self.assertEqual(res_gps.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=other_driver)
        res_gps_other = self.client.post(f"/api/driver/pickups/{booking.id}/location/", {"latitude": 12.9784, "longitude": 77.6408}, format="json")
        self.assertEqual(res_gps_other.status_code, status.HTTP_403_FORBIDDEN)

    def test_mechanic_inspection_evidence_repair_request_and_customer_response(self):
        mechanic = User.objects.create_user(username="mech2", email="mech2@example.com", role=UserRole.MECHANIC)
        booking = ServiceBooking.objects.create(
            customer=self.user1,
            vehicle=self.vehicle1,
            service_type=self.service_type,
            service_center=self.service_center,
            assigned_mechanic=mechanic,
            pickup_address="Mechanic test address",
            status="In Service",
        )

        self.client.force_authenticate(user=mechanic)

        res_insp = self.client.post(
            "/api/inspections/",
            {
                "booking": booking.id,
                "inspection_notes": "Front brake pads worn out down to 2mm.",
                "issue_description": "Thin brake pads causing metal squeal.",
                "severity": "HIGH",
                "estimated_additional_cost": 1500,
            },
            format="json",
        )
        self.assertEqual(res_insp.status_code, status.HTTP_201_CREATED)

        res_ev = self.client.post(
            "/api/repair-evidence/",
            {
                "booking": booking.id,
                "issue_title": "Brake Pad Wear",
                "description": "Photo of worn pad",
                "media_type": "PHOTO",
                "file_url": "https://example.com/evidence1.jpg",
            },
            format="json",
        )
        self.assertEqual(res_ev.status_code, status.HTTP_201_CREATED)

        res_rr = self.client.post(
            "/api/repair-requests/",
            {
                "booking": booking.id,
                "issue_title": "Brake Pad Replacement",
                "description": "Replace front brake pads and bleed lines",
                "additional_cost": 1500,
            },
            format="json",
        )
        self.assertEqual(res_rr.status_code, status.HTTP_201_CREATED)
        rr_id = res_rr.data["id"]

        booking.refresh_from_db()
        self.assertEqual(booking.status, "Repair Approval Required")

        self.client.force_authenticate(user=self.user2)
        res_unauth = self.client.post(f"/api/repair-requests/{rr_id}/approve/")
        self.assertEqual(res_unauth.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.user1)
        res_app = self.client.post(f"/api/repair-requests/{rr_id}/approve/")
        self.assertEqual(res_app.status_code, status.HTTP_200_OK)
        self.assertEqual(res_app.data["repair_request"]["status"], "APPROVED")

        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.IN_SERVICE)
        self.assertEqual(float(booking.estimated_cost), 2499.00 + 1500.00)


class Phase9To11CompleteOperationsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.customer1 = User.objects.create_user(
            username="p9_cust1",
            email="p9_cust1@example.com",
            phone="+919100000001",
            role=UserRole.CUSTOMER,
        )
        self.customer2 = User.objects.create_user(
            username="p9_cust2",
            email="p9_cust2@example.com",
            phone="+919100000002",
            role=UserRole.CUSTOMER,
        )
        self.driver = User.objects.create_user(
            username="p9_driver",
            email="p9_driver@example.com",
            phone="+919100000003",
            role=UserRole.DRIVER,
        )
        self.mechanic = User.objects.create_user(
            username="p9_mech",
            email="p9_mech@example.com",
            phone="+919100000004",
            role=UserRole.MECHANIC,
        )
        self.ops_admin = User.objects.create_user(
            username="p9_ops",
            email="p9_ops@example.com",
            phone="+919100000005",
            role=UserRole.ADMIN,
        )
        self.admin = User.objects.create_superuser(
            username="p9_admin",
            email="p9_admin@example.com",
            password="adminpassword",
            role=UserRole.ADMIN,
        )

        self.brand = CarBrand.objects.create(name="Tata")
        self.model = CarModel.objects.create(brand=self.brand, name="Nexon")
        self.variant = CarVariant.objects.create(model=self.model, name="XZ+", fuel_type="Electric")

        self.vehicle1 = Vehicle.objects.create(
            customer=self.customer1,
            car_brand=self.brand,
            car_model=self.model,
            car_variant=self.variant,
            brand="Tata",
            model="Nexon",
            registration_number="KA05EV9999",
            year=2023,
            fuel_type="Electric",
        )

        self.service_type = ServiceType.objects.create(
            name="Periodic Maintenance",
            base_price=3000.00,
            estimated_duration="4 hours",
        )
        self.service_center = ServiceCenter.objects.create(
            user=self.ops_admin,
            name="Tata Authorized Service Hub",
            address="Whitefield, Bengaluru",
            phone="+918045000000",
            email="hub@tataservice.com",
        )

    def test_ai_cost_estimator_and_permissions(self):
        self.client.force_authenticate(user=self.customer1)
        res = self.client.post(
            "/api/repair-cost/estimate/",
            {
                "vehicle": self.vehicle1.id,
                "service_type": self.service_type.id,
                "issue_description": "Battery management system warning light on dashboard",
                "severity": "HIGH",
                "estimated_labor_hours": 2.5,
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("estimated_min_cost", res.data)
        self.assertIn("estimated_max_cost", res.data)
        self.assertIn("explanation", res.data)
        self.assertGreater(float(res.data["estimated_max_cost"]), float(res.data["estimated_min_cost"]))

        # Customer 2 cannot estimate for Customer 1's vehicle
        self.client.force_authenticate(user=self.customer2)
        res_unauth = self.client.post(
            "/api/repair-cost/estimate/",
            {
                "vehicle": self.vehicle1.id,
                "issue_description": "Test issue",
                "severity": "LOW",
            },
            format="json",
        )
        self.assertEqual(res_unauth.status_code, status.HTTP_403_FORBIDDEN)

        # Invalid vehicle returns 404
        self.client.force_authenticate(user=self.customer1)
        res_404 = self.client.post(
            "/api/repair-cost/estimate/",
            {"vehicle": 99999, "issue_description": "Non-existent vehicle"},
            format="json",
        )
        self.assertEqual(res_404.status_code, status.HTTP_404_NOT_FOUND)

    def test_invoice_generation_calculations_and_isolation(self):
        booking = ServiceBooking.objects.create(
            customer=self.customer1,
            vehicle=self.vehicle1,
            service_type=self.service_type,
            service_center=self.service_center,
            pickup_address="Whitefield Villa 12",
            status=BookingStatus.IN_SERVICE,
        )

        from api.models import RepairRequest, RepairRequestStatus
        RepairRequest.objects.create(
            booking=booking,
            mechanic=self.mechanic,
            issue_title="Coolant Hose Replacement",
            description="Leaking coolant line",
            additional_cost=2000.00,
            estimated_extra_hours=1,
            status=RepairRequestStatus.APPROVED,
        )

        # Not invoiceable before the service is completed
        self.client.force_authenticate(user=self.ops_admin)
        res_early = self.client.post(f"/api/bookings/{booking.id}/generate-invoice/")
        self.assertEqual(res_early.status_code, status.HTTP_400_BAD_REQUEST)

        booking.status = BookingStatus.COMPLETED
        booking.save()

        # Customers, mechanics and drivers cannot generate invoices
        for outsider in (self.customer1, self.mechanic, self.driver):
            self.client.force_authenticate(user=outsider)
            res_forbidden = self.client.post(f"/api/bookings/{booking.id}/generate-invoice/")
            self.assertEqual(res_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.ops_admin)
        res_inv = self.client.post(f"/api/bookings/{booking.id}/generate-invoice/")
        self.assertEqual(res_inv.status_code, status.HTTP_200_OK)
        inv_data = res_inv.data

        self.assertTrue(inv_data["invoice_number"].startswith("SDV-INV-"))
        # Subtotal (3000) + Approved Repair (2000) + Labor (1 hr * 400 = 400) = 5400
        # GST (18% of 5400 = 972) -> Grand Total = 6372
        self.assertEqual(float(inv_data["subtotal"]), 3000.00)
        self.assertEqual(float(inv_data["additional_repairs_total"]), 2000.00)
        self.assertEqual(float(inv_data["labor_total"]), 400.00)
        self.assertEqual(float(inv_data["tax"]), 972.00)
        self.assertEqual(float(inv_data["grand_total"]), 6372.00)

        # Customer 1 can list and view their invoice
        self.client.force_authenticate(user=self.customer1)
        res_list = self.client.get("/api/invoices/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)

        # Customer 2 gets empty list (isolated)
        self.client.force_authenticate(user=self.customer2)
        res_list2 = self.client.get("/api/invoices/")
        self.assertEqual(len(res_list2.data), 0)

        # Customer 2 cannot access Customer 1's invoice detail
        res_detail_unauth = self.client.get(f"/api/invoices/{inv_data['id']}/")
        self.assertEqual(res_detail_unauth.status_code, status.HTTP_403_FORBIDDEN)

        # The admin sees the invoices
        self.client.force_authenticate(user=self.ops_admin)
        res_mgr_list = self.client.get("/api/invoices/")
        self.assertEqual(res_mgr_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_mgr_list.data), 1)

        # Drivers can neither list nor open customer invoices
        self.client.force_authenticate(user=self.driver)
        self.assertEqual(self.client.get("/api/invoices/").status_code, status.HTTP_403_FORBIDDEN)
        res_drv_detail = self.client.get(f"/api/invoices/{inv_data['id']}/")
        self.assertEqual(res_drv_detail.status_code, status.HTTP_403_FORBIDDEN)

    def test_car_health_score_calculation(self):
        self.client.force_authenticate(user=self.customer1)
        res = self.client.get(f"/api/vehicles/{self.vehicle1.id}/health-score/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        score = res.data["score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertIn("maintenance_compliance", res.data)
        self.assertIn("explanation", res.data)

    def test_notifications_lifecycle_and_mark_read(self):
        from api.notification_service import send_notification
        from api.models import NotificationType

        send_notification(
            user=self.customer1,
            notification_type=NotificationType.BOOKING_CREATED,
            title="Test Alert",
            message="Test message body",
        )

        self.client.force_authenticate(user=self.customer1)
        res = self.client.get("/api/notifications/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        notif_id = res.data[0]["id"]
        self.assertFalse(res.data[0]["is_read"])

        # Customer 2 has zero notifications (isolated)
        self.client.force_authenticate(user=self.customer2)
        res2 = self.client.get("/api/notifications/")
        self.assertEqual(len(res2.data), 0)

        # Mark single notification read
        self.client.force_authenticate(user=self.customer1)
        res_read = self.client.patch(f"/api/notifications/{notif_id}/read/")
        self.assertEqual(res_read.status_code, status.HTTP_200_OK)
        self.assertTrue(res_read.data["notification"]["is_read"])

        # Mark all read
        res_all = self.client.post("/api/notifications/mark-all-read/")
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)

    def test_full_service_operations_end_to_end_workflow(self):
        # 1. Customer creates booking
        self.client.force_authenticate(user=self.customer1)
        res_b = self.client.post(
            "/api/bookings/",
            {
                "vehicle": self.vehicle1.id,
                "service_type": self.service_type.id,
                "service_center": self.service_center.id,
                "pickup_address": "Indiranagar 100ft Rd",
                "preferred_date": FUTURE_DATE,
                "preferred_time": "09:00:00",
            },
            format="json",
        )
        self.assertEqual(res_b.status_code, status.HTTP_201_CREATED)
        booking_id = res_b.data["id"]

        # 2. Admin confirms booking & assigns driver + mechanic
        self.client.force_authenticate(user=self.ops_admin)
        res_up = self.client.patch(
            f"/api/service-center/bookings/{booking_id}/",
            {
                "status": BookingStatus.CONFIRMED,
                "assigned_driver_id": self.driver.id,
                "assigned_mechanic_id": self.mechanic.id,
            },
            format="json",
        )
        self.assertEqual(res_up.status_code, status.HTTP_200_OK)

        # 3. Driver requests handover OTP
        self.client.force_authenticate(user=self.driver)
        res_otp_req = self.client.post(f"/api/driver/pickups/{booking_id}/handover-otp/request/")
        self.assertEqual(res_otp_req.status_code, status.HTTP_200_OK)

        booking_obj = ServiceBooking.objects.get(id=booking_id)
        valid_otp = booking_obj.handover_otp

        # 4. Driver verifies customer OTP
        res_otp_ver = self.client.post(
            f"/api/driver/pickups/{booking_id}/handover-otp/verify/",
            {"otp_code": valid_otp},
            format="json",
        )
        self.assertEqual(res_otp_ver.status_code, status.HTTP_200_OK)
        booking_obj.refresh_from_db()
        self.assertEqual(booking_obj.status, BookingStatus.VEHICLE_PICKED_UP)

        # 5. Mechanic starts service
        self.client.force_authenticate(user=self.mechanic)
        res_mech_start = self.client.patch(
            f"/api/mechanic/jobs/{booking_id}/status/",
            {"status": BookingStatus.IN_SERVICE},
            format="json",
        )
        self.assertEqual(res_mech_start.status_code, status.HTTP_200_OK)

        # 6. Mechanic creates repair request
        res_rep = self.client.post(
            "/api/repair-requests/",
            {
                "booking": booking_id,
                "issue_title": "AC Compressor Belt Replacement",
                "description": "Belt frayed and slipping",
                "additional_cost": 1800.00,
                "estimated_extra_hours": 1,
            },
            format="json",
        )
        self.assertEqual(res_rep.status_code, status.HTTP_201_CREATED)
        rep_id = res_rep.data["id"]

        # 7. Customer approves repair
        self.client.force_authenticate(user=self.customer1)
        res_app = self.client.post(f"/api/repair-requests/{rep_id}/approve/")
        self.assertEqual(res_app.status_code, status.HTTP_200_OK)

        # 8. Admin marks Completed
        self.client.force_authenticate(user=self.ops_admin)
        res_comp = self.client.patch(
            f"/api/service-center/bookings/{booking_id}/",
            {"status": BookingStatus.COMPLETED},
            format="json",
        )
        self.assertEqual(res_comp.status_code, status.HTTP_200_OK)

        # Verify invoice auto-generated
        from api.models import Invoice
        inv = Invoice.objects.filter(booking_id=booking_id).first()
        self.assertIsNotNone(inv)
        self.assertGreater(float(inv.grand_total), 0)

        # 9. Admin checks dashboard analytics
        self.client.force_authenticate(user=self.admin)
        res_admin = self.client.get("/api/admin/dashboard-stats/")
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res_admin.data["completed_services"], 1)
        # The invoice is not paid yet, so it is outstanding rather than revenue
        self.assertEqual(res_admin.data["total_revenue"], 0)
        self.assertEqual(res_admin.data["outstanding_amount"], round(float(inv.grand_total), 2))


# ==========================================
# PHONE NUMBER NORMALIZATION
# ==========================================
from unittest.mock import patch
from api.otp_service import normalize_phone_number


class PhoneNumberNormalizationTests(TestCase):
    def test_phone_number_normalization(self):
        # 10-digit Indian number normalized to E.164
        self.assertEqual(normalize_phone_number("9876543210"), "+919876543210")
        # Existing E.164 not duplicated
        self.assertEqual(normalize_phone_number("+919876543210"), "+919876543210")
        # Spaces, hyphens, parentheses removed
        self.assertEqual(normalize_phone_number("+91 98765 43210"), "+919876543210")
        self.assertEqual(normalize_phone_number("+91-98765-43210"), "+919876543210")
        self.assertEqual(normalize_phone_number("(+91) 98765-43210"), "+919876543210")
        # Leading 0 stripped and converted to +91
        self.assertEqual(normalize_phone_number("09876543210"), "+919876543210")
        # 12 digits starting with 91
        self.assertEqual(normalize_phone_number("919876543210"), "+919876543210")
        # Accidental double prefix
        self.assertEqual(normalize_phone_number("+91+919876543210"), "+919876543210")
        # International numbers preserved
        self.assertEqual(normalize_phone_number("+14155552671"), "+14155552671")
        self.assertEqual(normalize_phone_number("+447911123456"), "+447911123456")


class AuthSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="sec_cust", email="sec_cust@example.com", role=UserRole.CUSTOMER
        )

    @override_settings(OTP_BYPASS=False)
    def test_demo_login_disabled_without_bypass(self):
        res = self.client.post(
            "/api/auth/bypass-login/", {"identifier": "attacker@example.com", "role": "ADMIN"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(email="attacker@example.com").exists())
        self.assertFalse(self.client.get("/api/health-check/").data["demo_login"])

    @override_settings(OTP_BYPASS=True)
    def test_demo_login_cannot_create_admin_or_change_roles(self):
        res_admin = self.client.post(
            "/api/auth/bypass-login/", {"identifier": "newadmin@example.com", "role": "ADMIN"}, format="json"
        )
        self.assertEqual(res_admin.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(email="newadmin@example.com").exists())

        # Existing account keeps its own role whatever role is requested
        res_existing = self.client.post(
            "/api/auth/bypass-login/", {"identifier": "sec_cust@example.com", "role": "ADMIN"}, format="json"
        )
        self.assertEqual(res_existing.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, UserRole.CUSTOMER)
        self.assertFalse(self.customer.is_staff)

        # New non-admin demo accounts are allowed
        res_driver = self.client.post(
            "/api/auth/bypass-login/", {"identifier": "newdriver@example.com", "role": "DRIVER"}, format="json"
        )
        self.assertEqual(res_driver.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.get(email="newdriver@example.com").role, UserRole.DRIVER)
        self.assertTrue(self.client.get("/api/health-check/").data["demo_login"])


class InvoicePaymentAndTrackingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username="pay_cust", email="pay_cust@example.com", role=UserRole.CUSTOMER)
        self.other = User.objects.create_user(username="pay_other", email="pay_other@example.com", role=UserRole.CUSTOMER)
        self.ops_admin = User.objects.create_user(
            username="pay_mgr", email="pay_mgr@example.com", role=UserRole.ADMIN
        )
        self.driver = User.objects.create_user(username="pay_drv", email="pay_drv@example.com", role=UserRole.DRIVER)
        brand = CarBrand.objects.create(name="Kia")
        model = CarModel.objects.create(brand=brand, name="Seltos")
        vehicle = Vehicle.objects.create(
            customer=self.customer, car_brand=brand, car_model=model, brand="Kia", model="Seltos",
            registration_number="KA01PAY1", year=2022, fuel_type="Petrol",
        )
        service_type = ServiceType.objects.create(name="General Service", base_price=2000, estimated_duration="3 hours")
        center = ServiceCenter.objects.create(
            user=self.ops_admin, name="Pay Hub", address="Indiranagar", phone="+918000000000", email="hub@example.com",
        )
        self.booking = ServiceBooking.objects.create(
            customer=self.customer, vehicle=vehicle, service_type=service_type, service_center=center,
            pickup_address="Koramangala", status=BookingStatus.COMPLETED, assigned_driver=self.driver,
        )
        self.invoice = Invoice.objects.create(booking=self.booking, subtotal=2000, tax=360, grand_total=2360)

    def pay(self, user, **body):
        self.client.force_authenticate(user=user)
        return self.client.post(f"/api/invoices/{self.invoice.id}/pay/", body, format="json")

    @override_settings(PAYMENT_GATEWAY="mock")
    def test_customer_pays_with_upi_once(self):
        res = self.pay(self.customer, method="UPI", upi_id="rahul@okhdfc")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["payment"]["status"], "SUCCESS")
        self.assertEqual(float(res.data["payment"]["amount"]), 2360.0)
        self.assertEqual(res.data["invoice"]["payment_status"], "PAID")
        self.assertEqual(len(res.data["invoice"]["payments"]), 1)
        self.assertTrue(Notification.objects.filter(user=self.ops_admin, title="Invoice paid").exists())

        again = self.pay(self.customer, method="UPI", upi_id="rahul@okhdfc")
        self.assertEqual(again.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Payment.objects.filter(invoice=self.invoice).count(), 1)

    @override_settings(PAYMENT_GATEWAY="mock")
    def test_card_payment_stores_only_last_four_digits(self):
        res = self.pay(self.customer, method="CARD", card_number="4111 1111 1111 1111", card_expiry="12/39")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        payment = Payment.objects.get(invoice=self.invoice)
        self.assertEqual(payment.payer_reference, "Card ending 1111")
        self.assertNotIn("41111111", str(res.data))

    @override_settings(PAYMENT_GATEWAY="mock")
    def test_declined_payment_can_be_retried(self):
        res = self.pay(self.customer, method="UPI", upi_id="failure@mock")
        self.assertEqual(res.status_code, status.HTTP_402_PAYMENT_REQUIRED)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_status, "FAILED")

        retry = self.pay(self.customer, method="UPI", upi_id="rahul@okhdfc")
        self.assertEqual(retry.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.filter(invoice=self.invoice).count(), 2)

    @override_settings(PAYMENT_GATEWAY="mock")
    def test_invalid_details_and_wrong_payer_are_rejected(self):
        self.assertEqual(self.pay(self.customer, method="UPI", upi_id="not-an-upi").status_code, 400)
        self.assertEqual(
            self.pay(self.customer, method="CARD", card_number="4111111111111112", card_expiry="12/39").status_code, 400
        )
        self.assertEqual(
            self.pay(self.customer, method="CARD", card_number="4111111111111111", card_expiry="01/20").status_code, 400
        )
        self.assertEqual(self.pay(self.other, method="UPI", upi_id="x@okaxis").status_code, 403)
        self.assertEqual(self.pay(self.ops_admin, method="UPI", upi_id="x@okaxis").status_code, 403)
        self.assertFalse(Payment.objects.exists())

    @override_settings(PAYMENT_GATEWAY="")
    def test_payment_disabled_without_gateway(self):
        res = self.pay(self.customer, method="UPI", upi_id="rahul@okhdfc")
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIsNone(self.client.get("/api/health-check/").data["payment_gateway"])

    def test_tracking_returns_driver_route_oldest_first(self):
        self.booking.status = BookingStatus.PICKUP_SCHEDULED
        self.booking.save()
        self.client.force_authenticate(user=self.driver)
        for lat in (12.90, 12.91, 12.92):
            res = self.client.post(
                f"/api/driver/pickups/{self.booking.id}/location/", {"latitude": lat, "longitude": 77.6}, format="json"
            )
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        bad = self.client.post(
            f"/api/driver/pickups/{self.booking.id}/location/", {"latitude": 500, "longitude": 77.6}, format="json"
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

        self.client.force_authenticate(user=self.customer)
        data = self.client.get(f"/api/bookings/{self.booking.id}/tracking/").data
        self.assertEqual([p["latitude"] for p in data["driver_route"]], [12.90, 12.91, 12.92])
        self.assertEqual(data["latest_driver_location"]["latitude"], 12.92)

    @override_settings(PAYMENT_GATEWAY="mock")
    def test_invoice_generation_rules(self):
        self.invoice.delete()
        url = f"/api/bookings/{self.booking.id}/generate-invoice/"

        # Only an admin can generate it: not the customer, and not an account of the retired manager role
        retired = User.objects.create_user(
            username="other_mgr", email="other_mgr@example.com", role=UserRole.SERVICE_CENTER_MANAGER
        )
        for outsider in (self.customer, retired):
            self.client.force_authenticate(user=outsider)
            self.assertEqual(self.client.post(url).status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.ops_admin)
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        invoice_id = res.data["id"]

        # Once paid, it can no longer be recalculated (by the endpoint or by re-completing the booking)
        self.client.force_authenticate(user=self.customer)
        self.client.post(f"/api/invoices/{invoice_id}/pay/", {"method": "UPI", "upi_id": "rahul@okhdfc"}, format="json")
        paid_total = Invoice.objects.get(pk=invoice_id).grand_total
        self.client.force_authenticate(user=self.ops_admin)
        self.assertEqual(self.client.post(url).status_code, status.HTTP_409_CONFLICT)
        res_complete = self.client.patch(
            f"/api/service-center/bookings/{self.booking.id}/", {"status": "Completed"}, format="json"
        )
        self.assertEqual(res_complete.status_code, status.HTTP_200_OK)
        self.assertEqual(Invoice.objects.get(pk=invoice_id).grand_total, paid_total)

    def test_completing_booking_creates_invoice_automatically(self):
        self.invoice.delete()
        self.booking.status = BookingStatus.IN_SERVICE
        self.booking.save()
        self.client.force_authenticate(user=self.ops_admin)
        res = self.client.patch(f"/api/service-center/bookings/{self.booking.id}/", {"status": "Completed"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(Invoice.objects.filter(booking=self.booking).exists())



class RepairEvidenceUploadTests(TestCase):
    def setUp(self):
        import tempfile

        self.media_dir = tempfile.mkdtemp()
        self.client = APIClient()
        customer = User.objects.create_user(username="ev_cust", email="ev_cust@example.com", role=UserRole.CUSTOMER)
        self.mechanic = User.objects.create_user(username="ev_mech", email="ev_mech@example.com", role=UserRole.MECHANIC)
        brand = CarBrand.objects.create(name="Skoda")
        model = CarModel.objects.create(brand=brand, name="Slavia")
        vehicle = Vehicle.objects.create(
            customer=customer, car_brand=brand, car_model=model, brand="Skoda", model="Slavia",
            registration_number="KA01EV01", year=2023, fuel_type="Petrol",
        )
        service_type = ServiceType.objects.create(name="Brake Check", base_price=999, estimated_duration="1 hour")
        center = ServiceCenter.objects.create(name="Ev Hub", address="HSR", phone="+918000000002", email="ev@example.com")
        self.booking = ServiceBooking.objects.create(
            customer=customer, vehicle=vehicle, service_type=service_type, service_center=center,
            pickup_address="HSR Layout", status=BookingStatus.IN_SERVICE, assigned_mechanic=self.mechanic,
        )
        self.client.force_authenticate(user=self.mechanic)

    def upload(self, name, content, content_type):
        from django.core.files.uploadedfile import SimpleUploadedFile

        with self.settings(MEDIA_ROOT=self.media_dir):
            return self.client.post(
                "/api/repair-evidence/",
                {"booking": self.booking.id, "issue_title": "Worn pads", "file": SimpleUploadedFile(name, content, content_type)},
                format="multipart",
            )

    def test_real_photo_is_saved_under_a_safe_name(self):
        from io import BytesIO
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (8, 8), "red").save(buf, format="JPEG")
        res = self.upload("brake.html", buf.getvalue(), "image/jpeg")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data["media_type"], "PHOTO")
        self.assertTrue(res.data["file"].endswith(".jpg"))
        self.assertNotIn("brake", res.data["file"])

    def test_disguised_or_missing_files_are_rejected(self):
        fake = self.upload("photo.jpg", b"<html><script>alert(1)</script></html>", "image/jpeg")
        self.assertEqual(fake.status_code, status.HTTP_400_BAD_REQUEST)
        wrong_type = self.upload("notes.txt", b"hello", "text/plain")
        self.assertEqual(wrong_type.status_code, status.HTTP_400_BAD_REQUEST)
        missing = self.client.post(
            "/api/repair-evidence/", {"booking": self.booking.id, "issue_title": "No media"}, format="json"
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_revenue_counts_only_paid_invoices(self):
        self.booking.status = BookingStatus.COMPLETED
        self.booking.save()
        invoice = Invoice.objects.create(booking=self.booking, subtotal=999, tax=179.82, grand_total=1178.82)
        admin = User.objects.create_superuser(username="ev_admin", email="ev_admin@example.com", password="x", role=UserRole.ADMIN)
        self.client.force_authenticate(user=admin)
        stats = self.client.get("/api/admin/dashboard-stats/").data
        self.assertEqual(stats["total_revenue"], 0)
        self.assertEqual(stats["outstanding_amount"], 1178.82)
        invoice.payment_status = Invoice.PaymentStatus.PAID
        invoice.save()
        stats = self.client.get("/api/admin/dashboard-stats/").data
        self.assertEqual(stats["total_revenue"], 1178.82)
        self.assertEqual(stats["outstanding_amount"], 0)


class MechanicScopeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        customer = User.objects.create_user(username="ms_cust", email="ms_cust@example.com", role=UserRole.CUSTOMER)
        self.mech = User.objects.create_user(username="ms_mech", email="ms_mech@example.com", role=UserRole.MECHANIC)
        self.other = User.objects.create_user(username="ms_other", email="ms_other@example.com", role=UserRole.MECHANIC)
        brand = CarBrand.objects.create(name="Renault")
        model = CarModel.objects.create(brand=brand, name="Kiger")
        self.vehicle = Vehicle.objects.create(
            customer=customer, car_brand=brand, car_model=model, brand="Renault", model="Kiger",
            registration_number="KA01MS01", year=2022, fuel_type="Petrol",
        )
        st = ServiceType.objects.create(name="Clutch Check", base_price=1200, estimated_duration="2 hours")
        center = ServiceCenter.objects.create(name="MS Hub", address="JP Nagar", phone="+918000000003", email="ms@example.com")
        common = dict(customer=customer, vehicle=self.vehicle, service_type=st, service_center=center, pickup_address="JP Nagar")
        self.job = ServiceBooking.objects.create(status=BookingStatus.IN_SERVICE, assigned_mechanic=self.mech, **common)
        self.unassigned = ServiceBooking.objects.create(status=BookingStatus.IN_SERVICE, **common)

    def post_as(self, user, url, body):
        self.client.force_authenticate(user=user)
        return self.client.post(url, body, format="json")

    def test_job_list_shows_only_assigned_jobs(self):
        self.client.force_authenticate(user=self.mech)
        self.assertEqual([j["id"] for j in self.client.get("/api/mechanic/jobs/").data], [self.job.id])
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get("/api/mechanic/jobs/").data, [])

    def test_other_mechanic_cannot_touch_the_job(self):
        bid = self.job.id
        self.assertEqual(self.post_as(self.other, "/api/inspections/", {"booking": bid, "issue_description": "x", "severity": "LOW"}).status_code, 403)
        self.assertEqual(self.post_as(self.other, "/api/repair-evidence/", {"booking": bid, "issue_title": "x", "file_url": "https://e.com/a.jpg"}).status_code, 403)
        self.assertEqual(self.post_as(self.other, "/api/repair-requests/", {"booking": bid, "issue_title": "x", "additional_cost": 100}).status_code, 403)
        res = self.client.patch(f"/api/mechanic/jobs/{bid}/status/", {"status": "Ready for Delivery"}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.post_as(self.other, "/api/repair-cost/estimate/", {"vehicle": self.vehicle.id, "issue_description": "noise"}).status_code, 403)

    def test_unassigned_job_cannot_be_claimed(self):
        self.client.force_authenticate(user=self.mech)
        res = self.client.patch(f"/api/mechanic/jobs/{self.unassigned.id}/status/", {"status": "Inspection"}, format="json")
        self.assertEqual(res.status_code, 403)
        self.unassigned.refresh_from_db()
        self.assertIsNone(self.unassigned.assigned_mechanic)

    def test_assigned_mechanic_status_rules(self):
        self.client.force_authenticate(user=self.mech)
        url = f"/api/mechanic/jobs/{self.job.id}/status/"
        self.assertEqual(self.client.patch(url, {"status": "Completed"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"status": "Ready for Delivery"}, format="json").status_code, 200)
        # No longer at the workshop stage, so further mechanic status changes are refused
        self.assertEqual(self.client.patch(url, {"status": "In Service"}, format="json").status_code, 400)
        self.job.status = BookingStatus.COMPLETED
        self.job.save()
        self.assertEqual(self.post_as(self.mech, "/api/repair-requests/", {"booking": self.job.id, "issue_title": "x", "additional_cost": 1}).status_code, 400)

    def test_assigned_mechanic_can_work_and_estimate(self):
        res = self.post_as(self.mech, "/api/repair-requests/", {"booking": self.job.id, "issue_title": "Clutch plate", "description": "Clutch slipping under load", "additional_cost": 3000})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        est = self.post_as(self.mech, "/api/repair-cost/estimate/", {"vehicle": self.vehicle.id, "issue_description": "clutch slipping"})
        self.assertEqual(est.status_code, status.HTTP_200_OK)


class DriverScopeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        customer = User.objects.create_user(username="ds_cust", email="ds_cust@example.com", role=UserRole.CUSTOMER)
        self.drv = User.objects.create_user(username="ds_drv", email="ds_drv@example.com", role=UserRole.DRIVER)
        self.other = User.objects.create_user(username="ds_other", email="ds_other@example.com", role=UserRole.DRIVER)
        brand = CarBrand.objects.create(name="Mahindra")
        model = CarModel.objects.create(brand=brand, name="XUV300")
        vehicle = Vehicle.objects.create(
            customer=customer, car_brand=brand, car_model=model, brand="Mahindra", model="XUV300",
            registration_number="KA01DS01", year=2021, fuel_type="Diesel",
        )
        st = ServiceType.objects.create(name="Oil Change", base_price=1500, estimated_duration="1 hour")
        center = ServiceCenter.objects.create(name="DS Hub", address="BTM", phone="+918000000004", email="ds@example.com")
        common = dict(customer=customer, vehicle=vehicle, service_type=st, service_center=center, pickup_address="BTM Layout")
        self.job = ServiceBooking.objects.create(status=BookingStatus.PICKUP_SCHEDULED, assigned_driver=self.drv, **common)
        self.unassigned = ServiceBooking.objects.create(status=BookingStatus.PICKUP_SCHEDULED, **common)

    def as_user(self, user, url, body=None):
        self.client.force_authenticate(user=user)
        return self.client.post(url, body or {}, format="json")

    def test_pickup_list_shows_only_assigned_jobs(self):
        self.client.force_authenticate(user=self.drv)
        self.assertEqual([j["id"] for j in self.client.get("/api/driver/pickups/").data], [self.job.id])
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.get("/api/driver/pickups/").data, [])

    def test_other_driver_cannot_touch_the_pickup(self):
        base = f"/api/driver/pickups/{self.job.id}"
        self.assertEqual(self.as_user(self.other, f"{base}/status/", {"status": "En Route for Pickup"}).status_code, 403)
        self.assertEqual(self.as_user(self.other, f"{base}/handover-otp/request/").status_code, 403)
        self.assertEqual(self.as_user(self.other, f"{base}/handover-otp/verify/", {"otp_code": "123456"}).status_code, 403)
        self.assertEqual(self.as_user(self.other, f"{base}/location/", {"latitude": 12.9, "longitude": 77.6}).status_code, 403)

    def test_unassigned_pickup_cannot_be_claimed(self):
        res = self.as_user(self.drv, f"/api/driver/pickups/{self.unassigned.id}/status/", {"status": "En Route for Pickup"})
        self.assertEqual(res.status_code, 403)
        self.unassigned.refresh_from_db()
        self.assertIsNone(self.unassigned.assigned_driver)

    def test_assigned_driver_stage_rules(self):
        base = f"/api/driver/pickups/{self.job.id}"
        # Picked-up and later statuses come only from the OTP handover / workshop
        self.assertEqual(self.as_user(self.drv, f"{base}/status/", {"status": "Vehicle Picked Up"}).status_code, 400)
        self.assertEqual(self.as_user(self.drv, f"{base}/status/", {"status": "Completed"}).status_code, 400)
        self.assertEqual(self.as_user(self.drv, f"{base}/status/", {"status": "En Route for Pickup"}).status_code, 200)
        self.assertEqual(self.as_user(self.drv, f"{base}/handover-otp/request/").status_code, 200)
        self.job.refresh_from_db()
        res = self.as_user(self.drv, f"{base}/handover-otp/verify/", {"otp_code": self.job.handover_otp})
        self.assertEqual(res.status_code, 200)
        # After pickup: GPS to the workshop still allowed, a new handover OTP is not
        self.assertEqual(self.as_user(self.drv, f"{base}/location/", {"latitude": 12.9, "longitude": 77.6}).status_code, 201)
        self.assertEqual(self.as_user(self.drv, f"{base}/handover-otp/request/").status_code, 400)
        self.job.status = BookingStatus.COMPLETED
        self.job.save()
        self.assertEqual(self.as_user(self.drv, f"{base}/location/", {"latitude": 12.9, "longitude": 77.6}).status_code, 400)


class SecurityAuditTests(TestCase):
    """Regression tests for the permission audit fixes."""

    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username="sa_cust", email="sa_cust@example.com", role=UserRole.CUSTOMER, phone="+919845000002")
        self.ops_admin = User.objects.create_user(
            username="sa_mgr", email="sa_mgr@example.com", role=UserRole.ADMIN, is_staff=True
        )
        self.other_mgr = User.objects.create_user(
            username="sa_mgr2", email="sa_mgr2@example.com", role=UserRole.ADMIN
        )
        self.mechanic = User.objects.create_user(username="sa_mech", email="sa_mech@example.com", role=UserRole.MECHANIC)
        brand = CarBrand.objects.create(name="Honda")
        model = CarModel.objects.create(brand=brand, name="City")
        self.vehicle = Vehicle.objects.create(
            customer=self.customer, car_brand=brand, car_model=model, brand="Honda", model="City",
            registration_number="KA01SA01", year=2024, fuel_type="Petrol",
        )
        self.st = ServiceType.objects.create(name="Full Service", base_price=4000, estimated_duration="5 hours")
        self.center = ServiceCenter.objects.create(user=self.ops_admin, name="SA Hub", address="Jayanagar", phone="+918000000005", email="sa@example.com")
        self.other_center = ServiceCenter.objects.create(user=self.other_mgr, name="SA Hub 2", address="Hebbal", phone="+918000000006", email="sa2@example.com")
        self.booking = ServiceBooking.objects.create(
            customer=self.customer, vehicle=self.vehicle, service_type=self.st, service_center=self.center,
            pickup_address="Jayanagar 4th Block", status=BookingStatus.PENDING,
        )

    def test_staff_flag_does_not_make_a_mechanic_an_admin(self):
        self.mechanic.is_staff = True  # only opens the Django admin site; app permissions come from the role
        self.mechanic.save()
        self.client.force_authenticate(user=self.mechanic)
        self.assertEqual(self.client.get("/api/admin/dashboard-stats/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post("/api/car-brands/", {"name": "Hacked"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/service-center/bookings/").status_code, status.HTTP_403_FORBIDDEN)
        res = self.client.patch(f"/api/service-center/bookings/{self.booking.id}/", {"status": "Cancelled"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_sees_the_bookings_of_every_center(self):
        other = ServiceBooking.objects.create(
            customer=self.customer, vehicle=self.vehicle, service_type=self.st, service_center=self.other_center, pickup_address="x",
        )
        self.client.force_authenticate(user=self.ops_admin)
        ids = [b["id"] for b in self.client.get("/api/service-center/bookings/").data]
        self.assertIn(self.booking.id, ids)
        self.assertIn(other.id, ids)

    def test_customer_can_only_edit_pickup_details_or_cancel(self):
        self.client.force_authenticate(user=self.customer)
        url = f"/api/bookings/{self.booking.id}/"
        for body in ({"status": "Completed"}, {"handover_otp_verified": True}, {"estimated_cost": 1}, {"assigned_mechanic": self.mechanic.id}):
            self.assertEqual(self.client.patch(url, body, format="json").status_code, status.HTTP_400_BAD_REQUEST, body)
        self.assertEqual(self.client.patch(url, {"customer_notes": "Gate code 1234"}, format="json").status_code, 200)
        self.booking.status = BookingStatus.IN_SERVICE
        self.booking.save()
        self.assertEqual(self.client.patch(url, {"status": "Cancelled"}, format="json").status_code, 400)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.IN_SERVICE)

    def test_booking_price_comes_from_the_package(self):
        self.client.force_authenticate(user=self.customer)
        res = self.client.post("/api/bookings/", {
            "vehicle": self.vehicle.id, "service_type": self.st.id, "service_center": self.center.id,
            "pickup_address": "Jayanagar", "estimated_cost": 1,
            "preferred_date": FUTURE_DATE, "preferred_time": "09:00:00",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(res.data["estimated_cost"]), 4000.0)

    def test_repair_request_can_be_answered_once_at_the_workshop(self):
        from api.models import RepairRequest

        self.booking.status = "Repair Approval Required"
        self.booking.estimated_cost = 4000
        self.booking.save()
        rr = RepairRequest.objects.create(booking=self.booking, mechanic=self.mechanic, issue_title="Pads", description="Worn", additional_cost=1500)
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.client.post(f"/api/repair-requests/{rr.id}/approve/").status_code, 200)
        self.assertEqual(self.client.post(f"/api/repair-requests/{rr.id}/approve/").status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(self.client.post(f"/api/repair-requests/{rr.id}/reject/").status_code, status.HTTP_409_CONFLICT)
        self.booking.refresh_from_db()
        self.assertEqual(float(self.booking.estimated_cost), 5500.0)

        self.booking.status = BookingStatus.COMPLETED
        self.booking.save()
        late = RepairRequest.objects.create(booking=self.booking, mechanic=self.mechanic, issue_title="Late", description="x", additional_cost=999)
        self.assertEqual(self.client.post(f"/api/repair-requests/{late.id}/approve/").status_code, 400)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.COMPLETED)

    def test_vehicle_with_service_history_cannot_be_deleted(self):
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.client.delete(f"/api/vehicles/{self.vehicle.id}/").status_code, 400)
        self.assertTrue(Vehicle.objects.filter(pk=self.vehicle.id).exists())
        spare = Vehicle.objects.create(customer=self.customer, brand="Honda", model="Amaze", registration_number="KA01SA02", year=2020, fuel_type="Petrol")
        self.assertEqual(self.client.delete(f"/api/vehicles/{spare.id}/").status_code, 200)

    def test_staff_of_another_center_cannot_be_assigned(self):
        from api.models import Employee

        theirs = User.objects.create_user(username="sa_drv2", email="sa_drv2@example.com", role=UserRole.DRIVER)
        Employee.objects.create(user=theirs, service_center=self.other_center, employee_type=Employee.EmployeeType.VALET)
        pool = User.objects.create_user(username="sa_drv3", email="sa_drv3@example.com", role=UserRole.DRIVER)
        self.client.force_authenticate(user=self.ops_admin)
        url = f"/api/service-center/bookings/{self.booking.id}/"
        self.assertEqual(self.client.patch(url, {"assigned_driver_id": theirs.id}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"assigned_driver_id": pool.id}, format="json").status_code, 200)
        staff = self.client.get("/api/service-center/employees/").data
        driver_ids = [d["id"] for d in staff["drivers"]]
        self.assertIn(pool.id, driver_ids)
        self.assertIn(theirs.id, driver_ids)  # listed for the admin, but only assignable at their own center
        self.assertEqual(self.client.patch(url, {"status": "Teleported"}, format="json").status_code, 400)

    def test_only_the_owner_an_admin_or_the_assigned_mechanic_can_estimate(self):
        body = {"vehicle": self.vehicle.id, "issue_description": "noise"}
        stranger = User.objects.create_user(username="sa_x", email="sa_x@example.com", role=UserRole.CUSTOMER)
        self.client.force_authenticate(user=stranger)
        self.assertEqual(self.client.post("/api/repair-cost/estimate/", body, format="json").status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.ops_admin)
        self.assertEqual(self.client.post("/api/repair-cost/estimate/", body, format="json").status_code, status.HTTP_200_OK)

    def test_repaired_critical_fault_stops_lowering_health_score(self):
        from api.models import RepairRequest, ServiceInspection
        from api.health_service import recalculate_car_health_score

        ServiceInspection.objects.create(booking=self.booking, mechanic=self.mechanic, issue_description="Brake failure", severity="CRITICAL")
        self.booking.status = BookingStatus.IN_SERVICE
        self.booking.save()
        unfixed = recalculate_car_health_score(self.vehicle).score
        RepairRequest.objects.create(booking=self.booking, mechanic=self.mechanic, issue_title="Brakes", description="Replace", additional_cost=3000, status="APPROVED")
        self.booking.status = BookingStatus.COMPLETED
        self.booking.save()
        fixed = recalculate_car_health_score(self.vehicle).score
        self.assertEqual(unfixed, 90 - 25)  # new car, no completed services yet, one open critical issue
        self.assertEqual(fixed, 90 + 5 + 3)  # completed service + approved repair, fault resolved


class BookingSlotTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username="slotc", email="slotc@example.com", role=UserRole.CUSTOMER, phone="+919845000001")
        self.center = ServiceCenter.objects.create(
            name="Slot Center", address="MG Road", phone="+918000000001", email="slot@example.com", slot_capacity=2
        )
        self.st = ServiceType.objects.create(name="Slot Service", base_price=1000)
        self.vehicles = [
            Vehicle.objects.create(customer=self.customer, brand="Tata", model="Nexon", registration_number=f"KA05SL{i:04d}")
            for i in range(4)
        ]
        self.client.force_authenticate(user=self.customer)

    def book(self, vehicle, day=FUTURE_DATE, slot="09:00:00"):
        return self.client.post("/api/bookings/", {
            "vehicle": vehicle.id, "service_type": self.st.id, "service_center": self.center.id,
            "pickup_address": "Koramangala", "preferred_date": day, "preferred_time": slot,
        }, format="json")

    def test_slot_fills_up_at_capacity(self):
        self.assertEqual(self.book(self.vehicles[0]).status_code, 201)
        self.assertEqual(self.book(self.vehicles[1]).status_code, 201)
        res = self.book(self.vehicles[2])
        self.assertEqual(res.status_code, 400)
        self.assertIn("fully booked", res.data["error"])
        # Another slot on the same day still has room
        self.assertEqual(self.book(self.vehicles[2], slot="11:00:00").status_code, 201)

    def test_cancelled_booking_frees_its_place(self):
        first = self.book(self.vehicles[0]).data
        self.book(self.vehicles[1])
        self.client.patch(f"/api/bookings/{first['id']}/", {"status": "Cancelled"}, format="json")
        self.assertEqual(self.book(self.vehicles[2]).status_code, 201)

    def test_availability_endpoint(self):
        self.book(self.vehicles[0])
        res = self.client.get(f"/api/service-centers/{self.center.id}/slots/?date={FUTURE_DATE}")
        self.assertEqual(res.status_code, 200)
        nine = next(s for s in res.data["slots"] if s["time"] == "09:00:00")
        self.assertEqual((nine["booked"], nine["available"], nine["is_full"]), (1, 1, False))
        self.assertEqual(self.client.get(f"/api/service-centers/{self.center.id}/slots/?date=bad").status_code, 400)

    def test_rejects_past_dates_unknown_slots_and_missing_date(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(self.book(self.vehicles[0], day=yesterday).status_code, 400)
        self.assertEqual(self.book(self.vehicles[0], slot="03:00:00").status_code, 400)
        too_far = (timezone.localdate() + timedelta(days=45)).isoformat()
        self.assertEqual(self.book(self.vehicles[0], day=too_far).status_code, 400)
        res = self.client.post("/api/bookings/", {
            "vehicle": self.vehicles[0].id, "service_type": self.st.id, "service_center": self.center.id,
            "pickup_address": "Koramangala", "preferred_time": "09:00:00",
        }, format="json")
        self.assertEqual(res.status_code, 400)

    def test_reschedule_into_a_full_slot_is_refused(self):
        self.book(self.vehicles[0], slot="11:00:00")
        self.book(self.vehicles[1], slot="11:00:00")
        mine = self.book(self.vehicles[2]).data
        res = self.client.patch(f"/api/bookings/{mine['id']}/", {"preferred_time": "11:00:00"}, format="json")
        self.assertEqual(res.status_code, 400)
        res = self.client.patch(f"/api/bookings/{mine['id']}/", {"preferred_time": "14:00:00"}, format="json")
        self.assertEqual(res.status_code, 200)


@override_settings(OTP_BYPASS=False)
class ReturnDeliveryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username="rd_cust", email="rd_cust@example.com", role=UserRole.CUSTOMER)
        self.drv = User.objects.create_user(username="rd_drv", email="rd_drv@example.com", role=UserRole.DRIVER)
        self.other = User.objects.create_user(username="rd_other", email="rd_other@example.com", role=UserRole.DRIVER)
        vehicle = Vehicle.objects.create(customer=self.customer, brand="Kia", model="Seltos", registration_number="KA02RD01")
        st = ServiceType.objects.create(name="RD Service", base_price=2000)
        center = ServiceCenter.objects.create(name="RD Hub", address="HSR", phone="+918000000009", email="rd@example.com")
        self.job = ServiceBooking.objects.create(
            customer=self.customer, vehicle=vehicle, service_type=st, service_center=center,
            pickup_address="HSR Layout", status=BookingStatus.READY_FOR_DELIVERY, assigned_driver=self.drv,
        )
        self.base = f"/api/driver/pickups/{self.job.id}"

    def post(self, user, path, body=None):
        self.client.force_authenticate(user=user)
        return self.client.post(f"{self.base}/{path}", body or {}, format="json")

    def test_full_return_delivery_completes_and_invoices(self):
        # Delivery code only exists once the driver is on the way
        self.assertEqual(self.post(self.drv, "delivery-otp/request/").status_code, 400)
        self.assertEqual(self.post(self.drv, "status/", {"status": "Out for Delivery"}).status_code, 200)
        self.assertEqual(self.post(self.drv, "location/", {"latitude": 12.91, "longitude": 77.64}).status_code, 201)
        self.assertEqual(self.post(self.drv, "delivery-otp/request/").status_code, 200)
        self.job.refresh_from_db()

        # The customer sees the code on their tracking page
        self.client.force_authenticate(user=self.customer)
        tracking = self.client.get(f"/api/bookings/{self.job.id}/tracking/").data
        self.assertEqual(tracking["delivery_otp_code"], self.job.delivery_otp)

        wrong = "000000" if self.job.delivery_otp != "000000" else "111111"
        res = self.post(self.drv, "delivery-otp/verify/", {"otp_code": wrong})
        self.assertEqual(res.status_code, 400)
        self.assertIn("4 attempt(s) remaining", res.data["error"])
        res = self.post(self.drv, "delivery-otp/verify/", {"otp_code": self.job.delivery_otp})
        self.assertEqual(res.status_code, 200)

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, BookingStatus.COMPLETED)
        self.assertTrue(self.job.delivery_otp_verified)
        self.assertIsNotNone(self.job.delivered_at)
        self.assertIsNotNone(self.job.completed_at)
        self.assertTrue(Invoice.objects.filter(booking=self.job).exists())
        self.assertTrue(Notification.objects.filter(user=self.customer, notification_type="DELIVERY_COMPLETED").exists())
        # Code no longer shown once used
        self.client.force_authenticate(user=self.customer)
        self.assertIsNone(self.client.get(f"/api/bookings/{self.job.id}/tracking/").data["delivery_otp_code"])

    def test_other_driver_and_wrong_stage_are_refused(self):
        self.assertEqual(self.post(self.other, "status/", {"status": "Out for Delivery"}).status_code, 403)
        # Out for Delivery only follows Ready for Delivery
        self.job.status = BookingStatus.IN_SERVICE
        self.job.save()
        self.assertEqual(self.post(self.drv, "status/", {"status": "Out for Delivery"}).status_code, 400)
        # Pickup moves are not allowed during the return trip
        self.job.status = BookingStatus.READY_FOR_DELIVERY
        self.job.save()
        self.assertEqual(self.post(self.drv, "status/", {"status": "En Route for Pickup"}).status_code, 400)

    def test_delivery_code_locks_after_five_wrong_tries(self):
        self.post(self.drv, "status/", {"status": "Out for Delivery"})
        self.post(self.drv, "delivery-otp/request/")
        self.job.refresh_from_db()
        wrong = "000000" if self.job.delivery_otp != "000000" else "111111"
        for _ in range(5):
            self.post(self.drv, "delivery-otp/verify/", {"otp_code": wrong})
        res = self.post(self.drv, "delivery-otp/verify/", {"otp_code": self.job.delivery_otp})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Maximum", res.data["error"])


class ConditionReportTests(TestCase):
    def setUp(self):
        import tempfile

        self.media_dir = tempfile.mkdtemp()
        self.client = APIClient()
        self.customer = User.objects.create_user(username="cr_cust", email="cr_cust@example.com", role=UserRole.CUSTOMER)
        self.stranger = User.objects.create_user(username="cr_x", email="cr_x@example.com", role=UserRole.CUSTOMER)
        self.drv = User.objects.create_user(username="cr_drv", email="cr_drv@example.com", role=UserRole.DRIVER)
        self.vehicle = Vehicle.objects.create(customer=self.customer, brand="Honda", model="City", registration_number="KA03CR01")
        center = ServiceCenter.objects.create(name="CR Hub", address="Whitefield", phone="+918000000010", email="cr@example.com")
        self.job = ServiceBooking.objects.create(
            customer=self.customer, vehicle=self.vehicle, service_center=center, pickup_address="Whitefield",
            status="Arrived at Pickup",
            assigned_driver=self.drv,
        )
        self.base = f"/api/driver/pickups/{self.job.id}"

    def photo(self, angle="FRONT", content_type="image/jpeg"):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        buf = BytesIO()
        Image.new("RGB", (8, 8), "blue").save(buf, format="JPEG")
        self.client.force_authenticate(user=self.drv)
        with self.settings(MEDIA_ROOT=self.media_dir):
            return self.client.post(
                f"{self.base}/condition-photos/",
                {"angle": angle, "file": SimpleUploadedFile("x.jpg", buf.getvalue(), content_type)},
                format="multipart",
            )

    def odometer(self, km):
        self.client.force_authenticate(user=self.drv)
        return self.client.post(f"{self.base}/odometer/", {"reading_km": km}, format="json")

    def test_before_and_after_photos_and_km_driven(self):
        self.assertEqual(self.photo("FRONT").status_code, 201)
        self.assertEqual(self.odometer(40210).status_code, 200)
        # While the car is at the workshop no condition photos are taken
        ServiceBooking.objects.filter(pk=self.job.pk).update(status=BookingStatus.IN_SERVICE)
        self.assertEqual(self.photo("REAR").status_code, 400)
        ServiceBooking.objects.filter(pk=self.job.pk).update(status=BookingStatus.OUT_FOR_DELIVERY)
        self.assertEqual(self.photo("FRONT").status_code, 201)
        res = self.odometer(40190)
        self.assertEqual(res.status_code, 400)
        self.assertIn("lower than the pickup", res.data["error"])
        self.assertEqual(self.odometer(40236).status_code, 200)

        self.client.force_authenticate(user=self.customer)
        report = self.client.get(f"/api/bookings/{self.job.id}/condition-report/").data
        self.assertEqual(len(report["pickup_photos"]), 1)
        self.assertEqual(len(report["delivery_photos"]), 1)
        self.assertEqual(report["km_driven"], 26)
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.odometer_km, 40236)

    def test_non_image_is_rejected(self):
        res = self.photo(content_type="application/pdf")
        self.assertEqual(res.status_code, 400)

    def test_report_is_private(self):
        self.client.force_authenticate(user=self.stranger)
        self.assertEqual(self.client.get(f"/api/bookings/{self.job.id}/condition-report/").status_code, 403)
        other_driver = User.objects.create_user(username="cr_d2", email="cr_d2@example.com", role=UserRole.DRIVER)
        self.client.force_authenticate(user=other_driver)
        self.assertEqual(self.client.post(f"{self.base}/odometer/", {"reading_km": 5}, format="json").status_code, 403)


class PlateCheckTests(TestCase):
    def test_matching_rules(self):
        from api.plate_service import LIKELY, MATCH, MISMATCH, NO_TEXT, check_plate

        self.assertEqual(check_plate("KA 01 AB 1234", "KA01AB1234")["result"], MATCH)
        # OCR lookalikes: O for 0, I for 1, 8 for B
        self.assertEqual(check_plate("KA O1 A8 I234", "KA01AB1234")["result"], MATCH)
        # Plate text surrounded by other words, over two lines
        self.assertEqual(check_plate("IND\nKA-01-AB-1234\nSHOWROOM", "KA01AB1234")["result"], MATCH)
        # One unreadable character
        self.assertEqual(check_plate("KA01AB12E4", "KA01AB1234")["result"], LIKELY)
        self.assertEqual(check_plate("KA01AB234", "KA01AB1234")["result"], LIKELY)
        # A different car
        res = check_plate("MH12CD5678", "KA01AB1234")
        self.assertEqual(res["result"], MISMATCH)
        self.assertEqual(res["detected"], "MH12CD5678")
        self.assertEqual(check_plate("  --  ", "KA01AB1234")["result"], NO_TEXT)
        self.assertEqual(check_plate("22 BH 1234 AA", "22BH1234AA")["result"], MATCH)

    def test_endpoint_marks_booking_verified(self):
        client = APIClient()
        customer = User.objects.create_user(username="pc_c", email="pc_c@example.com", role=UserRole.CUSTOMER)
        drv = User.objects.create_user(username="pc_d", email="pc_d@example.com", role=UserRole.DRIVER)
        vehicle = Vehicle.objects.create(customer=customer, brand="Maruti", model="Swift", registration_number="KA51MX4321")
        job = ServiceBooking.objects.create(
            customer=customer, vehicle=vehicle, pickup_address="Jayanagar", status="Arrived at Pickup", assigned_driver=drv,
        )
        client.force_authenticate(user=drv)
        res = client.post(f"/api/driver/pickups/{job.id}/plate-check/", {"ocr_text": "TN09XY0001"}, format="json")
        self.assertEqual((res.status_code, res.data["result"], res.data["plate_verified"]), (200, "MISMATCH", False))
        res = client.post(f"/api/driver/pickups/{job.id}/plate-check/", {"ocr_text": "KA 51 MX 4321"}, format="json")
        self.assertEqual((res.data["result"], res.data["plate_verified"]), ("MATCH", True))
        job.refresh_from_db()
        self.assertTrue(job.plate_verified)


class ServiceReminderTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(username="sr_c", email="sr_c@example.com", role=UserRole.CUSTOMER)
        self.vehicle = Vehicle.objects.create(customer=self.customer, brand="Toyota", model="Glanza", registration_number="KA04SR01")
        self.today = timezone.localdate()

    def complete_service(self, days_ago, odometer=None):
        return ServiceBooking.objects.create(
            customer=self.customer, vehicle=self.vehicle, pickup_address="RT Nagar", status=BookingStatus.COMPLETED,
            completed_at=timezone.now() - timedelta(days=days_ago), delivery_odometer_km=odometer,
        )

    def test_due_by_time(self):
        from api.reminder_service import DUE_SOON, OK, OVERDUE, service_due

        self.complete_service(days_ago=30)
        self.assertEqual(service_due(self.vehicle, self.today)["status"], OK)
        ServiceBooking.objects.all().delete()
        self.complete_service(days_ago=170)
        self.assertEqual(service_due(self.vehicle, self.today)["status"], DUE_SOON)
        ServiceBooking.objects.all().delete()
        self.complete_service(days_ago=200)
        due = service_due(self.vehicle, self.today)
        self.assertEqual(due["status"], OVERDUE)
        self.assertEqual(due["days_left"], -20)

    def test_due_by_kilometres_first(self):
        from api.reminder_service import DUE_SOON, OVERDUE, service_due

        self.complete_service(days_ago=20, odometer=30000)
        self.vehicle.odometer_km = 39500
        self.vehicle.save()
        due = service_due(self.vehicle, self.today)
        self.assertEqual((due["status"], due["km_left"]), (DUE_SOON, 500))
        self.vehicle.odometer_km = 41200
        self.vehicle.save()
        self.assertEqual(service_due(self.vehicle, self.today)["status"], OVERDUE)

    def test_open_booking_suppresses_and_command_dedupes(self):
        from api.reminder_service import BOOKED, send_service_reminders, service_due

        self.complete_service(days_ago=400)
        self.assertEqual(send_service_reminders(self.today), 1)
        self.assertEqual(send_service_reminders(self.today), 0)  # not again within a week
        ServiceBooking.objects.create(customer=self.customer, vehicle=self.vehicle, pickup_address="RT Nagar")
        self.assertEqual(service_due(self.vehicle, self.today)["status"], BOOKED)

    def test_endpoint_lists_only_own_vehicles(self):
        other = User.objects.create_user(username="sr_o", email="sr_o@example.com", role=UserRole.CUSTOMER)
        Vehicle.objects.create(customer=other, brand="Tata", model="Punch", registration_number="KA04SR02")
        client = APIClient()
        client.force_authenticate(user=self.customer)
        res = client.get("/api/reminders/")
        self.assertEqual([r["registration_number"] for r in res.data], ["KA04SR01"])


class ServiceReviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="rv_c", email="rv_c@example.com", role=UserRole.CUSTOMER, first_name="Asha", last_name="Rao"
        )
        self.drv = User.objects.create_user(username="rv_d", email="rv_d@example.com", role=UserRole.DRIVER)
        vehicle = Vehicle.objects.create(customer=self.customer, brand="Hyundai", model="Creta", registration_number="KA05RV01")
        self.center = ServiceCenter.objects.create(name="RV Hub", address="Hebbal", phone="+918000000011", email="rv@example.com")
        self.job = ServiceBooking.objects.create(
            customer=self.customer, vehicle=vehicle, service_center=self.center, pickup_address="Hebbal",
            status=BookingStatus.COMPLETED, assigned_driver=self.drv,
        )
        self.url = f"/api/bookings/{self.job.id}/review/"

    def test_review_once_and_center_average_is_real(self):
        res = self.client.get("/api/service-centers/")
        center = next(c for c in res.data if c["id"] == self.center.id)
        self.assertEqual((center["review_count"], center["average_rating"]), (0, None))

        self.client.force_authenticate(user=self.customer)
        res = self.client.post(self.url, {"center_rating": 4, "driver_rating": 5, "comment": "On time"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["reviewer"], "Asha R.")
        self.assertEqual(self.client.post(self.url, {"center_rating": 1}, format="json").status_code, 409)

        public = self.client.get(f"/api/service-centers/{self.center.id}/reviews/").data
        self.assertEqual(public["service_center"]["average_rating"], 4.0)
        self.assertEqual(len(public["reviews"]), 1)
        self.center.refresh_from_db()
        self.assertEqual(self.center.rating, 4.0)

    def test_rules(self):
        stranger = User.objects.create_user(username="rv_s", email="rv_s@example.com", role=UserRole.CUSTOMER)
        self.client.force_authenticate(user=stranger)
        self.assertEqual(self.client.post(self.url, {"center_rating": 5}, format="json").status_code, 403)
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.client.post(self.url, {"center_rating": 6}, format="json").status_code, 400)
        self.assertEqual(self.client.post(self.url, {"center_rating": 0}, format="json").status_code, 400)
        ServiceBooking.objects.filter(pk=self.job.pk).update(status=BookingStatus.IN_SERVICE)
        self.assertEqual(self.client.post(self.url, {"center_rating": 5}, format="json").status_code, 400)


class InvoicePdfTests(TestCase):
    def setUp(self):
        from api.invoice_service import generate_invoice_for_booking

        self.client = APIClient()
        self.customer = User.objects.create_user(
            username="pdf_c", email="pdf_c@example.com", role=UserRole.CUSTOMER, first_name="Ravi & Sons <Ltd>"
        )
        vehicle = Vehicle.objects.create(customer=self.customer, brand="Tata", model="Altroz", registration_number="KA06PD1234")
        st = ServiceType.objects.create(name="PDF Service", base_price=1800)
        center = ServiceCenter.objects.create(name="PDF Hub", address="Yeshwanthpur", phone="+918000000012", email="pdf@example.com")
        booking = ServiceBooking.objects.create(
            customer=self.customer, vehicle=vehicle, service_type=st, service_center=center,
            pickup_address="Yeshwanthpur", status=BookingStatus.COMPLETED,
        )
        self.invoice = generate_invoice_for_booking(booking)

    def test_customer_downloads_pdf_and_stranger_cannot(self):
        self.client.force_authenticate(user=self.customer)
        res = self.client.get(f"/api/invoices/{self.invoice.id}/pdf/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))
        stranger = User.objects.create_user(username="pdf_s", email="pdf_s@example.com", role=UserRole.CUSTOMER)
        self.client.force_authenticate(user=stranger)
        self.assertEqual(self.client.get(f"/api/invoices/{self.invoice.id}/pdf/").status_code, 403)

    def test_qr_token_verifies_and_rejects_forgery(self):
        from api.invoice_pdf import verification_token

        token = verification_token(self.invoice)
        res = self.client.get(f"/api/invoices/verify/{token}/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["valid"])
        self.assertEqual(res.data["invoice_number"], self.invoice.invoice_number)
        self.assertEqual(res.data["vehicle"], "KA06****34")
        self.assertNotIn("customer", res.data)
        # Changing the invoice number in the token breaks the signature
        number, sig = token.rsplit(":", 1)
        forged = number[:-1] + ("2" if number[-1] != "2" else "3") + ":" + sig
        self.assertEqual(self.client.get(f"/api/invoices/verify/{forged}/").status_code, 404)

    @staticmethod
    def _pdf_text(pdf: bytes) -> str:
        """Page text of a ReportLab PDF, using only the standard library (streams are ASCII85 + Flate encoded)."""
        import base64
        import re
        import zlib

        chunks = []
        for raw in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
            try:
                chunks.append(zlib.decompress(base64.a85decode(raw.strip(), adobe=True)).decode("latin-1"))
            except Exception:
                continue  # images and other non-text streams
        return "\n".join(chunks)

    def _coupon_invoice(self):
        from decimal import Decimal
        from api.invoice_service import generate_invoice_for_booking
        from api.models import Coupon, RepairRequest, RepairRequestStatus

        mechanic = User.objects.create_user(username="pdf_m", email="pdf_m@example.com", role=UserRole.MECHANIC)
        coupon = Coupon.objects.create(code="WELCOME10", discount_type="PERCENT", value=10)
        booking = ServiceBooking.objects.create(
            customer=self.customer, vehicle=self.invoice.vehicle, service_center=self.invoice.service_center,
            service_type=ServiceType.objects.create(name="General Service", base_price=2999),
            pickup_address="Yeshwanthpur", status=BookingStatus.COMPLETED,
            coupon=coupon, coupon_discount=Decimal("299.90"),
        )
        RepairRequest.objects.create(
            booking=booking, mechanic=mechanic, issue_title="Clutch plate", description="Slipping",
            additional_cost=3200, estimated_extra_hours=2, status=RepairRequestStatus.APPROVED,
        )
        return generate_invoice_for_booking(booking)

    def test_totals_panel_lists_coupon_discount_and_adds_up(self):
        from decimal import Decimal
        from api.invoice_pdf import _totals_rows

        invoice = self._coupon_invoice()
        self.assertEqual(invoice.discount, Decimal("299.90"))
        self.assertEqual(invoice.grand_total, Decimal("7904.94"))
        rows = _totals_rows(invoice)
        self.assertEqual(
            [label for label, _ in rows],
            ["Service", "Approved repairs", "Repair labour", "Discount", "GST (18%)", "Grand total", "Status"],
        )
        self.assertEqual(dict(rows)["Discount"], "- Rs. 299.90")

        def amount(text):
            return Decimal(text.replace("- ", "-").replace("Rs. ", "").replace(",", ""))

        # Every row above the grand total adds up to it
        charges = sum((amount(value) for label, value in rows[:-2]), Decimal("0"))
        self.assertEqual(charges, amount(dict(rows)["Grand total"]))

        # The row is drawn in the actual PDF, not just in the row data
        from api.invoice_pdf import build_invoice_pdf

        text = self._pdf_text(build_invoice_pdf(invoice))
        self.assertIn("(Discount) Tj", text)
        self.assertIn("(- Rs. 299.90) Tj", text)
        self.assertIn("(Rs. 7,904.94) Tj", text)

    def test_totals_panel_has_no_discount_row_without_coupon(self):
        from api.invoice_pdf import _totals_rows, build_invoice_pdf

        self.assertNotIn("Discount", [label for label, _ in _totals_rows(self.invoice)])
        text = self._pdf_text(build_invoice_pdf(self.invoice))
        self.assertIn("(Grand total) Tj", text)
        self.assertNotIn("Discount", text)


class AnalyticsTests(TestCase):
    def setUp(self):
        from api.models import Employee, RepairRequest, ServiceReview

        self.client = APIClient()
        self.center = ServiceCenter.objects.create(name="AN Hub", address="Malleshwaram", phone="+918000000013", email="an@example.com")
        other_center = ServiceCenter.objects.create(name="AN Other", address="Vijayanagar", phone="+918000000014", email="an2@example.com")
        self.ops_admin = User.objects.create_user(username="an_m", email="an_m@example.com", role=UserRole.ADMIN)
        customer = User.objects.create_user(username="an_c", email="an_c@example.com", role=UserRole.CUSTOMER)
        mech = User.objects.create_user(username="an_k", email="an_k@example.com", role=UserRole.MECHANIC)
        vehicle = Vehicle.objects.create(customer=customer, brand="Maruti", model="Baleno", registration_number="KA07AN01")
        now = timezone.now()

        def booking(center, status_, hours=None):
            b = ServiceBooking.objects.create(customer=customer, vehicle=vehicle, service_center=center, pickup_address="x", status=status_)
            if hours is not None:
                b.completed_at = b.created_at + timedelta(hours=hours)
                b.save()
            return b

        done1 = booking(self.center, BookingStatus.COMPLETED, hours=10)
        booking(self.center, BookingStatus.COMPLETED, hours=30)
        booking(self.center, BookingStatus.CANCELLED)
        booking(other_center, BookingStatus.COMPLETED, hours=99)  # must not leak into AN Hub's numbers

        Invoice.objects.create(booking=done1, grand_total=1180, payment_status="PAID", issued_at=now)
        for title, st in [("Brake pads", "APPROVED"), ("brake  PADS", "REJECTED"), ("Wiper blades", "APPROVED")]:
            RepairRequest.objects.create(booking=done1, mechanic=mech, issue_title=title, description="d", additional_cost=1000, status=st)
        ServiceReview.objects.create(booking=done1, customer=customer, service_center=self.center, center_rating=4, comment="Good")

    def test_numbers_for_one_center(self):
        self.client.force_authenticate(user=self.ops_admin)
        data = self.client.get(f"/api/service-center/analytics/?center={self.center.id}").data
        self.assertEqual(data["scope"], "AN Hub")
        self.assertEqual((data["totals"]["bookings"], data["totals"]["completed"], data["totals"]["cancelled"]), (3, 2, 1))
        self.assertEqual(data["totals"]["revenue_paid"], 1180.0)
        self.assertEqual(data["turnaround_hours"], {"count": 2, "average": 20.0, "median": 20.0})
        self.assertEqual(data["repairs"]["top"][0], {"title": "Brake pads", "count": 2, "average_cost": 1000.0})
        self.assertAlmostEqual(data["repairs"]["approval_rate"], 66.7)
        self.assertEqual(data["ratings"]["average"], 4.0)
        self.assertEqual(len(data["monthly"]), 6)
        self.assertEqual(data["monthly"][-1]["bookings"], 3)
        self.assertEqual(data["monthly"][-1]["revenue"], 1180.0)

    def test_customers_cannot_read_analytics(self):
        customer = User.objects.get(username="an_c")
        self.client.force_authenticate(user=customer)
        self.assertEqual(self.client.get("/api/service-center/analytics/").status_code, 403)


class LearnedCostModelTests(TestCase):
    def setUp(self):
        from django.core.management import call_command

        ServiceType.objects.create(name="ML Service A", base_price=1500)
        ServiceType.objects.create(name="ML Service B", base_price=3500)
        self.admin = User.objects.create_user(username="ml_a", email="ml_a@example.com", role=UserRole.ADMIN)
        self.customer = User.objects.create_user(username="ml_c", email="ml_c@example.com", role=UserRole.CUSTOMER)
        self.vehicle = Vehicle.objects.create(customer=self.customer, brand="Kia", model="Sonet", registration_number="KA08ML01", year=2020)
        self.call = call_command

    def test_falls_back_to_formula_until_enough_data(self):
        from api.ai_cost_service import estimate_repair_cost
        from api.ml_cost_model import train_cost_model

        with self.assertRaises(ValueError):
            train_cost_model()
        self.assertEqual(estimate_repair_cost(self.vehicle, None, "noise", "HIGH", 2)["estimation_source"], "RULE_BASED")

    def test_trains_and_serves_learned_estimates(self):
        from io import StringIO

        from api.ai_cost_service import estimate_repair_cost
        from api.models import CostModel

        self.call("seed_repair_history", count=80, stdout=StringIO())
        self.call("train_cost_model", stdout=StringIO())
        model = CostModel.objects.get(is_active=True)
        self.assertEqual((model.n_samples, model.synthetic_share), (80, 100.0))
        self.assertLess(model.metrics["ml"]["mape"], model.metrics["rule_based"]["mape"])

        low = estimate_repair_cost(self.vehicle, None, "noise", "LOW", 2)
        critical = estimate_repair_cost(self.vehicle, None, "noise", "CRITICAL", 2)
        self.assertEqual(low["estimation_source"], "ML")
        self.assertLess(low["estimated_min_cost"], low["estimated_max_cost"])
        self.assertGreater(critical["estimated_min_cost"], low["estimated_min_cost"])
        self.assertIn("synthetic", low["explanation"])

        # Retraining replaces the active model
        self.call("train_cost_model", stdout=StringIO())
        self.assertEqual(CostModel.objects.filter(is_active=True).count(), 1)

    def test_synthetic_history_stays_out_of_business_numbers(self):
        from io import StringIO

        self.call("seed_repair_history", count=40, stdout=StringIO())
        client = APIClient()
        client.force_authenticate(user=self.admin)
        stats = client.get("/api/admin/dashboard-stats/").data
        self.assertEqual((stats["total_bookings"], stats["total_vehicles"], stats["total_customers"]), (0, 1, 1))
        self.assertEqual(client.get("/api/service-center/analytics/").data["totals"]["bookings"], 0)
        res = client.get("/api/admin/cost-model/")
        self.assertEqual((res.data["available_samples"], res.data["active"]), (40, None))
        self.assertEqual(client.post("/api/admin/cost-model/train/").status_code, 201)
        client.force_authenticate(user=self.customer)
        self.assertEqual(client.post("/api/admin/cost-model/train/").status_code, 403)


class SyntheticHistoryHiddenTests(TestCase):
    def test_admin_booking_lists_leave_out_synthetic_jobs(self):
        from io import StringIO

        from django.core.management import call_command

        ServiceType.objects.create(name="SH Service", base_price=1000)
        call_command("seed_repair_history", count=5, stdout=StringIO())
        admin = User.objects.create_user(username="sh_a", email="sh_a@example.com", role=UserRole.ADMIN)
        client = APIClient()
        client.force_authenticate(user=admin)
        for url in ["/api/bookings/", "/api/service-center/bookings/", "/api/driver/pickups/", "/api/mechanic/jobs/"]:
            self.assertEqual(client.get(url).data, [], url)


@override_settings(OTP_BYPASS=False)
class PasswordAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def register(self, **overrides):
        body = {"name": "Meera Iyer", "email": "meera@example.com", "phone": "9845012345", "password": "Garage#Blue77"}
        body.update(overrides)
        return self.client.post("/api/auth/register/", body, format="json")

    def login(self, identifier, password):
        return self.client.post("/api/auth/login/", {"identifier": identifier, "password": password}, format="json")

    def test_register_then_login_by_email_or_phone(self):
        res = self.register()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["user"]["role"], UserRole.CUSTOMER)
        self.assertTrue(res.data["user"]["has_password"])
        self.assertIn("access", res.data)
        user = User.objects.get(email="meera@example.com")
        self.assertNotEqual(user.password, "Garage#Blue77")  # stored hashed
        self.assertTrue(hasattr(user, "customer_profile"))

        self.assertEqual(self.login("MEERA@example.com", "Garage#Blue77").status_code, 200)
        self.assertEqual(self.login("+91 98450 12345", "Garage#Blue77").status_code, 200)

    def test_weak_password_and_duplicate_email_are_refused(self):
        res = self.register(password="12345678")
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data)
        self.assertEqual(self.register(password="password").status_code, 400)
        self.assertEqual(self.register().status_code, 201)
        # Registering again must not take over the existing account
        res = self.register(phone="", password="Another#Pass91")
        self.assertEqual(res.status_code, 400)
        self.assertIn("already exists", res.data["error"])
        self.assertEqual(self.login("meera@example.com", "Another#Pass91").status_code, 400)

    def test_same_message_for_unknown_account_and_wrong_password(self):
        self.register()
        wrong = self.login("meera@example.com", "nope-nope")
        unknown = self.login("nobody@example.com", "nope-nope")
        self.assertEqual((wrong.status_code, unknown.status_code), (400, 400))
        self.assertEqual(wrong.data["error"], unknown.data["error"])

    def test_lockout_after_five_wrong_passwords(self):
        self.register()
        for _ in range(5):
            self.login("meera@example.com", "wrong-guess")
        res = self.login("meera@example.com", "Garage#Blue77")
        self.assertEqual(res.status_code, 429)
        user = User.objects.get(email="meera@example.com")
        user.password_locked_until = timezone.now() - timedelta(seconds=1)
        user.save()
        self.assertEqual(self.login("meera@example.com", "Garage#Blue77").status_code, 200)

    def test_account_without_password_can_set_one(self):
        otp_user = User.objects.create(email="otp@example.com", username="otp_user", role=UserRole.CUSTOMER)
        self.assertEqual(self.login("otp@example.com", "").status_code, 400)
        self.client.force_authenticate(user=otp_user)
        self.assertFalse(self.client.get("/api/auth/me/").data["has_password"])
        res = self.client.post("/api/auth/change-password/", {"new_password": "Fresh#Start42"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        # Now a current password is required
        res = self.client.post("/api/auth/change-password/", {"current_password": "bad", "new_password": "Other#Pass55"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.login("otp@example.com", "Fresh#Start42").status_code, 200)


@override_settings(OTP_BYPASS=False)
class RoleSignInTabTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.driver = User.objects.create_user(username="tab_d", email="tab_d@example.com", role=UserRole.DRIVER, password="Road#Runner42")
        self.superuser = User.objects.create_user(
            username="tab_s", email="tab_s@example.com", role=UserRole.CUSTOMER, password="Root#Power42", is_superuser=True
        )

    def login(self, email, password, role=None):
        body = {"identifier": email, "password": password}
        if role:
            body["role"] = role
        return self.client.post("/api/auth/login/", body, format="json")

    def test_matching_tab_signs_in(self):
        self.assertEqual(self.login("tab_d@example.com", "Road#Runner42", "DRIVER").status_code, 200)
        self.assertEqual(self.login("tab_d@example.com", "Road#Runner42").status_code, 200)  # no tab given

    def test_wrong_tab_is_refused_with_the_right_tab(self):
        res = self.login("tab_d@example.com", "Road#Runner42", "CUSTOMER")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["account_role"], UserRole.DRIVER)
        self.assertNotIn("access", res.data)

    def test_wrong_password_on_wrong_tab_reveals_nothing(self):
        res = self.login("tab_d@example.com", "not-it", "CUSTOMER")
        self.assertEqual((res.status_code, res.data["error"]), (400, "Invalid email or password."))
        self.assertNotIn("account_role", res.data)

    def test_superuser_counts_as_admin(self):
        self.assertEqual(self.login("tab_s@example.com", "Root#Power42", "ADMIN").status_code, 200)
        self.assertEqual(self.login("tab_s@example.com", "Root#Power42", "CUSTOMER").data["account_role"], UserRole.ADMIN)


class GeocodingTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(user=User.objects.create_user(username="geo_c", email="geo_c@example.com"))

    def fake_urlopen(self, payload, calls):
        from io import BytesIO
        import json

        class Resp(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(request, timeout=None):
            calls.append(request.full_url)
            return Resp(json.dumps(payload).encode())

        return opener

    def test_search_returns_places_and_caches(self):
        from unittest import mock

        calls = []
        payload = [{"display_name": "Koramangala, Bengaluru, Karnataka, India", "lat": "12.9352", "lon": "77.6245"}]
        with mock.patch("api.geocoding_service.urllib.request.urlopen", self.fake_urlopen(payload, calls)):
            res = self.client.get("/api/location/search/?q=Koramangala")
            again = self.client.get("/api/location/search/?q=koramangala")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["results"][0], {"label": payload[0]["display_name"], "latitude": 12.9352, "longitude": 77.6245})
        self.assertEqual(again.data, res.data)
        self.assertEqual(len(calls), 1)  # second search served from the cache
        self.assertIn("countrycodes=in", calls[0])

    def test_reverse_and_validation(self):
        from unittest import mock

        calls = []
        with mock.patch("api.geocoding_service.urllib.request.urlopen", self.fake_urlopen({"display_name": "100 Feet Road, Indiranagar"}, calls)):
            res = self.client.get("/api/location/reverse/?lat=12.97841&lng=77.64081")
        self.assertEqual(res.data["address"], "100 Feet Road, Indiranagar")
        self.assertEqual(self.client.get("/api/location/reverse/?lat=abc&lng=1").status_code, 400)
        self.assertEqual(self.client.get("/api/location/reverse/?lat=95&lng=1").status_code, 400)
        self.assertEqual(self.client.get("/api/location/search/?q=ab").status_code, 400)

    def test_service_down_gives_a_friendly_502(self):
        from unittest import mock

        with mock.patch("api.geocoding_service.urllib.request.urlopen", side_effect=OSError("no network")):
            res = self.client.get("/api/location/search/?q=Whitefield")
        self.assertEqual(res.status_code, 502)
        self.assertIn("Move the map", res.data["error"])

    def test_requires_sign_in(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/location/search/?q=Whitefield").status_code, 401)


class RoutingTests(TestCase):
    """Road routes for the Track page come from OSRM through the backend, cached."""

    OSRM_REPLY = {
        "code": "Ok",
        "routes": [{
            "distance": 3412.7,
            "duration": 655.0,
            "geometry": {"type": "LineString", "coordinates": [[77.6408, 12.9784], [77.6412, 12.9750], [77.6245, 12.9352]]},
        }],
    }

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(user=User.objects.create_user(username="route_c", email="route_c@example.com"))

    fake_urlopen = GeocodingTests.fake_urlopen

    def test_route_follows_roads_and_is_cached(self):
        from unittest import mock

        calls = []
        with mock.patch("api.routing_service.urllib.request.urlopen", self.fake_urlopen(self.OSRM_REPLY, calls)):
            res = self.client.get("/api/location/route/?from=12.97841,77.64081&to=12.9352,77.6245")
            # GPS jitter of a few metres reuses the cached route
            again = self.client.get("/api/location/route/?from=12.97843,77.64079&to=12.9352,77.6245")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["coordinates"][0], [77.6408, 12.9784])
        self.assertEqual(len(res.data["coordinates"]), 3)
        self.assertEqual(res.data["distance_km"], 3.4)
        self.assertEqual(res.data["duration_min"], 11)
        self.assertEqual(again.data, res.data)
        self.assertEqual(len(calls), 1)
        # OSRM takes lng,lat pairs
        self.assertIn("/route/v1/driving/77.6408,12.9784;77.6245,12.9352?", calls[0])

    def test_validation(self):
        for query in ("", "from=12.9,77.6", "from=abc&to=12.9,77.6", "from=95,77.6&to=12.9,77.6", "from=12.9&to=12.9,77.6"):
            self.assertEqual(self.client.get(f"/api/location/route/?{query}").status_code, 400, query)

    def test_no_route_or_service_down_gives_502(self):
        from unittest import mock

        with mock.patch("api.routing_service.urllib.request.urlopen", self.fake_urlopen({"code": "NoRoute", "routes": []}, [])):
            self.assertEqual(self.client.get("/api/location/route/?from=12.97,77.64&to=12.93,77.62").status_code, 502)
        with mock.patch("api.routing_service.urllib.request.urlopen", side_effect=OSError("no network")):
            self.assertEqual(self.client.get("/api/location/route/?from=12.98,77.64&to=12.93,77.62").status_code, 502)

    def test_requires_sign_in(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/location/route/?from=12.97,77.64&to=12.93,77.62").status_code, 401)


class AutoAssignmentTests(TestCase):
    """Driver = nearest free driver, with a 3 km penalty per pickup already that day; mechanic = fewest open jobs."""

    def setUp(self):
        from datetime import date
        from api.models import Employee

        self.client = APIClient()
        self.day = date.today() + timedelta(days=2)
        # Workshop in Indiranagar; customer in Whitefield (about 12 km east)
        self.center = ServiceCenter.objects.create(
            name="AA Hub", address="Indiranagar", phone="+918000000020", email="aa@example.com", latitude=12.9784, longitude=77.6408
        )
        self.other_center = ServiceCenter.objects.create(name="AA Far", address="Yelahanka", phone="+918000000021", email="aa2@example.com")
        self.ops_admin = User.objects.create_user(username="aa_m", email="aa_m@example.com", role=UserRole.ADMIN)
        self.customer = User.objects.create_user(username="aa_c", email="aa_c@example.com", role=UserRole.CUSTOMER)
        self.vehicle = Vehicle.objects.create(customer=self.customer, brand="Tata", model="Tiago", registration_number="KA09AA01")

        def staff(name, role, center, employee_type, available=True):
            user = User.objects.create_user(username=name, email=f"{name}@example.com", role=role, first_name=name)
            Employee.objects.create(user=user, service_center=center, employee_type=employee_type, is_available=available)
            return user

        self.near = staff("near", UserRole.DRIVER, self.center, "VALET")
        self.far = staff("far", UserRole.DRIVER, self.center, "VALET")
        self.off = staff("off", UserRole.DRIVER, self.center, "VALET", available=False)
        self.elsewhere = staff("elsewhere", UserRole.DRIVER, self.other_center, "VALET")
        self.mech_busy = staff("mbusy", UserRole.MECHANIC, self.center, "MECHANIC")
        self.mech_free = staff("mfree", UserRole.MECHANIC, self.center, "MECHANIC")

        from api.models import DriverLocation

        self.booking = self.make_booking()
        # near: 1 km from the customer; far: back at the workshop (about 12 km)
        DriverLocation.objects.create(driver=self.near, booking=self.booking, latitude=12.9698, longitude=77.7400)
        DriverLocation.objects.create(driver=self.far, booking=self.booking, latitude=12.9784, longitude=77.6408)

    def make_booking(self, slot="09:00:00", **extra):
        return ServiceBooking.objects.create(
            customer=self.customer, vehicle=self.vehicle, service_center=self.center, pickup_address="Whitefield",
            pickup_latitude=12.9698, pickup_longitude=77.7499, preferred_date=self.day, preferred_time=slot,
            status=BookingStatus.PENDING, **extra,
        )

    def confirm(self, booking):
        self.client.force_authenticate(user=self.ops_admin)
        return self.client.patch(f"/api/service-center/bookings/{booking.id}/", {"status": "Confirmed"}, format="json")

    def test_confirm_picks_the_nearest_free_driver_and_least_busy_mechanic(self):
        self.make_booking(slot="14:00:00", assigned_mechanic=self.mech_busy)  # mbusy has an open job
        res = self.confirm(self.booking)
        self.assertEqual(res.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.assigned_driver, self.near)
        self.assertEqual(self.booking.assigned_mechanic, self.mech_free)
        self.assertEqual(res.data["auto_assigned"]["driver"]["name"], "near")
        self.assertTrue(Notification.objects.filter(user=self.near, notification_type="PICKUP_SCHEDULED").exists())

    def test_busy_slot_and_unavailable_drivers_are_skipped(self):
        self.make_booking(slot="09:00:00", assigned_driver=self.near)  # near already has a 9 AM pickup
        self.confirm(self.booking)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.assigned_driver, self.far)
        ranked = {r["name"]: r for r in self.client.get(f"/api/service-center/bookings/{self.booking.id}/staff-suggestions/").data["drivers"]}
        self.assertFalse(ranked["near"]["eligible"])
        self.assertIn("time slot", ranked["near"]["reason"])
        self.assertFalse(ranked["off"]["eligible"])
        self.assertNotIn("elsewhere", ranked)  # another center's driver is never offered

    def test_workload_penalty_beats_a_small_distance_advantage(self):
        # near (1 km) already has 4 pickups that day: 1 + 4 x 3 = 13 > far (~11.8 km, 0 pickups)
        for slot in ["11:00:00", "14:00:00", "16:00:00", "17:00:00"]:
            self.make_booking(slot=slot, assigned_driver=self.near)
        self.confirm(self.booking)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.assigned_driver, self.far)

    def test_admins_choice_is_kept(self):
        self.client.force_authenticate(user=self.ops_admin)
        res = self.client.patch(
            f"/api/service-center/bookings/{self.booking.id}/", {"status": "Confirmed", "assigned_driver_id": self.far.id}, format="json"
        )
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.assigned_driver, self.far)
        self.assertNotIn("driver", res.data["auto_assigned"])

    def test_suggestions_are_admin_only(self):
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.client.get(f"/api/service-center/bookings/{self.booking.id}/staff-suggestions/").status_code, 403)


class StaffManagementTests(TestCase):
    """Admins add drivers and mechanics to a center; staff then sign in."""

    PASSWORD = "Valet-Route-2048"

    def setUp(self):
        from api.models import Employee

        self.center = ServiceCenter.objects.create(name="SM Central", address="Indiranagar", phone="+918000000031", email="sm1@example.com")
        self.other = ServiceCenter.objects.create(name="SM North", address="Yelahanka", phone="+918000000032", email="sm2@example.com")
        self.admin = User.objects.create_user(username="sm_a", email="sm_a@example.com", role=UserRole.ADMIN)
        self.ops_admin = User.objects.create_user(username="sm_m", email="sm_m@example.com", role=UserRole.ADMIN)
        self.customer = User.objects.create_user(username="sm_c", email="sm_c@example.com", role=UserRole.CUSTOMER)
        self.client = APIClient()

    def add(self, user, **extra):
        self.client.force_authenticate(user=user)
        data = {"name": "Ravi Kumar", "email": "ravi@example.com", "phone": "9876500001", "password": self.PASSWORD, "role": "DRIVER",
                "service_center": self.center.id, **extra}
        return self.client.post("/api/staff/", data, format="json")

    def test_admin_adds_a_driver_who_can_then_sign_in(self):
        res = self.add(self.admin, service_center=self.other.id)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["role"], UserRole.DRIVER)
        self.assertEqual(res.data["service_center"]["id"], self.other.id)
        self.assertEqual(res.data["phone"], "+919876500001")
        self.assertTrue(res.data["is_available"])

        self.client.force_authenticate(user=None)
        login = self.client.post("/api/auth/login/", {"identifier": "ravi@example.com", "password": self.PASSWORD, "role": "DRIVER"}, format="json")
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn("access", login.data)

    def test_admin_chooses_the_center_and_can_add_mechanics(self):
        no_center = self.add(self.admin, role="MECHANIC", service_center="")
        self.assertEqual(no_center.status_code, 400)
        self.assertFalse(User.objects.filter(email="ravi@example.com").exists())
        res = self.add(self.admin, role="MECHANIC", service_center=self.other.id, speciality="AC and electricals")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["service_center"]["name"], "SM North")
        self.assertEqual(res.data["speciality"], "AC and electricals")

    def test_validation(self):
        self.assertEqual(self.add(self.ops_admin, role="ADMIN").status_code, 400)  # only drivers and mechanics
        self.assertEqual(self.add(self.ops_admin, role="SERVICE_CENTER_MANAGER").status_code, 400)
        self.assertEqual(self.add(self.ops_admin, password="12345678").status_code, 400)  # Django password rules
        self.assertEqual(self.add(self.ops_admin, email="sm_c@example.com").status_code, 400)  # email taken
        self.assertEqual(self.add(self.ops_admin, phone="12").status_code, 400)

    def test_only_admins(self):
        self.assertEqual(self.add(self.customer).status_code, 403)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/staff/").status_code, 401)

    def test_admin_sees_all_staff_and_can_take_one_off_duty(self):
        mine = self.add(self.admin).data
        self.add(self.admin, email="far@example.com", phone="9876500002", service_center=self.other.id)
        self.assertEqual(len(self.client.get("/api/staff/").data), 2)
        off = self.client.patch(f"/api/staff/{mine['id']}/", {"is_available": False}, format="json")
        self.assertEqual(off.status_code, 200)
        self.assertFalse(off.data["is_available"])
        # A driver cannot manage staff
        self.client.force_authenticate(user=User.objects.get(pk=mine["id"]))
        self.assertEqual(self.client.get("/api/staff/").status_code, 403)
        self.assertEqual(self.client.patch(f"/api/staff/{mine['id']}/", {"is_available": True}, format="json").status_code, 403)


class AvatarTests(TestCase):
    """Profile photos: resized to a square JPEG, stored in the database, served by token."""

    def setUp(self):
        self.user = User.objects.create_user(username="av_u", email="av_u@example.com", role=UserRole.CUSTOMER)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def photo(self, size=(800, 600), fmt="JPEG", exif=None, name="me.jpg", color=(200, 30, 30)):
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buf = BytesIO()
        mode = "RGBA" if fmt == "PNG" else "RGB"
        Image.new(mode, size, color).save(buf, format=fmt, **({"exif": exif} if exif else {}))
        return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")

    def upload(self, file):
        return self.client.post("/api/auth/avatar/", {"photo": file}, format="multipart")

    def test_upload_resizes_strips_location_and_serves_by_token(self):
        from io import BytesIO
        from PIL import Image

        # A phone photo taken sideways, with its GPS position in the EXIF data
        exif = Image.Exif()
        exif[0x0112] = 6  # orientation: rotate 90 degrees
        exif[0x8825] = {1: "N", 2: (12.0, 58.0, 0.0), 3: "E", 4: (77.0, 38.0, 0.0)}  # GPS
        res = self.upload(self.photo(size=(800, 600), exif=exif))
        self.assertEqual(res.status_code, 200, res.data)
        url = res.data["avatar_url"]
        self.assertRegex(url, r"^/api/avatars/[0-9a-f]{32}\.jpg$")

        self.client.force_authenticate(user=None)  # <img> tags load it without a token
        img = self.client.get(url)
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img["Content-Type"], "image/jpeg")
        stored = Image.open(BytesIO(b"".join(img.streaming_content) if img.streaming else img.content))
        self.assertEqual(stored.format, "JPEG")
        self.assertEqual(stored.size, (256, 256))
        self.assertEqual(len(stored.getexif()), 0)  # no GPS position, no orientation flag left
        self.assertLess(len(img.content), 40_000)

    def test_new_upload_changes_the_address_and_delete_removes_it(self):
        first = self.upload(self.photo()).data["avatar_url"]
        second = self.upload(self.photo(fmt="PNG", name="me.png")).data["avatar_url"]
        self.assertNotEqual(first, second)
        self.assertEqual(self.client.get(first).status_code, 404)
        self.assertEqual(self.client.get("/api/auth/me/").data["avatar_url"], second)

        res = self.client.delete("/api/auth/avatar/")
        self.assertIsNone(res.data["avatar_url"])
        self.assertEqual(self.client.get(second).status_code, 404)

    def test_rejects_files_that_are_not_photos(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.assertEqual(self.client.post("/api/auth/avatar/", {}, format="multipart").status_code, 400)
        fake = SimpleUploadedFile("me.jpg", b"not really an image", content_type="image/jpeg")
        res = self.upload(fake)
        self.assertEqual(res.status_code, 400)
        self.assertIn("isn't a photo", res.data["error"])
        gif = self.photo(fmt="GIF", name="me.gif")
        self.assertEqual(self.upload(gif).status_code, 400)
        big = SimpleUploadedFile("big.jpg", b"0" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")
        self.assertIn("too large", self.upload(big).data["error"])

    def test_requires_sign_in(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.upload(self.photo()).status_code, 401)


# ==========================================
# SIGN IN WITH GOOGLE (and "forgot password" through it)
# ==========================================
from google.auth import exceptions as google_exceptions
from rest_framework_simplejwt.tokens import AccessToken
from api import google_auth_service
from api.google_auth_service import GoogleSignInError, GoogleUnavailableError
from api.models import CustomerProfile


def google_claims(email="meera@gmail.com", **extra):
    return {"email": email, "email_verified": True, "given_name": "Meera", "family_name": "Nair", **extra}


@override_settings(OTP_BYPASS=False, GOOGLE_CLIENT_ID="test-client.apps.googleusercontent.com")
class GoogleSignInTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def google(self, claims=None, role=None, error=None):
        body = {"credential": "google-id-token"}
        if role:
            body["role"] = role
        with patch("api.views.verify_google_credential", side_effect=error, return_value=claims or google_claims()) as verify:
            res = self.client.post("/api/auth/google/", body, format="json")
        if error is None:
            verify.assert_called_once_with("google-id-token", "test-client.apps.googleusercontent.com")
        return res

    def test_new_google_user_becomes_a_customer_without_password(self):
        res = self.google()
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        user = User.objects.get(email="meera@gmail.com")
        self.assertEqual(user.role, UserRole.CUSTOMER)
        self.assertEqual(user.get_full_name(), "Meera Nair")
        self.assertTrue(user.is_verified)
        self.assertFalse(user.has_password())
        self.assertFalse(res.data["user"]["has_password"])
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())
        self.assertIn("access", res.data)

    def test_existing_account_signs_in_by_email_and_lockout_is_cleared(self):
        user = User.objects.create_user(username="meera", email="Meera@Gmail.com", password="Garage#Blue77", role=UserRole.CUSTOMER)
        user.password_attempts = 3
        user.password_locked_until = timezone.now() + timedelta(minutes=10)
        user.save()
        res = self.google()
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["user"]["id"], user.id)
        self.assertEqual(User.objects.filter(email__iexact="meera@gmail.com").count(), 1)
        user.refresh_from_db()
        self.assertIsNone(user.password_locked_until)
        self.assertTrue(user.check_password("Garage#Blue77"))  # password unchanged

    def test_staff_account_on_wrong_tab_is_pointed_to_its_tab(self):
        User.objects.create_user(username="drv", email="driver1@gmail.com", role=UserRole.DRIVER)
        res = self.google(google_claims("driver1@gmail.com"), role="CUSTOMER")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data["account_role"], UserRole.DRIVER)
        self.assertEqual(self.google(google_claims("driver1@gmail.com"), role="DRIVER").status_code, status.HTTP_200_OK)

    def test_google_cannot_create_staff_accounts(self):
        res = self.google(google_claims("newdriver@gmail.com"), role="DRIVER")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="newdriver@gmail.com").exists())

    def test_disabled_account_is_refused(self):
        User.objects.create_user(username="gone", email="meera@gmail.com", role=UserRole.CUSTOMER, is_active=False)
        self.assertEqual(self.google().status_code, status.HTTP_403_FORBIDDEN)

    def test_bad_credential_and_google_outage(self):
        self.assertEqual(self.google(error=GoogleSignInError("expired")).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.google(error=GoogleUnavailableError("timeout")).status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(self.client.post("/api/auth/google/", {}, format="json").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())

    @override_settings(GOOGLE_CLIENT_ID="")
    def test_not_configured(self):
        res = self.client.post("/api/auth/google/", {"credential": "x"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIsNone(self.client.get("/api/health-check/").data["google_client_id"])

    def test_health_check_gives_the_frontend_the_client_id(self):
        self.assertEqual(self.client.get("/api/health-check/").data["google_client_id"], "test-client.apps.googleusercontent.com")

    def test_forgot_password_via_google_sets_a_new_password_without_the_old_one(self):
        User.objects.create_user(username="meera", email="meera@gmail.com", password="Garage#Blue77", role=UserRole.CUSTOMER)
        token = self.google().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = self.client.post("/api/auth/change-password/", {"new_password": "Brand#New2026"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.client.credentials()
        login = self.client.post("/api/auth/login/", {"identifier": "meera@gmail.com", "password": "Brand#New2026"}, format="json")
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_password_sign_in_or_old_google_sign_in_still_needs_the_current_password(self):
        User.objects.create_user(username="meera", email="meera@gmail.com", password="Garage#Blue77", role=UserRole.CUSTOMER)
        password_token = self.client.post(
            "/api/auth/login/", {"identifier": "meera@gmail.com", "password": "Garage#Blue77"}, format="json"
        ).data["access"]
        stale = AccessToken(self.google().data["access"])
        stale["google_signin_at"] = int((timezone.now() - timedelta(minutes=16)).timestamp())
        for token in (password_token, str(stale)):
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            res = self.client.post("/api/auth/change-password/", {"new_password": "Brand#New2026"}, format="json")
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("current password", res.data["error"])

    def test_otp_sign_in_endpoints_are_gone(self):
        for path in ["/api/auth/send-otp/", "/api/auth/verify-otp/", "/api/auth/password-reset/request/",
                     "/api/auth/password-reset/confirm/"]:
            self.assertEqual(self.client.post(path, {"identifier": "a@b.com"}, format="json").status_code, 404, path)


class GoogleCredentialVerificationTests(TestCase):
    """The checks around google-auth's own signature/expiry/audience verification."""

    def verify(self, claims=None, error=None):
        with patch.object(google_auth_service.id_token, "verify_oauth2_token", side_effect=error, return_value=claims) as v:
            result = google_auth_service.verify_google_credential("tok", "client-id")
        self.assertEqual(v.call_args.args[0], "tok")
        self.assertEqual(v.call_args.args[2], "client-id")  # audience = our client ID
        return result

    def test_verified_email_is_accepted(self):
        self.assertEqual(self.verify(google_claims())["email"], "meera@gmail.com")

    def test_unverified_or_missing_email_is_refused(self):
        with self.assertRaises(GoogleSignInError):
            self.verify(google_claims(email_verified=False))
        with self.assertRaises(GoogleSignInError):
            self.verify({"email_verified": True})

    def test_invalid_token_and_network_failure(self):
        with self.assertRaises(GoogleSignInError):
            self.verify(error=ValueError("Token used too late"))
        with self.assertRaises(GoogleUnavailableError):
            self.verify(error=google_exceptions.TransportError("no route"))


# ==========================================
# CONTACT NUMBER, COUPONS, RESCHEDULING
# ==========================================
import hashlib
import hmac
import json
from decimal import Decimal
from api.models import Coupon, PushSubscription, Payment, Notification
from api import push_service, razorpay_service
from api.invoice_service import generate_invoice_for_booking


class BookingExtrasTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username="bx", email="bx@example.com", role=UserRole.CUSTOMER)
        self.ops_admin = User.objects.create_user(username="bxm", email="bxm@example.com", role=UserRole.ADMIN)
        self.center = ServiceCenter.objects.create(
            user=self.ops_admin, name="BX Center", address="MG Road", phone="+918000000009", email="bxc@example.com", slot_capacity=1
        )
        self.st = ServiceType.objects.create(name="BX Service", base_price=2000)
        self.vehicle = Vehicle.objects.create(customer=self.customer, brand="Tata", model="Nexon", registration_number="KA05BX0001")
        self.client.force_authenticate(user=self.customer)

    def book(self, **extra):
        body = {
            "vehicle": self.vehicle.id, "service_type": self.st.id, "service_center": self.center.id,
            "pickup_address": "Koramangala", "preferred_date": FUTURE_DATE, "preferred_time": "09:00:00", **extra,
        }
        return self.client.post("/api/bookings/", body, format="json")

    # --- contact number
    def test_booking_needs_a_number_the_driver_can_call(self):
        res = self.book()
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["field"], "contact_phone")
        self.assertEqual(self.book(contact_phone="12345").status_code, 400)
        self.assertEqual(self.book(contact_phone="5845012345").status_code, 400)  # Indian mobiles start 6-9
        self.assertFalse(ServiceBooking.objects.exists())

    def test_confirmed_number_is_normalised_shown_to_staff_and_saved_to_an_empty_profile(self):
        res = self.book(contact_phone="98450 12345")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["contact_phone"], "+919845012345")
        self.assertEqual(res.data["customer_phone"], "+919845012345")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.phone, "+919845012345")

    def test_profile_number_is_used_when_none_is_sent_and_a_different_one_does_not_overwrite_it(self):
        self.customer.phone = "+919845000077"
        self.customer.save()
        self.assertEqual(self.book().data["contact_phone"], "+919845000077")
        ServiceBooking.objects.all().delete()
        res = self.book(contact_phone="9845099999")
        self.assertEqual(res.data["customer_phone"], "+919845099999")
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.phone, "+919845000077")

    # --- coupons
    def coupon(self, **kw):
        return Coupon.objects.create(**{"code": "welcome10", "discount_type": "PERCENT", "value": 10, **kw})

    def check(self, code):
        return self.client.post("/api/coupons/check/", {"code": code, "service_type": self.st.id}, format="json")

    def test_percent_coupon_with_cap_and_flat_coupon(self):
        self.coupon(max_discount=150)
        Coupon.objects.create(code="FLAT500", discount_type="FLAT", value=500)
        res = self.check(" Welcome10 ")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Decimal(res.data["discount"]), Decimal("150.00"))  # 10% of 2000 = 200, capped
        self.assertEqual(Decimal(self.check("flat500").data["final_price"]), Decimal("1500.00"))
        self.assertEqual(self.check("NOPE").status_code, 400)

    def test_coupon_rules(self):
        today = timezone.localdate()
        Coupon.objects.create(code="OLD", value=10, valid_until=today - timedelta(days=1))
        Coupon.objects.create(code="SOON", value=10, valid_from=today + timedelta(days=1))
        Coupon.objects.create(code="BIG", value=10, min_order=5000)
        Coupon.objects.create(code="OFF", value=10, active=False)
        Coupon.objects.create(code="HUGE", discount_type="FLAT", value=9999)
        for code, text in [("OLD", "expired"), ("SOON", "not active yet"), ("BIG", "or more"), ("OFF", "not valid")]:
            res = self.check(code)
            self.assertEqual(res.status_code, 400, code)
            self.assertIn(text, res.data["error"])
        self.assertEqual(Decimal(self.check("HUGE").data["final_price"]), Decimal("0.00"))  # never below zero

    def test_coupon_is_applied_to_the_booking_and_invoice_and_used_once_per_customer(self):
        self.coupon()
        res = self.book(contact_phone="9845012345", coupon_code="WELCOME10")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["coupon_code"], "WELCOME10")
        self.assertEqual(Decimal(res.data["coupon_discount"]), Decimal("200.00"))

        booking = ServiceBooking.objects.get(pk=res.data["id"])
        booking.status = BookingStatus.COMPLETED
        booking.save()
        invoice = generate_invoice_for_booking(booking)
        self.assertEqual(invoice.discount, Decimal("200.00"))
        self.assertEqual(invoice.tax, Decimal("324.00"))          # 18% of (2000 - 200)
        self.assertEqual(invoice.grand_total, Decimal("2124.00"))
        self.assertEqual(sum(i.total_price for i in invoice.items.all()), invoice.grand_total)

        # Second use by the same customer is refused, and no booking is created
        self.center.slot_capacity = 5
        self.center.save()
        again = self.book(contact_phone="9845012345", coupon_code="WELCOME10")
        self.assertEqual(again.status_code, 400)
        self.assertEqual(again.data["field"], "coupon_code")
        self.assertEqual(ServiceBooking.objects.count(), 1)

    def test_total_usage_limit_and_cancelled_booking_gives_the_use_back(self):
        self.coupon(usage_limit=1, per_customer_limit=0)
        self.center.slot_capacity = 5
        self.center.save()
        first = self.book(contact_phone="9845012345", coupon_code="WELCOME10")
        self.assertEqual(first.status_code, 201)
        self.assertIn("fully used", self.book(contact_phone="9845012345", coupon_code="WELCOME10").data["error"])
        self.client.patch(f"/api/bookings/{first.data['id']}/", {"status": "Cancelled"}, format="json")
        self.assertEqual(self.book(contact_phone="9845012345", coupon_code="WELCOME10").status_code, 201)

    def test_customer_cannot_set_the_discount_directly(self):
        res = self.book(contact_phone="9845012345", coupon_discount="1999")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Decimal(res.data["coupon_discount"]), Decimal("0.00"))
        patch_res = self.client.patch(f"/api/bookings/{res.data['id']}/", {"coupon_discount": "1999"}, format="json")
        self.assertEqual(patch_res.status_code, 400)

    # --- rescheduling
    def test_reschedule_notifies_customer_and_admin(self):
        booking_id = self.book(contact_phone="9845012345").data["id"]
        Notification.objects.all().delete()
        new_day = (timezone.localdate() + timedelta(days=3)).isoformat()
        res = self.client.patch(f"/api/bookings/{booking_id}/", {"preferred_date": new_day, "preferred_time": "14:00:00"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["preferred_date"], new_day)
        titles = {(n.user_id, n.title) for n in Notification.objects.all()}
        self.assertEqual(titles, {(self.customer.id, "Pickup rescheduled"), (self.ops_admin.id, "Pickup rescheduled")})
        self.assertIn("02:00 PM - 04:00 PM", Notification.objects.filter(user=self.customer).first().message)

    def test_editing_only_the_address_sends_no_reschedule_notice(self):
        booking_id = self.book(contact_phone="9845012345").data["id"]
        Notification.objects.all().delete()
        self.client.patch(f"/api/bookings/{booking_id}/", {"pickup_address": "HSR Layout"}, format="json")
        self.assertFalse(Notification.objects.filter(title="Pickup rescheduled").exists())


# ==========================================
# RAZORPAY PAYMENTS
# ==========================================
RZP = dict(PAYMENT_GATEWAY="razorpay", RAZORPAY_KEY_ID="rzp_test_key", RAZORPAY_KEY_SECRET="rzp_secret", RAZORPAY_WEBHOOK_SECRET="hook_secret")


@override_settings(**RZP)
class RazorpayPaymentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username="rz", email="rz@example.com", role=UserRole.CUSTOMER, phone="+919845000010")
        self.other = User.objects.create_user(username="rz2", email="rz2@example.com", role=UserRole.CUSTOMER)
        self.ops_admin = User.objects.create_user(username="rzm", email="rzm@example.com", role=UserRole.ADMIN)
        center = ServiceCenter.objects.create(user=self.ops_admin, name="RZ", address="x", phone="+918000000008", email="rzc@example.com")
        st = ServiceType.objects.create(name="RZ Service", base_price=1000)
        vehicle = Vehicle.objects.create(customer=self.customer, brand="Tata", model="Nexon", registration_number="KA05RZ0001")
        booking = ServiceBooking.objects.create(
            customer=self.customer, vehicle=vehicle, service_type=st, service_center=center,
            pickup_address="x", status=BookingStatus.COMPLETED,
        )
        self.invoice = generate_invoice_for_booking(booking)  # 1000 + 18% = 1180.00
        Notification.objects.all().delete()
        self.client.force_authenticate(user=self.customer)
        self.api_calls = []

    def fake_api(self, payment=None):
        """Stands in for Razorpay's REST API."""
        def api(method, path, body=None):
            self.api_calls.append((method, path, body))
            if (method, path) == ("POST", "/orders"):
                return {"id": "order_TEST1", "amount": body["amount"], "currency": body["currency"], "notes": body["notes"]}
            if method == "GET" and path.startswith("/payments/"):
                return payment
            if method == "GET" and path.startswith("/orders/"):
                return {"id": path.split("/")[-1], "notes": {}}
            if method == "POST" and path.endswith("/capture"):
                return {**payment, "status": "captured"}
            raise AssertionError(f"unexpected Razorpay call {method} {path}")
        return patch.object(razorpay_service, "_api", side_effect=api)

    def payment(self, **kw):
        return {"id": "pay_TEST1", "order_id": "order_TEST1", "amount": 118000, "currency": "INR",
                "status": "captured", "method": "upi", "vpa": "meera@okbank", **kw}

    def create_order(self):
        with self.fake_api():
            return self.client.post(f"/api/invoices/{self.invoice.id}/razorpay/order/")

    def verify(self, payment=None, signature=None, order_id="order_TEST1", payment_id="pay_TEST1"):
        if signature is None:
            signature = hmac.new(b"rzp_secret", f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        with self.fake_api(payment or self.payment()):
            return self.client.post(f"/api/invoices/{self.invoice.id}/razorpay/verify/", {
                "razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature,
            }, format="json")

    def webhook(self, event, payment, secret=b"hook_secret"):
        body = json.dumps({"event": event, "payload": {"payment": {"entity": payment}}}).encode()
        signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
        with self.fake_api(payment):
            return APIClient().post("/api/payments/razorpay/webhook/", body, content_type="application/json",
                                    HTTP_X_RAZORPAY_SIGNATURE=signature)

    def test_order_is_created_for_the_invoice_total_in_paise(self):
        res = self.create_order()
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["order_id"], "order_TEST1")
        self.assertEqual(res.data["amount"], 118000)
        self.assertEqual(res.data["key_id"], "rzp_test_key")
        self.assertNotIn("rzp_secret", json.dumps(res.data))
        self.assertEqual(self.api_calls[0][2]["notes"]["invoice_id"], str(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.razorpay_order_id, "order_TEST1")

    def test_only_the_invoice_customer_can_create_an_order(self):
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.create_order().status_code, 403)

    def test_verified_checkout_marks_the_invoice_paid(self):
        self.create_order()
        res = self.verify()
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["invoice"]["payment_status"], "PAID")
        payment = Payment.objects.get()
        self.assertEqual((payment.transaction_id, payment.provider, payment.method, payment.payer_reference),
                         ("pay_TEST1", "RAZORPAY", "UPI", "meera@okbank"))
        self.assertEqual(payment.amount, Decimal("1180.00"))
        self.assertTrue(Notification.objects.filter(user=self.ops_admin, title="Invoice paid").exists())

    def test_wrong_signature_is_refused_without_calling_razorpay(self):
        self.create_order()
        self.api_calls.clear()
        res = self.verify(signature="0" * 64)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.api_calls, [])
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_status, "PENDING")

    def test_payment_for_another_order_or_wrong_amount_does_not_mark_paid(self):
        self.create_order()
        # A validly signed pair whose payment actually belongs to a different order
        res = self.verify(payment=self.payment(order_id="order_OTHER"))
        self.assertEqual(res.status_code, 400)
        # A validly signed pair for an order that isn't this invoice's
        res = self.verify(payment=self.payment(order_id="order_OTHER"), order_id="order_OTHER")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Payment.objects.exists())
        # Right order, but less money than the invoice total
        res = self.verify(payment=self.payment(amount=100))
        self.assertEqual(res.status_code, 402)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_status, "PENDING")
        self.assertIn("Needs review", Payment.objects.get().failure_reason)
        self.assertTrue(Notification.objects.filter(user=self.ops_admin, title="Payment needs review").exists())

    def test_another_customer_cannot_confirm_this_invoice(self):
        self.create_order()
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.verify().status_code, 403)

    def test_authorized_payment_is_captured(self):
        self.create_order()
        res = self.verify(payment=self.payment(status="authorized", method="card", card={"last4": "1111"}))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn(("POST", "/payments/pay_TEST1/capture", {"amount": 118000, "currency": "INR"}), self.api_calls)
        self.assertEqual(Payment.objects.get().payer_reference, "Card ending 1111")

    def test_webhook_marks_paid_and_is_idempotent_with_checkout(self):
        self.create_order()
        self.assertEqual(self.webhook("payment.captured", self.payment()).data["status"], "recorded")
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_status, "PAID")
        # The browser confirming the same payment afterwards, and a repeated webhook, change nothing
        self.assertEqual(self.verify().status_code, 200)
        self.webhook("payment.captured", self.payment())
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.customer, title="Payment successful").count(), 1)

    def test_webhook_with_bad_signature_or_unknown_event(self):
        self.create_order()
        self.assertEqual(self.webhook("payment.captured", self.payment(), secret=b"guess").status_code, 400)
        self.assertEqual(self.webhook("refund.created", self.payment()).data["status"], "ignored")
        self.assertFalse(Payment.objects.exists())

    def test_failed_payment_is_recorded_and_a_later_success_still_pays(self):
        self.create_order()
        self.webhook("payment.failed", self.payment(id="pay_FAIL", status="failed", error_description="Bank declined"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_status, "FAILED")
        self.assertEqual(Payment.objects.get().failure_reason, "Bank declined")
        self.assertEqual(self.verify().status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_status, "PAID")

    def test_second_payment_on_a_paid_invoice_is_flagged_for_refund(self):
        self.create_order()
        self.verify()
        self.webhook("payment.captured", self.payment(id="pay_TEST2"))
        self.assertIn("paid twice", Payment.objects.get(transaction_id="pay_TEST2").failure_reason)
        self.assertTrue(Notification.objects.filter(user=self.ops_admin, title="Payment needs review").exists())

    def test_mock_endpoint_is_closed_when_razorpay_is_the_gateway(self):
        res = self.client.post(f"/api/invoices/{self.invoice.id}/pay/", {"method": "UPI", "upi_id": "a@okbank"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_status, "PENDING")

    @override_settings(PAYMENT_GATEWAY="mock")
    def test_razorpay_endpoints_are_off_with_another_gateway(self):
        self.assertEqual(self.client.post(f"/api/invoices/{self.invoice.id}/razorpay/order/").status_code, 503)

    @override_settings(RAZORPAY_KEY_SECRET="")
    def test_missing_keys_give_a_clear_error(self):
        res = self.client.post(f"/api/invoices/{self.invoice.id}/razorpay/order/")
        self.assertEqual(res.status_code, 503)
        self.assertIn("not set up", res.data["error"])


# ==========================================
# BROWSER PUSH NOTIFICATIONS
# ==========================================
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import jwt as pyjwt

VAPID = push_service.generate_vapid_keys()


def browser_keys():
    """What a browser creates when it subscribes: a P-256 key pair and a 16-byte secret."""
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth = b"0123456789abcdef"
    return key, push_service.b64url_encode(public), push_service.b64url_encode(auth), public, auth


def browser_decrypt(body, key, public, auth):
    """The receiving side of RFC 8291, written from the spec independently of encrypt_payload."""
    salt, record_size, id_len = body[:16], int.from_bytes(body[16:20], "big"), body[20]
    sender_public = body[21:21 + id_len]
    ciphertext = body[21 + id_len:]
    shared = key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), sender_public))

    def hkdf(salt_, ikm_, info, length):
        return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt_, info=info).derive(ikm_)

    ikm = hkdf(auth, shared, b"WebPush: info\x00" + public + sender_public, 32)
    cek = hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    plain = AESGCM(cek).decrypt(nonce, ciphertext, None)
    assert record_size == 4096 and id_len == 65 and plain.endswith(b"\x02")
    return plain[:-1]


@override_settings(VAPID_PUBLIC_KEY=VAPID["public"], VAPID_PRIVATE_KEY=VAPID["private"], VAPID_CONTACT_EMAIL="ops@example.com")
class PushNotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="pu", email="pu@example.com", role=UserRole.CUSTOMER)
        self.client.force_authenticate(user=self.user)
        self.key, self.p256dh, self.auth, self.public, self.auth_raw = browser_keys()
        self.endpoint = "https://fcm.googleapis.com/fcm/send/abc123"

    def subscribe(self, **kw):
        body = {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}, **kw}
        return self.client.post("/api/push/subscription/", body, format="json")

    def test_message_round_trips_through_the_browser_side_decryption(self):
        text = "नमस्ते: driver arriving"
        body = push_service.encrypt_payload(text.encode(), self.p256dh, self.auth)
        self.assertEqual(browser_decrypt(body, self.key, self.public, self.auth_raw).decode(), text)
        # Fresh salt and sender key every time
        self.assertNotEqual(body, push_service.encrypt_payload(text.encode(), self.p256dh, self.auth))

    def test_subscribe_send_and_unsubscribe(self):
        self.assertEqual(self.subscribe().status_code, 201)
        self.assertEqual(self.subscribe().status_code, 201)  # same browser again: still one row
        self.assertEqual(PushSubscription.objects.count(), 1)

        with patch.object(push_service.requests, "post") as post:
            post.return_value.status_code = 201
            self.assertEqual(push_service.deliver(self.user.id, "Driver assigned", "Ravi is on the way", "/app/track"), 1)
        url = post.call_args.args[0]
        headers, data = post.call_args.kwargs["headers"], post.call_args.kwargs["data"]
        self.assertEqual(url, self.endpoint)
        self.assertEqual(headers["Content-Encoding"], "aes128gcm")
        message = json.loads(browser_decrypt(data, self.key, self.public, self.auth_raw))
        self.assertEqual(message, {"title": "Driver assigned", "body": "Ravi is on the way", "url": "/app/track"})

        # VAPID: a token signed with our private key, for the push service's origin
        scheme, rest = headers["Authorization"].split(" ", 1)
        fields = dict(part.strip().split("=", 1) for part in rest.split(","))
        self.assertEqual((scheme, fields["k"]), ("vapid", VAPID["public"]))
        public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), push_service.b64url_decode(VAPID["public"]))
        claims = pyjwt.decode(fields["t"], public_key, algorithms=["ES256"], audience="https://fcm.googleapis.com")
        self.assertEqual(claims["sub"], "mailto:ops@example.com")

        self.client.delete("/api/push/subscription/", {"endpoint": self.endpoint}, format="json")
        self.assertFalse(PushSubscription.objects.exists())

    def test_expired_subscription_is_removed_and_errors_do_not_escape(self):
        self.subscribe()
        with patch.object(push_service.requests, "post", side_effect=OSError("network down")):
            self.assertEqual(push_service.deliver(self.user.id, "t", "m", "/"), 0)
        self.assertTrue(PushSubscription.objects.exists())
        with patch.object(push_service.requests, "post") as post:
            post.return_value.status_code = 410
            self.assertEqual(push_service.deliver(self.user.id, "t", "m", "/"), 0)
        self.assertFalse(PushSubscription.objects.exists())

    def test_notifications_are_pushed_with_the_right_page(self):
        from api.notification_service import send_notification
        self.subscribe()
        with patch("api.push_service.push_to_user") as push:
            send_notification(self.user, "REPAIR_APPROVAL_REQUIRED", "Approve repair", "Brake pads need replacing")
        push.assert_called_once_with(self.user, "Approve repair", "Brake pads need replacing", "/app/approvals")

    def test_invalid_subscriptions_are_refused(self):
        self.assertEqual(self.subscribe(endpoint="http://insecure.example/x").status_code, 400)
        self.assertEqual(self.subscribe(keys={"p256dh": "", "auth": ""}).status_code, 400)
        self.assertEqual(APIClient().post("/api/push/subscription/", {}, format="json").status_code, 401)

    def test_health_check_gives_the_browser_the_public_key(self):
        self.assertEqual(self.client.get("/api/health-check/").data["push_public_key"], VAPID["public"])
        with override_settings(VAPID_PRIVATE_KEY=""):
            self.assertIsNone(self.client.get("/api/health-check/").data["push_public_key"])
            self.assertEqual(self.subscribe().status_code, 503)


class GoogleClientIdSettingTests(TestCase):
    """GOOGLE_CLIENT_ID: empty = the project's client, "off" = disabled, anything else = that client."""

    def client_id_for(self, value):
        """The setting as a fresh process computes it with GOOGLE_CLIENT_ID set to `value` (None = unset)."""
        import os
        import subprocess
        import sys
        from django.conf import settings

        code = "import django; django.setup(); from django.conf import settings; print(settings.GOOGLE_CLIENT_ID)"
        env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings", "IGNORE_DOTENV": "1", "DEBUG": "True"}
        env.pop("GOOGLE_CLIENT_ID", None)
        if value is not None:
            env["GOOGLE_CLIENT_ID"] = value
        run = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True, cwd=settings.BASE_DIR)
        return run.stdout.strip()

    def test_default_off_and_override(self):
        project = self.client_id_for(None)
        self.assertRegex(project, r"^\d+-[a-z0-9]+\.apps\.googleusercontent\.com$")
        self.assertEqual(self.client_id_for(""), project)
        self.assertEqual(self.client_id_for("OFF"), "")
        self.assertEqual(self.client_id_for("mine.apps.googleusercontent.com"), "mine.apps.googleusercontent.com")


# ==========================================
# THE MANAGER ROLE IS RETIRED: ADMINS RUN THE SERVICE CENTERS
# ==========================================
@override_settings(OTP_BYPASS=False)
class RetiredManagerRoleTests(TestCase):
    PASSWORD = "Garage#Blue77"

    def setUp(self):
        self.client = APIClient()
        self.old_manager = User.objects.create_user(
            username="old_m", email="old_m@example.com", password=self.PASSWORD, role=UserRole.SERVICE_CENTER_MANAGER
        )
        self.admin = User.objects.create_user(username="ad", email="ad@example.com", password=self.PASSWORD, role=UserRole.ADMIN)

    def test_old_manager_account_cannot_sign_in_with_password_or_google(self):
        res = self.client.post("/api/auth/login/", {"identifier": "old_m@example.com", "password": self.PASSWORD}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertIn("no longer used", res.data["error"])
        self.assertNotIn("access", res.data)
        # A wrong password still gets the usual answer, so the message doesn't reveal the account
        wrong = self.client.post("/api/auth/login/", {"identifier": "old_m@example.com", "password": "nope"}, format="json")
        self.assertEqual(wrong.status_code, 400)
        with override_settings(GOOGLE_CLIENT_ID="cid"), patch(
            "api.views.verify_google_credential", return_value={"email": "old_m@example.com", "email_verified": True}
        ):
            google = self.client.post("/api/auth/google/", {"credential": "tok"}, format="json")
        self.assertEqual(google.status_code, 403)

    @override_settings(OTP_BYPASS=True)
    def test_demo_login_has_no_manager(self):
        res = self.client.post("/api/auth/bypass-login/", {"identifier": "old_m@example.com"}, format="json")
        self.assertEqual(res.status_code, 403)
        # Asking for a new manager demo account gives a customer instead
        res = self.client.post("/api/auth/bypass-login/", {"identifier": "new@example.com", "role": "SERVICE_CENTER_MANAGER"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(User.objects.get(email="new@example.com").role, UserRole.CUSTOMER)

    def test_old_manager_token_opens_nothing_and_admin_does_the_work(self):
        paths = ["/api/service-center/bookings/", "/api/service-center/analytics/", "/api/service-center/employees/",
                 "/api/staff/", "/api/invoices/"]
        self.client.force_authenticate(user=self.old_manager)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 403, path)
        self.client.force_authenticate(user=self.admin)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_staff_cannot_be_created_as_managers(self):
        center = ServiceCenter.objects.create(name="C", address="x", phone="+918000000077", email="c@example.com")
        self.client.force_authenticate(user=self.admin)
        res = self.client.post("/api/staff/", {
            "name": "New Manager", "email": "nm@example.com", "password": self.PASSWORD,
            "role": "SERVICE_CENTER_MANAGER", "service_center": center.id,
        }, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(User.objects.filter(email="nm@example.com").exists())

    def test_operational_alerts_go_to_every_active_admin(self):
        from api.notification_service import notify_admins
        inactive = User.objects.create_user(username="ad2", email="ad2@example.com", role=UserRole.ADMIN, is_active=False)
        notify_admins("GENERAL", "Payment needs review", "Invoice X was paid twice")
        self.assertTrue(Notification.objects.filter(user=self.admin, title="Payment needs review").exists())
        self.assertFalse(Notification.objects.filter(user__in=[inactive, self.old_manager]).exists())


class FaviconTests(TestCase):
    def test_backend_serves_the_logo_for_browser_tabs(self):
        res = self.client.get("/favicon.ico")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "image/x-icon")
        self.assertEqual(b"".join(res.streaming_content)[:4], b"\x00\x00\x01\x00")  # ICO file signature


# ==========================================
# PRODUCTION SETTINGS: SAFETY CHECKS AND DATABASE URL
# ==========================================
class ProductionSettingsTests(TestCase):
    GOOD = {
        "DEBUG": "False", "SECRET_KEY": "k" * 50, "ALLOWED_HOSTS": "app.example.com", "OTP_BYPASS": "False",
        "PAYMENT_GATEWAY": "", "DATABASE_URL": "postgres://u:p%40ss@db.example.com:5432/doorstep?sslmode=require",
    }

    def load(self, **env):
        """Loads the settings in a fresh process, the way a production server would."""
        import os
        import subprocess
        import sys
        from django.conf import settings

        code = (
            "import json, django; django.setup(); from django.conf import settings as s; d = s.DATABASES['default'];"
            "print(json.dumps({'engine': d['ENGINE'], 'name': str(d['NAME']), 'user': d['USER'], 'password': d['PASSWORD'],"
            " 'host': d['HOST'], 'port': d['PORT'], 'options': d.get('OPTIONS', {}), 'ssl': s.SECURE_SSL_REDIRECT,"
            " 'csrf': s.CSRF_TRUSTED_ORIGINS, 'cookie': s.SESSION_COOKIE_SECURE}))"
        )
        keep = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "PYTHONPATH", "VIRTUAL_ENV", "LANG")}
        full = {**keep, "DJANGO_SETTINGS_MODULE": "config.settings", "IGNORE_DOTENV": "1", **self.GOOD, **env}
        return subprocess.run([sys.executable, "-c", code], env=full, capture_output=True, text=True, cwd=settings.BASE_DIR)

    def test_good_production_settings_start_with_https_protections_and_the_database_url(self):
        run = self.load()
        self.assertEqual(run.returncode, 0, run.stderr[-600:])
        loaded = json.loads(run.stdout)
        self.assertEqual(loaded["engine"], "django.db.backends.postgresql")
        self.assertEqual((loaded["name"], loaded["user"], loaded["password"], loaded["host"], loaded["port"]),
                         ("doorstep", "u", "p@ss", "db.example.com", "5432"))
        self.assertEqual(loaded["options"], {"sslmode": "require"})
        self.assertTrue(loaded["ssl"] and loaded["cookie"])
        self.assertEqual(loaded["csrf"], ["https://app.example.com"])

    def test_unsafe_production_settings_refuse_to_start(self):
        for env, text in [
            ({"OTP_BYPASS": "True"}, "OTP_BYPASS is on"),
            ({"PAYMENT_GATEWAY": "mock"}, "marks invoices paid without any money"),
            ({"PAYMENT_GATEWAY": "razorpay"}, "needs RAZORPAY_KEY_ID"),
            ({"PAYMENT_GATEWAY": "paypal"}, "Unknown PAYMENT_GATEWAY"),
            ({"SECRET_KEY": "short"}, "SECRET_KEY is too short"),
            ({"ALLOWED_HOSTS": ""}, "ALLOWED_HOSTS is empty"),
            ({"DATABASE_URL": ""}, "The database is SQLite"),
            ({"DATABASE_URL": "oracle://x/y"}, "DATABASE_URL must start with"),
        ]:
            run = self.load(**env)
            self.assertNotEqual(run.returncode, 0, env)
            self.assertIn(text, run.stderr, env)

    def test_every_problem_is_listed_at_once_and_sqlite_can_be_allowed_for_a_demo(self):
        run = self.load(OTP_BYPASS="True", PAYMENT_GATEWAY="mock")
        self.assertIn("OTP_BYPASS is on", run.stderr)
        self.assertIn("PAYMENT_GATEWAY=mock", run.stderr)
        demo = self.load(DATABASE_URL="", ALLOW_SQLITE_IN_PRODUCTION="True")
        self.assertEqual(demo.returncode, 0, demo.stderr[-400:])

    def test_razorpay_with_keys_and_mysql_url(self):
        run = self.load(PAYMENT_GATEWAY="razorpay", RAZORPAY_KEY_ID="rzp_live_x", RAZORPAY_KEY_SECRET="s",
                        DATABASE_URL="mysql://root:pw@127.0.0.1:3306/doorstep")
        self.assertEqual(run.returncode, 0, run.stderr[-400:])
        loaded = json.loads(run.stdout)
        self.assertEqual(loaded["engine"], "django.db.backends.mysql")
        self.assertEqual(loaded["options"]["charset"], "utf8mb4")

    def test_development_is_not_restricted(self):
        run = self.load(DEBUG="True", OTP_BYPASS="True", PAYMENT_GATEWAY="mock", DATABASE_URL="", SECRET_KEY="", ALLOWED_HOSTS="")
        self.assertEqual(run.returncode, 0, run.stderr[-400:])
        loaded = json.loads(run.stdout)
        self.assertEqual(loaded["engine"], "django.db.backends.sqlite3")
        self.assertFalse(loaded["ssl"])  # no HTTPS redirect on localhost


# ==========================================
# REFUNDS
# ==========================================
class RefundTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username="rf", email="rf@example.com", role=UserRole.CUSTOMER, phone="+919845000020")
        self.admin = User.objects.create_user(username="rfa", email="rfa@example.com", role=UserRole.ADMIN)
        center = ServiceCenter.objects.create(name="RF", address="x", phone="+918000000018", email="rfc@example.com")
        st = ServiceType.objects.create(name="RF Service", base_price=1000)
        vehicle = Vehicle.objects.create(customer=self.customer, brand="Tata", model="Nexon", registration_number="KA05RF0001")
        booking = ServiceBooking.objects.create(
            customer=self.customer, vehicle=vehicle, service_type=st, service_center=center,
            pickup_address="x", status=BookingStatus.COMPLETED,
        )
        self.invoice = generate_invoice_for_booking(booking)  # 1180.00

    def paid(self, provider="MOCK", transaction_id="SDVPAY-1", **kw):
        payment = Payment.objects.create(
            invoice=self.invoice, customer=self.customer, amount=self.invoice.grand_total, method="UPI",
            status=Payment.Status.SUCCESS, provider=provider, transaction_id=transaction_id, **kw,
        )
        self.invoice.payment_status = "PAID"
        self.invoice.invoice_status = "PAID"
        self.invoice.save()
        return payment

    def refund(self, payment, user=None, reason="Customer cancelled after payment"):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.post(f"/api/payments/{payment.id}/refund/", {"reason": reason}, format="json")

    def test_admin_refunds_a_test_payment_and_the_invoice_cannot_be_paid_again(self):
        payment = self.paid()
        # A payment alert moments earlier must not swallow the refund alert (alerts of one type are
        # de-duplicated within a minute)
        Notification.objects.all().delete()
        from api.payment_service import notify_invoice_paid
        notify_invoice_paid(self.invoice, payment)
        res = self.refund(payment)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["payment"]["status"], "REFUNDED")
        self.assertTrue(res.data["payment"]["refund_id"].startswith("SDVREF-"))
        self.assertEqual((res.data["invoice"]["payment_status"], res.data["invoice"]["invoice_status"]), ("REFUNDED", "CANCELLED"))
        payment.refresh_from_db()
        self.assertEqual(payment.refunded_by, self.admin)
        self.assertEqual(payment.refund_reason, "Customer cancelled after payment")
        note = Notification.objects.get(user=self.customer, title="Refund issued")
        self.assertEqual(note.notification_type, "REFUND_ISSUED")
        self.assertIn("1,180.00", note.message)

        self.assertEqual(self.refund(payment).status_code, 409)  # not twice
        with override_settings(PAYMENT_GATEWAY="mock"):
            self.client.force_authenticate(user=self.customer)
            again = self.client.post(f"/api/invoices/{self.invoice.id}/pay/", {"method": "UPI", "upi_id": "a@okbank"}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_only_an_admin_can_refund_and_a_reason_is_required(self):
        payment = self.paid()
        driver = User.objects.create_user(username="rfd", email="rfd@example.com", role=UserRole.DRIVER)
        for user in (self.customer, driver):
            self.assertEqual(self.refund(payment, user=user).status_code, 403)
        self.assertEqual(self.refund(payment, reason=" ").status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.client.post("/api/payments/999999/refund/", {"reason": "none"}, format="json").status_code, 404)

    def test_failed_payment_cannot_be_refunded(self):
        failed = Payment.objects.create(invoice=self.invoice, customer=self.customer, amount=1180, method="UPI",
                                        status=Payment.Status.FAILED, provider="MOCK", transaction_id="SDVPAY-F")
        self.assertEqual(self.refund(failed).status_code, 400)

    @override_settings(**RZP)
    def test_razorpay_payment_is_refunded_through_razorpay_for_the_full_amount(self):
        payment = self.paid(provider="RAZORPAY", transaction_id="pay_LIVE1")
        with patch.object(razorpay_service, "_api", return_value={"id": "rfnd_TEST1", "status": "processed"}) as api:
            res = self.refund(payment)
        self.assertEqual(res.status_code, 200, res.data)
        method, path, body = api.call_args.args
        self.assertEqual((method, path, body["amount"]), ("POST", "/payments/pay_LIVE1/refund", 118000))
        self.assertEqual(res.data["payment"]["refund_id"], "rfnd_TEST1")

    @override_settings(**RZP)
    def test_nothing_changes_when_razorpay_refuses_the_refund(self):
        from api.payment_service import PaymentError
        payment = self.paid(provider="RAZORPAY", transaction_id="pay_LIVE2")
        with patch.object(razorpay_service, "_api", side_effect=PaymentError("The payment service refused the request. Please try again.", 502)):
            res = self.refund(payment)
        self.assertEqual(res.status_code, 502)
        payment.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual((payment.status, self.invoice.payment_status), (Payment.Status.SUCCESS, "PAID"))
        self.assertFalse(Notification.objects.filter(title="Refund issued").exists())

    def test_refunding_an_accidental_second_payment_leaves_the_invoice_paid(self):
        self.paid()
        extra = self.paid(transaction_id="SDVPAY-2", failure_reason="Needs review: invoice was paid twice.")
        res = self.refund(extra, reason="Paid twice")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["invoice"]["payment_status"], "PAID")


class SetUserRoleCommandTests(TestCase):
    def run_command(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("set_user_role", *args, stdout=out)
        return out.getvalue()

    def test_brings_back_a_retired_manager_as_admin_who_can_then_sign_in(self):
        User.objects.create_user(username="om", email="om@example.com", password="Garage#Blue77", role=UserRole.SERVICE_CENTER_MANAGER)
        out = self.run_command("OM@example.com", "admin")
        self.assertIn("SERVICE_CENTER_MANAGER -> ADMIN", out)
        self.assertIn("controls the whole platform", out)
        with override_settings(OTP_BYPASS=False):
            res = APIClient().post("/api/auth/login/", {"identifier": "om@example.com", "password": "Garage#Blue77", "role": "ADMIN"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)

    def test_demoting_a_superuser_really_removes_admin_powers(self):
        boss = User.objects.create_superuser(username="boss", email="boss@example.com", password="x")
        self.run_command("boss@example.com", "CUSTOMER")
        boss.refresh_from_db()
        self.assertEqual((boss.role, boss.is_superuser, boss.is_staff), (UserRole.CUSTOMER, False, False))
        self.assertTrue(hasattr(boss, "customer_profile"))

    def test_unknown_email_or_role_is_refused(self):
        from django.core.management.base import CommandError
        User.objects.create_user(username="u", email="u@example.com", role=UserRole.CUSTOMER)
        with self.assertRaisesMessage(CommandError, "No account uses"):
            self.run_command("nobody@example.com", "ADMIN")
        for bad in ("SERVICE_CENTER_MANAGER", "pilot"):
            with self.assertRaisesMessage(CommandError, "Unknown role"):
                self.run_command("u@example.com", bad)
