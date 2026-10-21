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
)

User = get_user_model()


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
            "preferred_date": "2026-10-01",
            "preferred_time": "10:00:00",
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
            "preferred_date": "2026-10-01",
            "preferred_time": "10:00:00",
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
            "preferred_date": "2026-10-01",
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
            "preferred_date": "2026-10-05",
            "preferred_time": "10:00:00",
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
            "preferred_date": "2026-10-06",
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
            "preferred_date": "2026-10-07",
            "preferred_time": "10:00:00",
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
            "preferred_date": "2026-10-07",
            "preferred_time": "10:00:00",
        }
        res = self.client.post("/api/bookings/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("pickup_longitude", res.data)

    def test_calculate_distance_api(self):
        res = self.client.get(
            "/api/location/distance/?origin_lat=12.9784&origin_lng=77.6408&dest_lat=12.9352&dest_lng=77.6245"
        )
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

        self.client.force_authenticate(user=manager)
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
                "preferred_date": "2026-10-15",
                "preferred_time": "09:00 AM",
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
        self.assertGreater(res_admin.data["total_revenue"], 0)


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
