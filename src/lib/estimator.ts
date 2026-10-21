import type { CostEstimate, ServiceType } from "../types";

interface Rule {
  keywords: string[];
  serviceHint?: ServiceType[];
  estimate: CostEstimate;
}

const RULES: Rule[] = [
  {
    keywords: ["brake", "brakes", "pedal", "grinding", "squeak", "squeal", "vibrate", "vibrates", "vibration"],
    estimate: {
      possibleIssue: "Brake pad wear or brake disc issue",
      recommendedService: "Brake inspection and brake pad replacement",
      costMin: 3000,
      costMax: 6000,
      timeMinHours: 2,
      timeMaxHours: 4,
      confidence: "High",
    },
  },
  {
    keywords: ["ac", "a/c", "air condition", "cooling", "gas", "compressor"],
    estimate: {
      possibleIssue: "Low refrigerant or AC compressor strain",
      recommendedService: "AC gas top-up and cooling performance check",
      costMin: 2500,
      costMax: 8500,
      timeMinHours: 2,
      timeMaxHours: 5,
      confidence: "High",
    },
  },
  {
    keywords: ["battery", "won't start", "wont start", "jump", "crank", "clicking"],
    estimate: {
      possibleIssue: "Weak or failing battery",
      recommendedService: "Battery health test and possible replacement",
      costMin: 4000,
      costMax: 9500,
      timeMinHours: 1,
      timeMaxHours: 2,
      confidence: "High",
    },
  },
  {
    keywords: ["tyre", "tire", "puncture", "alignment", "steering pull"],
    estimate: {
      possibleIssue: "Tyre wear, puncture, or wheel alignment issue",
      recommendedService: "Tyre inspection, puncture repair or alignment",
      costMin: 800,
      costMax: 12000,
      timeMinHours: 1,
      timeMaxHours: 3,
      confidence: "Medium",
    },
  },
  {
    keywords: ["oil", "engine oil", "service due", "periodic", "mileage"],
    serviceHint: ["Periodic Service"],
    estimate: {
      possibleIssue: "Scheduled maintenance / oil and filter due",
      recommendedService: "Periodic service with oil, filter and multi-point check",
      costMin: 2800,
      costMax: 6500,
      timeMinHours: 3,
      timeMaxHours: 6,
      confidence: "High",
    },
  },
  {
    keywords: ["engine", "overheat", "smoke", "misfire", "check engine", "power loss"],
    estimate: {
      possibleIssue: "Engine performance or diagnostic fault",
      recommendedService: "Engine diagnostic scan and inspection",
      costMin: 1500,
      costMax: 18000,
      timeMinHours: 2,
      timeMaxHours: 8,
      confidence: "Medium",
    },
  },
  {
    keywords: ["dent", "scratch", "paint", "bumper", "accident", "body"],
    estimate: {
      possibleIssue: "Body panel damage or paint defect",
      recommendedService: "Denting and painting for affected panels",
      costMin: 2500,
      costMax: 25000,
      timeMinHours: 8,
      timeMaxHours: 48,
      confidence: "Low",
    },
  },
  {
    keywords: ["clutch", "gear", "gearbox", "slipping"],
    estimate: {
      possibleIssue: "Clutch wear or transmission concern",
      recommendedService: "Clutch inspection and possible replacement",
      costMin: 8000,
      costMax: 22000,
      timeMinHours: 6,
      timeMaxHours: 12,
      confidence: "Medium",
    },
  },
];

