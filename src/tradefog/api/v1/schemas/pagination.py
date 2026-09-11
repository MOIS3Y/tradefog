"""Bounded, consistently ordered collection requests and responses."""

from typing import Literal

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    """One page and the count after applying all collection filters."""

    items: list[T]
    total: int = Field(
        description="Matching items across all pages, after filtering.",
        examples=[1],
    )
    page: int = Field(examples=[1])
    page_size: int = Field(examples=[25])


class ListQuery(BaseModel):
    """Shared controls for profile collections and option searches."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    q: str = Field(default="", max_length=200)
    sort: str | None = None
    order: Literal["asc", "desc"] = "asc"
    visibility: Literal["all", "active", "archived"] = "all"
