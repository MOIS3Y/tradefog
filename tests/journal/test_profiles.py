import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.test import Client
from django.urls import reverse
from django.utils.translation import override
from pytest import mark

from tradefog.accounts.models import User
from tradefog.journal.models import (
    Asset,
    TradingProfile,
    TradingStrategy,
    Venue,
    VenueWalletAsset,
    Wallet,
    WalletAsset,
)

PASSWORD = "correct-horse-battery-staple"


def _login_as(**user_fields: Any) -> Client:
    client = Client()
    username = user_fields.pop("username", "trader")
    user = User.objects.create_user(
        username=username,
        password=PASSWORD,
        **user_fields,
    )
    client.force_login(user)
    return client


def _venue(name: str = "Bybit") -> Venue:
    return Venue.objects.create(name=name)


def _owner_client(username: str = "owner") -> tuple[Client, User]:
    user = User.objects.create_user(username=username, password=PASSWORD)
    client = Client()
    client.force_login(user)
    return client, user


def _profile(
    user: User,
    venue: Venue,
    name: str = "Main",
    **fields: object,
) -> TradingProfile:
    return TradingProfile.objects.create(
        owner=user,
        venue=venue,
        name=name,
        **fields,
    )


def _wallet_asset(venue: Venue, symbol: str = "USDT") -> VenueWalletAsset:
    asset = Asset.objects.create(
        symbol=symbol, name=symbol, asset_type="crypto"
    )
    return VenueWalletAsset.objects.create(venue=venue, asset=asset)


def _strategy(profile: TradingProfile, name: str = "S1") -> TradingStrategy:
    return TradingStrategy.objects.create(
        profile=profile,
        name=name,
        risk_percent=Decimal(1),
        reward_multiple=Decimal(3),
    )


def test_profile_modals_are_dialog_centered() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    profiles_root = repo_root / "src/tradefog/templates/tradefog/profiles"
    for template in (
        "partials/profile_create_modal.html",
        "partials/profile_archive_modal.html",
        "partials/profile_delete_modal.html",
    ):
        source = (profiles_root / template).read_text(encoding="utf-8")
        assert "modal-dialog-centered" in source


@mark.django_db
def test_anonymous_user_is_redirected_to_login() -> None:
    with override("en"):
        response = Client().get(reverse("journal:profile_overview"))

    assert response.status_code == 302
    assert response.headers["Location"] == "/en/login/?next=/en/profiles/"


@mark.django_db
def test_profile_overview_empty_state() -> None:
    with override("en"):
        response = _login_as().get(reverse("journal:profile_overview"))

    assert response.status_code == 200
    assert "No trading profiles yet" in response.content.decode()


@mark.django_db
def test_owner_sees_own_profiles_only() -> None:
    client, owner = _owner_client()
    other = User.objects.create_user(username="other", password=PASSWORD)
    venue = _venue()
    _profile(owner, venue, name="Mine")
    _profile(other, venue, name="Theirs")
    with override("en"):
        response = client.get(reverse("journal:profile_overview"))

    content = response.content.decode()
    assert "Mine" in content
    assert "Theirs" not in content


@mark.django_db
def test_profile_card_shows_venue_counts_and_archived_badge() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, name="Main")
    wallet = Wallet.objects.create(profile=profile)
    venue_wallet_asset = _wallet_asset(venue)
    WalletAsset.objects.create(
        wallet=wallet, venue_wallet_asset=venue_wallet_asset
    )
    _strategy(profile)
    with override("en"):
        response = client.get(reverse("journal:profile_overview"))

    content = response.content.decode()
    assert "Main" in content
    assert "Bybit" in content
    assert "1 wallet asset" in content
    assert "1 strategy" in content
    assert "Archived" not in content


@mark.django_db
def test_archived_profile_shows_badge_and_archive_section() -> None:
    client, owner = _owner_client()
    _profile(owner, _venue(), name="Main", is_archived=True)
    with override("en"):
        response = client.get(reverse("journal:profile_overview"))

    content = response.content.decode()
    assert "Archived" in content
    assert "Archives" in content
    assert "Restore profile" in content
    assert "Delete profile" in content


