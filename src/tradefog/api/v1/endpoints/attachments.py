"""Authenticated upload and serving of private trade images."""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Request, Response, UploadFile, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from tradefog.api.dependencies import CurrentUserDependency, SessionDependency
from tradefog.api.errors import api_error, not_found
from tradefog.api.v1.schemas.attachments import AttachmentResponse
from tradefog.config import Settings
from tradefog.db.models import Attachment, Trade
from tradefog.db.scoping import owned_select
from tradefog.services.attachments import (
    AttachmentStorageError,
    attachment_path,
    store_upload,
)
from tradefog.services.journal import get_owned

router = APIRouter(tags=["Attachments"])


def attachment_response(item: Attachment) -> AttachmentResponse:
    """Serialize metadata with its authenticated content endpoint."""
    return AttachmentResponse(
        id=item.id,
        trade_id=item.trade_id,
        original_name=item.original_name,
        content_type=item.content_type,
        size_bytes=item.size_bytes,
        created_at=item.created_at,
        content_url=f"/api/v1/attachments/{item.id}/content",
    )


def media_root(request: Request) -> Path:
    """Return the configured private storage root for this application."""
    settings: Settings = request.app.state.settings
    return settings.media.root


@router.get(
    "/trades/{trade_id}/attachments",
    response_model=list[AttachmentResponse],
)
async def list_attachments(
    trade_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> list[AttachmentResponse]:
    """List private image metadata belonging to one owned trade."""
    await get_owned(session, Trade, trade_id, user.id)
    items: Sequence[Attachment] = (
        await session.scalars(
            owned_select(Attachment, user.id)
            .where(Attachment.trade_id == trade_id)
            .order_by(Attachment.created_at, Attachment.id)
        )
    ).all()
    return [attachment_response(item) for item in items]


@router.post(
    "/trades/{trade_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    trade_id: int,
    request: Request,
    session: SessionDependency,
    user: CurrentUserDependency,
    upload: Annotated[UploadFile, File()],
) -> AttachmentResponse:
    """Store one verified private image for an owned trade."""
    await get_owned(session, Trade, trade_id, user.id)
    settings: Settings = request.app.state.settings
    try:
        storage_key, name, content_type, size = await store_upload(
            upload,
            settings.media.root,
            user.id,
            trade_id,
            settings.media.max_attachment_size_bytes(),
        )
    except AttachmentStorageError as error:
        status_code = 413 if error.code == "attachment_too_large" else 422
        api_error(status_code, error.code, error.message)
    item = Attachment(
        trade_id=trade_id,
        storage_key=storage_key,
        original_name=name,
        content_type=content_type,
        size_bytes=size,
    )
    session.add(item)
    try:
        await session.flush()
    except BaseException:
        path = attachment_path(settings.media.root, storage_key)
        await run_in_threadpool(path.unlink, missing_ok=True)
        raise
    return attachment_response(item)


@router.get("/attachments/{attachment_id}/content")
async def serve_attachment(
    attachment_id: int,
    request: Request,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> FileResponse:
    """Serve private content only after resolving owner-scoped metadata."""
    item = await get_owned(session, Attachment, attachment_id, user.id)
    try:
        path = attachment_path(media_root(request), item.storage_key)
    except AttachmentStorageError:
        not_found("Attachment content")
    if not path.is_file():
        not_found("Attachment content")
    return FileResponse(
        path,
        media_type=item.content_type,
        filename=item.original_name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_attachment(
    attachment_id: int,
    request: Request,
    session: SessionDependency,
    user: CurrentUserDependency,
) -> Response:
    """Delete owned attachment metadata and its private file."""
    item = await get_owned(
        session,
        Attachment,
        attachment_id,
        user.id,
        for_update=True,
    )
    try:
        path = attachment_path(media_root(request), item.storage_key)
    except AttachmentStorageError:
        not_found("Attachment content")
    await session.delete(item)
    await session.flush()
    await run_in_threadpool(path.unlink, missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
