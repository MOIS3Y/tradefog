"""Validation and persistence for private trade attachments."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from io import BufferedIOBase
from pathlib import PurePosixPath
from typing import cast

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from tradefog.journal.models import Trade, TradeAttachment

ALLOWED_ATTACHMENT_TYPES = {
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".webp": "image/webp",
}


@dataclass(frozen=True, slots=True)
class ValidatedAttachment:
    """Canonical metadata derived from one accepted upload."""

    original_name: str
    content_type: str
    size: int


def _safe_original_name(name: str) -> str:
    """Strip submitted path components and bound the stored display name."""
    normalized = name.replace("\\", "/").replace("\x00", "")
    basename = PurePosixPath(normalized).name.strip()
    if not basename:
        return "attachment"
    if len(basename) <= 255:
        return basename
    suffix = PurePosixPath(basename).suffix
    return f"{basename[: 255 - len(suffix)]}{suffix}"


def _matches_signature(content_type: str, header: bytes) -> bool:
    """Recognize the small fixed allowlist without trusting browser MIME."""
    if content_type == "image/png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return header.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if content_type == "application/pdf":
        return header.startswith(b"%PDF-")
    return False


def validate_attachment(upload: UploadedFile) -> ValidatedAttachment:
    """Validate size, suffix, and file signature for a private upload."""
    original_name = _safe_original_name(upload.name or "attachment")
    suffix = PurePosixPath(original_name).suffix.lower()
    content_type = ALLOWED_ATTACHMENT_TYPES.get(suffix)
    if content_type is None:
        raise ValidationError(
            _("Upload a PNG, JPEG, WebP, or PDF file."),
            code="unsupported_attachment_type",
        )
    size = upload.size or 0
    max_size = cast(int | None, settings.TRADEFOG_MAX_ATTACHMENT_SIZE)
    if max_size is not None and size > max_size:
        raise ValidationError(
            _("The file exceeds the configured attachment size limit."),
            code="attachment_too_large",
        )
    stream = cast(BufferedIOBase, cast(object, upload.file))
    header = stream.read(12)
    _position = stream.seek(0)
    if not _matches_signature(content_type, header):
        raise ValidationError(
            _("The file content does not match its extension."),
            code="invalid_attachment_content",
        )
    return ValidatedAttachment(
        original_name=original_name,
        content_type=content_type,
        size=size,
    )


def create_trade_attachment(
    trade: Trade,
    upload: UploadedFile,
) -> TradeAttachment:
    """Validate and persist one file under an opaque private-media name."""
    metadata = validate_attachment(upload)
    attachment = TradeAttachment(
        trade=trade,
        file=upload,
        original_name=metadata.original_name,
        content_type=metadata.content_type,
        size=metadata.size,
    )
    attachment.full_clean()
    try:
        attachment.save()
    except Exception:
        if attachment.file.name:
            attachment.file.storage.delete(attachment.file.name)
        raise
    return attachment


@transaction.atomic
def delete_trade_attachment(attachment: TradeAttachment) -> None:
    """Delete attachment metadata and remove its file after commit."""
    storage = attachment.file.storage
    name = attachment.file.name
    _deleted = attachment.delete()
    if name:
        transaction.on_commit(partial(storage.delete, name))
