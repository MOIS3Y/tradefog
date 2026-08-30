"""Owner-scoped HTTP views for journal workflows and analytics."""

from datetime import date
from decimal import Decimal
from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
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
from tradefog.journal.forms import (
    AnalyticsFilterForm,
    AssetForm,
    CapitalOperationForm,
    CloseTradeForm,
    ProfileTradingPairForm,
    TradeDateForm,
    TradeDraftForm,
    TradingProfileForm,
)
from tradefog.journal.models import (
    ACTIVE_PAIR_EXISTS,
    Asset,
    CapitalOperation,
    ProfileTradingPair,
    Trade,
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
    submit_trade,
    sync_profile_status,
    update_capital_operation,
    update_trade_result,
)


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


def _owned_trade(request: HttpRequest, trade_id: int) -> Trade:
    """Resolve one trade through its profile ownership boundary."""
    return get_object_or_404(
        Trade.objects.select_related(
            "profile__capital_asset",
            "trading_pair__asset",
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
        "trading_pairs": profile.trading_pairs.filter(
            archived_at__isnull=True
        ).select_related("asset", "profile__capital_asset"),
        "archived_trading_pairs": profile.trading_pairs.filter(
            archived_at__isnull=False
        ).select_related("asset", "profile__capital_asset"),
        "capital_operations": profile.capital_operations.all(),
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
    return render(
        request,
        "tradefog/journal/profile_detail.html",
        _profile_detail_context(
            profile,
            deposit_form=deposit_form,
            withdrawal_form=withdrawal_form,
        ),
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


@login_required
def asset_overview(request: HttpRequest) -> HttpResponse:
    """List reusable asset identities owned by the authenticated user."""
    assets = Asset.objects.filter(owner=_request_owner(request))
    return render(
        request,
        "tradefog/journal/asset_overview.html",
        {
            "assets": assets.filter(archived_at__isnull=True),
            "archived_assets": assets.filter(archived_at__isnull=False),
        },
    )


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
    if not hasattr(form, "cleaned_data"):
        return None
    trading_pair = form.cleaned_data.get("trading_pair")
    if isinstance(trading_pair, ProfileTradingPair):
        return trading_pair
    return None


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


def _trade_workspace_context(
    trade: Trade,
    *,
    form: TradeDraftForm | None = None,
) -> dict[str, object]:
    """Build the trade workspace context for draft and frozen plans."""
    context: dict[str, object] = {
        "trade": trade,
        "profile": trade.profile,
        "trading_pair": trade.trading_pair,
    }
    if trade.status != Trade.Status.DRAFT.value:
        return context
    if form is None:
        draft_form = TradeDraftForm(
            trade.profile,
            instance=trade,
            plan_url=reverse("trade_plan", kwargs={"trade_id": trade.id}),
        )
        try:
            plan, plan_error = calculate_trade_plan(trade), None
        except PositionPlanError as error:
            plan, plan_error = None, error.message
    else:
        draft_form = form
        plan, plan_error = _draft_plan(draft_form)
    context.update(
        {"form": draft_form, "plan": plan, "plan_error": plan_error}
    )
    selected_pair = _draft_trading_pair(draft_form)
    if plan is not None and selected_pair is not None:
        context["trading_pair"] = selected_pair
    context.update(_plan_context(trade.profile, plan))
    return context


@login_required
def trade_overview(request: HttpRequest) -> HttpResponse:
    """List journal decisions across every profile owned by the user."""
    trades = Trade.objects.filter(
        profile__owner=_request_owner(request)
    ).select_related(
        "profile__capital_asset",
        "trading_pair__asset",
    )
    return render(
        request,
        "tradefog/journal/trade_overview.html",
        {"trades": trades},
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
    form = TradeDraftForm(
        profile,
        request.POST if request.method == "POST" else None,
        plan_url=plan_url,
    )
    if request.method == "POST" and form.is_valid():
        trade = cast(Trade, form.save(commit=False))
        trade.profile = profile
        trade.save()
        return redirect("trade_detail", trade_id=trade.id)
    plan, plan_error = (
        _draft_plan(form) if request.method == "POST" else (None, None)
    )
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
        )
        if form.is_valid():
            _saved_trade = cast(Trade, form.save())
            messages.success(request, _("Draft saved."))
            return redirect("trade_detail", trade_id=trade.id)
        context = _trade_workspace_context(trade, form=form)
    else:
        context = _trade_workspace_context(trade)
    return render(request, "tradefog/journal/trade_detail.html", context)


def _render_plan_preview(
    request: HttpRequest,
    form: TradeDraftForm,
) -> HttpResponse:
    """Render the independently replaceable position-plan preview."""
    plan, plan_error = _draft_plan(form)
    return render(
        request,
        "tradefog/journal/partials/trade_plan.html",
        {
            "plan": plan,
            "plan_error": plan_error,
            "profile": form.profile,
            "trading_pair": _draft_trading_pair(form),
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
