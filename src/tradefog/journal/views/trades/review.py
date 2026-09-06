"""Views for trade post-trade review and Markdown descriptions."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from tradefog.journal.markdown import render_markdown
from tradefog.journal.models.trades import Trade
from tradefog.journal.services import set_trade_review_status


@login_required
@require_POST
def trade_description_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Save updated Markdown description and return rendered CommonMark HTML."""
    trade = get_object_or_404(
        Trade,
        pk=pk,
        profile__owner=request.user,
    )
    content_markdown = request.POST.get("content_markdown", "")
    trade.description_markdown = content_markdown
    trade.save(update_fields=["description_markdown"])

    rendered_html = render_markdown(content_markdown)
    is_empty = not content_markdown.strip()

    response = HttpResponse(rendered_html, content_type="text/html")
    response["X-Tradefog-Description"] = "rendered"
    response["X-Tradefog-Description-Empty"] = "true" if is_empty else "false"
    return response


@login_required
@require_POST
def trade_review_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """Toggle the review completion status of a closed trade."""
    trade = get_object_or_404(
        Trade,
        pk=pk,
        profile__owner=request.user,
    )
    completed = request.POST.get("completed") in ("1", "true", "True")
    try:
        set_trade_review_status(trade, completed=completed)
    except ValidationError as error:
        return HttpResponseBadRequest(str(error.message))

    return redirect("journal:trade_workspace", pk=trade.pk)
