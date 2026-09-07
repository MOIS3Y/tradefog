"""Consistent machine-readable HTTP errors for the REST API."""

from typing import Never

from fastapi import HTTPException, status


def api_error(
    status_code: int,
    code: str,
    message: str,
) -> Never:
    """Raise an API error with a stable code and a readable explanation."""
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"}
        if status_code == status.HTTP_401_UNAUTHORIZED
        else None,
    )


def not_found(resource: str) -> Never:
    """Raise the standard missing-resource response."""
    api_error(status.HTTP_404_NOT_FOUND, "not_found", f"{resource} not found")


def conflict(message: str) -> Never:
    """Raise the standard unique or state-conflict response."""
    api_error(status.HTTP_409_CONFLICT, "conflict", message)
