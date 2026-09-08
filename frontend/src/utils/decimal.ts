/** Exact decimal presentation helpers. */

/**
 * Remove insignificant fractional zeroes without converting the value to a
 * JavaScript number and therefore without losing decimal precision.
 */
export function formatDecimal(value: string): string {
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
