/** Compact order-book labels; source values retain their exact precision. */
import Decimal from "decimal.js";

/** Keep small amounts nonzero and abbreviate large display-only volumes. */
export function formatBookAmount(value: string): string {
  const amount = new Decimal(value);
  if (amount.isZero()) return "0";
  if (amount.lt(1)) {
    const rounded = amount.toSignificantDigits(4, Decimal.ROUND_HALF_UP);
    const fixed = rounded.toFixed();
    return fixed.length <= 12 ? fixed : rounded.toExponential();
  }
  if (amount.lt(10000)) return amount.toFixed(2, Decimal.ROUND_HALF_UP);
  for (const [scale, suffix] of [
    ["1e12", "T"],
    ["1e9", "B"],
    ["1e6", "M"],
    ["1e3", "K"],
  ] as const) {
    // Select the larger suffix when rounding crosses its boundary.
    if (amount.gte(new Decimal(scale).mul("0.999995"))) {
      const compact = amount.div(scale).toFixed(2, Decimal.ROUND_HALF_UP);
      return compact.length < 12
        ? `${compact}${suffix}`
        : amount.toExponential(3, Decimal.ROUND_HALF_UP);
    }
  }
  return amount.toFixed(2, Decimal.ROUND_HALF_UP);
}
