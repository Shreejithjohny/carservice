import { Router } from "express";
import multer from "multer";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { requireAuth, requireRole } from "../middleware/auth.js";
import * as auth from "../controllers/authController.js";
import * as app from "../controllers/appController.js";

mkdirSync(join(process.cwd(), "uploads"), { recursive: true });
const upload = multer({ dest: join(process.cwd(), "uploads") });

export const router = Router();

router.post("/auth/register/request-otp", auth.requestRegistrationOtp);
router.post("/auth/register/verify-otp", auth.verifyRegistrationOtp);
router.post("/auth/login", auth.login);
router.post("/auth/otp", auth.requestOtp);
router.get("/auth/me", requireAuth, auth.me);

router.get("/vehicles", requireAuth, app.listVehicles);
router.post("/vehicles", requireAuth, app.createVehicle);

router.get("/bookings", requireAuth, app.listBookings);
router.post("/bookings", requireAuth, app.createBooking);
router.patch("/bookings/:id/status", requireAuth, requireRole("admin", "mechanic", "driver"), app.updateBookingStatus);

router.get("/otp/:bookingId", requireAuth, app.getOtp);
router.post("/otp/verify", requireAuth, requireRole("driver", "admin"), app.verifyOtp);

router.get("/approvals", requireAuth, app.listApprovals);
router.post(
  "/approvals",
  requireAuth,
  requireRole("admin", "mechanic"),
  upload.single("video"),
  app.createApproval,
);
router.post("/approvals/:id/decision", requireAuth, app.decideApproval);

router.post("/estimator", requireAuth, upload.single("image"), app.runEstimate);

router.get("/health", requireAuth, app.getHealth);

router.get("/notifications", requireAuth, app.listNotifications);
router.post("/notifications/read", requireAuth, app.markNotificationsRead);

router.get("/admin/overview", requireAuth, requireRole("admin"), app.adminOverview);
router.get("/discounts", requireAuth, app.listDiscounts);
router.post("/discounts", requireAuth, requireRole("admin"), app.createDiscount);
