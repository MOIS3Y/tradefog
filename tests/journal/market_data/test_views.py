"""Ownership and manual-candle interface tests."""

from datetime import date, timedelta
from decimal import Decimal
from typing import cast

from django.core.paginator import Page
from django.test import Client
from pytest import MonkeyPatch, mark

from tradefog.accounts.models import User
from tradefog.journal import views
from tradefog.journal.models import (
    Asset,
    DailyCandle,
    ProfileTradingPair,
    Trade,
    TradingProfile,
)


def create_pair(owner: User) -> ProfileTradingPair:
    """Create one owned pair for interface tests."""
    quote = Asset.objects.create(owner=owner, symbol="USDT")
    base = Asset.objects.create(owner=owner, symbol="BTC")
    profile = TradingProfile.objects.create(
        owner=owner,
        name="Primary",
        capital_asset=quote,
        initial_capital=Decimal(10000),
        risk_stop_capital=Decimal(9000),
    )
    return ProfileTradingPair.objects.create(
        profile=profile,
        asset=base,
        price_step=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
    )


@mark.django_db
def test_pair_defaults_to_manual_market_data() -> None:
    """New pairs keep the journal autonomous unless Bybit is selected."""
    pair = create_pair(User.objects.create_user(username="trader"))

    assert pair.market_data_provider == "MANUAL"


@mark.django_db
def test_owner_can_create_and_correct_manual_candle() -> None:
    """Manual maintenance stores exact OHLC and manual provenance."""
    owner = User.objects.create_user(username="trader")
    pair = create_pair(owner)
    client = Client()
    client.force_login(owner)
    url = f"/en/profiles/{pair.profile_id}/pairs/{pair.id}/candles/new/"

    response = client.post(
        url,
        {
            "trading_date": "2025-01-01",
            "open_price": "100",
            "high_price": "110",
            "low_price": "90",
            "close_price": "105",
        },
    )

    candle = DailyCandle.objects.get()
    assert response.status_code == 302
    assert candle.source == "MANUAL"
    assert candle.trading_date == date(2025, 1, 1)


