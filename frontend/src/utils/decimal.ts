/** Exact decimal presentation helpers. */
import Decimal from "decimal.js";

/** Round ATR display amounts without hiding tiny nonzero crypto ranges. */
export function formatAtrAmount(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const amount = new Decimal(value);
  const rounded =
    !amount.isZero() && amount.abs().lt("0.01")
      ? amount.toSignificantDigits(4, Decimal.ROUND_HALF_UP)
      : amount.toDecimalPlaces(2, Decimal.ROUND_HALF_UP);
  return formatDecimal(rounded.toFixed());
}

/**
 * Remove insignificant fractional zeroes without converting the value to a
 * JavaScript number and therefore without losing decimal precision.
 */
export function formatDecimal(value: string): string {
  if (/^[+-]?0+(?:\.0+)?[eE][+-]?\d+$/.test(value)) {
    return "0";
  }

  if (/^[+-]?\d+(?:\.\d+)?[eE][+-]?\d+$/.test(value)) {
    const decimal = new Decimal(value);
    // Bound expansion while retaining every significant decimal digit.
    if (Math.abs(decimal.e) <= 1000) value = decimal.toFixed();
  }
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (match === null) {
    return value;
  }

  const sign = match[1] ?? "";
  const integer = match[2] ?? "";
  const fraction = match[3] ?? "";
  const significantFraction = fraction.replace(/0+$/, "");
  const normalizedSign =
    /^0+$/.test(integer) && !significantFraction ? "" : sign;
  return significantFraction
    ? `${normalizedSign}${integer}.${significantFraction}`
    : `${normalizedSign}${integer}`;
}

/** Return whether an exact decimal input represents a value above zero. */
export function isPositiveDecimal(value: string | number): boolean {
  const normalized = String(value).trim();
  return /^\d+(\.\d+)?$/.test(normalized) && /[1-9]/.test(normalized);
}

/** Compare two unsigned fixed-point decimal strings without floating point. */
export function compareDecimal(left: string, right: string): number {
  const leftMatch = /^(\d+)(?:\.(\d+))?$/.exec(left.trim());
  const rightMatch = /^(\d+)(?:\.(\d+))?$/.exec(right.trim());
  if (leftMatch === null || rightMatch === null) return 0;
  const scale = Math.max(leftMatch[2]?.length ?? 0, rightMatch[2]?.length ?? 0);
  const integer = (match: RegExpExecArray): bigint =>
    BigInt(`${match[1]}${(match[2] ?? "").padEnd(scale, "0")}`);
  const leftInteger = integer(leftMatch);
  const rightInteger = integer(rightMatch);
  return leftInteger === rightInteger ? 0 : leftInteger > rightInteger ? 1 : -1;
}

/** Round a fixed-point decimal for compact presentation without float loss. */
export function formatRoundedDecimal(value: string, places: number): string {
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(value.trim());
  if (match === null || places < 0) return formatDecimal(value);
  const sign = match[1] ?? "";
  const integer = match[2] ?? "0";
  const fraction = match[3] ?? "";
  const retained = fraction.slice(0, places).padEnd(places, "0");
  const next = fraction.charAt(places);
  const combined = BigInt(`${integer}${retained}` || "0");
  const rounded = combined + (next >= "5" ? 1n : 0n);
  const digits = rounded.toString().padStart(places + 1, "0");
  const split = places === 0 ? digits.length : digits.length - places;
  const result =
    places === 0
      ? `${sign}${digits}`
      : `${sign}${digits.slice(0, split)}.${digits.slice(split)}`;
  return formatDecimal(result);
}
