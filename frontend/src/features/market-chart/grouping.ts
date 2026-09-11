/** Exact, snapshot-local price buckets; never infer an exchange tick size. */
import Decimal from "decimal.js";
import type { BookLevel } from "./types";

const Exact = Decimal.clone({ precision: 96 });

/** Choose display increments from the precision of observed prices. */
export function groupingSteps(levels: BookLevel[]): string[] {
  const places = Math.max(0, ...levels.map((row) => new Exact(row.price).dp()));
  return [0, 1, 2, 3].map((power) =>
    new Exact(10).pow(power - places).toFixed(),
  );
}

/** Sum in the selected unit using original prices, then truncate buckets. */
export function groupLevels(
  levels: BookLevel[],
  step: string,
  side: "asks" | "bids",
  unit: "base" | "quote" = "base",
): BookLevel[] {
  const buckets = new Map<string, Decimal>();
  for (const level of levels) {
    const price =
      step === "0"
        ? level.price
        : new Exact(level.price)
            .div(step)
            .toDecimalPlaces(
              0,
              side === "asks" ? Decimal.ROUND_CEIL : Decimal.ROUND_FLOOR,
            )
            .mul(step)
            .toFixed();
    const size =
      unit === "quote" ? new Exact(level.size).mul(level.price) : level.size;
    buckets.set(price, (buckets.get(price) ?? new Exact(0)).plus(size));
  }
  let total = new Exact(0);
  return [...buckets].slice(0, 20).map(([price, size]) => {
    total = total.plus(size);
    return { price, size: size.toFixed(), total: total.toFixed() };
  });
}
