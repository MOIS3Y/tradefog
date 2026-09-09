/** Reactive directional assessment for the trade checklist. */

import type { DirectionalValue } from "@/features/trades/api";

export type ChecklistVerdict =
  "unanswered" | "balanced" | "lean" | "agree" | "conflict";

export interface ChecklistAssessment {
  gauge: number;
  direction: "SHORT" | "NEUTRAL" | "LONG";
  verdict: ChecklistVerdict;
}

const WEIGHTS = [1, 1, 3, 2] as const;
const MAXIMUM_SCORE = WEIGHTS.reduce((total, weight) => total + weight, 0);

function signedValue(value: DirectionalValue | null | undefined): number {
  if (value === "POSITIVE") return 1;
  if (value === "NEGATIVE") return -1;
  return 0;
}

export function assessChecklist(
  values: Array<DirectionalValue | null | undefined>,
  tradeDirection: "long" | "short",
): ChecklistAssessment {
  const score = values.reduce(
    (total, value, index) => total + signedValue(value) * (WEIGHTS[index] ?? 0),
    0,
  );
  const answered = values.some((value) => value != null);
  const scoreDirection = score > 0 ? "long" : score < 0 ? "short" : null;
  const direction = score > 1 ? "LONG" : score < -1 ? "SHORT" : "NEUTRAL";
  let verdict: ChecklistVerdict = "unanswered";

  if (answered && scoreDirection === null) verdict = "balanced";
  if (answered && scoreDirection === tradeDirection) {
    verdict = Math.abs(score) === 1 ? "lean" : "agree";
  }
  if (
    answered &&
    scoreDirection !== null &&
    scoreDirection !== tradeDirection
  ) {
    verdict = "conflict";
  }

  return {
    gauge: Math.round(((score + MAXIMUM_SCORE) / (MAXIMUM_SCORE * 2)) * 100),
    direction,
    verdict,
  };
}
