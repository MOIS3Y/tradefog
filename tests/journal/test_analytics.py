"""Tests for filtered trading-quality statistics and X/Y trajectory."""

# pyright: reportAny=false

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark, raises

from tradefog.accounts.models import User
from tradefog.journal.analytics import (
    ClosedTradeResult,
    Outcome,
    calculate_trade_analytics,
)
from tradefog.journal.models import (
    Asset,
    ProfileTradingPair,
    Trade,
    TradingProfile,
)


def result(
    result_r: str,
    *,
    trade_id: int = 1,
    trade_date: date | None = None,
) -> ClosedTradeResult:
    """Build one pure analytics input with the fixed strategy multiple."""
    return ClosedTradeResult(
        trade_id=trade_id,
        trade_date=trade_date or date(2026, 8, 1),
        profile_name="Primary",
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
        pair_symbol="BTC/USDT",
        direction=Trade.Direction.LONG.value,
        result_r=Decimal(result_r),
        reward_multiple=Decimal(3),
    )


def test_partial_outcomes_build_exact_trajectory_and_aggregates() -> None:
    """Partial outcomes should contribute proportional X/Y coordinates."""
    analytics = calculate_trade_analytics(
        [
            result("-1", trade_id=1),
            result("3", trade_id=2),
            result("-0.25", trade_id=3),
            result("1.5", trade_id=4),
            result("0", trade_id=5),
        ]
    )

    assert [(point.x, point.y) for point in analytics.points] == [
        (Decimal(1), Decimal(0)),
        (Decimal(1), Decimal(1)),
        (Decimal("1.25"), Decimal(1)),
        (Decimal("1.25"), Decimal("1.5")),
        (Decimal("1.25"), Decimal("1.5")),
    ]
    assert analytics.closed_trade_count == 5
    assert analytics.win_count == 2
    assert analytics.loss_count == 2
    assert analytics.break_even_count == 1
    assert analytics.win_rate == Decimal(40)
    assert analytics.net_result_r == Decimal("3.25")
    assert analytics.average_result_r == Decimal("0.65")
    assert analytics.gross_profit_r == Decimal("4.5")
    assert analytics.gross_loss_r == Decimal("1.25")
    assert analytics.current_streak.outcome is None
    assert analytics.current_streak.count == 0


def test_streaks_reset_on_break_even_and_direction_change() -> None:
    """Current and maximum streaks should describe actual consecutive runs."""
    analytics = calculate_trade_analytics(
        [
            result("3"),
            result("1"),
            result("0"),
            result("-1"),
            result("-0.5"),
            result("-0.25"),
        ]
    )

    assert analytics.current_streak.outcome is Outcome.LOSS
    assert analytics.current_streak.count == 3
    assert analytics.maximum_winning_streak == 2
    assert analytics.maximum_losing_streak == 3


def test_empty_selection_has_zero_metrics_and_no_points() -> None:
    """An empty analytics selection should remain mathematically defined."""
    analytics = calculate_trade_analytics([])

    assert analytics.closed_trade_count == 0
    assert analytics.win_rate == 0
    assert analytics.average_result_r == 0
    assert analytics.points == ()
    assert analytics.final_x == 0
    assert analytics.final_y == 0


def test_non_positive_reward_multiple_is_rejected() -> None:
    """Historical trajectory cannot divide by an invalid strategy multiple."""
    invalid = result("3")
    invalid = ClosedTradeResult(
        trade_id=invalid.trade_id,
        trade_date=invalid.trade_date,
        profile_name=invalid.profile_name,
        market_type=invalid.market_type,
        pair_symbol=invalid.pair_symbol,
        direction=invalid.direction,
        result_r=invalid.result_r,
        reward_multiple=Decimal(0),
    )

    with raises(ValueError):
        _ = calculate_trade_analytics([invalid])


