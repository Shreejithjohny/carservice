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

    def test_manager_permissions_and_assignments(self):
        manager = User.objects.create_user(username="mgr1", email="mgr1@example.com", role=UserRole.SERVICE_CENTER_MANAGER)
        driver = User.objects.create_user(username="drv1", email="drv1@example.com", role=UserRole.DRIVER)
        mechanic = User.objects.create_user(username="mech1", email="mech1@example.com", role=UserRole.MECHANIC)

        booking = ServiceBooking.objects.create(
            customer=self.user1,
            vehicle=self.vehicle1,
            service_type=self.service_type,
            service_center=self.service_center,
            pickup_address="Manager test address",
            preferred_date="2026-10-10",
        )

        # A manager not linked to any service center cannot manage bookings
        self.client.force_authenticate(user=manager)
        unlinked = self.client.patch(f"/api/service-center/bookings/{booking.id}/", {"status": "Confirmed"}, format="json")
        self.assertEqual(unlinked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/service-center/bookings/").status_code, status.HTTP_403_FORBIDDEN)

        self.service_center.user = manager
        self.service_center.save()
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
        self.manager = User.objects.create_user(
            username="p9_manager",
            email="p9_manager@example.com",
            phone="+919100000005",
            role=UserRole.SERVICE_CENTER_MANAGER,
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
            user=self.manager,
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
        self.client.force_authenticate(user=self.manager)
        res_early = self.client.post(f"/api/bookings/{booking.id}/generate-invoice/")
        self.assertEqual(res_early.status_code, status.HTTP_400_BAD_REQUEST)

        booking.status = BookingStatus.COMPLETED
        booking.save()

        # Customers, mechanics and drivers cannot generate invoices
        for outsider in (self.customer1, self.mechanic, self.driver):
            self.client.force_authenticate(user=outsider)
            res_forbidden = self.client.post(f"/api/bookings/{booking.id}/generate-invoice/")
            self.assertEqual(res_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.manager)
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

        # Manager sees their service center's invoices
        self.client.force_authenticate(user=self.manager)
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

        # 2. Manager confirms booking & assigns driver + mechanic
        self.client.force_authenticate(user=self.manager)
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

        # 8. Manager marks Completed
        self.client.force_authenticate(user=self.manager)
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
# TWILIO PROGRAMMABLE SMS OTP TESTS (10 CRITERIA)
# ==========================================
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.utils import timezone
from api.otp_service import normalize_phone_number, OTP_SMS_TEMPLATE


@override_settings(OTP_CONSOLE_FALLBACK=True)
class TwilioProgrammableSMSOTPTests(TestCase):
    def setUp(self):
        self.client = APIClient()

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

    @patch("twilio.rest.Client")
    def test_1_and_2_otp_request_and_sent_via_twilio(self, mock_twilio_client):
        # 1. OTP request works with Twilio credentials
        # 2. OTP is actually sent through Twilio
        mock_instance = MagicMock()
        mock_twilio_client.return_value = mock_instance
        mock_message = MagicMock()
        mock_message.sid = "SM_TEST_123456789"
        mock_instance.messages.create.return_value = mock_message

        with patch.dict("os.environ", {
            "TWILIO_ACCOUNT_SID": "AC_MOCK_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN": "MOCK_AUTH_TOKEN",
            "TWILIO_PHONE_NUMBER": "+15005550006"
        }):
            res = self.client.post(
                "/api/auth/send-otp/",
                {"identifier": "9876543210", "role": "CUSTOMER"},
                format="json"
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data["provider"], "twilio_sms")

            # Verify Twilio Client initialized with SID and Token
            mock_twilio_client.assert_called_once_with("AC_MOCK_ACCOUNT_SID", "MOCK_AUTH_TOKEN")

            # Verify Twilio messages.create called with normalized number and exact SMS template
            user = User.objects.get(phone="+919876543210")
            expected_body = (
                f"Smart Doorstep Vehicle Service:\n"
                f"Your OTP is {user.otp_code}.\n"
                f"It is valid for 5 minutes.\n"
                f"Do not share this OTP with anyone."
            )
            mock_instance.messages.create.assert_called_once_with(
                body=expected_body,
                from_="+15005550006",
                to="+919876543210"
            )

    @patch("twilio.rest.Client")
    def test_3_otp_not_present_in_api_response(self, mock_twilio_client):
        # 3. OTP is NOT present in the API response (both Twilio and fallback)
        mock_instance = MagicMock()
        mock_twilio_client.return_value = mock_instance
        mock_message = MagicMock()
        mock_message.sid = "SM_MOCK_SID"
        mock_instance.messages.create.return_value = mock_message

        with patch.dict("os.environ", {
            "TWILIO_ACCOUNT_SID": "AC_TEST",
            "TWILIO_AUTH_TOKEN": "AUTH_TEST",
            "TWILIO_PHONE_NUMBER": "+15005550006"
        }):
            res_twilio = self.client.post("/api/auth/send-otp/", {"identifier": "+919811122233"}, format="json")
            self.assertEqual(res_twilio.status_code, status.HTTP_200_OK)
            self.assertNotIn("otp", res_twilio.data)
            self.assertNotIn("otp_code", res_twilio.data)
            user_twilio = User.objects.get(phone="+919811122233")
            self.assertNotIn(user_twilio.otp_code, str(res_twilio.data))

        # Test in console fallback mode
        with patch.dict("os.environ", {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_PHONE_NUMBER": ""}):
            res_console = self.client.post("/api/auth/send-otp/", {"identifier": "+919822233344"}, format="json")
            self.assertEqual(res_console.status_code, status.HTTP_200_OK)
            self.assertNotIn("otp", res_console.data)
            self.assertNotIn("otp_code", res_console.data)
            user_console = User.objects.get(phone="+919822233344")
            self.assertNotIn(user_console.otp_code, str(res_console.data))

    def test_4_otp_verification_success_and_jwt(self):
        # 4. OTP verification still works
        self.client.post("/api/auth/send-otp/", {"identifier": "9876500001"}, format="json")
        user = User.objects.get(phone="+919876500001")
        valid_otp = user.otp_code

        res_verify = self.client.post(
            "/api/auth/verify-otp/",
            {"identifier": "9876500001", "otp_code": valid_otp, "name": "Aarav Sharma"},
            format="json"
        )
        self.assertEqual(res_verify.status_code, status.HTTP_200_OK)
        self.assertIn("access", res_verify.data)
        self.assertIn("refresh", res_verify.data)
        self.assertIn("user", res_verify.data)
        self.assertEqual(res_verify.data["user"]["phone"], "+919876500001")

        user.refresh_from_db()
        self.assertTrue(user.is_verified)
        self.assertIsNone(user.otp_code)
        self.assertIsNone(user.otp_expires_at)

    def test_5_invalid_otp_is_rejected(self):
        # 5. Invalid OTP is rejected
        self.client.post("/api/auth/send-otp/", {"identifier": "9876500002"}, format="json")
        res_bad = self.client.post(
            "/api/auth/verify-otp/",
            {"identifier": "9876500002", "otp_code": "000000"},
            format="json"
        )
        self.assertEqual(res_bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid OTP code", res_bad.data["error"])
        self.assertEqual(res_bad.data["remaining_attempts"], 4)

    def test_6_expired_otp_is_rejected(self):
        # 6. Expired OTP is rejected
        self.client.post("/api/auth/send-otp/", {"identifier": "9876500003"}, format="json")
        user = User.objects.get(phone="+919876500003")
        valid_otp = user.otp_code

        # Force expiration in past
        user.otp_expires_at = timezone.now() - timedelta(minutes=1)
        user.save()

        res_expired = self.client.post(
            "/api/auth/verify-otp/",
            {"identifier": "9876500003", "otp_code": valid_otp},
            format="json"
        )
        self.assertEqual(res_expired.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", res_expired.data["error"].lower())

    def test_7_sixth_verification_attempt_is_blocked(self):
        # 7. Sixth verification attempt is blocked (max 5 attempts)
        self.client.post("/api/auth/send-otp/", {"identifier": "9876500004"}, format="json")

        for attempt in range(1, 5):
            res = self.client.post(
                "/api/auth/verify-otp/",
                {"identifier": "9876500004", "otp_code": "111111"},
                format="json"
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(res.data["remaining_attempts"], 5 - attempt)

        # 5th failed attempt exhausts quota
        res_5th = self.client.post(
            "/api/auth/verify-otp/",
            {"identifier": "9876500004", "otp_code": "111111"},
            format="json"
        )
        self.assertEqual(res_5th.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Maximum verification attempts exceeded", res_5th.data["error"])

        # 6th attempt is completely blocked
        res_6th = self.client.post(
            "/api/auth/verify-otp/",
            {"identifier": "9876500004", "otp_code": "111111"},
            format="json"
        )
        self.assertEqual(res_6th.status_code, status.HTTP_400_BAD_REQUEST)

    def test_8_resend_within_60_seconds_is_blocked(self):
        # 8. Resend within 60 seconds is blocked
        res1 = self.client.post("/api/auth/send-otp/", {"identifier": "9876500005"}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        res2 = self.client.post("/api/auth/send-otp/", {"identifier": "9876500005"}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("cooldown_seconds", res2.data)
        self.assertIn("Please wait", res2.data["error"])

    def test_9_missing_twilio_credentials_uses_dev_fallback(self):
        # 9. Missing Twilio credentials use development fallback
        with patch.dict("os.environ", {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_PHONE_NUMBER": ""}):
            res = self.client.post("/api/auth/send-otp/", {"identifier": "9876500006"}, format="json")
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertEqual(res.data["provider"], "console")
            self.assertIn("Verification code sent", res.data["message"])

    def test_10_existing_jwt_login_flow_still_works(self):
        # 10. Existing JWT login flow still works
        self.client.post("/api/auth/send-otp/", {"identifier": "9876500007"}, format="json")
        user = User.objects.get(phone="+919876500007")
        res_verify = self.client.post(
            "/api/auth/verify-otp/",
            {"identifier": "9876500007", "otp_code": user.otp_code},
            format="json"
        )
        self.assertEqual(res_verify.status_code, status.HTTP_200_OK)
        access_token = res_verify.data["access"]

        # Access authenticated /api/auth/me/
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        res_me = self.client.get("/api/auth/me/")
        self.assertEqual(res_me.status_code, status.HTTP_200_OK)
        self.assertEqual(res_me.data["phone"], "+919876500007")

    @patch("twilio.rest.Client")
    def test_twilio_failure_returns_clean_error(self, mock_twilio_client):
        # Verify clean error handling without leaking secrets or exceptions
        mock_instance = MagicMock()
        mock_twilio_client.return_value = mock_instance
        mock_instance.messages.create.side_effect = Exception("Twilio 21211: The 'To' number is not a valid phone number")

        with patch.dict("os.environ", {
            "TWILIO_ACCOUNT_SID": "AC_INVALID",
            "TWILIO_AUTH_TOKEN": "AUTH_INVALID",
            "TWILIO_PHONE_NUMBER": "+15005550006"
        }):
            res = self.client.post("/api/auth/send-otp/", {"identifier": "9876500008"}, format="json")
            self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
            self.assertEqual(res.data["error"], "Unable to send OTP. Please try again.")
            self.assertNotIn("Twilio 21211", str(res.data))
            self.assertNotIn("AC_INVALID", str(res.data))


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

    @override_settings(OTP_CONSOLE_FALLBACK=True)
    def test_otp_signup_always_creates_customer(self):
        res = self.client.post("/api/auth/send-otp/", {"identifier": "wannabe@example.com", "role": "ADMIN"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user = User.objects.get(email="wannabe@example.com")
        self.assertEqual(user.role, UserRole.CUSTOMER)
        self.assertFalse(user.is_staff)
        self.assertRegex(user.otp_code, r"^[0-9]{6}$")

    @override_settings(OTP_CONSOLE_FALLBACK=False, EMAIL_HOST="")
    def test_missing_otp_provider_is_an_error_in_production(self):
        with patch.dict("os.environ", {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_PHONE_NUMBER": ""}):
            res = self.client.post("/api/auth/send-otp/", {"identifier": "9876500099"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("not configured", res.data["error"])


class InvoicePaymentAndTrackingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username="pay_cust", email="pay_cust@example.com", role=UserRole.CUSTOMER)
        self.other = User.objects.create_user(username="pay_other", email="pay_other@example.com", role=UserRole.CUSTOMER)
        self.manager = User.objects.create_user(
            username="pay_mgr", email="pay_mgr@example.com", role=UserRole.SERVICE_CENTER_MANAGER
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
            user=self.manager, name="Pay Hub", address="Indiranagar", phone="+918000000000", email="hub@example.com",
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
        self.assertTrue(Notification.objects.filter(user=self.manager, title="Invoice paid").exists())

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
        self.assertEqual(self.pay(self.manager, method="UPI", upi_id="x@okaxis").status_code, 403)
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

        # A manager of a different service center is refused
        other_mgr = User.objects.create_user(
            username="other_mgr", email="other_mgr@example.com", role=UserRole.SERVICE_CENTER_MANAGER
        )
        ServiceCenter.objects.create(
            user=other_mgr, name="Other Hub", address="Whitefield", phone="+918000000001", email="o@example.com"
        )
        self.client.force_authenticate(user=other_mgr)
        self.assertEqual(self.client.post(url).status_code, status.HTTP_403_FORBIDDEN)

        # The booking's own manager can generate it
        self.client.force_authenticate(user=self.manager)
        res = self.client.post(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        invoice_id = res.data["id"]

        # Once paid, it can no longer be recalculated (by the endpoint or by re-completing the booking)
        self.client.force_authenticate(user=self.customer)
        self.client.post(f"/api/invoices/{invoice_id}/pay/", {"method": "UPI", "upi_id": "rahul@okhdfc"}, format="json")
        paid_total = Invoice.objects.get(pk=invoice_id).grand_total
        self.client.force_authenticate(user=self.manager)
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
        self.client.force_authenticate(user=self.manager)
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
        self.customer = User.objects.create_user(username="sa_cust", email="sa_cust@example.com", role=UserRole.CUSTOMER)
        self.manager = User.objects.create_user(
            username="sa_mgr", email="sa_mgr@example.com", role=UserRole.SERVICE_CENTER_MANAGER, is_staff=True
        )
        self.other_mgr = User.objects.create_user(
            username="sa_mgr2", email="sa_mgr2@example.com", role=UserRole.SERVICE_CENTER_MANAGER
        )
        self.mechanic = User.objects.create_user(username="sa_mech", email="sa_mech@example.com", role=UserRole.MECHANIC)
        brand = CarBrand.objects.create(name="Honda")
        model = CarModel.objects.create(brand=brand, name="City")
        self.vehicle = Vehicle.objects.create(
            customer=self.customer, car_brand=brand, car_model=model, brand="Honda", model="City",
            registration_number="KA01SA01", year=2024, fuel_type="Petrol",
        )
        self.st = ServiceType.objects.create(name="Full Service", base_price=4000, estimated_duration="5 hours")
        self.center = ServiceCenter.objects.create(user=self.manager, name="SA Hub", address="Jayanagar", phone="+918000000005", email="sa@example.com")
        self.other_center = ServiceCenter.objects.create(user=self.other_mgr, name="SA Hub 2", address="Hebbal", phone="+918000000006", email="sa2@example.com")
        self.booking = ServiceBooking.objects.create(
            customer=self.customer, vehicle=self.vehicle, service_type=self.st, service_center=self.center,
            pickup_address="Jayanagar 4th Block", status=BookingStatus.PENDING,
        )

    def test_staff_flag_does_not_make_a_manager_an_admin(self):
        self.client.force_authenticate(user=self.manager)  # is_staff=True
        self.assertEqual(self.client.get("/api/admin/dashboard-stats/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post("/api/car-brands/", {"name": "Hacked"}, format="json").status_code, status.HTTP_403_FORBIDDEN)
        other = ServiceBooking.objects.create(
            customer=self.customer, vehicle=self.vehicle, service_type=self.st, service_center=self.other_center, pickup_address="x",
        )
        ids = [b["id"] for b in self.client.get("/api/service-center/bookings/").data]
        self.assertIn(self.booking.id, ids)
        self.assertNotIn(other.id, ids)
        res = self.client.patch(f"/api/service-center/bookings/{other.id}/", {"status": "Cancelled"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_manager_cannot_use_another_centers_staff(self):
        from api.models import Employee

        theirs = User.objects.create_user(username="sa_drv2", email="sa_drv2@example.com", role=UserRole.DRIVER)
        Employee.objects.create(user=theirs, service_center=self.other_center, employee_type=Employee.EmployeeType.VALET)
        pool = User.objects.create_user(username="sa_drv3", email="sa_drv3@example.com", role=UserRole.DRIVER)
        self.client.force_authenticate(user=self.manager)
        url = f"/api/service-center/bookings/{self.booking.id}/"
        self.assertEqual(self.client.patch(url, {"assigned_driver_id": theirs.id}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"assigned_driver_id": pool.id}, format="json").status_code, 200)
        staff = self.client.get("/api/service-center/employees/").data
        driver_ids = [d["id"] for d in staff["drivers"]]
        self.assertIn(pool.id, driver_ids)
        self.assertNotIn(theirs.id, driver_ids)
        self.assertEqual(self.client.patch(url, {"status": "Teleported"}, format="json").status_code, 400)

    def test_manager_estimates_only_for_own_center_vehicles(self):
        self.client.force_authenticate(user=self.other_mgr)
        res = self.client.post("/api/repair-cost/estimate/", {"vehicle": self.vehicle.id, "issue_description": "noise"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(user=self.manager)
        res = self.client.post("/api/repair-cost/estimate/", {"vehicle": self.vehicle.id, "issue_description": "noise"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

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
        self.customer = User.objects.create_user(username="slotc", email="slotc@example.com", role=UserRole.CUSTOMER)
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
