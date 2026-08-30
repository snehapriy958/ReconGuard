import { describe, it, expect } from "vitest";
import {
  interpretAmount,
  interpretDate,
  interpretVendor,
  interpretReference,
  interpretCompetition,
} from "../evidence-interpretation";

describe("interpretAmount", () => {
  it("is strong under 1% difference", () => {
    expect(interpretAmount(0.005).strength).toBe("strong");
  });
  it("is moderate between 1% and 3%", () => {
    expect(interpretAmount(0.02).strength).toBe("moderate");
  });
  it("is weak above 3%", () => {
    expect(interpretAmount(0.1).strength).toBe("weak");
  });
});

describe("interpretDate", () => {
  it("is strong within 3 days", () => {
    expect(interpretDate(0).strength).toBe("strong");
    expect(interpretDate(3).strength).toBe("strong");
  });
  it("is moderate between 4 and 7 days", () => {
    expect(interpretDate(5).strength).toBe("moderate");
  });
  it("is weak beyond 7 days", () => {
    expect(interpretDate(14).strength).toBe("weak");
  });
});

describe("interpretVendor", () => {
  it("is strong at or above 0.85 token-set similarity", () => {
    expect(interpretVendor(0.9).strength).toBe("strong");
  });
  it("is moderate between 0.5 and 0.85", () => {
    expect(interpretVendor(0.6).strength).toBe("moderate");
  });
  it("is weak below 0.5", () => {
    expect(interpretVendor(0.2).strength).toBe("weak");
  });
});

describe("interpretReference", () => {
  it("is strong on exact match", () => {
    expect(interpretReference(1, 1, 1.0, 0).strength).toBe("strong");
  });
  it("is moderate on substring overlap without exact match", () => {
    expect(interpretReference(0, 1, 0.6, 0).strength).toBe("moderate");
  });
  it("is weak when both sides are missing — never treated as a match", () => {
    const result = interpretReference(0, 0, 0, 1);
    expect(result.strength).toBe("weak");
    expect(result.label).toMatch(/missing/i);
  });
  it("is weak on low similarity with no overlap", () => {
    expect(interpretReference(0, 0, 0.1, 0).strength).toBe("weak");
  });
});

describe("interpretCompetition", () => {
  it("is strong with zero competing candidates", () => {
    expect(interpretCompetition(0).strength).toBe("strong");
  });
  it("is moderate below the high-competition threshold (5)", () => {
    expect(interpretCompetition(2).strength).toBe("moderate");
  });
  it("is weak at or above the high-competition threshold (5) — matches risk.py's HIGH_COMPETITION_THRESHOLD", () => {
    expect(interpretCompetition(5).strength).toBe("weak");
    expect(interpretCompetition(10).strength).toBe("weak");
  });
});
