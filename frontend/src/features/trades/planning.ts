/** Exact, synchronous position planning for the interactive trade workspace. */

import Decimal from "decimal.js";

import type { Direction, PlanningContext } from "@/features/trades/api";

const ExactDecimal = Decimal.clone({
  precision: 96,
  rounding: Decimal.ROUND_HALF_EVEN,
  toExpNeg: -100,
  toExpPos: 100,
});

export type PlanningErrorCode =
  | "invalidPlan"
  | "invalidLongStop"
  | "invalidShortStop"
  | "nonPositiveTarget"
  | "quantityBelowMinimum"
  | "notionalBelowMinimum";

export class LocalPlanningError extends Error {
  readonly code: PlanningErrorCode;

  constructor(code: PlanningErrorCode) {
    super(code);
    this.code = code;
  }
}

export interface LocalPositionPlan {
  planned_entry: string;
  planned_stop: string;
  planned_take_profit: string;
  stop_distance: string;
  take_profit_distance: string;
  quantity: string;
  reward_multiple: number;
  planned_risk_percent: string;
  target_risk_amount: string;
  planned_risk_amount: string;
  planned_notional: string;
  allocation_capital: string;
  already_reserved_risk: string;
  remaining_risk_capacity: string;
  deposit_floor_breach: boolean;
  wallet_balance: string;
  wallet_reserved: string;
  wallet_available: string;
  capital_remaining: string;
  capital_sufficient: boolean;
  atr_value: string | null;
  take_profit_atr_percent: string | null;
  fits_atr_limit: boolean | null;
  atr_limit_percent: string;
}

function decimal(value: string | number): Decimal {
  return new ExactDecimal(value);
}

function exactString(value: Decimal): string {
  return value.isZero() ? "0" : value.toFixed();
}

/** Snap a raw price to the nearest executable instrument tick. */
export function normalizeToStep(value: string, step: string): string {
  try {
    const parsed = decimal(value);
    const tick = decimal(step);
    if (!parsed.isPositive() || !tick.isPositive()) return value;
    return exactString(parsed.toNearest(tick, Decimal.ROUND_HALF_UP));
  } catch {
    return value;
  }
}

function floorToStep(value: Decimal, step: Decimal): Decimal {
  return value.div(step).floor().mul(step);
}

/** Return the strategy's monetary 1R from capital and its risk percentage. */
export function calculateTargetRisk(
  capital: string | null | undefined,
  riskPercent: string | null | undefined,
): string {
  if (!capital || !riskPercent) return "0";
  return exactString(decimal(capital).mul(riskPercent).div(100));
}

/** Return capital left after reserving a planned position notional. */
export function calculateCapitalRemaining(
  available: string | null | undefined,
  notional: string | null | undefined,
): string {
  if (!available || !notional) return "0";
  return exactString(decimal(available).sub(notional));
}

/** Return the executable profit at the strategy's fixed reward multiple. */
export function calculatePlannedProfit(
  risk: string | null | undefined,
  rewardMultiple: string | number | null | undefined,
): string {
  if (!risk || rewardMultiple === null || rewardMultiple === undefined) {
    return "0";
  }
  return exactString(decimal(risk).mul(rewardMultiple));
}

/** Return target distance as a percentage of ATR, when ATR is usable. */
export function calculateAtrUsage(
  targetDistance: string | null | undefined,
  atrValue: string | null | undefined,
): string | null {
  if (!targetDistance || !atrValue) return null;
  try {
    const atr = decimal(atrValue);
    if (!atr.isPositive()) return null;
    return exactString(decimal(targetDistance).div(atr).mul(100));
  } catch {
    return null;
  }
}

/** Calculate the same executable plan as the backend without a network hop. */
export function calculateLocalPosition(
  context: PlanningContext,
  direction: Direction,
  rawEntry: string,
  rawStop: string,
  atrValue?: string | null,
): LocalPositionPlan {
  let entry: Decimal;
  let stop: Decimal;
  try {
    entry = decimal(normalizeToStep(rawEntry, context.price_step));
    stop = decimal(normalizeToStep(rawStop, context.price_step));
  } catch {
    throw new LocalPlanningError("invalidPlan");
  }
  if (!entry.isPositive() || !stop.isPositive()) {
    throw new LocalPlanningError("invalidPlan");
  }
  if (direction === "long" && stop.gte(entry)) {
    throw new LocalPlanningError("invalidLongStop");
  }
  if (direction === "short" && stop.lte(entry)) {
    throw new LocalPlanningError("invalidShortStop");
  }

  const reward = decimal(context.reward_multiple);
  const distance = entry.sub(stop).abs();
  const targetDistance = distance.mul(reward);
  const target =
    direction === "long"
      ? entry.add(targetDistance)
      : entry.sub(targetDistance);
  if (!target.isPositive()) {
    throw new LocalPlanningError("nonPositiveTarget");
  }

  const targetRisk = decimal(context.target_risk_amount);
  const quantityStep = decimal(context.quantity_step);
  const quantity = floorToStep(targetRisk.div(distance), quantityStep);
  if (!quantity.isPositive()) {
    throw new LocalPlanningError("quantityBelowMinimum");
  }
  if (
    context.minimum_quantity !== null &&
    quantity.lt(context.minimum_quantity)
  ) {
    throw new LocalPlanningError("quantityBelowMinimum");
  }

  const notional = quantity.mul(entry);
  if (
    context.minimum_notional !== null &&
    notional.lt(context.minimum_notional)
  ) {
    throw new LocalPlanningError("notionalBelowMinimum");
  }

  const actualRisk = quantity.mul(distance);
  const capitalRemaining = decimal(context.wallet_available).sub(notional);
  const riskAvailable = decimal(context.remaining_risk_capacity);
  const atrPercent = calculateAtrUsage(exactString(targetDistance), atrValue);

  return {
    planned_entry: exactString(entry),
    planned_stop: exactString(stop),
    planned_take_profit: exactString(target),
    stop_distance: exactString(distance),
    take_profit_distance: exactString(targetDistance),
    quantity: exactString(quantity),
    reward_multiple: context.reward_multiple,
    planned_risk_percent: context.planned_risk_percent,
    target_risk_amount: exactString(targetRisk),
    planned_risk_amount: exactString(actualRisk),
    planned_notional: exactString(notional),
    allocation_capital: context.allocation_capital,
    already_reserved_risk: context.already_reserved_risk,
    remaining_risk_capacity: exactString(riskAvailable.sub(actualRisk)),
    deposit_floor_breach: context.deposit_floor_breach,
    wallet_balance: context.wallet_balance,
    wallet_reserved: context.wallet_reserved,
    wallet_available: context.wallet_available,
    capital_remaining: exactString(capitalRemaining),
    capital_sufficient:
      capitalRemaining.gte(0) && targetRisk.lte(riskAvailable),
    atr_value: atrValue ?? null,
    take_profit_atr_percent: atrPercent,
    fits_atr_limit: atrPercent === null ? null : decimal(atrPercent).lte(75),
    atr_limit_percent: "75",
  };
}