def create_profile(
    owner: User,
    *,
    name: str,
    market_type: str,
) -> TradingProfile:
    """Create a profile suitable for analytics HTTP tests."""
    capital_asset, _created = Asset.objects.get_or_create(
        owner=owner,
        symbol="USDT",
    )
    return TradingProfile.objects.create(
        owner=owner,
        name=name,
        capital_asset=capital_asset,
        market_type=market_type,
        initial_capital=Decimal(10000),
        risk_per_trade_percent=Decimal(1),
        risk_stop_capital=Decimal(9000),
    )


def create_pair(
    profile: TradingProfile,
    symbol: str,
) -> ProfileTradingPair:
    """Create one profile-scoped pair with simple execution precision."""
    asset, _created = Asset.objects.get_or_create(
        owner=profile.owner,
        symbol=symbol,
    )
    return ProfileTradingPair.objects.create(
        profile=profile,
        asset=asset,
        price_step=Decimal(1),
        quantity_step=Decimal(1),
    )


def create_closed_trade(
    profile: TradingProfile,
    pair: ProfileTradingPair,
    *,
    trade_date: date,
    result_r: Decimal,
) -> Trade:
    """Persist the material facts of one already closed trade."""
    return Trade.objects.create(
        profile=profile,
        trading_pair=pair,
        status=Trade.Status.CLOSED.value,
        direction=Trade.Direction.LONG.value,
        trade_date=trade_date,
        planned_entry=Decimal(100),
        planned_stop=Decimal(99),
        planned_risk_amount=Decimal(100),
        reward_multiple=Decimal(3),
        realized_pnl=result_r * Decimal(100),
        result_r=result_r,
    )


