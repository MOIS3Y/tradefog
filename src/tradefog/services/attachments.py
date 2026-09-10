"""Private attachment storage helpers independent of HTTP transport."""

from pathlib import Path
from typing import Protocol
from uuid import uuid4

import aiofiles


class UploadSource(Protocol):
    """Minimal asynchronous upload interface required by storage."""

    filename: str | None

    async def read(self, size: int = -1) -> bytes:
        """Read at most size bytes from the upload."""
        ...


class AttachmentStorageError(ValueError):
    """Describe a user-correctable attachment storage failure."""

    def __init__(self, code: str, message: str) -> None:
        """Retain a stable API-facing error code and explanation."""
        super().__init__(message)
        self.code = code
        self.message = message


CHUNK_SIZE = 1024 * 1024
IMAGE_SIGNATURES: tuple[tuple[str, str, bytes], ...] = (
    ("image/jpeg", ".jpg", b"\xff\xd8\xff"),
    ("image/png", ".png", b"\x89PNG\r\n\x1a\n"),
    ("image/gif", ".gif", b"GIF87a"),
    ("image/gif", ".gif", b"GIF89a"),
)


def image_format(header: bytes) -> tuple[str, str] | None:
    """Identify one supported image format from trusted file bytes."""
    for content_type, extension, signature in IMAGE_SIGNATURES:
        if header.startswith(signature):
            return content_type, extension
    if (
        len(header) >= 12
        and header.startswith(b"RIFF")
        and header[8:12] == b"WEBP"
    ):
        return "image/webp", ".webp"
    return None


def sanitized_filename(filename: str | None, extension: str) -> str:
    """Return a path-free display filename within the database limit."""
    supplied = (filename or "attachment").replace("\\", "/")
    name = supplied.rsplit("/", maxsplit=1)[-1].replace("\x00", "").strip()
    stem = name.rsplit(".", maxsplit=1)[0].strip(". ")
    name = f"{stem or 'attachment'}{extension}"
    if len(name) > 255:
        name = f"{name[: 255 - len(extension)]}{extension}"
    return name


def attachment_path(media_root: Path, storage_key: str) -> Path:
    """Resolve a generated storage key below the configured media root."""
    root = media_root.resolve()
    candidate = (root / storage_key).resolve()
    if not candidate.is_relative_to(root):
        raise AttachmentStorageError(
            "invalid_storage_key",
            "Attachment storage key is invalid",
        )
    return candidate


async def store_upload(
    upload: UploadSource,
    media_root: Path,
    owner_id: int,
    trade_id: int,
    maximum_size: int | None,
) -> tuple[str, str, str, int]:
    """Stream, verify and atomically place one private image attachment."""
    identifier = uuid4().hex
    temporary_key = f"{owner_id}/{trade_id}/.{identifier}.upload"
    temporary_path = attachment_path(media_root, temporary_key)
    temporary_path.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    header = b""
    try:
        async with aiofiles.open(temporary_path, "xb") as output:
            while chunk := await upload.read(CHUNK_SIZE):
                size += len(chunk)
                if maximum_size is not None and size > maximum_size:
                    raise AttachmentStorageError(
                        "attachment_too_large",
                        "Attachment exceeds the configured size limit",
                    )
                if len(header) < 16:
                    header = (header + chunk)[:16]
                await output.write(chunk)
        temporary_path.chmod(0o600)
        detected = image_format(header)
        if size == 0 or detected is None:
            raise AttachmentStorageError(
                "unsupported_attachment",
                "Only JPEG, PNG, GIF and WebP images are supported",
            )
        content_type, extension = detected
        storage_key = f"{owner_id}/{trade_id}/{identifier}{extension}"
        final_path = attachment_path(media_root, storage_key)
        temporary_path.replace(final_path)
        return (
            storage_key,
            sanitized_filename(upload.filename, extension),
            content_type,
            size,
        )
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
