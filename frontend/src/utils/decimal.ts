/** Exact decimal presentation helpers. */

/**
 * Remove insignificant fractional zeroes without converting the value to a
 * JavaScript number and therefore without losing decimal precision.
 */
export function formatDecimal(value: string): string {
  if (/^[+-]?0+(?:\.0+)?[eE][+-]?\d+$/.test(value)) {
    return "0";
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

/** Return whether an exact decimal string represents a value above zero. */
export function isPositiveDecimal(value: string): boolean {
  const normalized = value.trim();
  return /^\d+(\.\d+)?$/.test(normalized) && /[1-9]/.test(normalized);
}