@mark.django_db
def test_analytics_page_is_owner_scoped_and_renders_apex_chart() -> None:
    """The page should expose only the authenticated owner's closed trades."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    profile = create_profile(
        owner,
        name="Primary",
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
    )
    pair = create_pair(profile, "BTC")
    _ = create_closed_trade(
        profile,
        pair,
        trade_date=date(2026, 8, 1),
        result_r=Decimal(3),
    )
    stranger_profile = create_profile(
        stranger,
        name="Hidden",
        market_type=TradingProfile.MarketType.SPOT.value,
    )
    _ = create_closed_trade(
        stranger_profile,
        create_pair(stranger_profile, "ETH"),
        trade_date=date(2026, 8, 2),
        result_r=Decimal(-1),
    )
    client = Client()
    client.force_login(owner)

    response = client.get("/en/analytics/")

    analytics = response.context["analytics"]
    assert response.status_code == 200
    assert analytics.closed_trade_count == 1
    assert analytics.net_result_r == Decimal(3)
    assert b"apexcharts/apexcharts.min.js" in response.content
    assert b'data-analytics-chart="xy-trajectory"' in response.content
    assert b"Hidden" not in response.content


@mark.django_db
def test_filters_recalculate_path_from_zero_in_deterministic_order() -> None:
    """A date-filtered sequence should neither inherit nor reorder old points."""
    owner = User.objects.create_user(username="owner")
    profile = create_profile(
        owner,
        name="Primary",
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
    )
    pair = create_pair(profile, "BTC")
    _ = create_closed_trade(
        profile,
        pair,
        trade_date=date(2026, 7, 31),
        result_r=Decimal(-1),
    )
    first_selected = create_closed_trade(
        profile,
        pair,
        trade_date=date(2026, 8, 1),
        result_r=Decimal(3),
    )
    second_selected = create_closed_trade(
        profile,
        pair,
        trade_date=date(2026, 8, 1),
        result_r=Decimal("-0.5"),
    )
    client = Client()
    client.force_login(owner)

    response = client.get(
        "/en/analytics/",
        {
            "period": "CUSTOM",
            "date_from": "2026-08-01",
            "date_to": "2026-08-31",
        },
    )

    analytics = response.context["analytics"]
    assert [point.trade.trade_id for point in analytics.points] == [
        first_selected.id,
        second_selected.id,
    ]
    assert [(point.x, point.y) for point in analytics.points] == [
        (Decimal(0), Decimal(1)),
        (Decimal("0.5"), Decimal(1)),
    ]


@mark.django_db
def test_profile_market_and_pair_filters_use_the_same_selection() -> None:
    """Every analytics metric should derive from all selected dimensions."""
    owner = User.objects.create_user(username="owner")
    linear = create_profile(
        owner,
        name="Linear",
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
    )
    spot = create_profile(
        owner,
        name="Spot",
        market_type=TradingProfile.MarketType.SPOT.value,
    )
    bitcoin = create_pair(linear, "BTC")
    ether = create_pair(linear, "ETH")
    spot_bitcoin = create_pair(spot, "BTC")
    for profile, pair, result_r in (
        (linear, bitcoin, Decimal(3)),
        (linear, ether, Decimal(-1)),
        (spot, spot_bitcoin, Decimal(2)),
    ):
        _ = create_closed_trade(
            profile,
            pair,
            trade_date=date(2026, 8, 1),
            result_r=result_r,
        )
    client = Client()
    client.force_login(owner)

    response = client.get(
        "/en/analytics/",
        {
            "period": "ALL",
            "profile": str(linear.id),
            "market_type": linear.market_type,
            "trading_pair": str(bitcoin.id),
        },
    )

    analytics = response.context["analytics"]
    assert analytics.closed_trade_count == 1
    assert analytics.net_result_r == Decimal(3)


@mark.django_db
def test_pair_filter_is_disabled_until_a_profile_is_selected() -> None:
    """A profile-scoped pair should not imply a hidden profile selection."""
    owner = User.objects.create_user(username="owner")
    profile = create_profile(
        owner,
        name="Linear",
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
    )
    _ = create_pair(profile, "BTC")
    client = Client()
    client.force_login(owner)

    response = client.get("/en/analytics/")

    pair_field = response.context["filter_form"].fields["trading_pair"]
    assert pair_field.disabled
    assert list(pair_field.queryset) == []
    assert pair_field.empty_label == "Unavailable"
    assert pair_field.widget.attrs["title"] == (
        "Choose a profile to enable this filter."
    )


@mark.django_db
def test_pair_filter_lists_only_pairs_from_the_selected_profile() -> None:
    """Pair labels should be canonical once their profile is explicit."""
    owner = User.objects.create_user(username="owner")
    linear = create_profile(
        owner,
        name="Linear",
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
    )
    spot = create_profile(
        owner,
        name="Spot",
        market_type=TradingProfile.MarketType.SPOT.value,
    )
    bitcoin = create_pair(linear, "BTC")
    _ = create_pair(linear, "ETH")
    _ = create_pair(spot, "SOL")
    client = Client()
    client.force_login(owner)

    response = client.get(
        "/en/analytics/",
        {"period": "ALL", "profile": str(linear.id)},
    )

    pair_field = response.context["filter_form"].fields["trading_pair"]
    assert not pair_field.disabled
    assert [label for _value, label in pair_field.choices] == [
        "All pairs",
        "BTC/USDT",
        "ETH/USDT",
    ]
    assert str(bitcoin) == "BTC/USDT | Linear"


@mark.django_db
def test_changing_profile_discards_a_stale_pair_filter() -> None:
    """A previous profile's pair should not produce an intermediate error."""
    owner = User.objects.create_user(username="owner")
    linear = create_profile(
        owner,
        name="Linear",
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
    )
    spot = create_profile(
        owner,
        name="Spot",
        market_type=TradingProfile.MarketType.SPOT.value,
    )
    linear_pair = create_pair(linear, "BTC")
    spot_pair = create_pair(spot, "ETH")
    _ = create_closed_trade(
        spot,
        spot_pair,
        trade_date=date(2026, 8, 1),
        result_r=Decimal(3),
    )
    client = Client()
    client.force_login(owner)

    response = client.get(
        "/en/analytics/",
        {
            "period": "ALL",
            "profile": str(spot.id),
            "trading_pair": str(linear_pair.id),
        },
    )

    form = response.context["filter_form"]
    assert form.is_valid()
    assert form.cleaned_data["trading_pair"] is None
    assert response.context["analytics"].closed_trade_count == 1


