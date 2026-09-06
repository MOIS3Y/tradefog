"""Tests for shared frontend resources."""

from pathlib import Path

from django.template.loader import get_template
from django.utils.translation import override

from tradefog.assets.build import ASSET_ROOT, build_icon_sprite
from tradefog.config import Settings


def test_shared_template_and_static_directories_are_configured() -> None:
    settings = Settings()

    template_dirs = settings.templates.django_templates()[0]["DIRS"]
    with override("en"):
        rendered_template = get_template("tradefog/base.html").render()
        trade_template = get_template("tradefog/trades/workspace.html").render(
            {"is_new": True}
        )
        analytics_template = get_template("tradefog/analytics.html").render()

    assert '<html lang="en">' in rendered_template
    assert "tradefog/vendor/htmx/htmx.min.js" in rendered_template
    assert "tradefog/vendor/tabler/tabler.min.css" in rendered_template
    assert "tradefog/vendor/tabler/tabler.min.js" in rendered_template
    assert "tradefog/js/tradefog.js" in rendered_template
    assert "tradefog/js/htmx-config.js" in rendered_template
    assert "tradefog/js/toasts.js" in rendered_template
    assert "tradefog/js/modals.js" in rendered_template
    assert "tradefog/images/favicon.svg" in rendered_template
    assert "data-theme-toggle" in rendered_template
    assert "navbar-brand-autodark" in rendered_template
    assert "venue_overview" not in rendered_template

    assert "tradefog/vendor/apexcharts/apexcharts.min.js" in trade_template
    assert "tradefog/js/market-context.js" in trade_template
    assert "tradefog/js/trade-description.js" in trade_template
    assert "tradefog/vendor/easymde/easymde.min.css" in trade_template
    assert "data-analytics-chart" in analytics_template
    assert "tradefog/js/analytics.js" in analytics_template
    assert "tradefog/vendor/apexcharts/apexcharts.min.js" in analytics_template

    template_root = settings.static.source_dirs()[0].parent / "templates"
    market_context_source = (
        template_root / "tradefog/trades/partials/market_context.html"
    ).read_text(encoding="utf-8")
    assert "data-market-candle-chart" in market_context_source
    login_source = (template_root / "registration/login.html").read_text(
        encoding="utf-8"
    )
    assert "Login to your account" in login_source
    assert "brand-oauth" in login_source
    assert "data-password-toggle" in login_source
    assert 'aria-disabled="true"' in login_source
    assert "Remember me on this device" in login_source
    assert 'aria-describedby="username-help' not in login_source
    assert 'aria-describedby="password-help' not in login_source

    page_heading_template = (
        template_root / "tradefog/components/page_heading.html"
    ).read_text(encoding="utf-8")
    assert 'data-bs-toggle="tooltip"' in page_heading_template
    assert 'class="page-title mb-0 tf-page-heading"' in page_heading_template
    assert 'name="help-circle"' not in page_heading_template

    for section_template in (
        "home.html",
        "profiles/overview.html",
        "trades/overview.html",
        "analytics.html",
    ):
        section_source = (
            template_root / "tradefog" / section_template
        ).read_text(encoding="utf-8")
        assert "components/page_heading.html" in section_source
        assert "{% block page_header %}" in section_source

    catalog_source = (
        template_root / "tradefog/catalog/asset_overview.html"
    ).read_text(encoding="utf-8")
    assert "components/page_heading.html" in catalog_source
    assert "{% block page_header %}" in catalog_source
    assert "catalog/partials/asset_filters.html" in catalog_source
    assert "catalog/partials/asset_results.html" in catalog_source

    trade_source = (
        template_root / "tradefog/trades/workspace.html"
    ).read_text(encoding="utf-8")
    assert "{% block page_header %}" in trade_source

    for action_template in (
        "profiles/overview.html",
        "trades/overview.html",
    ):
        action_source = (
            template_root / "tradefog" / action_template
        ).read_text(encoding="utf-8")
        assert "btn-animate-icon-rotate" in action_source
        assert 'name="plus"' in action_source

    for empty_template in (
        "home.html",
        "profiles/partials/profile_cards.html",
        "trades/overview.html",
    ):
        empty_source = (template_root / "tradefog" / empty_template).read_text(
            encoding="utf-8"
        )
        assert "empty-bordered" in empty_source
        assert "empty-icon" in empty_source
        assert "empty-subtitle" in empty_source

    template_source = (template_root / "tradefog/base.html").read_text(
        encoding="utf-8"
    )
    for url_name in (
        "home",
        "profile_overview",
        "trades",
        "analytics",
        "asset_overview",
    ):
        assert f"{{% url 'journal:{url_name}' %}}" in template_source
    assert "Catalog" in template_source
    assert "Trading pairs" in template_source
    assert "Venues" in template_source
    assert 'name="user-cog" class="icon"' in template_source
    assert "Account settings" in template_source
    assert "Coming soon" in template_source
    assert "tf-auth-shell" in template_source
    assert "container container-tight py-4" in template_source
    assert "data-scroll-top" in template_source
    assert 'id="toast-region"' in template_source
    assert 'id="toast-template"' in template_source
    assert "components/toast.html" in template_source
    toast_source = (
        template_root / "tradefog/components/toast.html"
    ).read_text(encoding="utf-8")
    assert "toast-header" in toast_source
    assert "status-dot" in toast_source
    assert "data-toast-body" in toast_source
    assert '<span class="dropdown-item disabled"' in template_source
    assert 'aria-disabled="true"' in template_source
    assert 'data-bs-target="#navbar-menu"' in template_source
    assert "navbar-vertical" not in template_source
    assert "data-sidebar-dropdown" not in template_source
    assert "tf-navbar-control" not in template_source
    assert 'data-theme-choice="system"' not in template_source
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
