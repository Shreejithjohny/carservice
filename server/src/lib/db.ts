import mongoose from "mongoose";

export const mongoReady = () => mongoose.connection.readyState === 1;

export async function connectMongo() {
  const uri = process.env.MONGODB_URI;
  if (!uri) {
    console.log("No MONGODB_URI — using JSON store (models still match Mongo schemas).");
    return false;
  }
  try {
    await mongoose.connect(uri, { serverSelectionTimeoutMS: 2500 });
    console.log("Connected to MongoDB");
    return true;
  } catch {
    console.warn("MongoDB unreachable — using JSON store. Start MongoDB to persist in Atlas/local.");
    return false;
  }
}
