"""Tests for language selection and translation catalogs."""

from django.test import Client, override_settings
from django.urls import reverse
from django.utils.translation import gettext, override

from tradefog.settings import LANGUAGES


def test_application_supports_english_and_russian() -> None:
    assert [code for code, _name in LANGUAGES] == ["en", "ru"]


def test_urls_include_the_active_language() -> None:
    with override("en"):
        assert reverse("home") == "/en/"
        assert reverse("login") == "/en/login/"
        assert reverse("logout") == "/en/logout/"
        assert reverse("set_language") == "/en/set-language/"
        assert reverse("admin:index") == "/en/admin/"
        assert reverse("javascript-catalog") == "/en/jsi18n/"

    with override("ru"):
        assert reverse("home") == "/ru/"
        assert reverse("login") == "/ru/login/"
        assert reverse("logout") == "/ru/logout/"
        assert reverse("set_language") == "/ru/set-language/"
        assert reverse("admin:index") == "/ru/admin/"
        assert reverse("javascript-catalog") == "/ru/jsi18n/"


@override_settings(ALLOWED_HOSTS=["testserver"])
def test_unprefixed_url_redirects_to_preferred_language() -> None:
    response = Client().get(
        "/admin/",
        headers={"accept-language": "ru"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/ru/admin/"


def test_russian_catalog_translates_application_strings() -> None:
    with override("ru"):
        assert gettext("English") == "Английский"
        assert gettext("Russian") == "Русский"


@override_settings(ALLOWED_HOSTS=["testserver"])
def test_language_switch_translates_the_current_url_prefix() -> None:
    english_response = Client().post(
        "/en/set-language/",
        {"next": "/en/login/", "language": "ru"},
    )
    russian_response = Client().post(
        "/ru/set-language/",
        {"next": "/ru/login/", "language": "en"},
    )

    assert english_response.status_code == 302
    assert english_response.headers["Location"] == "/ru/login/"
    assert russian_response.status_code == 302
    assert russian_response.headers["Location"] == "/en/login/"


@override_settings(ALLOWED_HOSTS=["testserver"])
def test_localized_javascript_catalog_uses_url_language() -> None:
    response = Client().get("/ru/jsi18n/")

    assert response.status_code == 200
    assert response.headers["Content-Language"] == "ru"
