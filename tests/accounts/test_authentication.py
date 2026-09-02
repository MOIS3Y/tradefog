"""Tests for application authentication and access control."""

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark

from tradefog.accounts.models import User


def test_application_uses_custom_user_model() -> None:
    """Django should resolve the extensible application user."""
    assert get_user_model() is User


@mark.django_db
def test_anonymous_user_is_redirected_to_localized_login() -> None:
    """The application home should require authentication."""
    response = Client().get("/en/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/en/login/?next=/en/"


@mark.django_db
def test_user_can_sign_in_and_open_home() -> None:
    """A valid account should reach the protected application home."""
    _ = User.objects.create_user(
        username="trader",
        first_name="Ada",
        last_name="Lovelace",
        password="correct-horse-battery-staple",
    )
    client = Client()

    response = client.post(
        "/en/login/",
        {
            "username": "trader",
            "password": "correct-horse-battery-staple",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/en/"

    home = client.get("/en/")

    assert home.status_code == 200
    assert b"Home" in home.content
    assert b'href="/en/profiles/"' in home.content
    assert b"Open user menu" in home.content
    assert b"Ada Lovelace" in home.content
    assert b"trader" in home.content
    assert b"Settings" in home.content


@mark.django_db
def test_invalid_credentials_are_explained_and_highlighted() -> None:
    """A rejected login should identify both credential fields."""
    _ = User.objects.create_user(
        username="trader", password="correct-password"
    )

    response = Client().post(
        "/en/login/",
        {"username": "trader", "password": "wrong-password"},
    )

    assert response.status_code == 200
    assert response.content.count(b'aria-invalid="true"') == 2
    assert b"Please enter a correct username and password" in response.content


@mark.django_db
def test_home_uses_url_language() -> None:
    """The language prefix should select the rendered translation."""
    user = User.objects.create_user(username="trader")
    client = Client()
    client.force_login(user)

    response = client.get("/ru/")

    assert response.status_code == 200
    assert "Главная" in response.content.decode()


@mark.django_db
def test_logout_requires_post_and_ends_session() -> None:
    """Logout should use a CSRF-protected POST action."""
    user = User.objects.create_user(username="trader")
    client = Client()
    client.force_login(user)

    assert client.get("/en/logout/").status_code == 405

    response = client.post("/en/logout/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/en/login/"
    assert client.get("/en/").status_code == 302


def test_authentication_routes_are_language_prefixed() -> None:
    """Authentication routes should follow the active URL language."""
    with override("en"):
        assert reverse("journal:home") == "/en/"
        assert reverse("accounts:login") == "/en/login/"
        assert reverse("accounts:logout") == "/en/logout/"

    with override("ru"):
        assert reverse("journal:home") == "/ru/"
        assert reverse("accounts:login") == "/ru/login/"
        assert reverse("accounts:logout") == "/ru/logout/"


@mark.django_db
def test_public_registration_route_does_not_exist() -> None:
    """The first version should not expose self-registration."""
    assert Client().get("/en/register/").status_code == 404
