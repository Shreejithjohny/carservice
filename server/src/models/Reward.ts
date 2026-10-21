import mongoose, { Schema } from "mongoose";

const schema = new Schema(
  {
    userId: { type: String, required: true, unique: true },
    points: { type: Number, default: 0 },
    badges: [String],
    discountEligible: { type: Boolean, default: false },
  },
  { timestamps: true },
);

export default mongoose.models.Reward || mongoose.model("Reward", schema);
