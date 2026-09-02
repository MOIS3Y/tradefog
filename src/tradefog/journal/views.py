"""Views for the static journal application shell.

These views render the shell pages only. No business logic or model
access happens here; the frontend is static until backend logic is
reintroduced.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """Render the home stub page."""
    return render(request, "tradefog/home.html")


@login_required
def profiles(request: HttpRequest) -> HttpResponse:
    """Render the trading profiles stub page."""
    return render(request, "tradefog/profiles.html")


@login_required
def trades(request: HttpRequest) -> HttpResponse:
    """Render the trades stub page."""
    return render(request, "tradefog/trades.html")


@login_required
def trade_new(request: HttpRequest) -> HttpResponse:
    """Render the static trade-entry page."""
    return render(request, "tradefog/trade.html")


@login_required
def analytics(request: HttpRequest) -> HttpResponse:
    """Render the static analytics page."""
    return render(request, "tradefog/analytics.html")


@login_required
def settings(request: HttpRequest) -> HttpResponse:
    """Render the global project settings stub page."""
    return render(request, "tradefog/settings.html")