"""Tests for shared frontend resources."""

from pathlib import Path

from django.template.loader import get_template

from tradefog.assets.build import ASSET_ROOT, build_icon_sprite
from tradefog.config import Settings


def test_shared_template_and_static_directories_are_configured() -> None:
    settings = Settings()

    template_dirs = settings.templates.django_templates()[0]["DIRS"]
    rendered_template = get_template("tradefog/base.html").render()

    assert '<html lang="en">' in rendered_template
    assert "tradefog/vendor/htmx/htmx.min.js" in rendered_template
    assert "tradefog/vendor/tabler/tabler.min.css" in rendered_template
    assert "tradefog/vendor/tabler/tabler.min.js" in rendered_template
    assert "tradefog/js/tradefog.js" in rendered_template
    assert "tradefog/vendor/pico" not in rendered_template
    assert "cdn.jsdelivr.net" not in rendered_template
    assert "function selectTheme" not in rendered_template
    assert "tradefog/images/favicon.svg" in rendered_template
    assert "data-theme-toggle" in rendered_template
    assert "btn-animate-icon" in rendered_template
    assert "btn-animate-icon-move-start" in rendered_template
    assert "btn-animate-icon-rotate" not in rendered_template
    assert "tf-navbar-control" not in rendered_template
    assert 'data-theme-choice="system"' not in rendered_template
    assert settings.static.source_dirs()[0].is_dir()
    assert template_dirs == [
        settings.static.source_dirs()[0].parent / "templates"
    ]


def test_icon_sprite_contains_only_selected_icons(tmp_path: Path) -> None:
    output_path = build_icon_sprite(tmp_path)
    sprite = output_path.read_text(encoding="utf-8")
    expected_icons = sorted(
        path.stem for path in (ASSET_ROOT / "icons/tabler").glob("*.svg")
    )

    assert expected_icons
    for icon_name in expected_icons:
        assert f'id="tabler-{icon_name}"' in sprite