const SERVICE_DEFAULTS: Record<ServiceType, CostEstimate> = {
  "Periodic Service": {
    possibleIssue: "Routine wear items due for scheduled service",
    recommendedService: "Periodic service package (oil, filters, inspection)",
    costMin: 2800,
    costMax: 6500,
    timeMinHours: 3,
    timeMaxHours: 6,
    confidence: "High",
  },
  Repair: {
    possibleIssue: "Unspecified mechanical or electrical fault",
    recommendedService: "Workshop diagnostic followed by targeted repair",
    costMin: 1500,
    costMax: 12000,
    timeMinHours: 2,
    timeMaxHours: 8,
    confidence: "Low",
  },
  "Brake Service": {
    possibleIssue: "Brake pad wear or brake disc issue",
    recommendedService: "Brake inspection and brake pad replacement",
    costMin: 3000,
    costMax: 6000,
    timeMinHours: 2,
    timeMaxHours: 4,
    confidence: "High",
  },
  "AC Service": {
    possibleIssue: "Reduced cooling efficiency",
    recommendedService: "AC service, gas check and cabin filter replacement",
    costMin: 2500,
    costMax: 8500,
    timeMinHours: 2,
    timeMaxHours: 5,
    confidence: "High",
  },
  "Battery Replacement": {
    possibleIssue: "Battery nearing end of life",
    recommendedService: "Battery test and replacement if required",
    costMin: 4000,
    costMax: 9500,
    timeMinHours: 1,
    timeMaxHours: 2,
    confidence: "High",
  },
  "Tyre Service": {
    possibleIssue: "Tyre condition or alignment concern",
    recommendedService: "Tyre inspection, rotation or replacement",
    costMin: 800,
    costMax: 12000,
    timeMinHours: 1,
    timeMaxHours: 3,
    confidence: "Medium",
  },
  "Denting & Painting": {
    possibleIssue: "Cosmetic body damage",
    recommendedService: "Denting and painting for affected panels",
    costMin: 2500,
    costMax: 25000,
    timeMinHours: 8,
    timeMaxHours: 48,
    confidence: "Low",
  },
  "Engine Diagnostic": {
    possibleIssue: "Engine or ECU-related fault",
    recommendedService: "Full diagnostic scan and technician inspection",
    costMin: 1500,
    costMax: 18000,
    timeMinHours: 2,
    timeMaxHours: 8,
    confidence: "Medium",
  },
  "General Inspection": {
    possibleIssue: "Needs a multi-point workshop inspection",
    recommendedService: "General inspection and written job card",
    costMin: 499,
    costMax: 1999,
    timeMinHours: 1,
    timeMaxHours: 3,
    confidence: "Medium",
  },
};

function yearFactor(year: number): number {
  const age = Math.max(0, new Date().getFullYear() - year);
  if (age >= 10) return 1.18;
  if (age >= 6) return 1.1;
  return 1;
}

export function estimateRepairCost(input: {
  make: string;
  model: string;
  year: number;
  serviceType: ServiceType;
  problem: string;
}): CostEstimate {
  const text = input.problem.toLowerCase();
  let best: { score: number; estimate: CostEstimate } | null = null;

  for (const rule of RULES) {
    const hits = rule.keywords.filter((k) => text.includes(k)).length;
    if (hits === 0) continue;
    const bonus = rule.serviceHint?.includes(input.serviceType) ? 1 : 0;
    const score = hits + bonus;
    if (!best || score > best.score) best = { score, estimate: { ...rule.estimate } };
  }

  const base = best?.estimate ?? { ...SERVICE_DEFAULTS[input.serviceType] };
  const factor = yearFactor(input.year);
  const premium = /creta|fortuner|harrier|safari|xuv|kodiaq|elevate/i.test(
    `${input.make} ${input.model}`,
  )
    ? 1.12
    : 1;

  return {
    ...base,
    costMin: Math.round((base.costMin * factor * premium) / 100) * 100,
    costMax: Math.round((base.costMax * factor * premium) / 100) * 100,
  };
}

export function formatInrRange(min: number, max: number): string {
  const fmt = (n: number) => `₹${n.toLocaleString("en-IN")}`;
  return `${fmt(min)} – ${fmt(max)}`;
}

export function formatHours(min: number, max: number): string {
  if (max >= 24) {
    const d1 = Math.max(1, Math.round(min / 8));
    const d2 = Math.max(d1, Math.round(max / 8));
    return d1 === d2 ? `${d1} workshop day${d1 > 1 ? "s" : ""}` : `${d1}–${d2} workshop days`;
  }
  return `${min}–${max} Hours`;
}
