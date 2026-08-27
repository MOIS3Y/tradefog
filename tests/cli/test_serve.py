"""Tests for the standalone server management command."""

from pathlib import Path

from django.core.management import call_command
from pytest import MonkeyPatch

from tradefog.cli.management.commands import serve
from tradefog.config.base import CONFIG_PATH_ENV


def test_serve_starts_uvicorn_with_cli_values(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    uvicorn_arguments: dict[str, object] = {}
    config_path = tmp_path / "settings.toml"
    _ = config_path.write_text(
        """[uvicorn]
workers = 3
timeout_keep_alive = 15
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config_path))

    def run_uvicorn(options: dict[str, object]) -> None:
        uvicorn_arguments.update(options)

    monkeypatch.setattr(serve, "run_uvicorn", run_uvicorn)

    _ = call_command(
        "serve",
        host="0.0.0.0",
        port=9000,
        reload=True,
    )

    assert uvicorn_arguments == {
        "host": "0.0.0.0",
        "log_config": None,
        "port": 9000,
        "reload": True,
        "timeout_keep_alive": 15,
        "workers": 3,
    }
