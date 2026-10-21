import mongoose, { Schema } from "mongoose";

const schema = new Schema(
  {
    bookingId: String,
    approvalId: String,
    mechanicId: String,
    url: String,
    caption: String,
  },
  { timestamps: true },
);

export default mongoose.models.RepairVideo || mongoose.model("RepairVideo", schema);
