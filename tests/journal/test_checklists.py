"""Tests for the fixed directional checklist assessment."""

from decimal import Decimal

from pytest import raises

from tradefog.journal.checklists import (
    AssessmentDirection,
    ChecklistAnswers,
    DirectionalValue,
    TrendRelationship,
    calculate_checklist_assessment,
)


def test_empty_checklist_is_neutral_and_incomplete() -> None:
    assessment = calculate_checklist_assessment(ChecklistAnswers())

    assert assessment.score == 0
    assert assessment.direction == AssessmentDirection.NEUTRAL
    assert assessment.completeness == 0
    assert assessment.answered_count == 0
    assert assessment.gauge_position == 50
    assert assessment.trend_relationship == TrendRelationship.UNASSESSED
    assert assessment.agrees_with_trade is None


def test_weighted_observations_produce_signed_assessment() -> None:
    assessment = calculate_checklist_assessment(
        ChecklistAnswers(
            market_sentiment=DirectionalValue.NEGATIVE,
            information_background=DirectionalValue.NEUTRAL,
            global_daily_direction=DirectionalValue.NEGATIVE,
            local_daily_movement=DirectionalValue.POSITIVE,
        ),
        selected_direction="LONG",
    )

    assert assessment.score == Decimal(-2) / Decimal(7)
    assert assessment.direction == AssessmentDirection.SHORT
    assert assessment.completeness == 1
    assert assessment.trend_relationship == TrendRelationship.DIVERGENT
    assert assessment.agrees_with_trade is False


def test_missing_answer_retains_its_weight_in_score_denominator() -> None:
    assessment = calculate_checklist_assessment(
        ChecklistAnswers(
            local_daily_movement=DirectionalValue.POSITIVE,
        ),
        selected_direction="LONG",
    )

    assert assessment.score == Decimal(2) / Decimal(7)
    assert assessment.completeness == Decimal("0.25")
    assert assessment.agrees_with_trade is True


def test_matching_non_neutral_daily_observations_are_aligned() -> None:
    assessment = calculate_checklist_assessment(
        ChecklistAnswers(
            global_daily_direction=DirectionalValue.POSITIVE,
            local_daily_movement=DirectionalValue.POSITIVE,
        )
    )

    assert assessment.trend_relationship == TrendRelationship.ALIGNED


def test_neutral_and_directional_daily_observations_are_mixed() -> None:
    assessment = calculate_checklist_assessment(
        ChecklistAnswers(
            global_daily_direction=DirectionalValue.NEUTRAL,
            local_daily_movement=DirectionalValue.POSITIVE,
        )
    )

    assert assessment.trend_relationship == TrendRelationship.MIXED


def test_unknown_answer_is_rejected() -> None:
    with raises(ValueError):
        _ = calculate_checklist_assessment(
            ChecklistAnswers(market_sentiment="UNKNOWN")
        )
