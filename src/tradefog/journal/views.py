"""Owner-scoped HTTP views for journal workflows and analytics."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Page, Paginator
from django.db.models import Case, Count, DecimalField, F, Max, Min, Q, When
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from tradefog.accounts.models import User
from tradefog.journal.analytics import (
    TradeAnalytics,
    calculate_trade_analytics,
)
from tradefog.journal.analytics_queries import (
    AnalyticsFilters,
    select_closed_trade_results,
)
from tradefog.journal.calculations import PositionPlan, PositionPlanError
from tradefog.journal.checklists import (
    ChecklistAnswers,
    ChecklistAssessment,
    calculate_checklist_assessment,
)
from tradefog.journal.forms import (
    AnalyticsFilterForm,
    AssetForm,
    CapitalOperationForm,
    CloseTradeForm,
    DailyCandleFilterForm,
    DailyCandleForm,
    ProfileTradingPairForm,
    TradeChecklistForm,
    TradeDateForm,
    TradeDraftForm,
    TradeOverviewFilterForm,
    TradingPairFilterForm,
    TradingProfileForm,
)
from tradefog.journal.market_data.calculations import (
    compare_target_move_with_atr,
)
from tradefog.journal.market_data.services import (
    get_market_context,
    refresh_market_context,
)
from tradefog.journal.market_data.types import (
    AtrTargetComparison,
    MarketContext,
)
from tradefog.journal.models import (
    ACTIVE_PAIR_EXISTS,
    Asset,
    CapitalOperation,
    DailyCandle,
    ProfileTradingPair,
    Trade,
    TradeChecklist,
    TradingProfile,
)
from tradefog.journal.services import (
    archive_asset,
    archive_profile,
    archive_trading_pair,
    calculate_trade_plan,
    cancel_trade,
    close_trade,
    create_capital_operation,
    delete_capital_operation,
    open_trade,
    restore_asset,
    restore_profile,
    restore_trading_pair,
    save_trade_draft,
    submit_trade,
    sync_profile_status,
    update_capital_operation,
    update_trade_result,
)


@dataclass(frozen=True, slots=True)
class AssetOverviewRow:
    """Present one asset with its unique linked trading profiles."""

    asset: Asset
    profiles: tuple[TradingProfile, ...]

    @property
    def remaining_profiles(self) -> tuple[TradingProfile, ...]:
        """Return profiles hidden behind the compact overflow badge."""
        return self.profiles[1:]

    @property
    def profile_sort_value(self) -> str:
        """Return one deterministic key for optional profile sorting."""
        return " | ".join(profile.name for profile in self.profiles)

    @property
    def profile_names(self) -> str:
        """Return the complete readable profile list for the tooltip."""
        return ", ".join(profile.name for profile in self.profiles)

    @property
    def remaining_profile_names(self) -> str:
        """Return names disclosed by the compact overflow badge."""
        return ", ".join(
            profile.name for profile in self.remaining_profiles
        )


PAIR_PAGE_SIZE = 25
CANDLE_PAGE_SIZE = 50
TRADE_PAGE_SIZE = 50
ASSET_PAGE_SIZE = 50
PROFILE_TABLE_PAGE_SIZE = 25


def _request_owner(request: HttpRequest) -> User:
    """Return the authenticated application user attached to a request."""
    return cast(User, request.user)


def _owned_profile(request: HttpRequest, profile_id: int) -> TradingProfile:
    """Resolve a non-archived profile within the ownership boundary."""
    return get_object_or_404(
        TradingProfile.objects.exclude(
            status=TradingProfile.Status.ARCHIVED.value
        ),
        id=profile_id,
        owner=_request_owner(request),
    )


def _owned_archived_profile(
    request: HttpRequest,
    profile_id: int,
) -> TradingProfile:
    """Resolve an archived profile within the ownership boundary."""
    return get_object_or_404(
        TradingProfile,
        id=profile_id,
        owner=_request_owner(request),
        status=TradingProfile.Status.ARCHIVED.value,
    )


def _owned_asset(
    request: HttpRequest,
    asset_id: int,
    *,
    archived: bool = False,
) -> Asset:
    """Resolve one asset inside the authenticated ownership boundary."""
    return get_object_or_404(
        Asset,
        id=asset_id,
        owner=_request_owner(request),
        archived_at__isnull=not archived,
    )


def _owned_capital_operation(
    profile: TradingProfile,
    operation_id: int,
) -> CapitalOperation:
    """Resolve a capital operation belonging to the selected profile."""
    return get_object_or_404(
        CapitalOperation,
        id=operation_id,
        profile=profile,
    )


def _owned_trading_pair(
    profile: TradingProfile,
    pair_id: int,
) -> ProfileTradingPair:
    """Resolve an active trading pair belonging to the selected profile."""
    return get_object_or_404(
        ProfileTradingPair.objects.select_related("asset"),
        id=pair_id,
        profile=profile,
        archived_at__isnull=True,
    )


def _owned_daily_candle(
    trading_pair: ProfileTradingPair,
    candle_id: int,
) -> DailyCandle:
    """Resolve one candle through its owner-scoped profile pair."""
    return get_object_or_404(
        DailyCandle,
        id=candle_id,
        trading_pair=trading_pair,
    )


def _owned_trade(request: HttpRequest, trade_id: int) -> Trade:
    """Resolve one trade through its profile ownership boundary."""
    return get_object_or_404(
        Trade.objects.select_related(
            "profile__capital_asset",
            "trading_pair__asset",
            "checklist",
        ),
        id=trade_id,
        profile__owner=_request_owner(request),
    )


def _owned_archived_trading_pair(
    profile: TradingProfile,
    pair_id: int,
) -> ProfileTradingPair:
    """Resolve an archived pair belonging to an active profile."""
    return get_object_or_404(
        ProfileTradingPair.objects.select_related("asset"),
        id=pair_id,
        profile=profile,
        archived_at__isnull=False,
    )


def _analytics_chart_data(analytics: TradeAnalytics) -> dict[str, object]:
    """Serialize exact analytics into ApexCharts presentation data."""
    trajectory: list[dict[str, object]] = [
        {
            "x": 0.0,
            "y": 0.0,
            "sequence": 0,
            "trade": None,
        }
    ]
    for point in analytics.points:
        trajectory.append(
            {
                "x": float(point.x),
                "y": float(point.y),
                "sequence": point.sequence,
                "trade": {
                    "date": point.trade.trade_date.isoformat(),
                    "profile": point.trade.profile_name,
                    "pair": point.trade.pair_symbol,
                    "direction": point.trade.direction,
                    "resultR": float(point.trade.result_r),
                },
            }
        )

    break_even_end = max(
        analytics.final_x,
        analytics.final_y * Decimal(3),
        Decimal(1),
    )
    return {
        "trajectory": trajectory,
        "breakEven": [
            {"x": 0.0, "y": 0.0},
            {
                "x": float(break_even_end),
                "y": float(break_even_end / Decimal(3)),
            },
        ],
        "labels": {
            "trajectory": _("Trading trajectory"),
            "breakEven": _("Break-even line"),
            "start": _("Start"),
            "trade": _("Trade"),
            "profile": _("Profile"),
            "result": _("Result"),
        },
    }


def _analytics_context(request: HttpRequest) -> dict[str, object]:
    """Build filtered, owner-scoped analytics for a full or HTMX response."""
    query_data = request.GET.copy()
    if "period" not in query_data:
        query_data["period"] = "ALL"
    form = AnalyticsFilterForm(_request_owner(request), query_data)
    if not form.is_valid():
        analytics = calculate_trade_analytics(())
        return {
            "filter_form": form,
            "analytics": analytics,
            "chart_data": None,
        }

    profile = cast(TradingProfile | None, form.cleaned_data["profile"])
    trading_pair = cast(
        ProfileTradingPair | None,
        form.cleaned_data["trading_pair"],
    )
    filters = AnalyticsFilters(
        date_from=cast(date | None, form.cleaned_data["date_from"]),
        date_to=cast(date | None, form.cleaned_data["date_to"]),
        profile_id=profile.id if profile is not None else None,
        market_type=cast(str, form.cleaned_data["market_type"]) or None,
        trading_pair_id=(
            trading_pair.id if trading_pair is not None else None
        ),
    )
    analytics = calculate_trade_analytics(
        select_closed_trade_results(_request_owner(request), filters)
    )
    return {
        "filter_form": form,
        "analytics": analytics,
        "chart_data": (
            _analytics_chart_data(analytics)
            if analytics.closed_trade_count
            else None
        ),
    }


@login_required
def analytics_overview(request: HttpRequest) -> HttpResponse:
    """Show the central filtered trading-quality view."""
    context = _analytics_context(request)
    if bool(getattr(request, "htmx", False)):
        return render(
            request,
            "tradefog/journal/partials/analytics_content.html",
            context,
        )
    return render(
        request,
        "tradefog/journal/analytics_overview.html",
        context,
    )


def _profile_detail_context(
    request: HttpRequest,
    profile: TradingProfile,
    *,
    deposit_form: CapitalOperationForm | None = None,
    withdrawal_form: CapitalOperationForm | None = None,
) -> dict[str, object]:
    """Build the configuration context shared by profile detail responses."""
    current_capital = profile.current_capital
    risk_base = max(profile.initial_capital, current_capital)
    reserved_risk = profile.reserved_risk
    worst_case_capital = current_capital - reserved_risk
    capital_sort_fields = {
        "operation": ("operation_type", "-created_at", "-id"),
        "-operation": ("-operation_type", "-created_at", "-id"),
        "amount": ("signed_amount_sort", "-created_at", "-id"),
        "-amount": ("-signed_amount_sort", "-created_at", "-id"),
        "note": ("note", "-created_at", "-id"),
        "-note": ("-note", "-created_at", "-id"),
        "recorded": ("created_at", "id"),
        "-recorded": ("-created_at", "-id"),
    }
    requested_capital_sort = request.GET.get(
        "capital_sort",
        "-recorded",
    )
    capital_sort = (
        requested_capital_sort
        if requested_capital_sort in capital_sort_fields
        else "-recorded"
    )
    capital_operations = profile.capital_operations.annotate(
        signed_amount_sort=Case(
            When(
                operation_type=CapitalOperation.Type.WITHDRAWAL.value,
                then=-F("amount"),
            ),
            default=F("amount"),
            output_field=DecimalField(max_digits=24, decimal_places=8),
        )
    ).order_by(*capital_sort_fields[capital_sort])
    capital_page = Paginator(
        capital_operations,
        PROFILE_TABLE_PAGE_SIZE,
    ).get_page(request.GET.get("capital_page"))

    pair_sort_fields = {
        "pair": ("asset__symbol", "id"),
        "-pair": ("-asset__symbol", "-id"),
        "price": ("price_step", "asset__symbol", "id"),
        "-price": ("-price_step", "-asset__symbol", "-id"),
        "quantity": ("quantity_step", "asset__symbol", "id"),
        "-quantity": ("-quantity_step", "-asset__symbol", "-id"),
        "minimum": ("minimum_quantity", "asset__symbol", "id"),
        "-minimum": ("-minimum_quantity", "-asset__symbol", "-id"),
    }
    requested_pair_sort = request.GET.get("pair_sort", "pair")
    pair_sort = (
        requested_pair_sort
        if requested_pair_sort in pair_sort_fields
        else "pair"
    )
    trading_pairs = (
        profile.trading_pairs.filter(archived_at__isnull=True)
        .select_related("asset", "profile__capital_asset")
        .order_by(*pair_sort_fields[pair_sort])
    )
    pair_page = Paginator(
        trading_pairs,
        PROFILE_TABLE_PAGE_SIZE,
    ).get_page(request.GET.get("pair_page"))

    archived_sort_fields = {
        "pair": ("asset__symbol", "id"),
        "-pair": ("-asset__symbol", "-id"),
        "archived": ("archived_at", "asset__symbol", "id"),
        "-archived": ("-archived_at", "-asset__symbol", "-id"),
    }
    requested_archived_sort = request.GET.get(
        "archived_sort",
        "-archived",
    )
    archived_sort = (
        requested_archived_sort
        if requested_archived_sort in archived_sort_fields
        else "-archived"
    )
    archived_pairs = (
        profile.trading_pairs.filter(archived_at__isnull=False)
        .select_related("asset", "profile__capital_asset")
        .order_by(*archived_sort_fields[archived_sort])
    )
    archived_pair_page = Paginator(
        archived_pairs,
        PROFILE_TABLE_PAGE_SIZE,
    ).get_page(request.GET.get("archived_page"))

    return {
        "profile": profile,
        "current_capital": current_capital,
        "risk_base": risk_base,
        "risk_amount": (
            risk_base * profile.risk_per_trade_percent / Decimal(100)
        ),
        "reserved_risk": reserved_risk,
        "worst_case_capital": worst_case_capital,
        "risk_capacity": worst_case_capital - profile.risk_stop_capital,
        "capital_page": capital_page,
        "capital_pagination": _pagination_urls(
            request,
            capital_page,
            "capital_page",
        ),
        "capital_sort_headers": _sort_headers(
            request,
            capital_sort,
            (
                ("operation", _("Operation")),
                ("amount", _("Amount")),
                ("note", _("Note")),
                ("recorded", _("Recorded")),
            ),
            sort_parameter="capital_sort",
            page_parameter="capital_page",
        ),
        "pair_page": pair_page,
        "pair_pagination": _pagination_urls(
            request,
            pair_page,
            "pair_page",
        ),
        "pair_sort_headers": _sort_headers(
            request,
            pair_sort,
            (
                ("pair", _("Pair")),
                ("price", _("Price step")),
                ("quantity", _("Quantity step")),
                ("minimum", _("Minimum order")),
            ),
            sort_parameter="pair_sort",
            page_parameter="pair_page",
        ),
        "archived_pair_page": archived_pair_page,
        "archived_pair_pagination": _pagination_urls(
            request,
            archived_pair_page,
            "archived_page",
        ),
        "archived_pair_sort_headers": _sort_headers(
            request,
            archived_sort,
            (
                ("pair", _("Pair")),
                ("archived", _("Archived")),
            ),
            sort_parameter="archived_sort",
            page_parameter="archived_page",
        ),
        "deposit_form": deposit_form
        or CapitalOperationForm(CapitalOperation.Type.DEPOSIT.value),
        "withdrawal_form": withdrawal_form
        or CapitalOperationForm(CapitalOperation.Type.WITHDRAWAL.value),
    }


def _render_profile_detail(
    request: HttpRequest,
    profile: TradingProfile,
    *,
    deposit_form: CapitalOperationForm | None = None,
    withdrawal_form: CapitalOperationForm | None = None,
) -> HttpResponse:
    """Render one profile with optional bound capital forms."""
    context = _profile_detail_context(
        request,
        profile,
        deposit_form=deposit_form,
        withdrawal_form=withdrawal_form,
    )
    return render(
        request,
        "tradefog/journal/profile_detail.html",
        context,
    )


def _add_validation_errors(
    form: CapitalOperationForm,
    error: ValidationError,
) -> None:
    """Attach service validation failures to their form controls."""
    if hasattr(error, "message_dict"):
        for field_name, field_errors in error.message_dict.items():
            target = field_name if field_name in form.fields else None
            for field_error in field_errors:
                form.add_error(target, field_error)
        return
    for field_error in error.messages:
        form.add_error(None, field_error)


def _asset_overview_rows(
    owner: User,
    assets: list[Asset],
) -> list[AssetOverviewRow]:
    """Join assets to unique capital and trading-pair profiles efficiently."""
    if not assets:
        return []

    asset_ids = [asset.id for asset in assets]
    profiles_by_asset: dict[int, dict[int, TradingProfile]] = {
        asset_id: {} for asset_id in asset_ids
    }
    capital_profiles = TradingProfile.objects.filter(
        owner=owner,
        capital_asset_id__in=asset_ids,
    ).only("id", "name", "capital_asset_id")
    for profile in capital_profiles:
        profiles_by_asset[profile.capital_asset_id][profile.id] = profile

    trading_pairs = (
        ProfileTradingPair.objects.filter(
            profile__owner=owner,
            asset_id__in=asset_ids,
        )
        .select_related("profile")
        .only("asset_id", "profile__id", "profile__name")
    )
    for trading_pair in trading_pairs:
        profiles_by_asset[trading_pair.asset_id][trading_pair.profile_id] = (
            trading_pair.profile
        )

    return [
        AssetOverviewRow(
            asset=asset,
            profiles=tuple(
                sorted(
                    profiles_by_asset[asset.id].values(),
                    key=lambda profile: (profile.name.casefold(), profile.id),
                )
            ),
        )
        for asset in assets
    ]


@login_required
def asset_overview(request: HttpRequest) -> HttpResponse:
    """List reusable asset identities owned by the authenticated user."""
    owner = _request_owner(request)
    assets = Asset.objects.filter(owner=owner)
    active_assets = assets.filter(archived_at__isnull=True).annotate(
        capital_profile_sort=Min("capital_profiles__name"),
        pair_profile_sort=Min("trading_pairs__profile__name"),
    )
    requested_sort = request.GET.get("sort", "symbol")
    sort_fields = {
        "symbol": ("symbol", "id"),
        "-symbol": ("-symbol", "-id"),
        "name": ("name", "symbol", "id"),
        "-name": ("-name", "-symbol", "-id"),
        "class": ("asset_class", "symbol", "id"),
        "-class": ("-asset_class", "-symbol", "-id"),
        "profiles": (
            "capital_profile_sort",
            "pair_profile_sort",
            "symbol",
            "id",
        ),
        "-profiles": (
            "-capital_profile_sort",
            "-pair_profile_sort",
            "-symbol",
            "-id",
        ),
    }
    current_sort = (
        requested_sort if requested_sort in sort_fields else "symbol"
    )
    page_obj = Paginator(
        active_assets.order_by(*sort_fields[current_sort]),
        ASSET_PAGE_SIZE,
    ).get_page(request.GET.get("page"))
    asset_rows = _asset_overview_rows(
        owner,
        list(page_obj.object_list),
    )
    context = {
        "page_obj": page_obj,
        "asset_rows": asset_rows,
        "pagination": _pagination_urls(request, page_obj),
        "current_sort": current_sort,
        "sort_headers": _sort_headers(
            request,
            current_sort,
            (
                ("symbol", _("Symbol")),
                ("name", _("Name")),
                ("class", _("Asset class")),
                ("profiles", _("Profiles")),
            ),
        ),
        "archived_assets": assets.filter(archived_at__isnull=False),
    }
    template = "tradefog/journal/asset_overview.html"
    if request.headers.get("HX-Request") == "true":
        template = "tradefog/journal/partials/asset_results.html"
    return render(
        request,
        template,
        context,
    )


def _sort_headers(
    request: HttpRequest,
    current_sort: str,
    columns: tuple[tuple[str, str], ...],
    *,
    sort_parameter: str = "sort",
    page_parameter: str = "page",
) -> tuple[dict[str, str | bool], ...]:
    """Build safe sort links while preserving the active filter query."""
    headers: list[dict[str, str | bool]] = []
    for key, label in columns:
        active = current_sort.lstrip("-") == key
        descending = current_sort == f"-{key}"
        next_sort = key if descending or not active else f"-{key}"
        query = request.GET.copy()
        query[sort_parameter] = next_sort
        _removed_page = query.pop(page_parameter, None)
        headers.append(
            {
                "key": key,
                "label": label,
                "url": f"?{query.urlencode()}",
                "active": active,
                "descending": descending,
            }
        )
    return tuple(headers)


def _pagination_urls[PageItem](
    request: HttpRequest,
    page_obj: Page[PageItem],
    page_parameter: str = "page",
) -> dict[str, str | None]:
    """Preserve all list state while changing one page parameter."""
    previous_url = None
    next_url = None
    if page_obj.has_previous():
        previous_query = request.GET.copy()
        previous_query[page_parameter] = str(
            page_obj.previous_page_number()
        )
        previous_url = f"?{previous_query.urlencode()}"
    if page_obj.has_next():
        next_query = request.GET.copy()
        next_query[page_parameter] = str(page_obj.next_page_number())
        next_url = f"?{next_query.urlencode()}"
    return {"previous_url": previous_url, "next_url": next_url}


@login_required
def trading_pair_overview(request: HttpRequest) -> HttpResponse:
    """List active owner-scoped pairs with market-data shortcuts."""
    owner = _request_owner(request)
    filter_form = TradingPairFilterForm(owner, request.GET or None)
    pairs = (
        ProfileTradingPair.objects.filter(
            profile__owner=owner,
            archived_at__isnull=True,
        )
        .exclude(profile__status=TradingProfile.Status.ARCHIVED.value)
        .select_related("profile__capital_asset", "asset")
        .annotate(
            candle_count=Count("daily_candles"),
            latest_candle_date=Max("daily_candles__trading_date"),
        )
    )
    if filter_form.is_valid():
        search = filter_form.cleaned_data.get("search")
        profile = filter_form.cleaned_data.get("profile")
        market_type = filter_form.cleaned_data.get("market_type")
        market_data_provider = filter_form.cleaned_data.get(
            "market_data_provider"
        )
        if search:
            pairs = pairs.filter(
                Q(asset__symbol__icontains=search)
                | Q(profile__capital_asset__symbol__icontains=search)
                | Q(profile__name__icontains=search)
            )
        if isinstance(profile, TradingProfile):
            pairs = pairs.filter(profile=profile)
        if market_type:
            pairs = pairs.filter(profile__market_type=market_type)
        if market_data_provider:
            pairs = pairs.filter(
                market_data_provider=market_data_provider
            )

    requested_sort = request.GET.get("sort", "pair")
    sort_fields = {
        "pair": ("asset__symbol", "profile__capital_asset__symbol", "id"),
        "-pair": (
            "-asset__symbol",
            "-profile__capital_asset__symbol",
            "-id",
        ),
        "profile": ("profile__name", "asset__symbol", "id"),
        "-profile": ("-profile__name", "-asset__symbol", "-id"),
        "market": ("profile__market_type", "asset__symbol", "id"),
        "-market": ("-profile__market_type", "-asset__symbol", "-id"),
        "source": ("market_data_provider", "asset__symbol", "id"),
        "-source": ("-market_data_provider", "-asset__symbol", "-id"),
        "candles": ("candle_count", "asset__symbol", "id"),
        "-candles": ("-candle_count", "-asset__symbol", "-id"),
        "latest": ("latest_candle_date", "asset__symbol", "id"),
        "-latest": ("-latest_candle_date", "-asset__symbol", "-id"),
    }
    current_sort = (
        requested_sort if requested_sort in sort_fields else "pair"
    )
    page_obj = Paginator(
        pairs.order_by(*sort_fields[current_sort]),
        PAIR_PAGE_SIZE,
    ).get_page(request.GET.get("page"))
    context = {
        "filter_form": filter_form,
        "page_obj": page_obj,
        "pagination": _pagination_urls(request, page_obj),
        "current_sort": current_sort,
        "sort_headers": _sort_headers(
            request,
            current_sort,
            (
                ("pair", _("Pair")),
                ("profile", _("Profile")),
                ("market", _("Market")),
                ("source", _("Data source")),
                ("candles", _("Candles")),
                ("latest", _("Latest candle")),
            ),
        ),
    }
    template = "tradefog/journal/trading_pair_overview.html"
    if request.headers.get("HX-Request") == "true":
        template = "tradefog/journal/partials/trading_pair_results.html"
    return render(request, template, context)


@login_required
@require_http_methods(["GET", "POST"])
def asset_create(request: HttpRequest) -> HttpResponse:
    """Create one canonical user-owned asset identity."""
    asset = Asset(owner=_request_owner(request))
    form = AssetForm(
        request.POST if request.method == "POST" else None,
        instance=asset,
    )
    if request.method == "POST" and form.is_valid():
        created_asset = cast(Asset, form.save(commit=False))
        created_asset.owner = _request_owner(request)
        created_asset.save()
        messages.success(request, _("Asset created."))
        return redirect("asset_overview")
    return render(
        request,
        "tradefog/journal/asset_form.html",
        {"form": form, "editing": False},
    )


@login_required
@require_http_methods(["GET", "POST"])
def asset_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    """Correct one active user-owned asset."""
    asset = _owned_asset(request, asset_id)
    form = AssetForm(
        request.POST if request.method == "POST" else None,
        instance=asset,
    )
    if request.method == "POST" and form.is_valid():
        _updated_asset = cast(Asset, form.save())
        messages.success(request, _("Asset updated."))
        return redirect("asset_overview")
    return render(
        request,
        "tradefog/journal/asset_form.html",
        {"form": form, "editing": True, "asset": asset},
    )


@login_required
@require_POST
def asset_archive(request: HttpRequest, asset_id: int) -> HttpResponse:
    """Archive an asset while preserving existing pair references."""
    archive_asset(_owned_asset(request, asset_id))
    messages.success(request, _("Asset archived."))
    return redirect("asset_overview")


@login_required
@require_POST
def asset_restore(request: HttpRequest, asset_id: int) -> HttpResponse:
    """Restore an archived asset to profile and pair selectors."""
    restore_asset(_owned_asset(request, asset_id, archived=True))
    messages.success(request, _("Asset restored."))
    return redirect("asset_overview")


@login_required
def profile_overview(request: HttpRequest) -> HttpResponse:
    """List non-archived profiles owned by the authenticated user."""
    profiles = TradingProfile.objects.filter(owner=_request_owner(request))
    profiles = profiles.exclude(status=TradingProfile.Status.ARCHIVED.value)
    return render(
        request,
        "tradefog/journal/profile_overview.html",
        {
            "profiles": profiles,
            "archived_profile_count": TradingProfile.objects.filter(
                owner=_request_owner(request),
                status=TradingProfile.Status.ARCHIVED.value,
            ).count(),
        },
    )


@login_required
def archived_profile_overview(request: HttpRequest) -> HttpResponse:
    """List archived profiles owned by the authenticated user."""
    profiles = TradingProfile.objects.filter(
        owner=_request_owner(request),
        status=TradingProfile.Status.ARCHIVED.value,
    )
    return render(
        request,
        "tradefog/journal/archived_profile_overview.html",
        {"profiles": profiles},
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_create(request: HttpRequest) -> HttpResponse:
    """Create a manual trading profile for the authenticated user."""
    form = TradingProfileForm(
        _request_owner(request),
        request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        profile = cast(TradingProfile, form.save(commit=False))
        profile.owner = _request_owner(request)
        profile.save()
        _ = sync_profile_status(profile)
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/profile_form.html",
        {"form": form, "editing": False},
    )


@login_required
def profile_detail(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Show one profile's capital policy and configured instruments."""
    return _render_profile_detail(request, _owned_profile(request, profile_id))


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Edit an active profile owned by the authenticated user."""
    profile = _owned_profile(request, profile_id)
    form = TradingProfileForm(
        _request_owner(request),
        request.POST if request.method == "POST" else None,
        instance=profile,
    )
    if request.method == "POST" and form.is_valid():
        profile = cast(TradingProfile, form.save())
        _ = sync_profile_status(profile)
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/profile_form.html",
        {"form": form, "editing": True, "profile": profile},
    )


@login_required
@require_http_methods(["GET", "POST"])
def profile_archive(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Confirm and archive an owned trading profile."""
    profile = _owned_profile(request, profile_id)
    if request.method == "POST":
        archive_profile(profile)
        return redirect("profile_overview")
    return render(
        request,
        "tradefog/journal/archive_confirm.html",
        {
            "object": profile,
            "object_kind": "profile",
            "cancel_url": profile.get_absolute_url(),
        },
    )