@mark.django_db
def test_corrections_are_reflected_without_persisted_trajectory_points() -> None:
    """Corrected analytical facts should rebuild both order and coordinates."""
    owner = User.objects.create_user(username="owner")
    profile = create_profile(
        owner,
        name="Primary",
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
    )
    pair = create_pair(profile, "BTC")
    later = create_closed_trade(
        profile,
        pair,
        trade_date=date(2026, 8, 2),
        result_r=Decimal(-1),
    )
    earlier = create_closed_trade(
        profile,
        pair,
        trade_date=date(2026, 8, 1),
        result_r=Decimal(3),
    )
    later.trade_date = date(2026, 7, 31)
    later.result_r = Decimal("-0.25")
    later.save(update_fields=["trade_date", "result_r"])
    client = Client()
    client.force_login(owner)

    response = client.get("/en/analytics/")

    analytics = response.context["analytics"]
    assert [point.trade.trade_id for point in analytics.points] == [
        later.id,
        earlier.id,
    ]
    assert analytics.final_x == Decimal("0.25")
    assert analytics.final_y == Decimal(1)


@mark.django_db
def test_htmx_filter_returns_only_replaceable_analytics_fragment() -> None:
    """Reactive filtering should not duplicate the application shell."""
    owner = User.objects.create_user(username="owner")
    client = Client()
    client.force_login(owner)

    response = client.get(
        "/en/analytics/",
        {"period": "ALL"},
        headers={"hx-request": "true"},
    )

    assert response.status_code == 200
    assert b'id="analytics-content"' in response.content
    assert b"<!doctype html>" not in response.content


@mark.django_db
def test_invalid_custom_date_range_is_shown_without_results() -> None:
    """An inverted custom range should not silently show all-time results."""
    owner = User.objects.create_user(username="owner")
    client = Client()
    client.force_login(owner)

    response = client.get(
        "/en/analytics/",
        {
            "period": "CUSTOM",
            "date_from": "2026-08-31",
            "date_to": "2026-08-01",
        },
    )

    assert response.status_code == 200
    assert response.context["analytics"].closed_trade_count == 0
    assert b"end date must not be earlier" in response.content


@mark.django_db
def test_rolling_period_uses_configured_local_date() -> None:
    """A rolling range should include today and the preceding 29 dates."""
    owner = User.objects.create_user(username="owner")
    profile = create_profile(
        owner,
        name="Primary",
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
    )
    pair = create_pair(profile, "BTC")
    _ = create_closed_trade(
        profile,
        pair,
        trade_date=date(2026, 7, 31),
        result_r=Decimal(-1),
    )
    _ = create_closed_trade(
        profile,
        pair,
        trade_date=date(2026, 8, 2),
        result_r=Decimal(3),
    )
    client = Client()
    client.force_login(owner)

    with patch(
        "tradefog.journal.forms.timezone.localdate",
        return_value=date(2026, 8, 30),
    ):
        response = client.get("/en/analytics/", {"period": "30D"})

    analytics = response.context["analytics"]
    assert analytics.closed_trade_count == 1
    assert analytics.net_result_r == Decimal(3)


def test_analytics_url_follows_active_language_prefix() -> None:
    """The analytics route should use the explicit request language."""
    with override("en"):
        assert reverse("analytics_overview") == "/en/analytics/"
    with override("ru"):
        assert reverse("analytics_overview") == "/ru/analytics/"


@mark.django_db
def test_analytics_empty_state_is_translated_by_url_language() -> None:
    """Analytics fragments should use the language activated by their URL."""
    owner = User.objects.create_user(username="owner")
    client = Client()
    client.force_login(owner)

    response = client.get("/ru/analytics/")

    content = response.content.decode()
    assert response.status_code == 200
    assert response.headers["Content-Language"] == "ru"
    assert "В выбранном диапазоне нет закрытых сделок" in content
    assert "Недоступно" in content
    assert "Сначала выберите профиль." in content
    assert "Выберите профиль, чтобы включить этот фильтр." in content
    assert "col-12 col-md-8 col-xl-3 tf-pair-filter" in content
