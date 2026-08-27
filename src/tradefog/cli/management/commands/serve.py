"""Run tradefog with its standalone ASGI server."""

from collections.abc import Callable
from typing import cast, override

import uvicorn
from django_typer.management import TyperCommand

from tradefog.config import Settings


def run_uvicorn(options: dict[str, object]) -> None:
    """Run the configured ASGI application with Uvicorn."""
    runner = cast(Callable[..., None], uvicorn.run)
    runner(
        "tradefog.asgi:application",
        **options,
    )


class Command(TyperCommand):
    """Run tradefog using Uvicorn."""

    @override
    def handle(
        self,
        host: str | None = None,
        port: int | None = None,
        reload: bool | None = None,
    ) -> None:
        """Start Uvicorn without changing application state."""
        options = Settings().uvicorn.options()
        if host is not None:
            options["host"] = host
        if port is not None:
            options["port"] = port
        if reload is not None:
            options["reload"] = reload
        run_uvicorn(options)
