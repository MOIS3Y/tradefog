"""Tests for manual trade lifecycle, risk snapshots, and HTTP ownership."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark, raises

from tradefog.accounts.models import User
from tradefog.journal.forms import TradeDraftForm
from tradefog.journal.models import (
    Asset,
    ProfileTradingPair,
    Trade,
    TradeChecklist,
    TradingProfile,
)
from tradefog.journal.services import (
    cancel_trade,
    close_trade,
    open_trade,
    save_trade_draft,
    submit_trade,
    update_trade_result,
)

DEFAULT_RISK_STOP_CAPITAL = Decimal(9000)


def test_trade_urls_follow_active_language_prefix() -> None:
    """Trade routes should reverse inside the explicit request language."""
    with override("ru"):
        assert reverse("trade_overview") == "/ru/trades/"
        assert reverse("trade_profile_select") == "/ru/trades/new/"
        assert reverse("trade_create", args=[7]) == "/ru/trades/new/7/"
        assert reverse("new_trade_checklist", args=[7]) == (
            "/ru/trades/new/7/checklist/"
        )
        assert reverse("trade_detail", args=[9]) == "/ru/trades/9/"
        assert reverse("trade_checklist", args=[9]) == (
            "/ru/trades/9/checklist/"
        )


def create_profile(
    owner: User,
    *,
    risk_stop_capital: Decimal = DEFAULT_RISK_STOP_CAPITAL,
    market_type: str = TradingProfile.MarketType.LINEAR_PERPETUAL.value,
) -> TradingProfile:
    """Create a round manual allocation for trade tests."""
    capital_asset, _created = Asset.objects.get_or_create(
        owner=owner,
        symbol="USDT",
    )
    return TradingProfile.objects.create(
        owner=owner,
        name="Primary",
        capital_asset=capital_asset,
        market_type=market_type,
        initial_capital=Decimal(10000),
        risk_per_trade_percent=Decimal(1),
        risk_stop_capital=risk_stop_capital,
    )


def create_trading_pair(profile: TradingProfile) -> ProfileTradingPair:
    """Create a pair with simple executable precision."""
    asset, _created = Asset.objects.get_or_create(
        owner=profile.owner,
        symbol="BTC",
    )
    return ProfileTradingPair.objects.create(
        profile=profile,
        asset=asset,
        price_step=Decimal("0.5"),
        quantity_step=Decimal("0.1"),
        minimum_quantity=Decimal("0.1"),
        minimum_notional=Decimal(10),
    )


def create_trade(
    profile: TradingProfile,
    trading_pair: ProfileTradingPair,
    *,
    direction: str = Trade.Direction.LONG.value,
) -> Trade:
    """Create a valid but unsnapshotted draft."""
    return Trade.objects.create(
        profile=profile,
        trading_pair=trading_pair,
        direction=direction,
        trade_date=date(2026, 8, 29),
        planned_entry=Decimal(100),
        planned_stop=Decimal(95) if direction == "LONG" else Decimal(105),
    )


@mark.django_db
def test_submit_freezes_plan_and_reserves_actual_rounded_risk() -> None:
    """Submission should preserve decision context and reserve the plan."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    trade = create_trade(profile, create_trading_pair(profile))

    submitted = submit_trade(trade)

    profile.refresh_from_db()
    assert submitted.status == Trade.Status.PENDING_ENTRY.value
    assert submitted.planned_take_profit == Decimal(115)
    assert submitted.planned_quantity == Decimal(20)
    assert submitted.planned_risk_amount == Decimal(100)
    assert submitted.planned_risk_percent == Decimal("1.000")
    assert submitted.reward_multiple == Decimal(3)
    assert submitted.capital_snapshot == Decimal("10000.00000000")
    assert submitted.risk_base_snapshot == Decimal("10000.00000000")
    assert submitted.reserved_risk_snapshot == Decimal(0)
    assert submitted.risk_capacity_snapshot == Decimal(900)
    assert not submitted.risk_limit_breached
    assert profile.reserved_risk == Decimal(100)


