import bcrypt from "bcryptjs";
import { col, snapshot } from "./lib/store.js";
import { notify } from "./lib/notify.js";

const SAMPLE_VIDEO =
  "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4";

export async function seedIfEmpty() {
  const users = await col("users").find({});
  if (users.length > 0) return snapshot();

  const passwordHash = await bcrypt.hash("demo123", 10);
  const adminHash = await bcrypt.hash("admin123", 10);

  const customer = await col("users").create({
    name: "Shreejith",
    phone: "9876543210",
    email: "shreejith@example.com",
    passwordHash,
    role: "customer",
    walletBalance: 2450,
    avatarUrl: "https://api.dicebear.com/9.x/adventurer/svg?seed=Shreejith",
  });
  const admin = await col("users").create({
    name: "Ops Admin",
    phone: "9000000001",
    email: "admin@doorstep.local",
    passwordHash: adminHash,
    role: "admin",
    walletBalance: 0,
    avatarUrl: "https://api.dicebear.com/9.x/identicon/svg?seed=Admin",
  });
  const driver = await col("users").create({
    name: "Ravi Kumar",
    phone: "9000000002",
    email: "ravi@doorstep.local",
    passwordHash,
    role: "driver",
    walletBalance: 0,
    avatarUrl: "https://api.dicebear.com/9.x/adventurer/svg?seed=Ravi",
  });
  const mechUser = await col("users").create({
    name: "Anita Sharma",
    phone: "9000000003",
    email: "anita@doorstep.local",
    passwordHash,
    role: "mechanic",
    walletBalance: 0,
    avatarUrl: "https://api.dicebear.com/9.x/adventurer/svg?seed=Anita",
  });
  void admin;

  const mechanic = await col("mechanics").create({
    userId: mechUser._id,
    speciality: "Brakes & diagnostics",
    rating: 4.9,
    jobsCompleted: 312,
    active: true,
  });

  const swift = await col("vehicles").create({
    userId: customer._id,
    nickname: "Family Swift",
    brand: "Maruti",
    model: "Swift",
    year: 2019,
    fuelType: "Petrol",
    registration: "KA 05 MJ 2148",
    color: "Pearl White",
  });
  const creta = await col("vehicles").create({
    userId: customer._id,
    nickname: "Office Creta",
    brand: "Hyundai",
    model: "Creta",
    year: 2022,
    fuelType: "Diesel",
    registration: "KA 03 AB 9021",
    color: "Phantom Black",
  });

  await col("healthScores").create({
    userId: customer._id,
    vehicleId: swift._id,
    overall: 92,
    engine: 94,
    battery: 88,
    brakes: 76,
    tires: 90,
    oilLife: 64,
    ac: 93,
    nextServiceInDays: 27,
    monthlyTrend: [
      { month: "Mar", score: 86 },
      { month: "Apr", score: 88 },
      { month: "May", score: 90 },
      { month: "Jun", score: 91 },
      { month: "Jul", score: 92 },
    ],
  });
  await col("healthScores").create({
    userId: customer._id,
    vehicleId: creta._id,
    overall: 81,
    engine: 80,
    battery: 84,
    brakes: 79,
    tires: 72,
    oilLife: 55,
    ac: 88,
    nextServiceInDays: 12,
    monthlyTrend: [
      { month: "Mar", score: 78 },
      { month: "Apr", score: 79 },
      { month: "May", score: 80 },
      { month: "Jun", score: 81 },
    ],
  });

  await col("rewards").create({
    userId: customer._id,
    points: 1450,
    badges: ["On-Time Hero", "Video Verified", "Health 90+"],
    discountEligible: true,
  });

  const booking = await col("bookings").create({
    userId: customer._id,
    vehicleId: swift._id,
    mechanicId: mechanic._id,
    driverId: driver._id,
    serviceType: "Brake Service",
    problem: "Strange noise from brakes and vibration while braking.",
    pickupAt: "2026-08-29T10:00:00.000Z",
    address: "12, 4th Cross, Indiranagar, Bengaluru",
    status: "Waiting for Approval",
    estimatedCost: "₹3,000 – ₹6,000",
  });

  const otp = await col("otpVerifications").create({
    bookingId: booking._id,
    userId: customer._id,
    driverId: driver._id,
    code: "482913",
    expiresAt: new Date(Date.now() + 1000 * 60 * 60 * 8).toISOString(),
    verified: true,
    faceVerified: true,
    attempts: 1,
  });
  await col("bookings").findByIdAndUpdate(booking._id, { otpId: otp._id });

  const video = await col("repairVideos").create({
    bookingId: booking._id,
    mechanicId: mechUser._id,
    url: SAMPLE_VIDEO,
    caption: "Front left pad wear",
  });

  await col("repairApprovals").create({
    bookingId: booking._id,
    userId: customer._id,
    mechanicId: mechUser._id,
    title: "Front brake pad replacement",
    description:
      "Pads are below 2mm on the front-left. Disc has light scoring. Recommend pad replacement now to avoid disc machining.",
    videoUrl: SAMPLE_VIDEO,
    extraCost: 4200,
    extraHours: 3,
    decision: "pending",
    stage: "Waiting for Approval",
    videoId: video._id,
  });

  await col("bookings").create({
    userId: customer._id,
    vehicleId: creta._id,
    mechanicId: mechanic._id,
    driverId: driver._id,
    serviceType: "Periodic Service",
    problem: "Regular 10,000 km service.",
    pickupAt: "2026-08-12T08:00:00.000Z",
    address: "12, 4th Cross, Indiranagar, Bengaluru",
    status: "Delivered",
    estimatedCost: "₹4,200",
  });

  await col("discounts").create({ title: "Health 90+ members", percent: 10, code: "HEALTH90", active: true });
  await col("discounts").create({ title: "First video approval", percent: 5, code: "VIDEO5", active: true });

  const notes = [
    ["Booking Confirmed", "Brake service booked for Maruti Swift."],
    ["Driver Assigned", "Ravi Kumar is assigned for pickup."],
    ["Vehicle Picked Up", "OTP verified. Swift is heading to the workshop."],
    ["Video Approval Required", "Anita uploaded a brake inspection video. Approve or decline extra work."],
  ] as const;
  for (const [type, body] of notes) {
    await notify({ userId: customer._id, type, title: type, body, meta: { bookingId: booking._id } });
  }

  return snapshot();
}
