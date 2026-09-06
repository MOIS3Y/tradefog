"""Shared helpers for the staff-managed reference catalog views.

Each catalog domain module keeps its own constants and list-state builder but
reuses the sort-link and pagination helpers here so behavior stays consistent
across the assets, trading pairs, and (future) venues pages.
"""

from __future__ import annotations

from typing import Any

from django.core.paginator import Page, Paginator
from django.db.models import Model, QuerySet
from django.http import HttpRequest

type SortColumn = tuple[str, str]
"""A sortable column as a ``(key, label)`` pair."""


def build_results_context[ModelT: Model](
    request: HttpRequest,
    *,
    queryset: QuerySet[ModelT],
    page_size: int,
    current_sort: str,
    columns: tuple[SortColumn, ...],
    filters_active: bool,
    can_manage: bool,
    results_key: str,
    swap_oob: bool = False,
    sort_parameter: str = "sort",
    page_parameter: str = "page",
) -> dict[str, Any]:
    """Build the shared results-wrapper context for a catalog list.

    The domain object list is stored under ``results_key`` on the returned
    mapping. Several collections on one page pass distinct ``sort_parameter``
    and ``page_parameter`` values so they do not reset one another.
    """
    page_obj = Paginator(queryset, page_size).get_page(
        request.GET.get(page_parameter)
    )
    return {
        "page_obj": page_obj,
        results_key: page_obj.object_list,
        "pagination": _pagination_urls(
            request, page_obj, page_parameter=page_parameter
        ),
        "sort_headers": _sort_headers(
            request,
            current_sort,
            columns,
            sort_parameter=sort_parameter,
            page_parameter=page_parameter,
        ),
        "filters_active": filters_active,
        "can_manage": can_manage,
        "swap_oob": swap_oob,
    }


def _sort_headers(
    request: HttpRequest,
    current_sort: str,
    columns: tuple[SortColumn, ...],
    *,
    sort_parameter: str = "sort",
    page_parameter: str = "page",
) -> tuple[dict[str, str | bool], ...]:
    """Build safe sort links while preserving the active filter query."""
    headers: list[dict[str, str | bool]] = []
    for key, label in columns:
        active = current_sort.lstrip("-") == key
        descending = current_sort == f"-{key}"
        next_sort = key if descending or not active else f"-{key}"
        query = request.GET.copy()
        query[sort_parameter] = next_sort
        _removed_page = query.pop(page_parameter, None)
        headers.append(
            {
                "key": key,
                "label": label,
                "url": f"?{query.urlencode()}",
                "active": active,
                "descending": descending,
            }
        )
    return tuple(headers)


def _pagination_urls(
    request: HttpRequest,
    page_obj: Page,
    page_parameter: str = "page",
) -> dict[str, str | None]:
    """Preserve all list state while changing one page parameter."""
    previous_url = None
    next_url = None
    if page_obj.has_previous():
        previous_query = request.GET.copy()
        previous_query[page_parameter] = str(page_obj.previous_page_number())
        previous_url = f"?{previous_query.urlencode()}"
    if page_obj.has_next():
        next_query = request.GET.copy()
        next_query[page_parameter] = str(page_obj.next_page_number())
        next_url = f"?{next_query.urlencode()}"
    return {"previous_url": previous_url, "next_url": next_url}