@mark.django_db
def test_advisory_breach_is_recorded_and_profile_becomes_at_risk() -> None:
    """A manual violating order remains recordable with an explicit fact."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user, risk_stop_capital=Decimal(9950))
    trade = create_trade(profile, create_trading_pair(profile))

    submitted = submit_trade(trade)

    profile.refresh_from_db()
    assert submitted.risk_limit_breached
    assert submitted.risk_capacity_snapshot == Decimal(-50)
    assert profile.status == TradingProfile.Status.AT_RISK.value


@mark.django_db
def test_each_pending_trade_accounts_for_existing_reserved_risk() -> None:
    """A new snapshot should include independent pending and open decisions."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user, risk_stop_capital=Decimal(9800))
    instrument = create_trading_pair(profile)
    first = submit_trade(create_trade(profile, instrument))
    second = submit_trade(create_trade(profile, instrument))

    profile.refresh_from_db()
    assert first.reserved_risk_snapshot == 0
    assert second.reserved_risk_snapshot == Decimal(100)
    assert second.risk_capacity_snapshot == 0
    assert second.risk_limit_breached
    assert profile.reserved_risk == Decimal(200)
    assert profile.status == TradingProfile.Status.AT_RISK.value


@mark.django_db
def test_cancel_pending_trade_releases_risk() -> None:
    """Cancelling an unfilled order should release its reservation."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user, risk_stop_capital=Decimal(9950))
    submitted = submit_trade(
        create_trade(profile, create_trading_pair(profile))
    )

    cancelled = cancel_trade(submitted)

    profile.refresh_from_db()
    assert cancelled.status == Trade.Status.CANCELLED.value
    assert cancelled.cancelled_at is not None
    assert profile.reserved_risk == 0
    assert profile.status == TradingProfile.Status.ACTIVE.value


@mark.django_db
def test_open_and_close_trade_updates_capital_and_result_r() -> None:
    """Only the final aggregate result should enter profile capital."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    submitted = submit_trade(
        create_trade(profile, create_trading_pair(profile))
    )
    opened = open_trade(submitted)

    closed = close_trade(
        opened,
        realized_pnl=Decimal(300),
        actual_exit_price=Decimal(115),
    )

    profile.refresh_from_db()
    assert closed.status == Trade.Status.CLOSED.value
    assert closed.result_r == Decimal(3)
    assert closed.actual_exit_price == Decimal(115)
    assert closed.closed_at is not None
    assert profile.realized_pnl_total == Decimal(300)
    assert profile.current_capital == Decimal("10300.00000000")
    assert profile.reserved_risk == 0


@mark.django_db
def test_fee_and_funding_are_reference_facts_inside_net_pnl() -> None:
    """Optional costs must never be subtracted from authoritative net P&L."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    trade = open_trade(
        submit_trade(create_trade(profile, create_trading_pair(profile)))
    )

    closed = close_trade(
        trade,
        realized_pnl=Decimal(275),
        commission_total=Decimal(15),
        funding_result=Decimal(-10),
    )

    profile.refresh_from_db()
    assert closed.commission_total == Decimal(15)
    assert closed.funding_result == Decimal(-10)
    assert closed.result_r == Decimal("2.75")
    assert profile.current_capital == Decimal(10275)


@mark.django_db
def test_submission_records_advisory_notional_limit_breach() -> None:
    """A 1x plan beyond capital remains recordable but preserves a warning."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    trading_pair = create_trading_pair(profile)
    trade = create_trade(profile, trading_pair)
    trade.planned_entry = Decimal(10000)
    trade.planned_stop = Decimal(9995)
    trade.save(update_fields=["planned_entry", "planned_stop"])

    submitted = submit_trade(trade)

    assert submitted.notional_limit_breached
    assert submitted.status == Trade.Status.PENDING_ENTRY.value


@mark.django_db
def test_loss_does_not_reduce_future_risk_below_initial_floor() -> None:
    """A losing result changes capital while preserving the sizing floor."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    instrument = create_trading_pair(profile)
    first = submit_trade(create_trade(profile, instrument))
    first = open_trade(first)
    first = close_trade(first, realized_pnl=Decimal(-100))

    second = submit_trade(create_trade(profile, instrument))

    profile.refresh_from_db()
    assert profile.current_capital == Decimal("9900.00000000")
    assert profile.risk_base == Decimal("10000.00000000")
    assert second.capital_snapshot == Decimal("9900.00000000")
    assert second.risk_base_snapshot == Decimal("10000.00000000")
    assert second.planned_risk_amount == Decimal(100)
    assert first.planned_risk_amount == Decimal(100)


@mark.django_db
def test_correcting_closed_result_recalculates_capital_without_resnapshot() -> (
    None
):
    """A journal correction should update P&L but retain decision context."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    trade = submit_trade(
        create_trade(profile, create_trading_pair(profile))
    )
    trade = open_trade(trade)
    trade = close_trade(trade, realized_pnl=Decimal(-100))

    corrected = update_trade_result(trade, realized_pnl=Decimal(300))

    profile.refresh_from_db()
    assert corrected.result_r == Decimal(3)
    assert corrected.capital_snapshot == Decimal("10000.00000000")
    assert corrected.planned_risk_amount == Decimal(100)
    assert profile.current_capital == Decimal("10300.00000000")


