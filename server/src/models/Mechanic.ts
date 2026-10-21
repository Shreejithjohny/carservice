import mongoose, { Schema } from "mongoose";

const schema = new Schema(
  {
    userId: { type: String, required: true },
    speciality: String,
    rating: { type: Number, default: 4.8 },
    jobsCompleted: { type: Number, default: 0 },
    active: { type: Boolean, default: true },
  },
  { timestamps: true },
);

export default mongoose.models.Mechanic || mongoose.model("Mechanic", schema);
