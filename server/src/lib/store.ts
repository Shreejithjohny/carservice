import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const FILE = join(process.cwd(), "data", "store.json");

export type Doc = { _id: string; createdAt: string; updatedAt: string; [k: string]: unknown };

type DB = Record<string, Doc[]>;

const empty = (): DB => ({
  users: [],
  vehicles: [],
  bookings: [],
  mechanics: [],
  repairApprovals: [],
  repairVideos: [],
  notifications: [],
  healthScores: [],
  rewards: [],
  otpVerifications: [],
  discounts: [],
});

function load(): DB {
  try {
    if (existsSync(FILE)) return { ...empty(), ...JSON.parse(readFileSync(FILE, "utf8")) };
  } catch {
    /* first boot */
  }
  return empty();
}

let data = load();

function persist() {
  mkdirSync(dirname(FILE), { recursive: true });
  writeFileSync(FILE, JSON.stringify(data, null, 2));
}

function match(doc: Doc, query: Record<string, unknown>) {
  return Object.entries(query).every(([k, v]) => {
    if (k === "_id") return String(doc._id) === String(v);
    return doc[k] === v;
  });
}

export function col(name: string) {
  if (!data[name]) data[name] = [];
  return {
    async create(doc: Record<string, unknown>) {
      const now = new Date().toISOString();
      const row: Doc = {
        ...doc,
        _id: String(doc._id ?? randomUUID()),
        createdAt: (doc.createdAt as string) ?? now,
        updatedAt: now,
      };
      data[name].push(row);
      persist();
      return row;
    },
    async find(query: Record<string, unknown> = {}) {
      return data[name].filter((d) => match(docFix(d), query)).sort((a, b) =>
        String(b.createdAt).localeCompare(String(a.createdAt)),
      );
    },
    async findOne(query: Record<string, unknown>) {
      return data[name].find((d) => match(d, query)) ?? null;
    },
    async findById(id: string) {
      return data[name].find((d) => d._id === id) ?? null;
    },
    async findByIdAndUpdate(id: string, update: Record<string, unknown>) {
      const i = data[name].findIndex((d) => d._id === id);
      if (i < 0) return null;
      data[name][i] = { ...data[name][i], ...update, updatedAt: new Date().toISOString() };
      persist();
      return data[name][i];
    },
    async deleteById(id: string) {
      data[name] = data[name].filter((d) => d._id !== id);
      persist();
    },
  };
}

function docFix(d: Doc) {
  return d;
}

export function resetStore(next?: DB) {
  data = next ?? empty();
  persist();
}

export function snapshot() {
  return data;
}