@mark.django_db
def test_invalid_lifecycle_transition_is_rejected() -> None:
    """An opened position cannot be cancelled as an unfilled order."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    opened = open_trade(
        submit_trade(create_trade(profile, create_trading_pair(profile)))
    )

    with raises(ValidationError):
        _ = cancel_trade(opened)


@mark.django_db
def test_spot_form_rejects_short_direction() -> None:
    """Ordinary spot instruments should expose LONG decisions only."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(
        user,
        market_type=TradingProfile.MarketType.SPOT.value,
    )
    instrument = create_trading_pair(profile)
    data = QueryDict(mutable=True)
    data.update(
        {
            "trade_date": "2026-08-29",
            "trading_pair": str(instrument.id),
            "direction": Trade.Direction.SHORT.value,
            "planned_entry": "100",
            "planned_stop": "105",
        }
    )
    form = TradeDraftForm(profile, data)

    assert not form.is_valid()
    assert "direction" in form.errors


@mark.django_db
def test_new_trade_form_uses_browser_compatible_current_date() -> None:
    """A new draft should show the configured current date immediately."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)

    with patch(
        "tradefog.journal.forms.timezone.localdate",
        return_value=date(2026, 8, 29),
    ):
        form = TradeDraftForm(profile)

    assert 'value="2026-08-29"' in str(form["trade_date"])


@mark.django_db
def test_trade_form_identifies_market_and_renders_direction_toggle() -> None:
    """The workspace should identify markets without repeating the profile."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(
        user,
        market_type=TradingProfile.MarketType.SPOT.value,
    )
    _ = create_trading_pair(profile)
    client = Client()
    client.force_login(user)

    response = client.get(f"/en/trades/new/{profile.id}/")
    content = response.content.decode()

    assert response.status_code == 200
    assert "BTC/USDT" in content
    assert "BTC/USDT — Primary" not in content
    assert "Spot" in content
    assert content.count('name="direction"') == 1
    assert ">SHORT</button>" in content
    assert 'data-bs-toggle="tooltip"' in content
    assert "SHORT is unavailable for Spot markets." in content


@mark.django_db
def test_trade_workspace_renders_localized_segmented_checklist() -> None:
    """The fixed checklist should remain legible in the Russian workspace."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    _ = create_trading_pair(profile)
    client = Client()
    client.force_login(user)

    response = client.get(f"/ru/trades/new/{profile.id}/")
    content = response.content.decode()

    assert response.status_code == 200
    assert "Чек-лист рынка" in content
    assert "Информационный фон" in content
    assert "Глобальное направление D1" in content
    assert (
        "Взвешенный контекст от SHORT через нейтральную зону к LONG."
        in content
    )
    assert "Не оценено" not in content
    assert content.count('name="checklist-market_sentiment"') == 3
    assert content.count('name="checklist-global_daily_direction"') == 3
    assert 'id="checklist-assessment"' in content


@mark.django_db
def test_submitted_trade_locks_profile_risk_source() -> None:
    """Historical snapshots require initial capital and risk to stay fixed."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    _ = submit_trade(create_trade(profile, create_trading_pair(profile)))

    profile.initial_capital = Decimal(12000)
    with raises(ValidationError):
        profile.full_clean()


@mark.django_db
def test_profile_form_disables_locked_risk_source_fields() -> None:
    """The profile editor should communicate submitted-trade immutability."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    _ = submit_trade(create_trade(profile, create_trading_pair(profile)))
    client = Client()
    client.force_login(user)

    response = client.get(f"/en/profiles/{profile.id}/edit/")

    assert response.status_code == 200
    assert b'name="initial_capital"' in response.content
    assert b'name="risk_per_trade_percent"' in response.content
    assert response.content.count(b"disabled") >= 3
    assert b"locked because a trade was submitted" in response.content

    profile.refresh_from_db()
    profile.risk_per_trade_percent = Decimal(2)
    with raises(ValidationError):
        profile.full_clean()


@mark.django_db
def test_trade_routes_enforce_profile_ownership() -> None:
    """Trade views must resolve decisions through the profile owner."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    profile = create_profile(owner)
    trade = create_trade(profile, create_trading_pair(profile))
    client = Client()
    client.force_login(stranger)

    assert client.get(f"/en/trades/{trade.id}/").status_code == 404
    assert client.post(f"/en/trades/{trade.id}/submit/").status_code == 404
    assert client.get(f"/en/trades/new/{profile.id}/").status_code == 404


