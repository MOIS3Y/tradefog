"""Private attachment upload, serve, and deletion views."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
)
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from tradefog.journal.attachments import (
    create_trade_attachment,
    delete_trade_attachment,
)
from tradefog.journal.models.trades import Trade, TradeAttachment


@login_required
@require_POST
def trade_attachment_upload(request: HttpRequest, pk: int) -> HttpResponse:
    """Upload and validate one private file attachment for a trade."""
    trade = get_object_or_404(
        Trade,
        pk=pk,
        profile__owner=request.user,
    )
    upload = request.FILES.get("file")
    if not upload:
        return HttpResponseBadRequest(_("No file was uploaded."))

    try:
        attachment = create_trade_attachment(trade, upload)
    except ValidationError as error:
        return HttpResponseBadRequest(
            error.messages[0] if error.messages else str(error)
        )

    is_image = attachment.content_type.startswith("image/")
    return render(
        request,
        "tradefog/trades/partials/attachment_card.html",
        {
            "trade": trade,
            "attachment": attachment,
            "is_image": is_image,
        },
        status=201,
    )


@login_required
@require_GET
def trade_attachment_serve(
    request: HttpRequest, pk: int, attachment_pk: int
) -> FileResponse:
    """Stream a private trade attachment with an ownership check."""
    attachment = get_object_or_404(
        TradeAttachment.objects.select_related("trade__profile"),
        pk=attachment_pk,
        trade__pk=pk,
        trade__profile__owner=request.user,
    )
    as_attachment = request.GET.get("download") == "1"
    response = FileResponse(
        attachment.file.open("rb"),
        content_type=attachment.content_type,
        as_attachment=as_attachment,
        filename=attachment.original_name,
    )
    return response


@login_required
@require_POST
def trade_attachment_delete(
    request: HttpRequest, pk: int, attachment_pk: int
) -> HttpResponse:
    """Delete a private trade attachment."""
    attachment = get_object_or_404(
        TradeAttachment.objects.select_related("trade__profile"),
        pk=attachment_pk,
        trade__pk=pk,
        trade__profile__owner=request.user,
    )
    delete_trade_attachment(attachment)
    return HttpResponse(status=204)
