"""Static shell pages that are not yet backed by domain logic."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """Render the home stub page."""
    return render(request, "tradefog/home.html")


@login_required
def analytics(request: HttpRequest) -> HttpResponse:
    """Render the static analytics page."""
    return render(request, "tradefog/analytics.html")
