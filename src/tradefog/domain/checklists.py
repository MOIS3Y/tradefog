"""Pure calculations for the fixed directional trade checklist."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext
from enum import StrEnum
from typing import cast


class DirectionalValue(StrEnum):
    """Stored polarity shared by every directional checklist answer."""

    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    POSITIVE = "POSITIVE"


class AssessmentDirection(StrEnum):
    """Human-scale direction derived from the signed checklist score."""

    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"
    LONG = "LONG"


class TrendRelationship(StrEnum):
    """Relationship between the global and local daily observations."""

    UNASSESSED = "UNASSESSED"
    ALIGNED = "ALIGNED"
    MIXED = "MIXED"
    DIVERGENT = "DIVERGENT"


@dataclass(frozen=True, slots=True)
class ChecklistAnswers:
    """Nullable answers recorded for one trade decision."""

    market_sentiment: str | None = None
    information_background: str | None = None
    global_daily_direction: str | None = None
    local_daily_movement: str | None = None


@dataclass(frozen=True, slots=True)
class ChecklistAssessment:
    """Deterministic directional assessment and completion state."""

    score: Decimal
    direction: AssessmentDirection
    completeness: Decimal
    answered_count: int
    total_count: int
    gauge_position: int
    trend_relationship: TrendRelationship
    agrees_with_trade: bool | None


QUESTION_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("market_sentiment", 1),
    ("information_background", 1),
    ("global_daily_direction", 3),
    ("local_daily_movement", 2),
)
TOTAL_WEIGHT = sum(weight for _field_name, weight in QUESTION_WEIGHTS)

_SIGNED_VALUES = {
    DirectionalValue.NEGATIVE.value: -1,
    DirectionalValue.NEUTRAL.value: 0,
    DirectionalValue.POSITIVE.value: 1,
}


def _signed_value(answer: str | None) -> int:
    """Translate one stored answer into its signed numerical value."""
    if answer is None or answer == "":
        return 0
    try:
        return _SIGNED_VALUES[answer]
    except KeyError as error:
        raise ValueError(f"Unsupported checklist answer: {answer}") from error


def _trend_relationship(
    global_direction: str | None,
    local_movement: str | None,
) -> TrendRelationship:
    """Classify the two D1 observations without adding another score."""
    if not global_direction or not local_movement:
        return TrendRelationship.UNASSESSED
    global_value = _signed_value(global_direction)
    local_value = _signed_value(local_movement)
    if global_value == local_value and global_value != 0:
        return TrendRelationship.ALIGNED
    if global_value == -local_value and global_value != 0:
        return TrendRelationship.DIVERGENT
    return TrendRelationship.MIXED


def calculate_checklist_assessment(
    answers: ChecklistAnswers,
    *,
    trade_direction: str | None = None,
) -> ChecklistAssessment:
    """Evaluate directional consensus and agreement with the planned trade."""
    accumulated_score = Decimal(0)
    answered_count = 0

    for field_name, weight in QUESTION_WEIGHTS:
        raw_answer = cast(str | None, getattr(answers, field_name))
        if raw_answer:
            answered_count += 1
            accumulated_score += Decimal(_signed_value(raw_answer) * weight)

    with localcontext() as context:
        context.prec = 28
        score = accumulated_score / Decimal(TOTAL_WEIGHT)
        completeness = Decimal(answered_count) / Decimal(len(QUESTION_WEIGHTS))
        gauge_scaled = (score + Decimal(1)) * Decimal(50)
        gauge_position = int(
            gauge_scaled.to_integral_value(rounding=ROUND_HALF_UP)
        )

    if score > Decimal("0.2"):
        direction = AssessmentDirection.LONG
    elif score < Decimal("-0.2"):
        direction = AssessmentDirection.SHORT
    else:
        direction = AssessmentDirection.NEUTRAL

    trend_rel = _trend_relationship(
        answers.global_daily_direction,
        answers.local_daily_movement,
    )

    agrees_with_trade: bool | None = None
    if trade_direction and answered_count > 0:
        normalized_trade = trade_direction.upper().strip()
        if direction != AssessmentDirection.NEUTRAL:
            agrees_with_trade = direction.value == normalized_trade
        else:
            agrees_with_trade = False

    return ChecklistAssessment(
        score=score,
        direction=direction,
        completeness=completeness,
        answered_count=answered_count,
        total_count=len(QUESTION_WEIGHTS),
        gauge_position=gauge_position,
        trend_relationship=trend_rel,
        agrees_with_trade=agrees_with_trade,
    )
