import jwt from "jsonwebtoken";

const SECRET = process.env.JWT_SECRET || "doorstep-dev-jwt-change-me";

export type TokenUser = {
  id: string;
  role: "customer" | "admin" | "mechanic" | "driver";
  name: string;
  phone: string;
};

export function signToken(user: TokenUser) {
  return jwt.sign(user, SECRET, { expiresIn: "7d" });
}

export function verifyToken(token: string) {
  return jwt.verify(token, SECRET) as TokenUser;
}
