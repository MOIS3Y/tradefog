"""Command-line interface for Tradefog."""

import json
from typing import Annotated

import typer
import uvicorn
from rich.console import Console

from tradefog import __version__
from tradefog.config import get_settings

app = typer.Typer(
    name="tradefog",
    help="Tradefog: A self-hosted journal for deliberate trading under uncertainty.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def serve(
    host: Annotated[
        str | None,
        typer.Option("--host", "-h", help="Host IP to bind server to"),
    ] = None,
    port: Annotated[
        int | None,
        typer.Option("--port", "-p", help="Port to bind server to"),
    ] = None,
    reload: Annotated[
        bool | None,
        typer.Option("--reload", help="Enable auto-reload for development"),
    ] = None,
    workers: Annotated[
        int | None,
        typer.Option("--workers", "-w", help="Number of worker processes"),
    ] = None,
) -> None:
    """Start the Tradefog FastAPI application server with Uvicorn."""
    settings = get_settings()

    target_host = host or settings.uvicorn.host
    target_port = port or settings.uvicorn.port
    target_reload = reload if reload is not None else settings.uvicorn.reload
    target_workers = workers or settings.uvicorn.workers

    console.print(
        f"[bold blue]Starting {settings.application.app_name} v{__version__}[/bold blue]"
    )
    console.print(
        f"Serving on [green]http://{target_host}:{target_port}[/green] "
        + f"(reload={'on' if target_reload else 'off'})"
    )

    uvicorn.run(
        "tradefog.main:app",
        host=target_host,
        port=target_port,
        reload=target_reload,
        workers=target_workers if not target_reload else 1,
    )


@app.command()
def config() -> None:
    """Display active runtime configuration."""
    settings = get_settings()
    dumped = settings.model_dump(mode="json")
    console.print_json(json.dumps(dumped))


@app.command()
def version() -> None:
    """Display Tradefog version information."""
    settings = get_settings()
    console.print(
        f"[bold]{settings.application.app_name}[/bold] version [green]{__version__}[/green]"
    )


def main() -> None:
    """CLI execution entrypoint."""
    app()


if __name__ == "__main__":
    main()