@mark.django_db
def test_user_creates_retrospective_draft_and_corrects_its_date() -> None:
    """The analytical date should remain an owner-correctable journal fact."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    instrument = create_trading_pair(profile)
    client = Client()
    client.force_login(user)

    create_response = client.post(
        f"/en/trades/new/{profile.id}/",
        {
            "trade_date": "2026-07-31",
            "trading_pair": str(instrument.id),
            "direction": "LONG",
            "planned_entry": "100",
            "planned_stop": "95",
        },
    )
    trade = Trade.objects.get()
    date_response = client.post(
        f"/en/trades/{trade.id}/date/",
        {"trade_date": "2026-07-30"},
    )

    trade.refresh_from_db()
    assert create_response.status_code == 302
    assert date_response.status_code == 302
    assert trade.trade_date == date(2026, 7, 30)


@mark.django_db
def test_trade_creation_persists_typed_checklist_answers() -> None:
    """An explicit draft save should create its checklist atomically."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    instrument = create_trading_pair(profile)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/trades/new/{profile.id}/",
        {
            "trade_date": "2026-08-29",
            "trading_pair": str(instrument.id),
            "direction": "LONG",
            "planned_entry": "100",
            "planned_stop": "95",
            "checklist-market_sentiment": "NEGATIVE",
            "checklist-information_background": "NEUTRAL",
            "checklist-global_daily_direction": "NEGATIVE",
            "checklist-local_daily_movement": "POSITIVE",
        },
    )

    checklist = TradeChecklist.objects.select_related("trade").get()
    assert response.status_code == 302
    assert checklist.schema_version == 1
    assert checklist.market_sentiment == "NEGATIVE"
    assert checklist.information_background == "NEUTRAL"
    assert checklist.global_daily_direction == "NEGATIVE"
    assert checklist.local_daily_movement == "POSITIVE"
    assert checklist.assessment.direction.value == "SHORT"
    assert checklist.assessment.agrees_with_trade is False


@mark.django_db
def test_saved_checklist_cannot_be_changed_after_submission() -> None:
    """The application boundary should freeze answers outside draft."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    trade = create_trade(profile, create_trading_pair(profile))
    checklist = TradeChecklist(
        trade=trade,
        global_daily_direction="POSITIVE",
    )
    _ = save_trade_draft(trade, checklist)
    submitted = submit_trade(trade)
    checklist.global_daily_direction = "NEGATIVE"

    with raises(ValidationError):
        _ = save_trade_draft(submitted, checklist)

    checklist.refresh_from_db()
    assert checklist.global_daily_direction == "POSITIVE"


@mark.django_db
def test_saved_draft_renders_its_current_checklist_assessment() -> None:
    """An unbound edit form should assess answers loaded from persistence."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    trade = create_trade(profile, create_trading_pair(profile))
    checklist = TradeChecklist(
        trade=trade,
        global_daily_direction="POSITIVE",
        local_daily_movement="POSITIVE",
    )
    _ = save_trade_draft(trade, checklist)
    client = Client()
    client.force_login(user)

    response = client.get(f"/en/trades/{trade.id}/")

    assert response.status_code == 200
    assert b"--tf-gauge-position: 86%" in response.content
    assert b"2 of 4 assessed" in response.content
    assert b"Global and local D1 observations are aligned" in response.content


