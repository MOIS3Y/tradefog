"""Tests for evolving descriptions and private trade attachments."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.paginator import Page
from django.test import Client, override_settings
from pytest import mark, raises

from tradefog.accounts.models import User
from tradefog.asgi import application
from tradefog.journal.attachments import validate_attachment
from tradefog.journal.markdown import render_markdown
from tradefog.journal.models import (
    Asset,
    ProfileTradingPair,
    Trade,
    TradeAttachment,
    TradeDescription,
    TradingProfile,
)
from tradefog.journal.services import (
    close_trade,
    open_trade,
    save_trade_description,
    set_trade_review_completion,
    submit_trade,
)

PNG_CONTENT = b"\x89PNG\r\n\x1a\n" + b"private-image"


def create_trade(owner: User, *, suffix: str = "") -> Trade:
    """Create one valid draft with a simple owned profile and pair."""
    quote, _created = Asset.objects.get_or_create(owner=owner, symbol="USDT")
    base = Asset.objects.create(owner=owner, symbol=f"BTC{suffix}")
    profile = TradingProfile.objects.create(
        owner=owner,
        name=f"Primary{suffix}",
        capital_asset=quote,
        market_type=TradingProfile.MarketType.LINEAR_PERPETUAL.value,
        initial_capital=Decimal(10000),
        risk_per_trade_percent=Decimal(1),
        risk_stop_capital=Decimal(9000),
    )
    pair = ProfileTradingPair.objects.create(
        profile=profile,
        asset=base,
        price_step=Decimal("0.5"),
        quantity_step=Decimal("0.1"),
    )
    return Trade.objects.create(
        profile=profile,
        trading_pair=pair,
        direction=Trade.Direction.LONG.value,
        trade_date=date(2026, 8, 31),
        planned_entry=Decimal(100),
        planned_stop=Decimal(95),
    )


def close(trade: Trade) -> Trade:
    """Advance one draft through the ordinary complete lifecycle."""
    return close_trade(
        open_trade(submit_trade(trade)),
        realized_pnl=Decimal(300),
    )


def png_upload(name: str = "setup.png") -> SimpleUploadedFile:
    """Return a minimal signature-valid image upload."""
    return SimpleUploadedFile(name, PNG_CONTENT, content_type="image/png")


@mark.parametrize(
    ("name", "content", "expected_type"),
    (
        ("chart.png", PNG_CONTENT, "image/png"),
        ("chart.jpg", b"\xff\xd8\xffimage", "image/jpeg"),
        ("chart.webp", b"RIFF\x00\x00\x00\x00WEBPimage", "image/webp"),
        ("plan.pdf", b"%PDF-1.7\ncontent", "application/pdf"),
    ),
)
def test_attachment_allowlist_uses_file_signatures(
    name: str,
    content: bytes,
    expected_type: str,
) -> None:
    """Every documented attachment format should pass signature checks."""
    upload = SimpleUploadedFile(name, content)

    metadata = validate_attachment(upload)

    assert metadata.content_type == expected_type
    assert metadata.size == len(content)


@mark.django_db
def test_description_is_editable_throughout_trade_lifecycle() -> None:
    """Description changes must remain independent of trade status."""
    owner = User.objects.create_user(username="description-owner")
    draft = create_trade(owner)

    first = save_trade_description(
        draft,
        content_markdown="# Premarket\n\nInitial context.",
    )
    opened = open_trade(submit_trade(draft))
    second = save_trade_description(
        opened,
        content_markdown="# Premarket\n\nUpdated while open.",
    )

    assert first.trade_id == draft.id
    assert second.id == first.id
    assert second.content_markdown.endswith("Updated while open.")


@mark.django_db
def test_review_completion_requires_closed_trade_and_can_be_reopened() -> None:
    """Review is an explicit fact without extending trade lifecycle."""
    owner = User.objects.create_user(username="review-owner")
    trade = create_trade(owner)

    with raises(ValidationError):
        _ = set_trade_review_completion(trade, completed=True)

    closed = close(trade)
    completed = set_trade_review_completion(closed, completed=True)
    reopened = set_trade_review_completion(closed, completed=False)

    assert closed.status == Trade.Status.CLOSED.value
    assert completed.review_completed_at is not None
    assert reopened.review_completed_at is None


def test_markdown_renderer_escapes_raw_html() -> None:
    """Persisted Markdown must not become an owner-triggered XSS vector."""
    source = """# Review

