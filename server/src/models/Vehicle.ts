import mongoose, { Schema } from "mongoose";

const schema = new Schema(
  {
    userId: { type: String, required: true, index: true },
    nickname: String,
    brand: String,
    model: String,
    year: Number,
    fuelType: { type: String, enum: ["Petrol", "Diesel", "CNG", "Electric", "Hybrid"] },
    registration: String,
    color: String,
  },
  { timestamps: true },
);

export default mongoose.models.Vehicle || mongoose.model("Vehicle", schema);
