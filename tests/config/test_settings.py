"""Tests for runtime configuration loading."""

from pathlib import Path

from pydantic import ValidationError
from pytest import MonkeyPatch, raises

from tradefog.config import Settings
from tradefog.config.base import CONFIG_PATH_ENV, config_file_path


def test_config_path_defaults_to_xdg_directory(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(CONFIG_PATH_ENV, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert config_file_path() == tmp_path / "tradefog/settings.toml"


def test_explicit_config_path_overrides_xdg_directory(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "custom.toml"
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert config_file_path() == config_path


def test_nested_environment_values_override_toml(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "settings.toml"
    _ = config_path.write_text(
        """[application]
debug = false
allowed_hosts = ["file.example"]

[localization]
time_zone = "Europe/Berlin"

[logging]
level = "warning"

[database]
active = "psql"

[database.psql]
name = "journal"
user = "journal_user"
password = "file-secret"
host = "database.example"
port = 5433
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config_path))
    monkeypatch.setenv("TRADEFOG_APPLICATION__DEBUG", "true")
    monkeypatch.setenv(
        "TRADEFOG_APPLICATION__ALLOWED_HOSTS",
        '["env.example"]',
    )
    monkeypatch.setenv(
        "TRADEFOG_DATABASE__PSQL__PASSWORD",
        "env-secret",
    )
    monkeypatch.setenv("TRADEFOG_LOGGING__LEVEL", "debug")

    config = Settings()

    assert config.application.debug is True
    assert config.application.allowed_hosts == ["env.example"]
    assert config.localization.time_zone == "Europe/Berlin"
    assert config.logging.level == "DEBUG"
    assert config.database.active == "psql"
    assert config.database.psql.name == "journal"
    assert config.database.psql.password.get_secret_value() == "env-secret"


def test_sqlite_is_the_default_database(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV, str(tmp_path / "missing.toml"))
    monkeypatch.setenv("TRADEFOG_DATABASE__ACTIVE", "sqlite")

    database = Settings().database.django_databases()["default"]

    assert database["ENGINE"] == "django.db.backends.sqlite3"


def test_postgresql_config_is_translated_for_django(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "settings.toml"
    _ = config_path.write_text(
        """[database]
active = "psql"

[database.psql]
name = "journal"
user = "journal_user"
password = "secret"
host = "localhost"
port = 5432
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config_path))

    database = Settings().database.django_databases()["default"]

    assert database == {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "journal",
        "USER": "journal_user",
        "PASSWORD": "secret",
        "HOST": "localhost",
        "PORT": 5432,
    }


def test_model_defaults_are_used_without_config_file(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(CONFIG_PATH_ENV, str(tmp_path / "missing.toml"))
    monkeypatch.delenv("TRADEFOG_APPLICATION__DEBUG", raising=False)
    monkeypatch.delenv(
        "TRADEFOG_APPLICATION__ALLOWED_HOSTS",
        raising=False,
    )

    config = Settings()

    assert config.application.debug is False
    assert config.application.allowed_hosts == []
    assert config.localization.language_code() == "en"
    assert config.localization.time_zone == "UTC"
    assert config.localization.use_i18n() is True
    assert config.localization.use_tz() is True
    assert config.logging.level == "INFO"
    assert config.database.active == "sqlite"
    assert config.media.url == "/media/"
    assert config.media.max_attachment_size_mib == 10
    assert config.media.max_attachment_size_bytes() == 10 * 1024 * 1024
    assert config.authentication.user_model() == "accounts.User"
    assert config.authentication.login_url() == "login"
    assert config.authentication.login_redirect_url() == "home"
    assert config.authentication.logout_redirect_url() == "login"


def test_structural_localization_setting_is_rejected(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "settings.toml"
    _ = config_path.write_text(
        """[localization]
language_code = "de"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config_path))

    with raises(ValidationError, match="Extra inputs are not permitted"):
        _ = Settings()


def test_unknown_logging_level_is_rejected(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "settings.toml"
    _ = config_path.write_text(
        """[logging]
level = "verbose"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config_path))

    with raises(ValidationError, match="level"):
        _ = Settings()


def test_relative_paths_are_resolved_from_config_file(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "config/tradefog"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "settings.toml"
    _ = config_path.write_text(
        """[database.sqlite]
path = "../../data/tradefog/db.sqlite3"

[static]
root = "../../cache/tradefog/static"

[media]
root = "../../data/tradefog/media"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config_path))

    config = Settings()

    assert config.database.sqlite.path == (
        tmp_path / "data/tradefog/db.sqlite3"
    )
    assert config.static.root == tmp_path / "cache/tradefog/static"
    assert config.media.root == tmp_path / "data/tradefog/media"


def test_media_attachment_limit_can_be_disabled(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A self-hosted deployment may rely on an external upload limit."""
    config_path = tmp_path / "settings.toml"
    _ = config_path.write_text(
        """[media]
max_attachment_size_mib = 0
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config_path))

    assert Settings().media.max_attachment_size_bytes() is None


def test_uvicorn_rejects_unknown_options(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "settings.toml"
    _ = config_path.write_text(
        """[uvicorn]
workres = 4
""",
        encoding="utf-8",
    )
    monkeypatch.setenv(CONFIG_PATH_ENV, str(config_path))

    with raises(ValidationError, match="Unknown Uvicorn option.*workres"):
        _ = Settings()
