import { createHash, randomInt } from "node:crypto";
import bcrypt from "bcryptjs";
import type { Request, Response } from "express";
import { col } from "../lib/store.js";
import { signToken } from "../lib/jwt.js";
import type { AuthedRequest } from "../middleware/auth.js";

export async function requestRegistrationOtp(req: Request, res: Response) {
  const { name, phone, email, password } = req.body ?? {};
  const normalizedPhone = String(phone ?? "").replace(/\D/g, "");
  if (String(name ?? "").trim().length < 2 || normalizedPhone.length < 10 || typeof password !== "string" || password.length < 6) {
    return res.status(400).json({ error: "Enter your name, a valid phone number, and a 6-character password." });
  }
  if (await col("users").findOne({ phone: normalizedPhone })) {
    return res.status(409).json({ error: "An account with this phone already exists." });
  }

  const code = randomOtp();
  const expiresAt = Date.now() + 10 * 60 * 1000;
  const existing = await col("otpVerifications").findOne({ phone: normalizedPhone, purpose: "registration" });
  if (existing) await col("otpVerifications").deleteById(existing._id);
  await col("otpVerifications").create({
    phone: normalizedPhone,
    purpose: "registration",
    name: String(name).trim(),
    email: String(email ?? "").trim(),
    passwordHash: await bcrypt.hash(password, 10),
    codeHash: hashOtp(code),
    expiresAt: String(expiresAt),
    attempts: 0,
  });
  const delivery = await sendSms(normalizedPhone, `Your DoorStep verification code is ${code}. It expires in 10 minutes.`);
  res.json({ ok: true, delivery, expiresIn: 600 });
}

export async function verifyRegistrationOtp(req: Request, res: Response) {
  const normalizedPhone = String(req.body?.phone ?? "").replace(/\D/g, "");
  const code = String(req.body?.code ?? "");
  const pending = await col("otpVerifications").findOne({ phone: normalizedPhone, purpose: "registration" });
  if (!pending || Number(pending.expiresAt) < Date.now()) return res.status(400).json({ error: "This OTP has expired. Request a new one." });
  if (Number(pending.attempts ?? 0) >= 5) return res.status(429).json({ error: "Too many attempts. Request a new OTP." });
  if (pending.codeHash !== hashOtp(code)) {
    await col("otpVerifications").findByIdAndUpdate(pending._id, { attempts: Number(pending.attempts ?? 0) + 1 });
    return res.status(400).json({ error: "Incorrect OTP." });
  }
  if (await col("users").findOne({ phone: normalizedPhone })) return res.status(409).json({ error: "An account with this phone already exists." });
  const user = await col("users").create({
    name: pending.name,
    phone: normalizedPhone,
    email: pending.email || "",
    passwordHash: pending.passwordHash,
    role: "customer",
    walletBalance: 500,
    avatarUrl: "",
  });
  await col("rewards").create({ userId: user._id, points: 50, badges: ["New Member"], discountEligible: false });
  await col("otpVerifications").deleteById(pending._id);
  const token = signToken({ id: user._id, role: "customer", name: user.name as string, phone: user.phone as string });
  res.json({ token, user: publicUser(user) });
}

export async function login(req: Request, res: Response) {
  const { phone, password, role } = req.body ?? {};
  const user = await col("users").findOne({ phone: String(phone) });
  if (!user) return res.status(401).json({ error: "No account found for this phone." });
  if (role && user.role !== role) {
    return res.status(403).json({ error: "Use the correct portal for this account." });
  }
  if (user.passwordHash) {
    const ok = await bcrypt.compare(String(password || ""), user.passwordHash as string);
    if (!ok) return res.status(401).json({ error: "Incorrect password." });
  }
  const token = signToken({
    id: user._id,
    role: user.role as "customer",
    name: user.name as string,
    phone: user.phone as string,
  });
  res.json({ token, user: publicUser(user) });
}

/** Request an OTP for a registered phone number. */
export async function requestOtp(req: Request, res: Response) {
  const { phone } = req.body ?? {};
  const user = await col("users").findOne({ phone: String(phone) });
  if (!user) return res.status(404).json({ error: "Register this number first." });
  res.json({ ok: true });
}

export async function me(req: AuthedRequest, res: Response) {
  const user = await col("users").findById(req.user!.id);
  if (!user) return res.status(404).json({ error: "User not found" });
  res.json(publicUser(user));
}

export function publicUser(user: Record<string, unknown>) {
  const { passwordHash: _, ...rest } = user;
  return rest;
}

export function randomOtp() {
  return String(randomInt(100000, 999999));
}

function hashOtp(code: string) {
  return createHash("sha256").update(code).digest("hex");
}

async function sendSms(phone: string, message: string): Promise<"sms" | "local"> {
  const { TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER } = process.env;
  if (!TWILIO_ACCOUNT_SID || !TWILIO_AUTH_TOKEN || !TWILIO_FROM_NUMBER) {
    if (process.env.NODE_ENV === "production") throw new Error("SMS provider is not configured.");
    console.log(`[local OTP] ${phone}: ${message}`);
    return "local";
  }
  const countryCode = process.env.TWILIO_DEFAULT_COUNTRY_CODE || "91";
  const e164Phone = phone.length === 10 ? `+${countryCode}${phone}` : `+${phone}`;
  const body = new URLSearchParams({ To: e164Phone, From: TWILIO_FROM_NUMBER, Body: message });
  const response = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Messages.json`, {
    method: "POST",
    headers: { Authorization: `Basic ${Buffer.from(`${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}`).toString("base64")}`, "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!response.ok) throw new Error("Could not send verification SMS.");
  return "sms";
}
