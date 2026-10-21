import mongoose, { Schema } from "mongoose";

export const BOOKING_STATUSES = [
  "Requested",
  "Driver Assigned",
  "OTP Verified",
  "Vehicle Picked Up",
  "In Service",
  "Waiting for Approval",
  "Repair Started",
  "Completed",
  "Out for Delivery",
  "Delivered",
  "Cancelled",
] as const;

const schema = new Schema(
  {
    userId: { type: String, required: true, index: true },
    vehicleId: String,
    mechanicId: String,
    driverId: String,
    serviceType: String,
    problem: String,
    pickupAt: String,
    address: String,
    status: { type: String, default: "Requested" },
    estimatedCost: String,
    otpId: String,
  },
  { timestamps: true },
);

export default mongoose.models.Booking || mongoose.model("Booking", schema);
