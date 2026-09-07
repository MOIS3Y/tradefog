"""Command-line interface for Tradefog."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import typer
import uvicorn
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from rich.console import Console
from rich.table import Table

from tradefog import __version__
from tradefog.api.security import hash_password
from tradefog.config import get_settings
from tradefog.db.models import User
from tradefog.db.session import Database
from tradefog.domain.accounts import normalize_username, validate_password

app = typer.Typer(
    name="tradefog",
    help="Tradefog: A self-hosted journal for deliberate trading under uncertainty.",
    no_args_is_help=True,
)
console = Console()
users_app = typer.Typer(help="Administrative user account management.")
app.add_typer(users_app, name="users")


@asynccontextmanager
async def cli_session() -> AsyncIterator[AsyncSession]:
    """Provide one committed CLI transaction and dispose its engine."""
    database = Database(get_settings().database)
    try:
        async with database.session() as session:
            yield session
    finally:
        await database.dispose()


def normalized_username(username: str) -> str:
    """Validate and normalize a CLI-provided login identifier."""
    try:
        return normalize_username(username)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def validated_password(password: str) -> str:
    """Apply the same password length policy as public registration."""
    try:
        return validate_password(password)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


async def create_user_record(
    username: str,
    password: str,
    *,
    is_staff: bool,
) -> User:
    """Create one account through an isolated CLI transaction."""
    async with cli_session() as session:
        user = User(
            username=username,
            password=hash_password(password),
            is_staff=is_staff,
        )
        session.add(user)
        try:
            await session.flush()
        except IntegrityError as error:
            raise typer.BadParameter("Username is already in use") from error
        return user


async def list_user_records() -> list[User]:
    """Load all accounts for administrative CLI display."""
    async with cli_session() as session:
        return list(
            (
                await session.scalars(
                    select(User).order_by(User.username, User.id)
                )
            ).all()
        )


async def update_user_flag(
    username: str,
    field: str,
    value: bool,
) -> User:
    """Update one approved administrative account flag."""
    if field not in {"is_active", "is_staff"}:
        raise ValueError(f"Unsupported user flag: {field}")
    async with cli_session() as session:
        user = await session.scalar(
            select(User)
            .where(User.username == username)
            .with_for_update()
        )
        if user is None:
            raise typer.BadParameter("User not found")
        if field == "is_active":
            user.is_active = value
        else:
            user.is_staff = value
        await session.flush()
        return user


async def update_user_password(username: str, password: str) -> User:
    """Replace one account password through an isolated transaction."""
    async with cli_session() as session:
        user = await session.scalar(
            select(User)
            .where(User.username == username)
            .with_for_update()
        )
        if user is None:
            raise typer.BadParameter("User not found")
        user.password = hash_password(password)
        await session.flush()
        return user


def change_user_flag(username: str, field: str, value: bool) -> None:
    """Run an administrative flag mutation and print its result."""
    normalized = normalized_username(username)
    user = asyncio.run(update_user_flag(normalized, field, value))
    console.print(
        f"Updated [bold]{user.username}[/bold]: "
        f"{field}=[green]{str(value).lower()}[/green]"
    )


@users_app.command("create")
def create_user(
    username: Annotated[str, typer.Argument(help="Unique login identifier")],
    password: Annotated[
        str,
        typer.Option(
            "--password",
            prompt=True,
            hide_input=True,
            confirmation_prompt=True,
        ),
    ],
    staff: Annotated[
        bool,
        typer.Option("--staff", help="Grant staff catalog access"),
    ] = False,
) -> None:
    """Create a regular or staff account without public registration."""
    user = asyncio.run(
        create_user_record(
            normalized_username(username),
            validated_password(password),
            is_staff=staff,
        )
    )
    role = "staff" if user.is_staff else "regular"
    console.print(
        f"Created [bold]{user.username}[/bold] as [green]{role}[/green]"
    )


@users_app.command("list")
def list_users() -> None:
    """List account identities and administrative flags."""
    table = Table("ID", "Username", "Staff", "Active")
    for user in asyncio.run(list_user_records()):
        table.add_row(
            str(user.id),
            user.username,
            str(user.is_staff).lower(),
            str(user.is_active).lower(),
        )
    console.print(table)


@users_app.command("activate")
def activate_user(username: str) -> None:
    """Enable an existing account."""
    change_user_flag(username, "is_active", True)


@users_app.command("deactivate")
def deactivate_user(username: str) -> None:
    """Disable an existing account and reject future authenticated calls."""
    change_user_flag(username, "is_active", False)


@users_app.command("promote")
def promote_user(username: str) -> None:
    """Grant staff catalog permissions to an existing account."""
    change_user_flag(username, "is_staff", True)


@users_app.command("demote")
def demote_user(username: str) -> None:
    """Remove staff catalog permissions from an existing account."""
    change_user_flag(username, "is_staff", False)


@users_app.command("password")
def change_user_password(
    username: Annotated[str, typer.Argument(help="Existing login identifier")],
    password: Annotated[
        str,
        typer.Option(
            "--password",
            prompt=True,
            hide_input=True,
            confirmation_prompt=True,
        ),
    ],
) -> None:
    """Set a new password for an existing account."""
    user = asyncio.run(
        update_user_password(
            normalized_username(username),
            validated_password(password),
        )
    )
    console.print(f"Updated password for [bold]{user.username}[/bold]")


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
