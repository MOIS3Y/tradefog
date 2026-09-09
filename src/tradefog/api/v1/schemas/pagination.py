"""Bounded, consistently ordered collection requests and responses."""

from typing import Literal

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    """One page and the count after applying all collection filters."""

    items: list[T]
    total: int
    page: int
    page_size: int


class ListQuery(BaseModel):
    """Shared controls for catalog lists and remote option searches."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    q: str = Field(default="", max_length=200)
    sort: str | None = None
    order: Literal["asc", "desc"] = "asc"
    visibility: Literal["all", "active", "archived"] = "all"
    asset_type: Literal["crypto", "fiat", "equity"] | None = None
    exclude_venue_id: int | None = Field(default=None, gt=0)
    exclude_ids: list[int] = Field(default_factory=list, max_length=1000)
    venue_id: int | None = Field(default=None, gt=0)
    pair_id: int | None = Field(default=None, gt=0)
    product: Literal["spot", "perpetual_future", "cash_equity"] | None = None
