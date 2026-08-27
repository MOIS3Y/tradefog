"""Prepare persistent and generated application resources."""

from typing import override

from django.core.management import CommandError, call_command
from django_typer.management import TyperCommand


def run_migrations() -> None:
    """Apply pending database migrations without interactive prompts."""
    _ = call_command(
        "migrate",
        interactive=False,
    )


def collect_static_files() -> None:
    """Collect static assets without interactive prompts."""
    _ = call_command(
        "collectstatic",
        interactive=False,
    )


class Command(TyperCommand):
    """Prepare explicitly selected application resources."""

    @override
    def handle(
        self,
        migrate: bool = False,
        collect_static: bool = False,
    ) -> None:
        """Run the selected setup actions in a deterministic order."""
        if not migrate and not collect_static:
            raise CommandError(
                "Select at least one action: --migrate or --collect-static."
            )

        if migrate:
            run_migrations()
        if collect_static:
            collect_static_files()
