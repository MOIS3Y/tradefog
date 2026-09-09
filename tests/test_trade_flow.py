"""Critical API flow from account login through trade analytics."""

from collections.abc import AsyncIterator, Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from tradefog.api.security import hash_password
from tradefog.config import get_settings
from tradefog.config.authentication import AuthenticationSettings
from tradefog.config.database import DatabaseSettings, SQLiteSettings
from tradefog.config.root import Settings
from tradefog.db.models import User
from tradefog.main import create_app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def flow_database_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Path]:
    """Apply production migrations to an isolated flow-test database."""
    path = tmp_path / "trade-flow.db"
    monkeypatch.setenv("TRADEFOG_DATABASE__ACTIVE", "sqlite")
    monkeypatch.setenv("TRADEFOG_DATABASE__SQLITE__PATH", str(path))
    get_settings.cache_clear()
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    try:
        yield path
    finally:
        get_settings.cache_clear()


@pytest.fixture
async def flow_client(
    flow_database_path: Path,
) -> AsyncIterator[AsyncClient]:
    """Provide the complete API with CLI-equivalent provisioned accounts."""
    settings = Settings(
        database=DatabaseSettings(
            sqlite=SQLiteSettings(path=flow_database_path),
        ),
        authentication=AuthenticationSettings(
            jwt_secret_key=SecretStr(
                "flow-test-signing-key-with-32-characters"
            ),
        ),
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with app.state.database.session() as session:
            session.add_all(
                [
                    User(
                        username="staff",
                        password=hash_password("staff-password-123"),
                        is_staff=True,
                    ),
                    User(
                        username="trader",
                        password=hash_password("trader-password-123"),
                    ),
                ]
            )
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client


async def authenticated_headers(
    client: AsyncClient,
    username: str,
    password: str,
) -> dict[str, str]:
    """Return bearer headers for one provisioned account."""
    response = await client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_complete_trade_lifecycle_updates_capital_and_analytics(
    flow_client: AsyncClient,
) -> None:
    """The primary journal workflow preserves risk and produces analytics."""
    staff = await authenticated_headers(
        flow_client,
        "staff",
        "staff-password-123",
    )
    trader = await authenticated_headers(
        flow_client,
        "trader",
        "trader-password-123",
    )

    base_response = await flow_client.post(
        "/api/v1/catalog/assets",
        headers=staff,
        json={"symbol": "BTC", "asset_type": "crypto"},
    )
    quote_response = await flow_client.post(
        "/api/v1/catalog/assets",
        headers=staff,
        json={"symbol": "USD", "asset_type": "fiat"},
    )
    assert base_response.status_code == quote_response.status_code == 201
    base_id = base_response.json()["id"]
    quote_id = quote_response.json()["id"]

    pair_response = await flow_client.post(
        "/api/v1/catalog/pairs",
        headers=staff,
        json={"base_id": base_id, "quote_id": quote_id},
    )
    venue_response = await flow_client.post(
        "/api/v1/catalog/venues",
        headers=staff,
        json={"name": "Test Exchange"},
    )
    assert pair_response.status_code == venue_response.status_code == 201
    pair_id = pair_response.json()["id"]
    venue_id = venue_response.json()["id"]

    instrument_response = await flow_client.post(
        f"/api/v1/catalog/venues/{venue_id}/instruments",
        headers=staff,
        json={
            "pair_id": pair_id,
            "product": "spot",
            "exec_symbol": "BTCUSD",
            "price_step": "0.01",
            "qty_step": "0.001",
            "settlement_asset_id": quote_id,
        },
    )
    capability_response = await flow_client.post(
        f"/api/v1/catalog/venues/{venue_id}/wallet-assets",
        headers=staff,
        json={"asset_id": quote_id},
    )
    assert instrument_response.status_code == 201, instrument_response.text
    assert capability_response.status_code == 201, capability_response.text
    instrument_id = instrument_response.json()["id"]
    capability_id = capability_response.json()["id"]

    profile_response = await flow_client.post(
        "/api/v1/profiles",
        headers=trader,
        json={"venue_id": venue_id, "name": "Main"},
    )
    assert profile_response.status_code == 201, profile_response.text
    profile_id = profile_response.json()["id"]

    wallet_asset_response = await flow_client.post(
        f"/api/v1/profiles/{profile_id}/wallet/assets",
        headers=trader,
        json={
            "venue_wallet_asset_id": capability_id,
            "risk_stop_capital": "5000",
        },
    )
    assert wallet_asset_response.status_code == 201
    wallet_asset_id = wallet_asset_response.json()["id"]
    assert wallet_asset_response.json()["status"] == "risk_stopped"

    deposit_response = await flow_client.post(
        f"/api/v1/profiles/wallet-assets/{wallet_asset_id}/operations",
        headers=trader,
        json={"kind": "deposit", "amount": "10000"},
    )
    assert deposit_response.status_code == 201, deposit_response.text
    assert Decimal(deposit_response.json()["amount"]) == Decimal(10000)
    operation_id = deposit_response.json()["id"]

    note_response = await flow_client.patch(
        f"/api/v1/profiles/wallet-operations/{operation_id}",
        headers=trader,
        json={"note": "Initial capital"},
    )
    assert note_response.status_code == 200, note_response.text
    assert note_response.json()["note"] == "Initial capital"
    assert note_response.json()["kind"] == "deposit"
    assert Decimal(note_response.json()["amount"]) == Decimal(10000)
    immutable_fields = await flow_client.patch(
        f"/api/v1/profiles/wallet-operations/{operation_id}",
        headers=trader,
        json={"note": "Corrected", "amount": "1"},
    )
    assert immutable_fields.status_code == 422

    strategy_response = await flow_client.post(
        f"/api/v1/profiles/{profile_id}/strategies",
        headers=trader,
        json={
            "name": "Three to one",
            "risk_percent": "1",
            "reward_multiple": 3,
        },
    )
    assert strategy_response.status_code == 201, strategy_response.text
    strategy_id = strategy_response.json()["id"]

    invalid_reward = await flow_client.post(
        f"/api/v1/profiles/{profile_id}/strategies",
        headers=trader,
        json={
            "name": "Insufficient edge",
            "risk_percent": "1",
            "reward_multiple": 2,
        },
    )
    assert invalid_reward.status_code == 422

    allocation_response = await flow_client.post(
        f"/api/v1/profiles/strategies/{strategy_id}/allocations",
        headers=trader,
        json={"wallet_asset_id": wallet_asset_id, "capital": "10000"},
    )
    assert allocation_response.status_code == 201, allocation_response.text
    allocation_id = allocation_response.json()["id"]

    protected_withdrawal = await flow_client.post(
        f"/api/v1/profiles/wallet-assets/{wallet_asset_id}/operations",
        headers=trader,
        json={"kind": "withdrawal", "amount": "1"},
    )
    assert protected_withdrawal.status_code == 409

    trade_response = await flow_client.post(
        "/api/v1/trades",
        headers=trader,
        json={
            "profile_id": profile_id,
            "strategy_id": strategy_id,
            "venue_instrument_id": instrument_id,
            "trade_date": "2026-09-07",
            "direction": "long",
        },
    )
    assert trade_response.status_code == 201, trade_response.text
    trade_id = trade_response.json()["id"]

    checklist_response = await flow_client.put(
        f"/api/v1/trades/{trade_id}/checklist",
        headers=trader,
        json={
            "market_sentiment": "POSITIVE",
            "information_background": "POSITIVE",
            "global_daily_direction": "POSITIVE",
            "local_daily_movement": "POSITIVE",
        },
    )
    assert checklist_response.status_code == 200
    assert Decimal(checklist_response.json()["score"]) == Decimal(1)
    assert checklist_response.json()["agrees_with_trade"] is True

    atr_response = await flow_client.post(
        f"/api/v1/trades/{trade_id}/atr",
        headers=trader,
        json={
            "value": "40",
            "contributing_date": "2026-09-07",
            "observed_session_range": "20",
        },
    )
    assert atr_response.status_code == 200, atr_response.text
    assert atr_response.json()["source"] == "manual"
    assert Decimal(atr_response.json()["session_range_percent"]) == Decimal(50)

    context_response = await flow_client.get(
        f"/api/v1/trades/{trade_id}/plan-context",
        headers=trader,
    )
    assert context_response.status_code == 200, context_response.text
    planning_context = context_response.json()
    assert planning_context["reward_multiple"] == 3
    assert Decimal(planning_context["target_risk_amount"]) == Decimal(100)
    assert Decimal(planning_context["wallet_available"]) == Decimal(10000)

    plan = {"planned_entry": "100", "planned_stop": "90"}
    preview_response = await flow_client.post(
        f"/api/v1/trades/{trade_id}/plan",
        headers=trader,
        json=plan,
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert Decimal(preview["planned_risk_amount"]) == Decimal(100)
    assert Decimal(preview["planned_take_profit"]) == Decimal(130)
    assert Decimal(preview["quantity"]) == Decimal(10)
    assert Decimal(preview["planned_notional"]) == Decimal(1000)
    assert Decimal(preview["take_profit_atr_percent"]) == Decimal(75)
    assert preview["fits_atr_limit"] is True
    assert preview["capital_sufficient"] is True
    assert Decimal(preview["target_risk_amount"]) == Decimal(100)
    assert Decimal(preview["capital_remaining"]) == Decimal(9000)

    missing_plan = await flow_client.post(
        f"/api/v1/trades/{trade_id}/submit",
        headers=trader,
        json={"status": "pending_entry"},
    )
    assert missing_plan.status_code == 422

    underfunded_plan = {"planned_entry": "100", "planned_stop": "99.90"}
    underfunded_preview = await flow_client.post(
        f"/api/v1/trades/{trade_id}/plan",
        headers=trader,
        json=underfunded_plan,
    )
    assert underfunded_preview.status_code == 200
    assert underfunded_preview.json()["capital_sufficient"] is False
    assert (
        await flow_client.put(
            f"/api/v1/trades/{trade_id}/plan",
            headers=trader,
            json=underfunded_plan,
        )
    ).status_code == 200
    blocked_submission = await flow_client.post(
        f"/api/v1/trades/{trade_id}/submit",
        headers=trader,
        json={"status": "pending_entry"},
    )
    assert blocked_submission.status_code == 409

    saved_plan = await flow_client.put(
        f"/api/v1/trades/{trade_id}/plan",
        headers=trader,
        json=plan,
    )
    assert saved_plan.status_code == 200, saved_plan.text

    reopened_draft = await flow_client.get(
        f"/api/v1/trades/{trade_id}",
        headers=trader,
    )
    assert reopened_draft.status_code == 200
    draft_context = reopened_draft.json()
    assert draft_context["plan"] == plan
    assert draft_context["checklist"]["market_sentiment"] == "POSITIVE"
    assert Decimal(draft_context["atr"]["value"]) == Decimal(40)

    submitted_response = await flow_client.post(
        f"/api/v1/trades/{trade_id}/submit",
        headers=trader,
        json={"status": "pending_entry"},
    )
    assert submitted_response.status_code == 200, submitted_response.text
    submitted = submitted_response.json()
    assert submitted["status"] == "pending_entry"
    assert submitted["submitted_at"] is not None
    assert submitted["opened_at"] is None
    assert submitted["snapshot"]["strategy_capital_id"] == allocation_id
    assert submitted["snapshot"]["settlement_asset_id"] == quote_id
    assert Decimal(submitted["snapshot"]["planned_entry"]) == Decimal(100)
    assert Decimal(submitted["snapshot"]["planned_stop"]) == Decimal(90)
    assert Decimal(submitted["snapshot"]["planned_take_profit"]) == Decimal(
        130
    )
    assert Decimal(submitted["snapshot"]["reward_multiple"]) == Decimal(3)
    assert Decimal(submitted["snapshot"]["planned_risk_amount"]) == Decimal(
        100
    )
    assert Decimal(submitted["snapshot"]["wallet_available"]) == Decimal(10000)
    assert Decimal(submitted["snapshot"]["atr_value"]) == Decimal(40)

    locked_strategy_rules = await flow_client.patch(
        f"/api/v1/profiles/strategies/{strategy_id}",
        headers=trader,
        json={"risk_percent": "2", "reward_multiple": 4},
    )
    assert locked_strategy_rules.status_code == 409

    locked_allocation = await flow_client.patch(
        f"/api/v1/profiles/allocations/{allocation_id}",
        headers=trader,
        json={"capital": "9000"},
    )
    assert locked_allocation.status_code == 409

    locked_checklist = await flow_client.put(
        f"/api/v1/trades/{trade_id}/checklist",
        headers=trader,
        json={},
    )
    assert locked_checklist.status_code == 409

    wallet_response = await flow_client.get(
        f"/api/v1/profiles/{profile_id}/wallet",
        headers=trader,
    )
    assert wallet_response.status_code == 200
    wallet_asset = wallet_response.json()["assets"][0]
    assert Decimal(wallet_asset["reserved"]) == Decimal(1000)
    assert Decimal(wallet_asset["available"]) == Decimal(9000)

    open_response = await flow_client.post(
        f"/api/v1/trades/{trade_id}/open",
        headers=trader,
    )
    assert open_response.status_code == 200
    assert open_response.json()["status"] == "open"
    assert open_response.json()["opened_at"] is not None

    close_response = await flow_client.post(
        f"/api/v1/trades/{trade_id}/close",
        headers=trader,
        json={"realized_pnl": "300", "actual_exit_price": "130"},
    )
    assert close_response.status_code == 200, close_response.text
    assert close_response.json()["status"] == "closed"
    assert close_response.json()["closed_at"] is not None
    closed_date = close_response.json()["closed_at"][:10]

    rating_response = await flow_client.patch(
        f"/api/v1/trades/{trade_id}",
        headers=trader,
        json={"quality_rating": 9},
    )
    assert rating_response.status_code == 200, rating_response.text
    assert rating_response.json()["quality_rating"] == 9

    invalid_rating = await flow_client.patch(
        f"/api/v1/trades/{trade_id}",
        headers=trader,
        json={"quality_rating": 11},
    )
    assert invalid_rating.status_code == 422

    locked_trade_date = await flow_client.patch(
        f"/api/v1/trades/{trade_id}",
        headers=trader,
        json={"trade_date": "2026-09-08"},
    )
    assert locked_trade_date.status_code == 409

    final_wallet_response = await flow_client.get(
        f"/api/v1/profiles/{profile_id}/wallet",
        headers=trader,
    )
    final_wallet_asset = final_wallet_response.json()["assets"][0]
    assert Decimal(final_wallet_asset["balance"]) == Decimal(10300)
    assert Decimal(final_wallet_asset["reserved"]) == Decimal(0)
    assert Decimal(final_wallet_asset["uncommitted"]) == Decimal(300)

    analytics_response = await flow_client.get(
        "/api/v1/analytics",
        headers=trader,
    )
    assert analytics_response.status_code == 200, analytics_response.text
    analytics = analytics_response.json()
    assert analytics["closed_trade_count"] == 1
    assert analytics["win_count"] == 1
    assert Decimal(analytics["win_rate_percent"]) == Decimal(100)
    assert Decimal(analytics["net_result_r"]) == Decimal(3)
    assert Decimal(analytics["expectancy_r"]) == Decimal(3)
    assert analytics["profit_factor_r"] is None
    assert Decimal(analytics["trajectory"][0]["result_r"]) == Decimal(3)
    assert analytics["average_quality_rating"] == "9"
    assert analytics["discipline_available"] is False
    assert analytics["discipline_break_even_reference"] == []
    assert analytics["trajectory"][0]["discipline_x"] is None
    money = analytics["monetary"][0]
    assert money["strategy_capital_id"] == allocation_id
    assert money["settlement_asset_id"] == quote_id
    assert money["settlement_asset_symbol"] == "USD"
    assert Decimal(money["net_pnl"]) == Decimal(300)
    assert Decimal(money["allocation_return_percent"]) == Decimal(3)

    allocation_analytics_response = await flow_client.get(
        "/api/v1/analytics",
        headers=trader,
        params={"strategy_capital_id": allocation_id},
    )
    assert allocation_analytics_response.status_code == 200
    allocation_analytics = allocation_analytics_response.json()
    assert allocation_analytics["discipline_available"] is True
    assert allocation_analytics["discipline_reward_multiple"] == 3
    discipline_reference = allocation_analytics[
        "discipline_break_even_reference"
    ]
    assert len(discipline_reference) == 2
    assert Decimal(discipline_reference[0]["x"]) == Decimal(0)
    assert Decimal(discipline_reference[0]["y"]) == Decimal(0)
    assert Decimal(discipline_reference[1]["x"]) == Decimal(3)
    assert Decimal(discipline_reference[1]["y"]) == Decimal(1)
    assert Decimal(
        allocation_analytics["trajectory"][0]["discipline_y"]
    ) == Decimal(1)

    close_period_response = await flow_client.get(
        "/api/v1/analytics",
        headers=trader,
        params={
            "period": "custom",
            "date_from": closed_date,
            "date_to": closed_date,
        },
    )
    assert close_period_response.status_code == 200
    assert close_period_response.json()["closed_trade_count"] == 1

    planning_period_response = await flow_client.get(
        "/api/v1/analytics",
        headers=trader,
        params={
            "period": "custom",
            "date_from": "2026-09-07",
            "date_to": "2026-09-07",
        },
    )
    assert planning_period_response.status_code == 200
    if closed_date != "2026-09-07":
        assert planning_period_response.json()["closed_trade_count"] == 0

    review_response = await flow_client.put(
        f"/api/v1/trades/{trade_id}/review",
        headers=trader,
        json={"completed": True},
    )
    assert review_response.status_code == 200
    assert review_response.json()["review_completed_at"] is not None

    await flow_client.patch(
        f"/api/v1/catalog/instruments/{instrument_id}",
        headers=staff,
        json={"is_active": False},
    )
    instrument_delete = await flow_client.delete(
        f"/api/v1/catalog/instruments/{instrument_id}",
        headers=staff,
    )
    assert instrument_delete.status_code == 409
    assert instrument_delete.json()["detail"]["code"] == "instrument_in_use"

    await flow_client.patch(
        f"/api/v1/catalog/wallet-assets/{capability_id}",
        headers=staff,
        json={"is_active": False},
    )
    capability_delete = await flow_client.delete(
        f"/api/v1/catalog/wallet-assets/{capability_id}",
        headers=staff,
    )
    assert capability_delete.status_code == 409
    assert capability_delete.json()["detail"]["code"] == "wallet_asset_in_use"

    archive_profile = await flow_client.patch(
        f"/api/v1/profiles/{profile_id}",
        headers=trader,
        json={"is_archived": True},
    )
    assert archive_profile.status_code == 200
    profile_delete = await flow_client.delete(
        f"/api/v1/profiles/{profile_id}",
        headers=trader,
    )
    assert profile_delete.status_code == 409


async def test_empty_profile_requires_archival_before_deletion(
    flow_client: AsyncClient,
) -> None:
    """Only an archived profile without journal facts can be removed."""
    staff = await authenticated_headers(
        flow_client,
        "staff",
        "staff-password-123",
    )
    trader = await authenticated_headers(
        flow_client,
        "trader",
        "trader-password-123",
    )
    venue = await flow_client.post(
        "/api/v1/catalog/venues",
        headers=staff,
        json={"name": "Paper account"},
    )
    profile = await flow_client.post(
        "/api/v1/profiles",
        headers=trader,
        json={"venue_id": venue.json()["id"], "name": "Disposable"},
    )
    profile_id = profile.json()["id"]

    active_delete = await flow_client.delete(
        f"/api/v1/profiles/{profile_id}",
        headers=trader,
    )
    assert active_delete.status_code == 409
    archived = await flow_client.patch(
        f"/api/v1/profiles/{profile_id}",
        headers=trader,
        json={"is_archived": True},
    )
    assert archived.status_code == 200
    deleted = await flow_client.delete(
        f"/api/v1/profiles/{profile_id}",
        headers=trader,
    )
    assert deleted.status_code == 204
