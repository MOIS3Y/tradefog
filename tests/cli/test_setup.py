"""Tests for the application setup management command."""

from django.core.management import CommandError, call_command
from pytest import MonkeyPatch, raises

from tradefog.cli.management.commands import setup


def test_setup_requires_an_explicit_action() -> None:
    with raises(CommandError, match="Select at least one action"):
        _ = call_command("setup")


def test_setup_runs_selected_actions_in_order(
    monkeypatch: MonkeyPatch,
) -> None:
    actions: list[str] = []

    def run_migrations() -> None:
        actions.append("migrate")

    def collect_static_files() -> None:
        actions.append("collect_static")

    monkeypatch.setattr(setup, "run_migrations", run_migrations)
    monkeypatch.setattr(setup, "collect_static_files", collect_static_files)

    _ = call_command(
        "setup",
        migrate=True,
        collect_static=True,
    )

    assert actions == ["migrate", "collect_static"]
