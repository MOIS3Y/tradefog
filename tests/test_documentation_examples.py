"""Guard hand-maintained Swagger examples against contract drift."""

import inspect
from decimal import Decimal

import pytest
from pydantic import BaseModel, JsonValue

from tradefog.api.documentation import (
    ALLOCATION_EXAMPLE,
    ANALYTICS_EXAMPLE,
    TRADE_CLOSE_EXAMPLE,
    TRADE_PLAN_RESPONSE_EXAMPLE,
)
from tradefog.api.v1.endpoints import operations
from tradefog.api.v1.schemas import analytics, instruments, journal, trades


def documented_models() -> list[type[BaseModel]]:
    """Collect concrete journal schemas with centralized object examples."""
    return [
        model
        for module in (analytics, instruments, journal, trades, operations)
        for _, model in inspect.getmembers(module, inspect.isclass)
        if issubclass(model, BaseModel)
        and model.__module__ == module.__name__
        and isinstance(model.model_config.get("json_schema_extra"), dict)
    ]


@pytest.mark.parametrize(
    "model", documented_models(), ids=lambda m: m.__name__
)
def test_examples_match_contract(model: type[BaseModel]) -> None:
    """Reject stale fields, invalid values and incorrect computed examples."""
    extra = model.model_config.get("json_schema_extra")
    assert isinstance(extra, dict)
    examples = extra["examples"]
    assert isinstance(examples, list) and examples
    for example in examples:
        parsed = model.model_validate(example)
        assert parsed.model_dump(mode="json", exclude_unset=True) == example


def amount(example: dict[str, JsonValue], key: str) -> Decimal:
    """Read exact financial strings from documentation fixtures."""
    value = example[key]
    assert isinstance(value, str)
    return Decimal(value)


def test_trade_example_financial_consistency() -> None:
    """Keep the shared position, closing result and analytics coherent."""
    plan = TRADE_PLAN_RESPONSE_EXAMPLE
    quantity = amount(plan, "quantity")
    capital = amount(ALLOCATION_EXAMPLE, "capital")
    risk = amount(plan, "planned_risk_amount")
    assert risk == capital * amount(plan, "planned_risk_percent") / 100
    assert risk == quantity * amount(plan, "stop_distance")
    assert amount(plan, "planned_notional") == (
        quantity * amount(plan, "planned_entry")
    )
    pnl = amount(TRADE_CLOSE_EXAMPLE, "realized_pnl")
    assert pnl == quantity * (
        amount(TRADE_CLOSE_EXAMPLE, "actual_exit_price")
        - amount(plan, "planned_entry")
    ) - amount(TRADE_CLOSE_EXAMPLE, "total_commission") + amount(
        TRADE_CLOSE_EXAMPLE, "funding_result"
    )
    assert amount(ANALYTICS_EXAMPLE, "net_result_r") == pnl / risk
