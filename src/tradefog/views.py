"""Project-level views for the authenticated application shell."""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """Render the future cross-profile dashboard workspace."""
    return render(request, "tradefog/home.html")
