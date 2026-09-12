"""Profile-wide virtual ledger browsing, independent of wallet selection."""

from datetime import UTC, date, datetime, time
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Query
from pydantic import Field, model_validator
from sqlalchemy import select

from tradefog.api.dependencies import CurrentUserDependency, SessionDependency
from tradefog.api.v1.schemas.journal import WalletOperationResponse
from tradefog.api.v1.schemas.pagination import ListQuery, Page
from tradefog.db.models import TradingAsset, TradingProfile, WalletOperation
from tradefog.domain.enums import WalletOperationKind
from tradefog.services.journal import get_owned
from tradefog.services.pagination import paginate

router = APIRouter(prefix="/profiles", tags=["Profiles · Operations"])


class OperationListQuery(ListQuery):
    """Filter ledger facts before pagination; dates refer to UTC days."""

    asset_id: int | None = Field(default=None, gt=0)
    kind: WalletOperationKind | None = None
    date_from: date | None = None
    date_to: date | None = None
    sort: str | None = "created_at"
    order: Literal["asc", "desc"] = "desc"

    @model_validator(mode="after")
    def ordered_dates(self) -> Self:
        """Reject inverted ranges instead of returning misleading emptiness."""
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not exceed date_to")
        return self


class ProfileOperationResponse(WalletOperationResponse):
    """Include the denomination without relying on the current asset page."""

    asset_symbol: str


@router.get(
    "/{profile_id}/operations",
    response_model=Page[ProfileOperationResponse],
)
async def list_profile_operations(
    profile_id: int,
    session: SessionDependency,
    user: CurrentUserDependency,
    query: Annotated[OperationListQuery, Query()],
) -> Page[ProfileOperationResponse]:
    """Read all denominations of one owned profile, including archived ones."""
    await get_owned(session, TradingProfile, profile_id, user.id)
    statement = (
        select(WalletOperation)
        .join(TradingAsset, WalletOperation.asset_id == TradingAsset.id)
        .where(TradingAsset.profile_id == profile_id)
    )
    if query.asset_id is not None:
        statement = statement.where(WalletOperation.asset_id == query.asset_id)
    if query.kind is not None:
        statement = statement.where(WalletOperation.kind == query.kind)
    if query.date_from:
        statement = statement.where(
            WalletOperation.created_at
            >= datetime.combine(query.date_from, time.min, UTC)
        )
    if query.date_to:
        statement = statement.where(
            WalletOperation.created_at
            <= datetime.combine(query.date_to, time.max, UTC)
        )
    items, total = await paginate(
        session,
        statement,
        query,
        {
            "created_at": WalletOperation.created_at,
            "kind": WalletOperation.kind,
        },
        "created_at",
        WalletOperation.id.desc()
        if query.order == "desc"
        else WalletOperation.id.asc(),
    )
    symbols = {
        asset_id: symbol
        for asset_id, symbol in (
            await session.execute(
                select(TradingAsset.id, TradingAsset.symbol).where(
                    TradingAsset.id.in_({item.asset_id for item in items})
                )
            )
        ).all()
    }
    return Page(
        items=[
            ProfileOperationResponse(
                **WalletOperationResponse.model_validate(item).model_dump(),
                asset_symbol=symbols[item.asset_id],
            )
            for item in items
        ],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )
