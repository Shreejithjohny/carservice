import mongoose, { Schema } from "mongoose";

const schema = new Schema(
  {
    userId: String,
    vehicleId: { type: String, required: true, unique: true },
    overall: Number,
    engine: Number,
    battery: Number,
    brakes: Number,
    tires: Number,
    oilLife: Number,
    ac: Number,
    monthlyTrend: [{ month: String, score: Number }],
    nextServiceInDays: Number,
  },
  { timestamps: true },
);

export default mongoose.models.HealthScore || mongoose.model("HealthScore", schema);