<script>alert('xss')</script>

[bad](javascript:alert(1))

![remote](https://example.com/a.png)"""
    rendered = render_markdown(source)

    assert "<h1>Review</h1>" in rendered
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert 'href="javascript:' not in rendered
    assert "<img" not in rendered


@mark.django_db
def test_description_section_is_inline_after_checklist() -> None:
    """The complete trade record should remain one cohesive workspace."""
    owner = User.objects.create_user(username="workspace-owner")
    trade = create_trade(owner)
    client = Client()
    client.force_login(owner)

    response = client.get(f"/en/trades/{trade.id}/")

    content = response.content
    assert response.status_code == 200
    assert content.index(b'id="checklist-title"') < content.index(
        b'id="trade-description"'
    )
    assert b"easymde.min.js" in content
    assert b"dompurify/purify.min.js" in content
    assert b"trade-description.js" in content
    assert b"data-attachment-upload" in content
    assert b"data-remove-label" in content
    assert b'id="attachment-delete-modal"' in content
    assert b"No description yet" not in content
    assert b"tf-description-source" in content


@mark.django_db
def test_owner_can_save_description_but_stranger_cannot() -> None:
    """Description writes must resolve the trade through its owner."""
    owner = User.objects.create_user(username="description-writer")
    stranger = User.objects.create_user(username="description-stranger")
    trade = create_trade(owner)
    client = Client()
    client.force_login(owner)

    response = client.post(
        f"/en/trades/{trade.id}/description/",
        {"content_markdown": "## Execution\n\nHeld the plan."},
    )
    reactive = client.post(
        f"/en/trades/{trade.id}/description/",
        {"content_markdown": "## Updated\n\nSaved without a reload."},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    client.force_login(stranger)
    forbidden = client.post(
        f"/en/trades/{trade.id}/description/",
        {"content_markdown": "Changed"},
    )

    assert response.status_code == 302
    assert reactive.status_code == 200
    assert reactive["X-Tradefog-Description"] == "rendered"
    assert reactive["X-Tradefog-Description-Empty"] == "false"
    assert b"<h2>Updated</h2>" in reactive.content
    assert forbidden.status_code == 404
    assert TradeDescription.objects.get(
        trade=trade
    ).content_markdown.startswith("## Updated")


@mark.django_db
def test_attachment_upload_and_delivery_are_private(tmp_path: Path) -> None:
    """Only the owner may receive content from the protected media root."""
    owner = User.objects.create_user(username="attachment-owner")
    stranger = User.objects.create_user(username="attachment-stranger")
    trade = create_trade(owner)
    client = Client()
    client.force_login(owner)

    with override_settings(MEDIA_ROOT=tmp_path):
        upload_response = client.post(
            f"/en/trades/{trade.id}/attachments/",
            {"file": png_upload("../setup.png")},
        )
        attachment = TradeAttachment.objects.get()
        stored_name = attachment.file.name
        assert stored_name is not None
        view_url = f"/en/trades/{trade.id}/attachments/{attachment.id}/"
        owner_response = client.get(view_url)
        client.force_login(stranger)
        stranger_response = client.get(view_url)
        client.logout()
        anonymous_response = client.get(view_url)

        assert upload_response.status_code == 201
        assert attachment.original_name == "setup.png"
        assert "setup.png" not in stored_name
        assert (tmp_path / stored_name).exists()
        assert owner_response.status_code == 200
        assert owner_response["X-Content-Type-Options"] == "nosniff"
        assert owner_response["Content-Security-Policy"] == "sandbox"
        assert stranger_response.status_code == 404
        assert anonymous_response.status_code == 302


@mark.django_db
def test_every_attachment_mutation_enforces_trade_ownership(
    tmp_path: Path,
) -> None:
    """Upload, download, and deletion must share one ownership boundary."""
    owner = User.objects.create_user(username="route-owner")
    stranger = User.objects.create_user(username="route-stranger")
    trade = create_trade(owner)
    client = Client()
    client.force_login(owner)

    with override_settings(MEDIA_ROOT=tmp_path):
        _response = client.post(
            f"/en/trades/{trade.id}/attachments/",
            {"file": png_upload()},
        )
        attachment = TradeAttachment.objects.get()
        client.force_login(stranger)

        upload = client.post(
            f"/en/trades/{trade.id}/attachments/",
            {"file": png_upload("other.png")},
        )
        attachment_base_url = (
            f"/en/trades/{trade.id}/attachments/{attachment.id}"
        )
        download = client.get(f"{attachment_base_url}/download/")
        delete = client.post(
            f"/en/trades/{trade.id}/attachments/{attachment.id}/delete/"
        )

    assert upload.status_code == 404
    assert download.status_code == 404
    assert delete.status_code == 404
    assert TradeAttachment.objects.filter(id=attachment.id).exists()


@mark.django_db
def test_attachment_validation_rejects_signature_and_size(
    tmp_path: Path,
) -> None:
    """Suffixes and browser MIME claims cannot bypass server validation."""
    owner = User.objects.create_user(username="validation-owner")
    trade = create_trade(owner)
    client = Client()
    client.force_login(owner)

    with override_settings(
        MEDIA_ROOT=tmp_path,
        TRADEFOG_MAX_ATTACHMENT_SIZE=12,
    ):
        bad_signature = client.post(
            f"/en/trades/{trade.id}/attachments/",
            {
                "file": SimpleUploadedFile(
                    "fake.png",
                    b"not-a-png",
                    content_type="image/png",
                )
            },
        )
        too_large = client.post(
            f"/en/trades/{trade.id}/attachments/",
            {"file": png_upload()},
        )

    assert bad_signature.status_code == 422
    assert b"does not match its extension" in bad_signature.content
    assert too_large.status_code == 422
    assert b"exceeds the configured" in too_large.content
    assert not TradeAttachment.objects.exists()


@mark.django_db(transaction=True)
def test_attachment_delete_removes_database_row_and_file(
    tmp_path: Path,
) -> None:
    """Explicit deletion should not leave private media behind."""
    owner = User.objects.create_user(username="delete-owner")
    trade = create_trade(owner)
    client = Client()
    client.force_login(owner)

    with override_settings(MEDIA_ROOT=tmp_path):
        _response = client.post(
            f"/en/trades/{trade.id}/attachments/",
            {"file": png_upload()},
        )
        attachment = TradeAttachment.objects.get()
        stored_name = attachment.file.name
        assert stored_name is not None
        stored_path = tmp_path / stored_name
        response = client.post(
            f"/en/trades/{trade.id}/attachments/{attachment.id}/delete/",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 204
    assert not TradeAttachment.objects.exists()
    assert not stored_path.exists()


@mark.django_db
def test_review_filter_selects_only_closed_trade_review_state() -> None:
    """Operational filtering should expose closed trades needing review."""
    owner = User.objects.create_user(username="filter-owner")
    incomplete = close(create_trade(owner))
    complete = close(create_trade(owner, suffix="2"))
    _description = set_trade_review_completion(complete, completed=True)
    client = Client()
    client.force_login(owner)

    incomplete_response = client.get("/en/trades/?review=INCOMPLETE")
    complete_response = client.get("/en/trades/?review=COMPLETE")

    incomplete_page = cast(
        Page[Trade],
        incomplete_response.context["page_obj"],
    )
    complete_page = cast(
        Page[Trade],
        complete_response.context["page_obj"],
    )
    assert list(incomplete_page.object_list) == [incomplete]
    assert list(complete_page.object_list) == [complete]


def test_asgi_does_not_mount_private_media() -> None:
    """The standalone application must not bypass Django owner checks."""
    mounted_paths = {
        getattr(route, "path", None) for route in application.routes
    }

    assert "/media" not in mounted_paths
