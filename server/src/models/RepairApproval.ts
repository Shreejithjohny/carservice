import mongoose, { Schema } from "mongoose";

export const APPROVAL_TIMELINE = [
  "Inspection",
  "Issue Found",
  "Video Uploaded",
  "Waiting for Approval",
  "Repair Started",
  "Completed",
] as const;

const schema = new Schema(
  {
    bookingId: { type: String, required: true, index: true },
    userId: String,
    mechanicId: String,
    title: String,
    description: String,
    videoUrl: String,
    extraCost: Number,
    extraHours: Number,
    decision: { type: String, enum: ["pending", "approved", "declined"], default: "pending" },
    decidedAt: String,
    stage: { type: String, default: "Waiting for Approval" },
  },
  { timestamps: true },
);

export default mongoose.models.RepairApproval || mongoose.model("RepairApproval", schema);
