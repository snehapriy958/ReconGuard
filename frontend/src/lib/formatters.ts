// ReconLens frontend — Centralized formatting utilities.

export const DEFAULT_CURRENCY_SYMBOL = "₹";

/**
 * Format a numeric amount with locale grouping and 2 decimal places.
 * Default symbol is ₹ (INR), matching project source dataset currency conventions.
 */
export function formatCurrency(
  amount: number | null | undefined,
  currencySymbol: string = DEFAULT_CURRENCY_SYMBOL
): string {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return "—";
  }
  return `${currencySymbol}${amount.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Format a 0-1 ratio as a human-readable percentage (e.g. 0.8523 -> "85.2%").
 */
export function formatPercent(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || isNaN(rate)) {
    return "0.0%";
  }
  return `${(rate * 100).toFixed(1)}%`;
}
