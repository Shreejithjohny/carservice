import { describe, expect, it } from "vitest";
import { colorFor, initialsOf } from "./Avatar";

describe("initialsOf", () => {
  it("uses the first and last name", () => {
    expect(initialsOf("Rahul Verma")).toBe("RV");
    expect(initialsOf("  anil  kumar gowda ")).toBe("AG");
  });

  it("uses the first two letters of a single name", () => {
    expect(initialsOf("ravi")).toBe("RA");
    expect(initialsOf("")).toBe("?");
  });
});

describe("colorFor", () => {
  it("always gives the same name the same colour", () => {
    expect(colorFor("Rahul Verma")).toBe(colorFor("Rahul Verma"));
    expect(colorFor("Rahul Verma")).toMatch(/^#[0-9a-f]{6}$/);
  });

  it("spreads different names over the colours", () => {
    const names = ["Rahul", "Priya", "Anil", "Suresh", "Kavya", "Meera", "Arjun", "Divya", "Rohan", "Sneha"];
    expect(new Set(names.map(colorFor)).size).toBeGreaterThan(3);
  });
});