@mark.django_db
def test_archive_section_hidden_without_archived_profiles() -> None:
    client, owner = _owner_client()
    _profile(owner, _venue(), name="Main")
    with override("en"):
        response = client.get(reverse("journal:profile_overview"))

    assert "Archives" not in response.content.decode()


@mark.django_db
def test_create_profile_creates_wallet_atomically() -> None:
    venue = _venue(name="Bybit")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:profile_create"),
            {"name": "Main", "venue": venue.pk},
        )

    assert response.status_code == 200
    profile = TradingProfile.objects.get(name="Main")
    owner = User.objects.get(username="trader")
    assert profile.owner == owner
    assert Wallet.objects.filter(profile=profile).exists()
    content = response.content.decode()
    assert 'id="profile-grid"' in content
    assert 'hx-swap-oob="outerHTML"' in content
    trigger = response.headers["HX-Trigger"]
    assert "Profile created." in trigger
    assert '"kind": "success"' in trigger
    assert "profile-create-modal" in trigger


@mark.django_db
def test_create_profile_requires_owner_and_venue() -> None:
    venue = _venue(name="Bybit")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:profile_create"),
            {"name": "Main", "venue": venue.pk},
        )

    assert response.status_code == 200
    assert Wallet.objects.count() == 1


@mark.django_db
def test_duplicate_profile_name_returns_422() -> None:
    client, owner = _owner_client()
    venue = _venue()
    _profile(owner, venue, name="Main")
    with override("en"):
        response = client.post(
            reverse("journal:profile_create"),
            {"name": "Main", "venue": venue.pk},
        )

    assert response.status_code == 422
    assert TradingProfile.objects.filter(owner=owner).count() == 1
    assert "A profile with this name already exists." in (
        response.content.decode()
    )


@mark.django_db
def test_active_profile_cannot_be_deleted() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, name="Main")
    Wallet.objects.create(profile=profile)
    with override("en"):
        response = client.post(
            reverse("journal:profile_delete", args=(profile.pk,))
        )

    assert response.status_code == 409
    assert TradingProfile.objects.filter(pk=profile.pk).exists()
    trigger = response.headers["HX-Trigger"]
    assert "Archive the profile before deleting it permanently." in trigger
    assert '"kind": "danger"' in trigger
    assert "profile-delete-modal" in trigger


@mark.django_db
def test_delete_archived_profile_cascades_wallet() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, name="Main", is_archived=True)
    wallet = Wallet.objects.create(profile=profile)
    with override("en"):
        response = client.post(
            reverse("journal:profile_delete", args=(profile.pk,))
        )

    assert response.status_code == 200
    assert not TradingProfile.objects.filter(pk=profile.pk).exists()
    assert not Wallet.objects.filter(pk=wallet.pk).exists()
    content = response.content.decode()
    assert 'id="profile-grid"' in content
    assert 'hx-swap-oob="outerHTML"' in content
    trigger = response.headers["HX-Trigger"]
    assert "Profile deleted." in trigger
    assert '"kind": "success"' in trigger
    assert "profile-delete-modal" in trigger


@mark.django_db
def test_user_cannot_delete_another_users_profile() -> None:
    _client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main", is_archived=True)
    intruder = _login_as(username="intruder")
    with override("en"):
        response = intruder.post(
            reverse("journal:profile_delete", args=(profile.pk,))
        )

    assert response.status_code == 404
    assert TradingProfile.objects.filter(pk=profile.pk).exists()


@mark.django_db
def test_profile_delete_confirm_renders_for_get() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main", is_archived=True)
    with override("en"):
        response = client.get(
            reverse("journal:profile_delete", args=(profile.pk,))
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Delete the profile Main" in content
    assert 'hx-target="#profile-delete-body"' in content


@mark.django_db
def test_archive_profile_keeps_history_and_shows_archive() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, name="Main")
    wallet = Wallet.objects.create(profile=profile)
    venue_wallet_asset = _wallet_asset(venue)
    WalletAsset.objects.create(
        wallet=wallet, venue_wallet_asset=venue_wallet_asset
    )
    _strategy(profile)
    with override("en"):
        response = client.post(
            reverse("journal:profile_archive", args=(profile.pk,))
        )

    profile.refresh_from_db()
    assert profile.is_archived is True
    assert Wallet.objects.filter(pk=wallet.pk).exists()
    assert WalletAsset.objects.filter(wallet=wallet).count() == 1
    assert TradingStrategy.objects.filter(profile=profile).count() == 1
    content = response.content.decode()
    assert 'id="profile-grid"' in content
    assert 'hx-swap-oob="outerHTML"' in content
    assert "Archives" in content
    trigger = response.headers["HX-Trigger"]
    assert "Profile archived." in trigger
    assert '"kind": "success"' in trigger
    assert "profile-archive-modal" in trigger


