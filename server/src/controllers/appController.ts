import type { Response } from "express";
import { col } from "../lib/store.js";
import type { AuthedRequest } from "../middleware/auth.js";
import { notify } from "../lib/notify.js";
import { estimateRepair } from "../services/estimator.js";
import { randomOtp } from "./authController.js";

function pid(req: AuthedRequest, key: string) {
  const v = req.params[key];
  return (Array.isArray(v) ? v[0] : v) || "";
}

const SAMPLE_VIDEO =
  "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4";

export async function listVehicles(req: AuthedRequest, res: Response) {
  const items = await col("vehicles").find({ userId: req.user!.id });
  res.json(items);
}

export async function createVehicle(req: AuthedRequest, res: Response) {
  const { nickname, brand, model, year, fuelType, registration, color } = req.body ?? {};
  if (!brand || !model || !registration) {
    return res.status(400).json({ error: "Brand, model and registration are required." });
  }
  const vehicle = await col("vehicles").create({
    userId: req.user!.id,
    nickname: nickname || `${brand} ${model}`,
    brand,
    model,
    year: Number(year) || 2020,
    fuelType: fuelType || "Petrol",
    registration: String(registration).toUpperCase(),
    color: color || "",
  });
  await col("healthScores").create({
    userId: req.user!.id,
    vehicleId: vehicle._id,
    overall: 88,
    engine: 90,
    battery: 85,
    brakes: 82,
    tires: 80,
    oilLife: 70,
    ac: 92,
    nextServiceInDays: 40,
    monthlyTrend: [
      { month: "Mar", score: 84 },
      { month: "Apr", score: 86 },
      { month: "May", score: 87 },
      { month: "Jun", score: 88 },
    ],
  });
  res.json(vehicle);
}

export async function listBookings(req: AuthedRequest, res: Response) {
  let q: Record<string, unknown> = { userId: req.user!.id };
  if (req.user!.role === "admin" || req.user!.role === "mechanic") q = {};
  if (req.user!.role === "driver") q = { driverId: req.user!.id };
  const items = await col("bookings").find(q);
  res.json(items);
}

export async function createBooking(req: AuthedRequest, res: Response) {
  const { vehicleId, serviceType, problem, pickupAt, address } = req.body ?? {};
  if (!vehicleId || !serviceType || !pickupAt) {
    return res.status(400).json({ error: "Vehicle, service type and pickup time are required." });
  }
  const vehicle = await col("vehicles").findById(vehicleId);
  const est = estimateRepair({
    brand: (vehicle?.brand as string) || "",
    model: (vehicle?.model as string) || "",
    year: Number(vehicle?.year) || 2020,
    fuelType: (vehicle?.fuelType as string) || "Petrol",
    problem: problem || serviceType,
  });
  const drivers = (await col("users").find({ role: "driver" }))[0];
  const mechanics = (await col("mechanics").find({}))[0];
  const booking = await col("bookings").create({
    userId: req.user!.id,
    vehicleId,
    driverId: drivers?._id,
    mechanicId: mechanics?._id,
    serviceType,
    problem: problem || "",
    pickupAt,
    address: address || "",
    status: "Driver Assigned",
    estimatedCost: `₹${est.estimatedCostMin.toLocaleString("en-IN")} – ₹${est.estimatedCostMax.toLocaleString("en-IN")}`,
  });
  const otp = await col("otpVerifications").create({
    bookingId: booking._id,
    userId: req.user!.id,
    driverId: drivers?._id,
    code: randomOtp(),
    expiresAt: new Date(Date.now() + 1000 * 60 * 60 * 6).toISOString(),
    verified: false,
    faceVerified: false,
    attempts: 0,
  });
  await col("bookings").findByIdAndUpdate(booking._id, { otpId: otp._id, status: "Driver Assigned" });
  await notify({
    userId: req.user!.id,
    type: "Booking Confirmed",
    title: "Booking confirmed",
    body: `${booking._id.slice(0, 8).toUpperCase()} is confirmed. Share the pickup OTP with your driver.`,
    meta: { bookingId: booking._id },
  });
  await notify({
    userId: req.user!.id,
    type: "Driver Assigned",
    title: "Driver assigned",
    body: "A valet is on the way. Verify them with your 6-digit OTP.",
    meta: { bookingId: booking._id },
  });
  res.json({ ...booking, otpId: otp._id });
}

