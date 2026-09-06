"""HTMX endpoint for directional checklist assessment preview."""

from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from tradefog.journal.forms.trades import ChecklistForm


@login_required
@require_http_methods(["GET", "POST"])
def trade_checklist_preview(request: HttpRequest) -> HttpResponse:
    """Calculate and render checklist assessment and advisory gauge."""
    data = request.POST if request.method == "POST" else request.GET
    selected_direction = data.get("direction")

    form = ChecklistForm(data)
    if form.is_valid():
        assessment = form.assessment(selected_direction=selected_direction)
    else:
        assessment = None

    context: dict[str, Any] = {
        "assessment": assessment,
    }

    return render(
        request,
        "tradefog/trades/partials/checklist_assessment.html",
        context,
    )