@mark.django_db
def test_htmx_plan_preview_does_not_persist_trade() -> None:
    """Reactive plan calculation should remain a read-only preview."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    instrument = create_trading_pair(profile)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/trades/new/{profile.id}/plan/",
        {
            "trade_date": "2026-08-29",
            "trading_pair": str(instrument.id),
            "direction": "LONG",
            "planned_entry": "100",
            "planned_stop": "95",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"115" in response.content
    assert b"20" in response.content
    assert b"Stop loss" in response.content
    assert b"95 USDT" in response.content
    assert b"Planned profit" in response.content
    assert b"300 USDT" in response.content
    assert not Trade.objects.exists()


@mark.django_db
def test_htmx_checklist_preview_is_advisory_and_does_not_persist() -> None:
    """Reactive assessment should preserve disagreement without saving."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/trades/new/{profile.id}/checklist/",
        {
            "direction": "LONG",
            "checklist-market_sentiment": "NEGATIVE",
            "checklist-information_background": "NEGATIVE",
            "checklist-global_daily_direction": "NEGATIVE",
            "checklist-local_daily_movement": "POSITIVE",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"--tf-gauge-position: 29%" in response.content
    assert b"Direction differs from the checklist" in response.content
    assert b"Global and local D1 observations diverge" in response.content
    assert not Trade.objects.exists()
    assert not TradeChecklist.objects.exists()


@mark.django_db
def test_checklist_preview_enforces_ownership_and_draft_status() -> None:
    """Only the owner may preview edits to an editable checklist."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    profile = create_profile(owner)
    trade = create_trade(profile, create_trading_pair(profile))
    stranger_client = Client()
    stranger_client.force_login(stranger)

    assert (
        stranger_client.post(f"/en/trades/{trade.id}/checklist/").status_code
        == 404
    )

    submitted = submit_trade(trade)
    owner_client = Client()
    owner_client.force_login(owner)
    assert (
        owner_client.post(
            f"/en/trades/{submitted.id}/checklist/"
        ).status_code
        == 409
    )


@mark.django_db
def test_direction_plan_preview_updates_checklist_out_of_band() -> None:
    """Changing trade direction should also refresh disagreement state."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    instrument = create_trading_pair(profile)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/trades/new/{profile.id}/plan/",
        {
            "trade_date": "2026-08-29",
            "trading_pair": str(instrument.id),
            "direction": "SHORT",
            "planned_entry": "100",
            "planned_stop": "105",
            "checklist-market_sentiment": "POSITIVE",
            "checklist-information_background": "POSITIVE",
            "checklist-global_daily_direction": "POSITIVE",
            "checklist-local_daily_movement": "POSITIVE",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b'hx-swap-oob="innerHTML"' in response.content
    assert b"--tf-gauge-position: 100%" in response.content
    assert b"Direction differs from the checklist" in response.content


@mark.django_db
def test_incomplete_htmx_plan_returns_guidance_instead_of_error() -> None:
    """Incremental input should tolerate fields that are not filled yet."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    _ = create_trading_pair(profile)
    client = Client()
    client.force_login(user)

    response = client.post(
        f"/en/trades/new/{profile.id}/plan/",
        {
            "trade_date": "2026-08-29",
            "trading_pair": "",
            "direction": "LONG",
            "planned_entry": "",
            "planned_stop": "",
        },
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    assert b"Plan needs attention" in response.content


@mark.django_db
def test_trade_pages_render_through_complete_manual_lifecycle() -> None:
    """Every lifecycle state should have a usable server-rendered workspace."""
    user = User.objects.create_user(username="trader")
    profile = create_profile(user)
    trade = create_trade(profile, create_trading_pair(profile))
    client = Client()
    client.force_login(user)

    assert client.get("/en/trades/").status_code == 200
    assert client.get("/en/trades/new/").status_code == 200

    draft_response = client.get(f"/en/trades/{trade.id}/")
    assert draft_response.status_code == 200
    assert b"Position plan" in draft_response.content

    trade = submit_trade(trade)
    pending_response = client.get(f"/en/trades/{trade.id}/")
    assert pending_response.status_code == 200
    assert b"Pending entry" in pending_response.content

    trade = open_trade(trade)
    open_response = client.get(f"/en/trades/{trade.id}/")
    assert open_response.status_code == 200
    assert b"Close position" in open_response.content
    assert client.get(f"/en/trades/{trade.id}/close/").status_code == 200

    trade = close_trade(trade, realized_pnl=Decimal(-50))
    closed_response = client.get(f"/en/trades/{trade.id}/")
    assert closed_response.status_code == 200
    assert b"-0.5R" in closed_response.content
    assert client.get(f"/en/trades/{trade.id}/close/").status_code == 200
    correction_response = client.post(
        f"/en/trades/{trade.id}/close/",
        {"realized_pnl": "-25", "actual_exit_price": "94.5"},
    )
    trade.refresh_from_db()
    assert correction_response.status_code == 302
    assert trade.result_r == Decimal("-0.25")
    assert client.get(f"/en/trades/{trade.id}/date/").status_code == 200
