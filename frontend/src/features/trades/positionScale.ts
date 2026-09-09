/** Direction-aware coordinates for the position risk diagram. */

import Decimal from "decimal.js";

import type { Direction } from "@/features/trades/api";

const ExactDecimal = Decimal.clone({ precision: 96 });
const MAX_EXTENSION_RATIO = new ExactDecimal("0.5");

export type ExitOverflow = "loss" | "profit" | null;

export interface PositionScale {
  stop: number;
  entry: number;
  target: number;
  exit: number | null;
  exitOverflow: ExitOverflow;
}

function percentage(value: Decimal, low: Decimal, span: Decimal): number {
  return value.sub(low).div(span).mul(100).toNumber();
}

/**
 * Map prices onto a loss-to-profit axis while preserving plan readability.
 * Extreme exits are clamped after allowing a half-span visual extension.
 */
export function calculatePositionScale(
  direction: Direction,
  entryValue: string,
  stopValue: string,
  targetValue: string,
  exitValue?: string | null,
): PositionScale {
  const entryPrice = new ExactDecimal(entryValue);
  const sign = new ExactDecimal(direction === "long" ? 1 : -1);
  const coordinate = (value: string): Decimal =>
    new ExactDecimal(value).sub(entryPrice).mul(sign);
  const stop = coordinate(stopValue);
  const target = coordinate(targetValue);
  const baseSpan = target.sub(stop);

  if (!baseSpan.isPositive()) {
    return { stop: 0, entry: 50, target: 100, exit: null, exitOverflow: null };
  }

  let low = stop;
  let high = target;
  let exit: Decimal | null = null;
  let exitOverflow: ExitOverflow = null;

  if (exitValue) {
    const rawExit = coordinate(exitValue);
    const extension = baseSpan.mul(MAX_EXTENSION_RATIO);
    const minimum = stop.sub(extension);
    const maximum = target.add(extension);
    exit = Decimal.max(minimum, Decimal.min(maximum, rawExit));
    if (rawExit.lt(minimum)) exitOverflow = "loss";
    if (rawExit.gt(maximum)) exitOverflow = "profit";
    low = Decimal.min(low, exit);
    high = Decimal.max(high, exit);
  }

  const span = high.sub(low);
  return {
    stop: percentage(stop, low, span),
    entry: percentage(new ExactDecimal(0), low, span),
    target: percentage(target, low, span),
    exit: exit === null ? null : percentage(exit, low, span),
    exitOverflow,
  };
}
