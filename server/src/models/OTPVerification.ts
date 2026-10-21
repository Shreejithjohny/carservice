import mongoose, { Schema } from "mongoose";

const schema = new Schema(
  {
    bookingId: { type: String, required: true },
    userId: String,
    driverId: String,
    code: { type: String, required: true },
    expiresAt: String,
    verified: { type: Boolean, default: false },
    faceVerified: { type: Boolean, default: false },
    attempts: { type: Number, default: 0 },
  },
  { timestamps: true },
);

export default mongoose.models.OTPVerification || mongoose.model("OTPVerification", schema);