@login_required
@require_POST
def profile_restore(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Restore an archived profile owned by the authenticated user."""
    profile = _owned_archived_profile(request, profile_id)
    restore_profile(profile)
    messages.success(request, _("Profile restored."))
    return redirect("profile_detail", profile_id=profile.id)


def _create_capital_operation(
    request: HttpRequest,
    profile: TradingProfile,
    operation_type: str,
) -> HttpResponse:
    """Validate and apply one profile capital action."""
    form = CapitalOperationForm(operation_type, request.POST)
    if form.is_valid():
        try:
            _created_operation = create_capital_operation(
                profile,
                operation_type=operation_type,
                amount=cast(Decimal, form.cleaned_data["amount"]),
                note=cast(str, form.cleaned_data["note"]),
            )
        except ValidationError as error:
            _add_validation_errors(form, error)
        else:
            messages.success(request, _("Capital updated."))
            return redirect("profile_detail", profile_id=profile.id)
    if operation_type == CapitalOperation.Type.DEPOSIT.value:
        return _render_profile_detail(request, profile, deposit_form=form)
    return _render_profile_detail(request, profile, withdrawal_form=form)


@login_required
@require_POST
def capital_deposit(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Allocate additional virtual capital to an owned profile."""
    return _create_capital_operation(
        request,
        _owned_profile(request, profile_id),
        CapitalOperation.Type.DEPOSIT.value,
    )


@login_required
@require_POST
def capital_withdraw(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Remove virtual capital from an owned profile."""
    return _create_capital_operation(
        request,
        _owned_profile(request, profile_id),
        CapitalOperation.Type.WITHDRAWAL.value,
    )


@login_required
@require_http_methods(["GET", "POST"])
def capital_operation_edit(
    request: HttpRequest,
    profile_id: int,
    operation_id: int,
) -> HttpResponse:
    """Correct the amount or note of an owned capital operation."""
    profile = _owned_profile(request, profile_id)
    operation = _owned_capital_operation(profile, operation_id)
    operation_type = operation.operation_type
    form = CapitalOperationForm(
        operation_type,
        request.POST if request.method == "POST" else None,
        instance=operation,
    )
    if request.method == "POST" and form.is_valid():
        try:
            _updated_operation = update_capital_operation(
                operation,
                amount=cast(Decimal, form.cleaned_data["amount"]),
                note=cast(str, form.cleaned_data["note"]),
            )
        except ValidationError as error:
            _add_validation_errors(form, error)
        else:
            messages.success(request, _("Capital operation updated."))
            return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/capital_operation_form.html",
        {"form": form, "profile": profile, "operation": operation},
    )


@login_required
@require_http_methods(["GET", "POST"])
def capital_operation_delete(
    request: HttpRequest,
    profile_id: int,
    operation_id: int,
) -> HttpResponse:
    """Confirm and delete an erroneous owned capital operation."""
    profile = _owned_profile(request, profile_id)
    operation = _owned_capital_operation(profile, operation_id)
    if request.method == "POST":
        try:
            delete_capital_operation(operation)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, _("Capital operation deleted."))
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/capital_operation_delete.html",
        {"profile": profile, "operation": operation},
    )


@login_required
@require_http_methods(["GET", "POST"])
def trading_pair_create(
    request: HttpRequest,
    profile_id: int,
) -> HttpResponse:
    """Add a provider-specific trading pair to an owned profile."""
    profile = _owned_profile(request, profile_id)
    form = ProfileTradingPairForm(
        profile,
        request.POST if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        trading_pair = cast(ProfileTradingPair, form.save(commit=False))
        trading_pair.profile = profile
        trading_pair.save()
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/trading_pair_form.html",
        {"form": form, "editing": False, "profile": profile},
    )


@login_required
@require_http_methods(["GET", "POST"])
def trading_pair_edit(
    request: HttpRequest,
    profile_id: int,
    pair_id: int,
) -> HttpResponse:
    """Edit an active trading pair within an owned profile."""
    profile = _owned_profile(request, profile_id)
    trading_pair = _owned_trading_pair(profile, pair_id)
    form = ProfileTradingPairForm(
        profile,
        request.POST if request.method == "POST" else None,
        instance=trading_pair,
    )
    if request.method == "POST" and form.is_valid():
        _ = cast(ProfileTradingPair, form.save())
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/trading_pair_form.html",
        {
            "form": form,
            "editing": True,
            "profile": profile,
            "trading_pair": trading_pair,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def trading_pair_archive(
    request: HttpRequest,
    profile_id: int,
    pair_id: int,
) -> HttpResponse:
    """Confirm and archive a trading pair within an owned profile."""
    profile = _owned_profile(request, profile_id)
    trading_pair = _owned_trading_pair(profile, pair_id)
    if request.method == "POST":
        archive_trading_pair(trading_pair)
        return redirect("profile_detail", profile_id=profile.id)
    return render(
        request,
        "tradefog/journal/archive_confirm.html",
        {
            "object": trading_pair,
            "object_kind": "trading_pair",
            "cancel_url": profile.get_absolute_url(),
        },
    )


@login_required
@require_POST
def trading_pair_restore(
    request: HttpRequest,
    profile_id: int,
    pair_id: int,
) -> HttpResponse:
    """Restore an archived pair within an owned active profile."""
    profile = _owned_profile(request, profile_id)
    trading_pair = _owned_archived_trading_pair(profile, pair_id)
    if restore_trading_pair(trading_pair):
        messages.success(request, _("Trading pair restored."))
    else:
        messages.error(
            request,
            ACTIVE_PAIR_EXISTS
            + " "
            + _("Archive that pair before restoring this one."),
        )
    return redirect("profile_detail", profile_id=profile.id)


@login_required
def daily_candle_overview(
    request: HttpRequest,
    profile_id: int,
    pair_id: int,
) -> HttpResponse:
    """List a filtered page of candles for one owned profile pair."""
    profile = _owned_profile(request, profile_id)
    trading_pair = _owned_trading_pair(profile, pair_id)
    filter_form = DailyCandleFilterForm(request.GET or None)
    candles = trading_pair.daily_candles.all()
    if filter_form.is_valid():
        date_from = filter_form.cleaned_data.get("date_from")
        date_to = filter_form.cleaned_data.get("date_to")
        source = filter_form.cleaned_data.get("source")
        if date_from:
            candles = candles.filter(trading_date__gte=date_from)
        if date_to:
            candles = candles.filter(trading_date__lte=date_to)
        if source:
            candles = candles.filter(source=source)

    requested_sort = request.GET.get("sort", "-date")
    sort_fields = {
        "date": ("trading_date", "id"),
        "-date": ("-trading_date", "-id"),
        "open": ("open_price", "trading_date", "id"),
        "-open": ("-open_price", "-trading_date", "-id"),
        "high": ("high_price", "trading_date", "id"),
        "-high": ("-high_price", "-trading_date", "-id"),
        "low": ("low_price", "trading_date", "id"),
        "-low": ("-low_price", "-trading_date", "-id"),
        "close": ("close_price", "trading_date", "id"),
        "-close": ("-close_price", "-trading_date", "-id"),
        "source": ("source", "-trading_date", "-id"),
        "-source": ("-source", "-trading_date", "-id"),
    }
    current_sort = (
        requested_sort if requested_sort in sort_fields else "-date"
    )
    page_obj = Paginator(
        candles.order_by(*sort_fields[current_sort]),
        CANDLE_PAGE_SIZE,
    ).get_page(request.GET.get("page"))
    context = {
        "profile": profile,
        "trading_pair": trading_pair,
        "filter_form": filter_form,
        "page_obj": page_obj,
        "pagination": _pagination_urls(request, page_obj),
        "current_sort": current_sort,
        "sort_headers": _sort_headers(
            request,
            current_sort,
            (
                ("date", _("Date")),
                ("open", _("Open price")),
                ("high", _("High price")),
                ("low", _("Low price")),
                ("close", _("Close price")),
                ("source", _("Source")),
            ),
        ),
    }
    template = "tradefog/journal/daily_candle_overview.html"
    if request.headers.get("HX-Request") == "true":
        template = "tradefog/journal/partials/daily_candle_results.html"
    return render(
        request,
        template,
        context,
    )


def _save_manual_candle(
    request: HttpRequest,
    profile: TradingProfile,
    trading_pair: ProfileTradingPair,
    candle: DailyCandle,
    *,
    editing: bool,
) -> HttpResponse:
    """Validate and save one canonical manually maintained candle."""
    form = DailyCandleForm(request.POST, instance=candle)
    if form.is_valid():
        saved_candle = cast(DailyCandle, form.save(commit=False))
        saved_candle.trading_pair = trading_pair
        saved_candle.source = (
            ProfileTradingPair.MarketDataProvider.MANUAL.value
        )
        saved_candle.fetched_at = timezone.now()
        saved_candle.save()
        messages.success(request, _("Daily candle saved."))
        return redirect(
            "daily_candle_overview",
            profile_id=profile.id,
            pair_id=trading_pair.id,
        )
    return render(
        request,
        "tradefog/journal/daily_candle_form.html",
        {
            "form": form,
            "profile": profile,
            "trading_pair": trading_pair,
            "candle": candle if editing else None,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def daily_candle_create(
    request: HttpRequest,
    profile_id: int,
    pair_id: int,
) -> HttpResponse:
    """Add one manually sourced closed candle to an owned pair."""
    profile = _owned_profile(request, profile_id)
    trading_pair = _owned_trading_pair(profile, pair_id)
    candle = DailyCandle(trading_pair=trading_pair)
    if request.method == "POST":
        return _save_manual_candle(
            request,
            profile,
            trading_pair,
            candle,
            editing=False,
        )
    return render(
        request,
        "tradefog/journal/daily_candle_form.html",
        {
            "form": DailyCandleForm(instance=candle),
            "profile": profile,
            "trading_pair": trading_pair,
            "candle": None,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def daily_candle_edit(
    request: HttpRequest,
    profile_id: int,
    pair_id: int,
    candle_id: int,
) -> HttpResponse:
    """Correct a stored candle and mark its provenance as manual."""
    profile = _owned_profile(request, profile_id)
    trading_pair = _owned_trading_pair(profile, pair_id)
    candle = _owned_daily_candle(trading_pair, candle_id)
    if request.method == "POST":
        return _save_manual_candle(
            request,
            profile,
            trading_pair,
            candle,
            editing=True,
        )
    return render(
        request,
        "tradefog/journal/daily_candle_form.html",
        {
            "form": DailyCandleForm(instance=candle),
            "profile": profile,
            "trading_pair": trading_pair,
            "candle": candle,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def daily_candle_delete(
    request: HttpRequest,
    profile_id: int,
    pair_id: int,
    candle_id: int,
) -> HttpResponse:
    """Confirm removal of one erroneous owned candle."""
    profile = _owned_profile(request, profile_id)
    trading_pair = _owned_trading_pair(profile, pair_id)
    candle = _owned_daily_candle(trading_pair, candle_id)
    if request.method == "POST":
        _deleted = candle.delete()
        messages.success(request, _("Daily candle deleted."))
        return redirect(
            "daily_candle_overview",
            profile_id=profile.id,
            pair_id=trading_pair.id,
        )
    return render(
        request,
        "tradefog/journal/daily_candle_delete.html",
        {
            "profile": profile,
            "trading_pair": trading_pair,
            "candle": candle,
        },
    )


def _draft_plan(
    form: TradeDraftForm,
) -> tuple[PositionPlan | None, str | None]:
    """Validate draft input and return a preview or one focused error."""
    if not form.is_valid():
        errors = [
            str(error) for errors in form.errors.values() for error in errors
        ]
        return None, errors[0] if errors else _(
            "Complete the position fields."
        )
    trade = cast(Trade, form.save(commit=False))
    try:
        return calculate_trade_plan(trade), None
    except PositionPlanError as error:
        return None, error.message


def _draft_trading_pair(form: TradeDraftForm) -> ProfileTradingPair | None:
    """Return the validated trading pair selected in a draft form."""
    if not form.is_bound:
        trade = cast(Trade, form.instance)
        if getattr(trade, "trading_pair_id", None) is not None:
            return trade.trading_pair
        return None
    if not hasattr(form, "cleaned_data"):
        return None
    trading_pair = form.cleaned_data.get("trading_pair")
    if isinstance(trading_pair, ProfileTradingPair):
        return trading_pair
    return None


def _draft_context_date(form: TradeDraftForm) -> date | None:
    """Return the validated provider-session date from a draft form."""
    if not form.is_bound:
        trade = cast(Trade, form.instance)
        return trade.trade_date
    if not hasattr(form, "cleaned_data"):
        return None
    context_date = form.cleaned_data.get("trade_date")
    return context_date if isinstance(context_date, date) else None


def _trade_checklist(trade: Trade) -> TradeChecklist | None:
    """Return an existing one-to-one checklist without requiring one."""
    try:
        return trade.checklist
    except TradeChecklist.DoesNotExist:
        return None


def _checklist_answers(form: TradeChecklistForm) -> ChecklistAnswers:
    """Return validated preview answers or a safe empty assessment."""
    if not form.is_bound:
        checklist = cast(TradeChecklist, form.instance)
        return checklist.answers
    if form.is_valid():
        checklist = cast(TradeChecklist, form.save(commit=False))
        return checklist.answers
    return ChecklistAnswers()


def _selected_direction(form: TradeDraftForm, fallback: str) -> str:
    """Return a validated edited direction when it is available."""
    if not hasattr(form, "cleaned_data"):
        return fallback
    direction = form.cleaned_data.get("direction")
    return direction if isinstance(direction, str) else fallback


def _checklist_assessment(
    form: TradeChecklistForm,
    *,
    selected_direction: str,
) -> ChecklistAssessment:
    """Calculate a reactive assessment from one bound or initial form."""
    return calculate_checklist_assessment(
        _checklist_answers(form),
        selected_direction=selected_direction,
    )


def _plan_context(
    profile: TradingProfile,
    plan: PositionPlan | None,
) -> dict[str, object]:
    """Add advisory capacity values for a calculated draft plan."""
    if plan is None:
        return {}
    remaining_capacity = profile.risk_capacity - plan.planned_risk_amount
    return {
        "plan_remaining_capacity": remaining_capacity,
        "plan_breached": remaining_capacity <= 0,
        "plan_notional_breached": plan.notional > profile.current_capital,
    }


def _atr_target_comparison(
    plan: PositionPlan | None,
    market_context: MarketContext | None,
) -> AtrTargetComparison | None:
    """Combine an exact position plan with cached date-aware ATR."""
    if plan is None or market_context is None:
        return None
    return compare_target_move_with_atr(
        plan.take_profit_distance,
        market_context.atr_value,
    )


def _trade_workspace_context(
    trade: Trade,
    *,
    form: TradeDraftForm | None = None,
    checklist_form: TradeChecklistForm | None = None,
) -> dict[str, object]:
    """Build the trade workspace context for draft and frozen plans."""
    context: dict[str, object] = {
        "trade": trade,
        "profile": trade.profile,
        "trading_pair": trade.trading_pair,
    }
    checklist = _trade_checklist(trade)
    if trade.status != Trade.Status.DRAFT.value:
        answers = checklist.answers if checklist else ChecklistAnswers()
        context.update(
            {
                "checklist": checklist,
                "checklist_assessment": calculate_checklist_assessment(
                    answers,
                    selected_direction=trade.direction,
                ),
            }
        )
        return context
    if form is None:
        market_context_url = reverse(
            "trade_market_context", kwargs={"trade_id": trade.id}
        )
        draft_form = TradeDraftForm(
            trade.profile,
            instance=trade,
            plan_url=reverse("trade_plan", kwargs={"trade_id": trade.id}),
            market_context_url=market_context_url,
        )
        try:
            plan, plan_error = calculate_trade_plan(trade), None
        except PositionPlanError as error:
            plan, plan_error = None, error.message
    else:
        draft_form = form
        plan, plan_error = _draft_plan(draft_form)
    if checklist_form is None:
        draft_checklist_form = TradeChecklistForm(
            instance=checklist,
            assessment_url=reverse(
                "trade_checklist", kwargs={"trade_id": trade.id}
            ),
        )
    else:
        draft_checklist_form = checklist_form
    assessment = _checklist_assessment(
        draft_checklist_form,
        selected_direction=_selected_direction(draft_form, trade.direction),
    )
    context.update(
        {
            "form": draft_form,
            "plan": plan,
            "plan_error": plan_error,
            "checklist_form": draft_checklist_form,
            "checklist_assessment": assessment,
            "market_context_url": reverse(
                "trade_market_context", kwargs={"trade_id": trade.id}
            ),
        }
    )
    selected_pair = _draft_trading_pair(draft_form)
    context_date = _draft_context_date(draft_form)
    market_context = None
    if plan is not None and selected_pair is not None:
        context["trading_pair"] = selected_pair
    if selected_pair is not None and context_date is not None:
        market_context = get_market_context(
            selected_pair,
            context_date,
        )
        context["market_context"] = market_context
    context["atr_target_comparison"] = _atr_target_comparison(
        plan,
        market_context,
    )
    context.update(_plan_context(trade.profile, plan))
    return context


@login_required
def trade_overview(request: HttpRequest) -> HttpResponse:
    """List journal decisions across every profile owned by the user."""
    owner = _request_owner(request)
    filter_form = TradeOverviewFilterForm(owner, request.GET or None)
    trades = Trade.objects.filter(
        profile__owner=owner
    ).select_related(
        "profile__capital_asset",
        "trading_pair__asset",
    )
    if filter_form.is_valid():
        search = filter_form.cleaned_data.get("search")
        profile = filter_form.cleaned_data.get("profile")
        status = filter_form.cleaned_data.get("status")
        direction = filter_form.cleaned_data.get("direction")
        market_type = filter_form.cleaned_data.get("market_type")
        date_from = filter_form.cleaned_data.get("date_from")
        date_to = filter_form.cleaned_data.get("date_to")
        if search:
            trades = trades.filter(
                Q(trading_pair__asset__symbol__icontains=search)
                | Q(profile__capital_asset__symbol__icontains=search)
                | Q(profile__name__icontains=search)
            )
        if isinstance(profile, TradingProfile):
            trades = trades.filter(profile=profile)
        if status:
            trades = trades.filter(status=status)
        if direction:
            trades = trades.filter(direction=direction)
        if market_type:
            trades = trades.filter(profile__market_type=market_type)
        if date_from:
            trades = trades.filter(trade_date__gte=date_from)
        if date_to:
            trades = trades.filter(trade_date__lte=date_to)

    requested_sort = request.GET.get("sort", "-date")
    sort_fields = {
        "direction": ("direction", "-trade_date", "-id"),
        "-direction": ("-direction", "-trade_date", "-id"),
        "pair": (
            "trading_pair__asset__symbol",
            "profile__capital_asset__symbol",
            "-trade_date",
            "-id",
        ),
        "-pair": (
            "-trading_pair__asset__symbol",
            "-profile__capital_asset__symbol",
            "-trade_date",
            "-id",
        ),
        "market": ("profile__market_type", "-trade_date", "-id"),
        "-market": ("-profile__market_type", "-trade_date", "-id"),
        "profile": ("profile__name", "-trade_date", "-id"),
        "-profile": ("-profile__name", "-trade_date", "-id"),
        "date": ("trade_date", "created_at", "id"),
        "-date": ("-trade_date", "-created_at", "-id"),
        "status": ("status", "-trade_date", "-id"),
        "-status": ("-status", "-trade_date", "-id"),
        "result": ("result_r", "-trade_date", "-id"),
        "-result": ("-result_r", "-trade_date", "-id"),
    }
    current_sort = (
        requested_sort if requested_sort in sort_fields else "-date"
    )
    page_obj = Paginator(
        trades.order_by(*sort_fields[current_sort]),
        TRADE_PAGE_SIZE,
    ).get_page(request.GET.get("page"))
    context = {
        "filter_form": filter_form,
        "page_obj": page_obj,
        "pagination": _pagination_urls(request, page_obj),
        "current_sort": current_sort,
        "sort_headers": _sort_headers(
            request,
            current_sort,
            (
                ("direction", _("Direction")),
                ("pair", _("Pair")),
                ("market", _("Market type")),
                ("profile", _("Profile")),
                ("date", _("Date")),
                ("status", _("Status")),
                ("result", _("Result")),
            ),
        ),
    }
    template = "tradefog/journal/trade_overview.html"
    if request.headers.get("HX-Request") == "true":
        template = "tradefog/journal/partials/trade_results.html"
    return render(
        request,
        template,
        context,
    )


@login_required
def trade_profile_select(request: HttpRequest) -> HttpResponse:
    """Select the explicit profile context for a new trade."""
    profiles = (
        TradingProfile.objects.filter(owner=_request_owner(request))
        .exclude(status=TradingProfile.Status.ARCHIVED.value)
        .filter(trading_pairs__archived_at__isnull=True)
        .distinct()
    )
    return render(
        request,
        "tradefog/journal/trade_profile_select.html",
        {"profiles": profiles},
    )


@login_required
@require_http_methods(["GET", "POST"])
def trade_create(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Create one editable trade draft in an explicit profile context."""
    profile = _owned_profile(request, profile_id)
    if not profile.trading_pairs.filter(archived_at__isnull=True).exists():
        messages.error(request, _("Add an active trading pair first."))
        return redirect("profile_detail", profile_id=profile.id)
    plan_url = reverse("new_trade_plan", kwargs={"profile_id": profile.id})
    checklist_url = reverse(
        "new_trade_checklist", kwargs={"profile_id": profile.id}
    )
    market_context_url = reverse(
        "new_trade_market_context", kwargs={"profile_id": profile.id}
    )
    form = TradeDraftForm(
        profile,
        request.POST if request.method == "POST" else None,
        plan_url=plan_url,
        market_context_url=market_context_url,
    )
    checklist_form = TradeChecklistForm(
        request.POST if request.method == "POST" else None,
        assessment_url=checklist_url,
    )
    trade_form_valid = form.is_valid() if request.method == "POST" else False
    checklist_form_valid = (
        checklist_form.is_valid() if request.method == "POST" else False
    )
    if trade_form_valid and checklist_form_valid:
        trade = cast(Trade, form.save(commit=False))
        trade.profile = profile
        checklist = cast(TradeChecklist, checklist_form.save(commit=False))
        _saved_trade = save_trade_draft(trade, checklist)
        return redirect("trade_detail", trade_id=trade.id)
    plan, plan_error = (
        _draft_plan(form) if request.method == "POST" else (None, None)
    )
    selected_pair = _draft_trading_pair(form)
    context_date = _draft_context_date(form)
    market_context = None
    if selected_pair is not None and context_date is not None:
        market_context = get_market_context(selected_pair, context_date)
    return render(
        request,
        "tradefog/journal/trade_form.html",
        {
            "form": form,
            "profile": profile,
            "creating": True,
            "plan": plan,
            "plan_error": plan_error,
            "trading_pair": _draft_trading_pair(form),
            "market_context": market_context,
            "atr_target_comparison": _atr_target_comparison(
                plan,
                market_context,
            ),
            "market_context_url": market_context_url,
            "checklist_form": checklist_form,
            "checklist_assessment": _checklist_assessment(
                checklist_form,
                selected_direction=_selected_direction(form, ""),
            ),
            **_plan_context(profile, plan),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def trade_detail(request: HttpRequest, trade_id: int) -> HttpResponse:
    """Show a trade workspace and update its editable draft facts."""
    trade = _owned_trade(request, trade_id)
    if trade.status == Trade.Status.DRAFT.value and request.method == "POST":
        form = TradeDraftForm(
            trade.profile,
            request.POST,
            instance=trade,
            plan_url=reverse("trade_plan", kwargs={"trade_id": trade.id}),
            market_context_url=reverse(
                "trade_market_context", kwargs={"trade_id": trade.id}
            ),
        )
        checklist_form = TradeChecklistForm(
            request.POST,
            instance=_trade_checklist(trade),
            assessment_url=reverse(
                "trade_checklist", kwargs={"trade_id": trade.id}
            ),
        )
        form_valid = form.is_valid()
        checklist_valid = checklist_form.is_valid()
        if form_valid and checklist_valid:
            edited_trade = cast(Trade, form.save(commit=False))
            checklist = cast(
                TradeChecklist, checklist_form.save(commit=False)
            )
            _saved_trade = save_trade_draft(edited_trade, checklist)
            messages.success(request, _("Draft saved."))
            return redirect("trade_detail", trade_id=trade.id)
        context = _trade_workspace_context(
            trade,
            form=form,
            checklist_form=checklist_form,
        )
    else:
        context = _trade_workspace_context(trade)
    return render(request, "tradefog/journal/trade_detail.html", context)


def _render_market_context_response(
    request: HttpRequest,
    form: TradeDraftForm,
) -> HttpResponse:
    """Refresh one selected pair and update ATR plus plan fragments."""
    plan, plan_error = _draft_plan(form)
    trading_pair = _draft_trading_pair(form)
    context_date = _draft_context_date(form)
    market_context = None
    if trading_pair is not None and context_date is not None:
        market_context = refresh_market_context(
            trading_pair,
            context_date,
        )
    return render(
        request,
        "tradefog/journal/partials/market_context_response.html",
        {
            "market_context": market_context,
            "market_context_url": request.path,
            "profile": form.profile,
            "trading_pair": trading_pair,
            "plan": plan,
            "plan_error": plan_error,
            "atr_target_comparison": _atr_target_comparison(
                plan,
                market_context,
            ),
            **_plan_context(form.profile, plan),
        },
    )


@login_required
@require_POST
def new_trade_market_context(
    request: HttpRequest,
    profile_id: int,
) -> HttpResponse:
    """Refresh market context for a selected unsaved owned draft pair."""
    profile = _owned_profile(request, profile_id)
    return _render_market_context_response(
        request,
        TradeDraftForm(profile, request.POST),
    )


@login_required
@require_POST
def trade_market_context(
    request: HttpRequest,
    trade_id: int,
) -> HttpResponse:
    """Refresh market context while an owned trade remains a draft."""
    trade = _owned_trade(request, trade_id)
    if trade.status != Trade.Status.DRAFT.value:
        return HttpResponse(status=409)
    return _render_market_context_response(
        request,
        TradeDraftForm(trade.profile, request.POST, instance=trade),
    )


def _render_plan_preview(
    request: HttpRequest,
    form: TradeDraftForm,
) -> HttpResponse:
    """Render the independently replaceable position-plan preview."""
    plan, plan_error = _draft_plan(form)
    trading_pair = _draft_trading_pair(form)
    context_date = _draft_context_date(form)
    market_context = None
    if trading_pair is not None and context_date is not None:
        market_context = get_market_context(trading_pair, context_date)
    return render(
        request,
        "tradefog/journal/partials/trade_plan_response.html",
        {
            "plan": plan,
            "plan_error": plan_error,
            "profile": form.profile,
            "trading_pair": trading_pair,
            "market_context": market_context,
            "atr_target_comparison": _atr_target_comparison(
                plan,
                market_context,
            ),
            "checklist_assessment": _checklist_assessment(
                TradeChecklistForm(request.POST),
                selected_direction=request.POST.get("direction", ""),
            ),
            **_plan_context(form.profile, plan),
        },
    )


@login_required
@require_POST
def new_trade_plan(request: HttpRequest, profile_id: int) -> HttpResponse:
    """Preview an unsaved draft plan for one owned profile."""
    profile = _owned_profile(request, profile_id)
    return _render_plan_preview(
        request,
        TradeDraftForm(profile, request.POST),
    )


def _render_checklist_assessment(
    request: HttpRequest,
    form: TradeChecklistForm,
    *,
    selected_direction: str,
) -> HttpResponse:
    """Render the independently replaceable directional assessment."""
    return render(
        request,
        "tradefog/journal/partials/checklist_assessment.html",
        {
            "checklist_assessment": _checklist_assessment(
                form,
                selected_direction=selected_direction,
            )
        },
    )


@login_required
@require_POST
def new_trade_checklist(
    request: HttpRequest,
    profile_id: int,
) -> HttpResponse:
    """Preview unsaved checklist answers for one owned profile."""
    _profile = _owned_profile(request, profile_id)
    return _render_checklist_assessment(
        request,
        TradeChecklistForm(request.POST),
        selected_direction=request.POST.get("direction", ""),
    )


@login_required
@require_POST
def trade_plan(request: HttpRequest, trade_id: int) -> HttpResponse:
    """Preview edits to an existing owned draft without persisting them."""
    trade = _owned_trade(request, trade_id)
    if trade.status != Trade.Status.DRAFT.value:
        return HttpResponse(status=409)
    return _render_plan_preview(
        request,
        TradeDraftForm(trade.profile, request.POST, instance=trade),
    )


@login_required
@require_POST
def trade_checklist(request: HttpRequest, trade_id: int) -> HttpResponse:
    """Preview checklist edits for an existing owned draft."""
    trade = _owned_trade(request, trade_id)
    if trade.status != Trade.Status.DRAFT.value:
        return HttpResponse(status=409)
    return _render_checklist_assessment(
        request,
        TradeChecklistForm(
            request.POST,
            instance=_trade_checklist(trade),
        ),
        selected_direction=request.POST.get("direction", trade.direction),
    )


def _transition_error(request: HttpRequest, error: ValidationError) -> None:
    """Present a lifecycle conflict without exposing an exception page."""
    messages.error(request, " ".join(error.messages))


@login_required
@require_POST
def trade_submit(request: HttpRequest, trade_id: int) -> HttpResponse:
    """Freeze an owned draft and reserve its pending-entry risk."""
    trade = _owned_trade(request, trade_id)
    try:
        frozen_trade = submit_trade(trade)
    except (ValidationError, PositionPlanError) as error:
        if isinstance(error, PositionPlanError):
            messages.error(request, error.message)
        else:
            _transition_error(request, error)
    else:
        if frozen_trade.risk_limit_breached:
            messages.warning(
                request,
                _("Order recorded with a risk-stop breach."),
            )
        else:
            messages.success(request, _("Order marked as pending entry."))
    return redirect("trade_detail", trade_id=trade.id)


@login_required
@require_POST
def trade_open(request: HttpRequest, trade_id: int) -> HttpResponse:
    """Mark an owned pending order as filled."""
    trade = _owned_trade(request, trade_id)
    try:
        _opened_trade = open_trade(trade)
    except ValidationError as error:
        _transition_error(request, error)
    else:
        messages.success(request, _("Position marked as open."))
    return redirect("trade_detail", trade_id=trade.id)


@login_required
@require_POST
def trade_cancel(request: HttpRequest, trade_id: int) -> HttpResponse:
    """Cancel an owned draft or pending order."""
    trade = _owned_trade(request, trade_id)
    try:
        _cancelled_trade = cancel_trade(trade)
    except ValidationError as error:
        _transition_error(request, error)
    else:
        messages.success(request, _("Trade cancelled."))
    return redirect("trade_detail", trade_id=trade.id)


@login_required
@require_http_methods(["GET", "POST"])
def trade_close(request: HttpRequest, trade_id: int) -> HttpResponse:
    """Close a position or correct its aggregate realized result."""
    trade = _owned_trade(request, trade_id)
    if trade.status not in {
        Trade.Status.OPEN.value,
        Trade.Status.CLOSED.value,
    }:
        return HttpResponse(status=409)
    initial: dict[str, object] | None = None
    if request.method == "GET" and trade.status == Trade.Status.CLOSED.value:
        initial = {
            "realized_pnl": trade.realized_pnl,
            "actual_exit_price": trade.actual_exit_price,
            "commission_total": trade.commission_total,
            "funding_result": trade.funding_result,
        }
    form = CloseTradeForm(
        request.POST if request.method == "POST" else None,
        trade=trade,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            realized_pnl = cast(
                Decimal,
                form.cleaned_data["realized_pnl"],
            )
            actual_exit_price = cast(
                Decimal | None,
                form.cleaned_data["actual_exit_price"],
            )
            commission_total = cast(
                Decimal | None,
                form.cleaned_data["commission_total"],
            )
            funding_result = cast(
                Decimal | None,
                form.cleaned_data.get("funding_result"),
            )
            if trade.status == Trade.Status.OPEN.value:
                _closed_trade = close_trade(
                    trade,
                    realized_pnl=realized_pnl,
                    actual_exit_price=actual_exit_price,
                    commission_total=commission_total,
                    funding_result=funding_result,
                )
            else:
                _corrected_trade = update_trade_result(
                    trade,
                    realized_pnl=realized_pnl,
                    actual_exit_price=actual_exit_price,
                    commission_total=commission_total,
                    funding_result=funding_result,
                )
        except ValidationError as error:
            _transition_error(request, error)
        else:
            if trade.status == Trade.Status.OPEN.value:
                messages.success(request, _("Trade closed."))
            else:
                messages.success(request, _("Trade result updated."))
            return redirect("trade_detail", trade_id=trade.id)
    return render(
        request,
        "tradefog/journal/trade_close.html",
        {
            "trade": trade,
            "form": form,
            "correcting": trade.status == Trade.Status.CLOSED.value,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def trade_date_edit(request: HttpRequest, trade_id: int) -> HttpResponse:
    """Correct an owned trade's analytical date at any lifecycle stage."""
    trade = _owned_trade(request, trade_id)
    form = TradeDateForm(
        request.POST if request.method == "POST" else None,
        instance=trade,
    )
    if request.method == "POST" and form.is_valid():
        _dated_trade = cast(Trade, form.save())
        messages.success(request, _("Trade date updated."))
        return redirect("trade_detail", trade_id=trade.id)
    return render(
        request,
        "tradefog/journal/trade_date_form.html",
        {"trade": trade, "form": form},
    )