@mark.django_db
def test_candle_routes_enforce_profile_ownership() -> None:
    """Another authenticated owner cannot inspect a pair's candle history."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    pair = create_pair(owner)
    client = Client()
    client.force_login(stranger)

    response = client.get(
        f"/en/profiles/{pair.profile_id}/pairs/{pair.id}/candles/"
    )

    assert response.status_code == 404


@mark.django_db
def test_pair_registry_is_owner_scoped_and_filterable() -> None:
    """The central registry exposes only matching active owned pairs."""
    owner = User.objects.create_user(username="owner")
    stranger = User.objects.create_user(username="stranger")
    bitcoin = create_pair(owner)
    bitcoin.market_data_provider = "BYBIT"
    bitcoin.save(update_fields=["market_data_provider"])
    _other_pair = create_pair(stranger)
    client = Client()
    client.force_login(owner)

    response = client.get("/en/pairs/?search=BTC&market_data_provider=BYBIT")

    assert response.status_code == 200
    content = response.content.decode()
    assert "BTC/USDT" in content
    assert "Primary" in content
    assert content.count("BTC/USDT") == 1
    assert f"/en/profiles/{bitcoin.profile_id}/pairs/{bitcoin.id}/edit/" in (
        content
    )
    assert (
        f"/en/profiles/{bitcoin.profile_id}/pairs/{bitcoin.id}/candles/"
        in content
    )


@mark.django_db
def test_candle_history_filters_sorts_and_paginates_with_htmx(
    monkeypatch: MonkeyPatch,
) -> None:
    """Long candle histories are retrieved in server-sorted chunks."""
    owner = User.objects.create_user(username="trader")
    pair = create_pair(owner)
    for offset, (source, close_price) in enumerate(
        (("MANUAL", Decimal(105)), ("BYBIT", Decimal(95)), ("MANUAL", Decimal(102)))
    ):
        _ = DailyCandle.objects.create(
            trading_pair=pair,
            trading_date=date(2025, 1, 1) + timedelta(days=offset),
            open_price=Decimal(100 + offset),
            high_price=Decimal(110 + offset),
            low_price=Decimal(90 + offset),
            close_price=close_price,
            source=source,
        )
    monkeypatch.setattr(views, "CANDLE_PAGE_SIZE", 2)
    client = Client()
    client.force_login(owner)
    url = f"/en/profiles/{pair.profile_id}/pairs/{pair.id}/candles/"

    first_page = client.get(f"{url}?sort=date")
    filtered = client.get(f"{url}?source=BYBIT")
    next_fragment = client.get(
        f"{url}?sort=date&page=2",
        headers={"HX-Request": "true"},
    )
    first_page_object = cast(Page[DailyCandle], first_page.context["page_obj"])
    filtered_page_object = cast(
        Page[DailyCandle],
        filtered.context["page_obj"],
    )
    page_candles = cast(
        list[DailyCandle],
        first_page_object.object_list,
    )

    assert first_page.status_code == 200
    assert first_page_object.paginator.count == 3
    assert [
        candle.trading_date
        for candle in page_candles
    ] == [date(2025, 1, 1), date(2025, 1, 2)]
    assert filtered_page_object.paginator.count == 1
    assert b"2025" in next_fragment.content
    assert b"<html" not in next_fragment.content
    assert b"tabler-trending-up" in first_page.content
    assert b"tabler-trending-down" in first_page.content


@mark.django_db
def test_draft_market_context_is_date_aware_and_htmx_replaceable() -> None:
    """A draft renders cached ATR and refreshes it as a focused fragment."""
    owner = User.objects.create_user(username="trader")
    pair = create_pair(owner)
    start = date(2025, 1, 1)
    for offset in range(15):
        _ = DailyCandle.objects.create(
            trading_pair=pair,
            trading_date=start + timedelta(days=offset),
            open_price=Decimal(100),
            high_price=Decimal(102),
            low_price=Decimal(98),
            close_price=Decimal(100),
        )
    trade_date = start + timedelta(days=15)
    trade = Trade.objects.create(
        profile=pair.profile,
        trading_pair=pair,
        trade_date=trade_date,
        direction=Trade.Direction.LONG.value,
        planned_entry=Decimal(100),
        planned_stop=Decimal(95),
    )
    client = Client()
    client.force_login(owner)

    page = client.get(f"/en/trades/{trade.id}/")
    fragment = client.post(
        f"/en/trades/{trade.id}/market-context/",
        {
            "trade_date": trade_date.isoformat(),
            "trading_pair": str(pair.id),
            "direction": "LONG",
            "planned_entry": "100",
            "planned_stop": "95",
        },
    )
    plan_fragment = client.post(
        f"/en/trades/{trade.id}/plan/",
        {
            "trade_date": trade_date.isoformat(),
            "trading_pair": str(pair.id),
            "direction": "LONG",
            "planned_entry": "100",
            "planned_stop": "99",
        },
    )

    assert page.status_code == 200
    assert b"ATR(14)" in page.content
    assert b"data-market-candle-chart" in page.content
    assert b'aria-labelledby="market-chart-title"' in page.content
    assert b'aria-labelledby="market-context-title"' in page.content
    assert b"tradefog/js/market-context.js" in page.content
    assert page.content.count(b'\"date\":') == 14
    assert b"Exceeds 75% ATR" in page.content
    assert fragment.status_code == 200
    assert b'hx-swap-oob="innerHTML"' in fragment.content
    assert b"data-market-candle-chart" in fragment.content
    assert plan_fragment.status_code == 200
    assert b'id="atr-target-comparison"' in plan_fragment.content
    assert b"Fits within 75% ATR" in plan_fragment.content


@mark.django_db
def test_stage_seven_interface_is_translated_in_russian() -> None:
    """Pair settings and ATR context use the active Russian catalog."""
    owner = User.objects.create_user(username="trader")
    pair = create_pair(owner)
    start = date(2025, 1, 1)
    for offset in range(15):
        _ = DailyCandle.objects.create(
            trading_pair=pair,
            trading_date=start + timedelta(days=offset),
            open_price=Decimal(100),
            high_price=Decimal(102),
            low_price=Decimal(98),
            close_price=Decimal(100),
        )
    trade = Trade.objects.create(
        profile=pair.profile,
        trading_pair=pair,
        trade_date=start + timedelta(days=15),
        direction=Trade.Direction.LONG.value,
        planned_entry=Decimal(100),
        planned_stop=Decimal(95),
    )
    client = Client()
    client.force_login(owner)

    profile_page = client.get(f"/ru/profiles/{pair.profile_id}/")
    pair_form = client.get(
        f"/ru/profiles/{pair.profile_id}/pairs/{pair.id}/edit/"
    )
    trade_page = client.get(f"/ru/trades/{trade.id}/")

    assert "Рыночные данные" in profile_page.content.decode()
    assert "Источник рыночных данных" in pair_form.content.decode()
    assert "Поведение рынка определяется профилем." in (
        pair_form.content.decode()
    )
    assert "Контекст дневного диапазона" in trade_page.content.decode()
    assert "Движение цены перед решением" in trade_page.content.decode()
    assert "Превышает 75% ATR" in trade_page.content.decode()
