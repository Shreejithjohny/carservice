import mongoose, { Schema } from "mongoose";

const schema = new Schema(
  {
    name: { type: String, required: true },
    phone: { type: String, required: true, unique: true },
    email: String,
    passwordHash: String,
    role: { type: String, enum: ["customer", "admin", "mechanic", "driver"], default: "customer" },
    avatarUrl: String,
    walletBalance: { type: Number, default: 0 },
  },
  { timestamps: true },
);

export default mongoose.models.User || mongoose.model("User", schema);