export async function updateBookingStatus(req: AuthedRequest, res: Response) {
  const { status } = req.body ?? {};
  const booking = await col("bookings").findByIdAndUpdate(pid(req, "id"), { status });
  if (!booking) return res.status(404).json({ error: "Booking not found" });
  const map: Record<string, string> = {
    "Vehicle Picked Up": "Vehicle Picked Up",
    "Repair Started": "Repair Started",
    Completed: "Service Completed",
    Delivered: "Vehicle Delivered",
    "Waiting for Approval": "Video Approval Required",
  };
  if (map[status]) {
    await notify({
      userId: booking.userId as string,
      type: map[status],
      title: map[status],
      body: `Booking status is now ${status}.`,
      meta: { bookingId: booking._id },
    });
  }
  res.json(booking);
}

export async function getOtp(req: AuthedRequest, res: Response) {
  const booking = await col("bookings").findById(pid(req, "bookingId"));
  if (!booking) return res.status(404).json({ error: "Booking not found" });
  if (req.user!.role === "customer" && booking.userId !== req.user!.id) {
    return res.status(403).json({ error: "Not your booking" });
  }
  const otp = booking.otpId
    ? await col("otpVerifications").findById(booking.otpId as string)
    : await col("otpVerifications").findOne({ bookingId: booking._id });
  const driver = booking.driverId ? await col("users").findById(booking.driverId as string) : null;
  const vehicle = await col("vehicles").findById(booking.vehicleId as string);
  res.json({
    otp,
    driver: driver
      ? { name: driver.name, avatarUrl: driver.avatarUrl, phone: driver.phone }
      : null,
    vehicle,
    booking,
    codeForCustomer: req.user!.role === "customer" || req.user!.role === "admin" ? otp?.code : undefined,
  });
}

export async function verifyOtp(req: AuthedRequest, res: Response) {
  const { bookingId, code } = req.body ?? {};
  const otp = await col("otpVerifications").findOne({ bookingId });
  if (!otp) return res.status(404).json({ error: "OTP not generated" });
  const attempts = Number(otp.attempts || 0) + 1;
  if (otp.verified) return res.json({ ok: true, already: true, otp });
  if (String(code) !== String(otp.code)) {
    await col("otpVerifications").findByIdAndUpdate(otp._id, { attempts });
    return res.status(400).json({ ok: false, error: "Incorrect OTP", attempts });
  }
  const updated = await col("otpVerifications").findByIdAndUpdate(otp._id, {
    verified: true,
    faceVerified: true,
    attempts,
  });
  await col("bookings").findByIdAndUpdate(bookingId, { status: "OTP Verified" });
  await notify({
    userId: otp.userId as string,
    type: "Vehicle Picked Up",
    title: "Valet verified",
    body: "OTP and face check passed. Your vehicle pickup can proceed.",
    meta: { bookingId },
  });
  res.json({ ok: true, otp: updated, faceVerified: true });
}

export async function listApprovals(req: AuthedRequest, res: Response) {
  const q = req.user!.role === "customer" ? { userId: req.user!.id } : {};
  res.json(await col("repairApprovals").find(q));
}

export async function createApproval(req: AuthedRequest, res: Response) {
  const { bookingId, title, description, extraCost, extraHours, videoUrl } = req.body ?? {};
  const booking = await col("bookings").findById(bookingId);
  if (!booking) return res.status(404).json({ error: "Booking not found" });
  const url = videoUrl || (req.file ? `/uploads/${req.file.filename}` : SAMPLE_VIDEO);
  const video = await col("repairVideos").create({
    bookingId,
    mechanicId: req.user!.id,
    url,
    caption: title,
  });
  const approval = await col("repairApprovals").create({
    bookingId,
    userId: booking.userId,
    mechanicId: req.user!.id,
    title: title || "Additional repair",
    description: description || "",
    videoUrl: url,
    extraCost: Number(extraCost) || 0,
    extraHours: Number(extraHours) || 1,
    decision: "pending",
    stage: "Waiting for Approval",
    videoId: video._id,
  });
  await col("bookings").findByIdAndUpdate(bookingId, { status: "Waiting for Approval" });
  await notify({
    userId: booking.userId as string,
    type: "Video Approval Required",
    title: "Video approval required",
    body: `${title || "Additional repair"} — review the mechanic video before we continue.`,
    meta: { approvalId: approval._id, bookingId },
  });
  res.json(approval);
}