@mark.django_db
def test_archive_confirm_renders_for_get() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main")
    with override("en"):
        response = client.get(
            reverse("journal:profile_archive", args=(profile.pk,))
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Archive the profile Main" in content
    assert 'hx-target="#profile-archive-body"' in content


@mark.django_db
def test_restore_profile_moves_it_out_of_archive() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, name="Main", is_archived=True)
    with override("en"):
        response = client.post(
            reverse("journal:profile_restore", args=(profile.pk,))
        )

    profile.refresh_from_db()
    assert profile.is_archived is False
    content = response.content.decode()
    assert "Archives" not in content
    trigger = response.headers["HX-Trigger"]
    assert "Profile restored." in trigger
    assert '"kind": "success"' in trigger


@mark.django_db
def test_user_cannot_archive_another_users_profile() -> None:
    _client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main")
    intruder = _login_as(username="intruder")
    with override("en"):
        response = intruder.post(
            reverse("journal:profile_archive", args=(profile.pk,))
        )

    assert response.status_code == 404
    profile.refresh_from_db()
    assert profile.is_archived is False


@mark.django_db
def test_user_cannot_restore_another_users_profile() -> None:
    _client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main", is_archived=True)
    intruder = _login_as(username="intruder")
    with override("en"):
        response = intruder.post(
            reverse("journal:profile_restore", args=(profile.pk,))
        )

    assert response.status_code == 404
    profile.refresh_from_db()
    assert profile.is_archived is True


