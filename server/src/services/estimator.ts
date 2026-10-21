export type EstimateResult = {
  possibleIssue: string;
  estimatedCostMin: number;
  estimatedCostMax: number;
  estimatedHoursMin: number;
  estimatedHoursMax: number;
  confidence: number;
  suggestedNextStep: string;
  recommendedService: string;
};

type Rule = {
  keywords: string[];
  result: EstimateResult;
};

const RULES: Rule[] = [
  {
    keywords: ["brake", "brakes", "pedal", "grinding", "squeak", "squeal", "vibrate", "vibration"],
    result: {
      possibleIssue: "Brake pad wear or warped brake disc",
      recommendedService: "Brake inspection and pad / disc replacement",
      estimatedCostMin: 3000,
      estimatedCostMax: 6000,
      estimatedHoursMin: 2,
      estimatedHoursMax: 4,
      confidence: 91,
      suggestedNextStep: "Book a doorstep brake inspection. Approve extra work only after the mechanic video.",
    },
  },
  {
    keywords: ["ac", "a/c", "cooling", "compressor", "gas"],
    result: {
      possibleIssue: "Low refrigerant or AC compressor strain",
      recommendedService: "AC gas top-up and performance check",
      estimatedCostMin: 2500,
      estimatedCostMax: 8500,
      estimatedHoursMin: 2,
      estimatedHoursMax: 5,
      confidence: 86,
      suggestedNextStep: "Book AC service; cabin filter is often replaced in the same visit.",
    },
  },
  {
    keywords: ["battery", "won't start", "wont start", "clicking", "crank", "jump"],
    result: {
      possibleIssue: "Weak or failing 12V battery",
      recommendedService: "Battery health test and replacement if required",
      estimatedCostMin: 4000,
      estimatedCostMax: 9500,
      estimatedHoursMin: 1,
      estimatedHoursMax: 2,
      confidence: 88,
      suggestedNextStep: "Avoid repeated jump-starts; book a battery test today.",
    },
  },
  {
    keywords: ["tyre", "tire", "puncture", "alignment", "steering pull"],
    result: {
      possibleIssue: "Tyre wear, puncture, or wheel alignment drift",
      recommendedService: "Tyre inspection, puncture repair or alignment",
      estimatedCostMin: 800,
      estimatedCostMax: 12000,
      estimatedHoursMin: 1,
      estimatedHoursMax: 3,
      confidence: 74,
      suggestedNextStep: "Upload a tyre photo on booking for a tighter estimate.",
    },
  },
  {
    keywords: ["oil", "engine oil", "service due", "periodic", "mileage"],
    result: {
      possibleIssue: "Scheduled oil and filter service due",
      recommendedService: "Periodic service with multi-point inspection",
      estimatedCostMin: 2800,
      estimatedCostMax: 6500,
      estimatedHoursMin: 3,
      estimatedHoursMax: 6,
      confidence: 90,
      suggestedNextStep: "Book periodic service and track oil-life on Car Health.",
    },
  },
  {
    keywords: ["engine", "overheat", "smoke", "misfire", "check engine", "power"],
    result: {
      possibleIssue: "Engine performance or ECU-related fault",
      recommendedService: "Engine diagnostic scan and inspection",
      estimatedCostMin: 1500,
      estimatedCostMax: 18000,
      estimatedHoursMin: 2,
      estimatedHoursMax: 8,
      confidence: 68,
      suggestedNextStep: "Diagnostic first — wait for mechanic video before approving major work.",
    },
  },
];

const FALLBACK: EstimateResult = {
  possibleIssue: "Needs a multi-point workshop inspection",
  recommendedService: "General inspection and digital job card",
  estimatedCostMin: 499,
  estimatedCostMax: 4999,
  estimatedHoursMin: 1,
  estimatedHoursMax: 4,
  confidence: 52,
  suggestedNextStep: "Book a doorstep inspection. Final cost is confirmed after video approval if extra work is found.",
};

export function estimateRepair(input: {
  brand: string;
  model: string;
  year: number;
  fuelType: string;
  problem: string;
}): EstimateResult {
  const text = input.problem.toLowerCase();
  let best: { score: number; result: EstimateResult } | null = null;
  for (const rule of RULES) {
    const score = rule.keywords.filter((k) => text.includes(k)).length;
    if (score && (!best || score > best.score)) best = { score, result: { ...rule.result } };
  }
  const age = Math.max(0, new Date().getFullYear() - input.year);
  const ageFactor = age >= 10 ? 1.15 : age >= 6 ? 1.08 : 1;
  const premium = /fortuner|harrier|safari|xuv|creta|kodiaq/i.test(`${input.brand} ${input.model}`)
    ? 1.1
    : 1;
  const base = best?.result ?? { ...FALLBACK };
  if (input.fuelType === "Diesel") {
    base.estimatedCostMin = Math.round(base.estimatedCostMin * 1.05);
    base.estimatedCostMax = Math.round(base.estimatedCostMax * 1.08);
  }
  return {
    ...base,
    estimatedCostMin: Math.round((base.estimatedCostMin * ageFactor * premium) / 50) * 50,
    estimatedCostMax: Math.round((base.estimatedCostMax * ageFactor * premium) / 50) * 50,
  };
}