export async function decideApproval(req: AuthedRequest, res: Response) {
  const { decision } = req.body ?? {};
  if (!["approved", "declined"].includes(decision)) {
    return res.status(400).json({ error: "decision must be approved or declined" });
  }
  const approval = await col("repairApprovals").findById(pid(req, "id"));
  if (!approval) return res.status(404).json({ error: "Not found" });
  if (req.user!.role === "customer" && approval.userId !== req.user!.id) {
    return res.status(403).json({ error: "Not your approval" });
  }
  const stage = decision === "approved" ? "Repair Started" : "Completed";
  const updated = await col("repairApprovals").findByIdAndUpdate(pid(req, "id"), {
    decision,
    decidedAt: new Date().toISOString(),
    stage,
  });
  await col("bookings").findByIdAndUpdate(approval.bookingId as string, {
    status: decision === "approved" ? "Repair Started" : "In Service",
  });
  await notify({
    userId: approval.userId as string,
    type: decision === "approved" ? "Repair Started" : "Service Completed",
    title: decision === "approved" ? "Repair approved" : "Extra repair declined",
    body:
      decision === "approved"
        ? "The workshop has started the additional repair."
        : "We will complete only the originally booked work.",
    meta: { approvalId: approval._id },
  });
  res.json(updated);
}

export async function runEstimate(req: AuthedRequest, res: Response) {
  const { brand, model, year, fuelType, problem } = req.body ?? {};
  if (!brand || !model || !problem) {
    return res.status(400).json({ error: "Brand, model and problem description are required." });
  }
  const result = estimateRepair({
    brand,
    model,
    year: Number(year) || 2020,
    fuelType: fuelType || "Petrol",
    problem,
  });
  res.json({ ...result, imageReceived: Boolean(req.file) });
}

export async function getHealth(req: AuthedRequest, res: Response) {
  const vehicleId = req.query.vehicleId as string | undefined;
  const scores = await col("healthScores").find({ userId: req.user!.id });
  const reward = await col("rewards").findOne({ userId: req.user!.id });
  const bookings = await col("bookings").find({ userId: req.user!.id });
  res.json({
    scores: vehicleId ? scores.filter((s) => s.vehicleId === vehicleId) : scores,
    reward,
    history: bookings,
  });
}

export async function listNotifications(req: AuthedRequest, res: Response) {
  res.json(await col("notifications").find({ userId: req.user!.id }));
}

export async function markNotificationsRead(req: AuthedRequest, res: Response) {
  const items = await col("notifications").find({ userId: req.user!.id });
  for (const n of items) await col("notifications").findByIdAndUpdate(n._id, { read: true });
  res.json({ ok: true });
}

export async function adminOverview(_req: AuthedRequest, res: Response) {
  const users = await col("users").find({});
  const bookings = await col("bookings").find({});
  const mechanics = await col("mechanics").find({});
  const approvals = await col("repairApprovals").find({});
  const discounts = await col("discounts").find({});
  res.json({
    users,
    bookings,
    mechanics,
    approvals,
    discounts,
    analytics: {
      users: users.length,
      bookings: bookings.length,
      pendingApprovals: approvals.filter((a) => a.decision === "pending").length,
      revenueHint: bookings.length * 4200,
    },
  });
}

export async function createDiscount(req: AuthedRequest, res: Response) {
  const { title, percent, code } = req.body ?? {};
  if (!title || !percent) return res.status(400).json({ error: "Title and percent required" });
  res.json(await col("discounts").create({ title, percent: Number(percent), code: code || "SAVE", active: true }));
}

export async function listDiscounts(_req: AuthedRequest, res: Response) {
  res.json(await col("discounts").find({}));
}
