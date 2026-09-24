import { describe, it, expect } from "vitest";
import { formatCurrency, formatPercent, DEFAULT_CURRENCY_SYMBOL } from "../formatters";

describe("formatters", () => {
  describe("formatCurrency", () => {
    it("formats standard amounts with default currency symbol", () => {
      expect(formatCurrency(1000)).toBe(`${DEFAULT_CURRENCY_SYMBOL}1,000.00`);
      expect(formatCurrency(1234567.89)).toBe(`${DEFAULT_CURRENCY_SYMBOL}12,34,567.89`);
      expect(formatCurrency(0)).toBe(`${DEFAULT_CURRENCY_SYMBOL}0.00`);
    });

    it("formats amounts with custom currency symbol", () => {
      expect(formatCurrency(500, "$")).toBe("$500.00");
    });

    it("handles null, undefined, and NaN gracefully", () => {
      expect(formatCurrency(null)).toBe("—");
      expect(formatCurrency(undefined)).toBe("—");
      expect(formatCurrency(NaN)).toBe("—");
    });
  });

  describe("formatPercent", () => {
    it("formats decimal ratios as percentages", () => {
      expect(formatPercent(0.8523)).toBe("85.2%");
      expect(formatPercent(1)).toBe("100.0%");
      expect(formatPercent(0)).toBe("0.0%");
    });

    it("handles null, undefined, and NaN gracefully", () => {
      expect(formatPercent(null)).toBe("0.0%");
      expect(formatPercent(undefined)).toBe("0.0%");
      expect(formatPercent(NaN)).toBe("0.0%");
    });
  });
});