@mark.django_db
def test_profile_overview_renders_in_russian() -> None:
    client = _login_as()
    with override("ru"):
        response = client.get(reverse("journal:profile_overview"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Профили" in content
    assert "Создать профиль" in content
    assert "Торговых профилей пока нет" in content


@mark.django_db
def test_profile_counts_render_russian_plurals() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, name="Main")
    wallet = Wallet.objects.create(profile=profile)
    for symbol in ("USDT", "USDC"):
        wallet_asset = _wallet_asset(venue, symbol)
        WalletAsset.objects.create(
            wallet=wallet, venue_wallet_asset=wallet_asset
        )
    _strategy(profile)
    _strategy(profile, name="S2")
    with override("ru"):
        response = client.get(reverse("journal:profile_overview"))

    content = response.content.decode()
    assert "2 актива кошелька" in content
    assert "2 стратегии" in content


@mark.django_db
def test_active_card_has_archive_button_but_no_delete() -> None:
    client, owner = _owner_client()
    _profile(owner, _venue(), name="Main")
    with override("en"):
        response = client.get(reverse("journal:profile_overview"))

    content = response.content.decode()
    assert 'aria-label="Archive profile"' in content
    assert 'aria-label="Restore profile"' not in content
    assert 'aria-label="Delete profile"' not in content


@mark.django_db
def test_archived_card_has_restore_and_delete_but_no_archive() -> None:
    client, owner = _owner_client()
    _profile(owner, _venue(), name="Main", is_archived=True)
    with override("en"):
        response = client.get(reverse("journal:profile_overview"))

    content = response.content.decode()
    assert 'aria-label="Restore profile"' in content
    assert 'aria-label="Delete profile"' in content
    assert 'aria-label="Archive profile"' not in content


@mark.django_db
def test_archive_section_renders_in_russian() -> None:
    client, owner = _owner_client()
    _profile(owner, _venue(), name="Main", is_archived=True)
    with override("ru"):
        response = client.get(reverse("journal:profile_overview"))

    content = response.content.decode()
    assert "Архив" in content
    assert "1 архивный профиль" in content
    assert 'aria-label="Восстановить профиль"' in content
    assert 'aria-label="Архивировать профиль"' not in content


@mark.django_db
def test_archive_toast_renders_in_russian() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main")
    with override("ru"):
        response = client.post(
            reverse("journal:profile_archive", args=(profile.pk,))
        )

    assert response.status_code == 200
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["tradefog:toast"]["message"] == "Профиль архивирован."


@mark.django_db
def test_profile_detail_anonymous_user_is_redirected() -> None:
    with override("en"):
        response = Client().get(reverse("journal:profile_detail", args=(1,)))

    assert response.status_code == 302
    assert response.headers["Location"] == "/en/login/?next=/en/profiles/1/"


@mark.django_db
def test_profile_detail_renders_four_tabs_with_overview_active() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main")
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    assert response.status_code == 200
    content = response.content.decode()
    assert profile.name in content
    assert 'id="profile-overview-tab"' in content
    assert 'id="profile-wallet-tab"' in content
    assert 'id="profile-strategies-tab"' in content
    assert 'id="profile-settings-tab"' in content
    assert 'class="nav-link active" href="#profile-overview-tab"' in content
    assert 'class="tab-pane active show" id="profile-overview-tab"' in content
    assert "Back to profiles" in content


@mark.django_db
def test_profile_detail_shows_summary_and_counts() -> None:
    client, owner = _owner_client()
    venue = _venue()
    profile = _profile(owner, venue, name="Main")
    wallet = Wallet.objects.create(profile=profile)
    wallet_asset = _wallet_asset(venue)
    WalletAsset.objects.create(wallet=wallet, venue_wallet_asset=wallet_asset)
    _strategy(profile)
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "Bybit" in content
    assert "Active" in content
    assert "Wallet assets" in content
    assert "Strategies" in content
    assert "Trades" in content
    assert ">1</span>" in content


@mark.django_db
def test_profile_detail_shows_archived_status() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main", is_archived=True)
    with override("en"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "Archived" in content
    assert "Active" not in content


@mark.django_db
def test_profile_detail_hides_content_from_other_users() -> None:
    _client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main")
    intruder = _login_as(username="intruder")
    with override("en"):
        response = intruder.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    assert response.status_code == 404


@mark.django_db
def test_profile_detail_renders_tabs_in_russian() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main")
    with override("ru"):
        response = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )

    content = response.content.decode()
    assert "Обзор" in content
    assert "Кошелёк" in content
    assert "Стратегии" in content
    assert "Настройки" in content
    assert "Назад к профилям" in content


@mark.django_db
def test_profile_card_links_to_detail() -> None:
    client, owner = _owner_client()
    profile = _profile(owner, _venue(), name="Main")
    with override("en"):
        response = client.get(reverse("journal:profile_overview"))

    detail_url = reverse("journal:profile_detail", args=(profile.pk,))
    assert f'href="{detail_url}"' in response.content.decode()


@mark.django_db
def test_profile_create_modal_without_venues_staff_en() -> None:
    client = _login_as(username="admin", is_staff=True)
    with override("en"):
        response = client.get(reverse("journal:profile_create"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "No venues available" in content
    assert "Add at least one venue in the catalog first" in content
    assert "Go to venues" in content
    assert reverse("journal:venue_overview") in content
    assert '<select name="venue"' not in content


@mark.django_db
def test_profile_create_modal_without_venues_staff_ru() -> None:
    client = _login_as(username="admin", is_staff=True)
    with override("ru"):
        response = client.get(reverse("journal:profile_create"))
        venue_url = reverse("journal:venue_overview")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Нет доступных площадок" in content
    assert "Сначала добавьте хотя бы одну площадку в каталог" in content
    assert "Перейти к площадкам" in content
    assert venue_url in content


@mark.django_db
def test_profile_create_modal_without_venues_regular_user_en() -> None:
    client = _login_as(username="regular", is_staff=False)
    with override("en"):
        response = client.get(reverse("journal:profile_create"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "No venues available" in content
    assert "Ask a staff member to add venues to the catalog" in content
    assert "Go to venues" not in content
    assert "Close" in content


@mark.django_db
def test_profile_create_post_without_venues_returns_conflict() -> None:
    client = _login_as(username="admin", is_staff=True)
    with override("en"):
        response = client.post(
            reverse("journal:profile_create"),
            {"name": "Main", "venue": 999},
        )

    assert response.status_code == 409


@mark.django_db
def test_profile_card_shows_venue_website_link() -> None:
    client, user = _owner_client()
    venue = Venue.objects.create(
        name="Bybit", website="https://www.bybit.com/"
    )
    profile = _profile(user, venue, name="Scalping")

    response = client.get(reverse("journal:profile_overview"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "www.bybit.com" in content
    assert "https://www.bybit.com/" in content
    assert "tabler-building-bank" in content

    # Detail overview tab
    detail_resp = client.get(
        reverse("journal:profile_detail", args=(profile.pk,))
    )
    assert detail_resp.status_code == 200
    detail_content = detail_resp.content.decode()
    assert "www.bybit.com" in detail_content


@mark.django_db
def test_profile_create_with_description() -> None:
    venue = _venue(name="Bybit")
    client = _login_as()
    with override("en"):
        response = client.post(
            reverse("journal:profile_create"),
            {
                "name": "Main Account",
                "description": "Primary high-conviction swing portfolio.",
                "venue": venue.pk,
            },
        )

    assert response.status_code == 200
    profile = TradingProfile.objects.get(name="Main Account")
    assert profile.description == "Primary high-conviction swing portfolio."


@mark.django_db
def test_profile_card_shows_profile_description_not_venue() -> None:
    client, user = _owner_client()
    venue = Venue.objects.create(
        name="Bybit", description="Venue exchange description."
    )
    _profile(
        user,
        venue,
        name="Scalping",
        description="My personal scalping profile description.",
    )

    response = client.get(reverse("journal:profile_overview"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "My personal scalping profile description." in content
    assert "Venue exchange description." not in content


@mark.django_db
def test_profile_settings_edit_and_oob_heading() -> None:
    client, user = _owner_client()
    venue = Venue.objects.create(
        name="Bybit", website="https://www.bybit.com/"
    )
    profile = _profile(user, venue, name="Initial Name")

    with override("en"):
        # GET profile detail: settings tab contains form
        detail_resp = client.get(
            reverse("journal:profile_detail", args=(profile.pk,))
        )
        assert detail_resp.status_code == 200
        detail_content = detail_resp.content.decode()
        assert 'id="profile-settings-tab"' in detail_content
        assert 'id="profile-settings-body"' in detail_content
        assert "Initial Name" in detail_content

        # POST profile_edit
        edit_resp = client.post(
            reverse("journal:profile_edit", args=(profile.pk,)),
            {
                "name": "Updated Swing",
                "description": "Updated swing profile description.",
            },
        )

    assert edit_resp.status_code == 200
    profile.refresh_from_db()
    assert profile.name == "Updated Swing"
    assert profile.description == "Updated swing profile description."

    edit_content = edit_resp.content.decode()
    assert 'id="profile-heading"' in edit_content
    assert 'id="profile-overview-content"' in edit_content
    assert 'hx-swap-oob="outerHTML"' in edit_content
    assert "Updated Swing" in edit_content
    assert "Updated swing profile description." in edit_content

    trigger = edit_resp.headers["HX-Trigger"]
    assert "Profile updated." in trigger
    assert '"kind": "success"' in trigger


@mark.django_db
def test_profile_settings_duplicate_name_error() -> None:
    client, user = _owner_client()
    venue = _venue()
    _profile(user, venue, name="Existing Name")
    profile = _profile(user, venue, name="Second Profile")

    with override("en"):
        edit_resp = client.post(
            reverse("journal:profile_edit", args=(profile.pk,)),
            {"name": "Existing Name", "description": ""},
        )

    assert edit_resp.status_code == 422
    assert (
        "A profile with this name already exists."
        in edit_resp.content.decode()
    )


@mark.django_db
def test_profile_settings_cannot_be_edited_by_other_user() -> None:
    _client1, user1 = _owner_client(username="user1")
    client2, _user2 = _owner_client(username="user2")
    venue = _venue()
    profile1 = _profile(user1, venue, name="User1 Profile")

    with override("en"):
        response = client2.post(
            reverse("journal:profile_edit", args=(profile1.pk,)),
            {"name": "Hacked", "description": ""},
        )

    assert response.status_code == 404
    profile1.refresh_from_db()
    assert profile1.name == "User1 Profile"
