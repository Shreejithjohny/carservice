import mongoose, { Schema } from "mongoose";

const schema = new Schema(
  {
    userId: { type: String, required: true, index: true },
    type: String,
    title: String,
    body: String,
    read: { type: Boolean, default: false },
    meta: Schema.Types.Mixed,
  },
  { timestamps: true },
);

export default mongoose.models.Notification || mongoose.model("Notification", schema);
