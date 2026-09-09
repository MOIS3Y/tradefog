"""SQL pagination with stable ordering and literal substring search."""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Select, String, cast, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from tradefog.api.errors import api_error
from tradefog.api.v1.schemas.pagination import ListQuery

type SQLColumn[T] = ColumnElement[T] | InstrumentedAttribute[T]


def search_text(columns: Sequence[SQLColumn[Any]]) -> ColumnElement[str]:
    """Join nullable text fields without discarding the remaining values."""
    result = func.coalesce(cast(columns[0], String), "")
    for column in columns[1:]:
        result = result + " " + func.coalesce(cast(column, String), "")
    return result


async def paginate[T](
    session: AsyncSession,
    statement: Select[tuple[T]],
    query: ListQuery,
    columns: Mapping[str, SQLColumn[Any]],
    default_sort: str,
    identifier: SQLColumn[int],
) -> tuple[list[T], int]:
    """Count filtered rows and fetch a bounded page with null values last."""
    key = query.sort or default_sort
    if key not in columns:
        api_error(422, "invalid_sort", "Unsupported sort column")
    column = columns[key]
    order = column.desc() if query.order == "desc" else column.asc()
    total = await session.scalar(
        select_count(statement),
    )
    rows = await session.scalars(
        statement.order_by(None)
        .order_by(order.nulls_last(), identifier)
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    return list(rows.all()), int(total or 0)


def select_count[T](statement: Select[tuple[T]]) -> Select[tuple[int]]:
    """Count a filtered query without loading entities or relationships."""
    from sqlalchemy import select

    return select(func.count()).select_from(
        statement.order_by(None).subquery()
    )
