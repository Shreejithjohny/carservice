from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Auth Endpoints
    path("auth/bypass-login/", views.bypass_login, name="bypass_login"),
    path("auth/quick-login/", views.bypass_login, name="quick_login"),
    path("auth/send-otp/", views.send_otp, name="send_otp"),
    path("auth/verify-otp/", views.verify_otp, name="verify_otp"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", views.me, name="auth_me"),

    # Vehicle Catalog Endpoints
    path("car-brands/", views.car_brand_list_create, name="car_brand_list_create"),
    path("car-brands/<int:pk>/", views.car_brand_detail, name="car_brand_detail"),
    path("car-brands/<int:pk>/models/", views.car_brand_models, name="car_brand_models"),

    path("car-models/", views.car_model_list_create, name="car_model_list_create"),
    path("car-models/<int:pk>/", views.car_model_detail, name="car_model_detail"),
    path("car-models/<int:pk>/variants/", views.car_model_variants, name="car_model_variants"),

    path("car-variants/", views.car_variant_list_create, name="car_variant_list_create"),
    path("car-variants/<int:pk>/", views.car_variant_detail, name="car_variant_detail"),

    # Customer Vehicle Endpoints
    path("vehicles/", views.vehicle_list_create, name="vehicle_list_create"),
    path("vehicles/<int:pk>/", views.vehicle_detail, name="vehicle_detail"),

    # Phase 4 Service & Booking Endpoints
    path("service-types/", views.service_type_list, name="service_type_list"),
    path("service-centers/", views.service_center_list, name="service_center_list"),
    path("service-centers/<int:pk>/slots/", views.service_center_slots, name="service_center_slots"),
    path("bookings/", views.booking_list_create, name="booking_list_create"),
    path("bookings/<str:pk>/", views.booking_detail, name="booking_detail"),

    # Phase 5 Location & Distance Endpoints
    path("location/distance/", views.calculate_distance_view, name="location_distance"),

    # Phase 6 Service Center Manager Endpoints
    path("service-center/bookings/", views.service_center_bookings_list, name="sc_bookings_list"),
    path("service-center/bookings/<str:pk>/", views.service_center_booking_update, name="sc_booking_update"),
    path("service-center/employees/", views.service_center_employees_list, name="sc_employees_list"),

    # Phase 7 Driver / Valet Endpoints
    path("driver/pickups/", views.driver_pickups_list, name="driver_pickups_list"),
    path("driver/pickups/<int:pk>/status/", views.driver_pickup_status_update, name="driver_pickup_status_update"),
    path("driver/pickups/<int:pk>/handover-otp/request/", views.driver_request_handover_otp, name="driver_request_handover_otp"),
    path("driver/pickups/<int:pk>/handover-otp/verify/", views.driver_verify_handover_otp, name="driver_verify_handover_otp"),
    path("driver/pickups/<int:pk>/delivery-otp/request/", views.driver_request_delivery_otp, name="driver_request_delivery_otp"),
    path("driver/pickups/<int:pk>/delivery-otp/verify/", views.driver_verify_delivery_otp, name="driver_verify_delivery_otp"),
    path("driver/pickups/<int:pk>/location/", views.driver_post_location, name="driver_post_location"),

    # Phase 8 Mechanic & Repair Endpoints
    path("mechanic/jobs/", views.mechanic_jobs_list, name="mechanic_jobs_list"),
    path("mechanic/jobs/<int:pk>/status/", views.mechanic_job_status_update, name="mechanic_job_status_update"),
    path("inspections/", views.create_service_inspection, name="create_service_inspection"),
    path("repair-evidence/", views.upload_repair_evidence, name="upload_repair_evidence"),
    path("repair-requests/", views.create_repair_request, name="create_repair_request"),

    # Customer Tracking & Approvals
    path("bookings/<str:pk>/tracking/", views.customer_booking_tracking_detail, name="customer_booking_tracking_detail"),
    path("repair-requests/<int:pk>/approve/", views.customer_approve_repair_request, name="customer_approve_repair_request"),
    path("repair-requests/<int:pk>/reject/", views.customer_reject_repair_request, name="customer_reject_repair_request"),

    # Phase 9 AI Repair Cost Estimator
    path("repair-cost/estimate/", views.repair_cost_estimate, name="repair_cost_estimate"),

    # Phase 10 Invoices & Car Health Score
    path("invoices/", views.invoices_list, name="invoices_list"),
    path("invoices/<str:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/pay/", views.invoice_pay, name="invoice_pay"),
    path("bookings/<str:pk>/generate-invoice/", views.booking_generate_invoice, name="booking_generate_invoice"),
    path("vehicles/<int:pk>/health-score/", views.vehicle_health_score, name="vehicle_health_score"),

    # Phase 11 Notifications & Admin Dashboard
    path("notifications/", views.notifications_list, name="notifications_list"),
    path("notifications/<int:pk>/read/", views.notification_mark_read, name="notification_mark_read"),
    path("notifications/mark-all-read/", views.notifications_mark_all_read, name="notifications_mark_all_read"),
    path("admin/dashboard-stats/", views.admin_dashboard_stats, name="admin_dashboard_stats"),

    # Health Check
    path("health-check/", views.health_check, name="health_check"),
]
