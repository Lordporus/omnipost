"""Phase 14 regression tests for platform copy limits and media contracts."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from adapters.base import PlatformCapabilities, PublishPayload, PublishResult
from adapters.linkedin import _select_linkedin_media
from scripts import ledger, publish_now
from scripts.errors import CopyValidationError, MediaContractError
from scripts.pipeline import populate_daily_plan
from scripts.platform_limits import (
    LIMITS,
    count_chars,
    count_for,
    count_graphemes,
    count_x_weighted,
    fit,
    truncate_words,
)
from scripts.repurpose import (
    format_linkedin,
    format_threads,
    format_x,
    repurpose_topic,
)
from tests.copy_fixtures import rich_topic


def test_x_weighted_count_cjk_emoji():
    assert count_x_weighted("hello") == 5
    assert count_x_weighted("你好") == 4
    assert count_x_weighted("🚀") == 2
    assert count_x_weighted("😀") == 2
    assert count_x_weighted("e\u0301") == 1
    assert count_for("x", "你好") > count_chars("你好")
    assert count_for("x", "hello") == 5


def test_bluesky_grapheme_count():
    assert count_graphemes("hello") == 5
    assert count_graphemes("e\u0301") == 1
    assert count_graphemes("👍🏽") == 1
    assert count_graphemes("👨‍👩‍👧‍👦") == 1
    assert count_graphemes("🇺🇸") == 1
    assert count_for("bluesky", "e\u0301") == 1


def test_threads_never_exceeds_500():
    topic = rich_topic()
    text = format_threads(
        topic["headline"],
        topic["takeaway"],
        topic["body"],
        topic["points"],
    )
    measured = count_for("threads", text)
    assert measured <= LIMITS["threads"]["hard_max"]
    assert measured >= LIMITS["threads"]["min"]
    assert "What architectural tradeoffs have you seen in your stack?" in text
    assert text.rstrip().endswith("?")


def test_truncate_words_never_splits():
    text = "alpha beta gamma delta epsilon"
    out = truncate_words(text, 15, "threads")
    assert out == "alpha beta..."
    for token in out.removesuffix("...").split():
        assert token in text.split()

    assert truncate_words("one two three four", 12, "x") == "one two..."

    url_text = "Read https://example.com/docs now for the complete reference"
    url_out = truncate_words(url_text, 40, "threads")
    assert "https://example.com/docs" in url_out
    for token in url_out.removesuffix("...").split():
        assert token in url_text.split()


def test_x_minimum_enforced():
    with pytest.raises(CopyValidationError) as exc_info:
        format_x("Tiny note", ["short"])
    assert exc_info.value.platform == "x"
    assert exc_info.value.count < LIMITS["x"]["min"]

    with pytest.raises(CopyValidationError):
        fit("x", "too short")


def test_linkedin_range():
    topic = rich_topic()
    text = format_linkedin(
        topic["headline"],
        topic["body"],
        topic["points"],
        topic["takeaway"],
        media_type="image",
    )
    measured = count_for("linkedin", text)
    assert LIMITS["linkedin"]["min"] <= measured <= LIMITS["linkedin"]["max"]


class _FakeAdapter:
    def __init__(self, name: str = "x"):
        self.platform_name = name
        self.capabilities = PlatformCapabilities(max_characters=1000)
        self.session = {"ok": True, "handle": "tester"}

    def check_session(self) -> dict:
        return dict(self.session)

    def publish(self, payload: PublishPayload) -> PublishResult:
        return PublishResult(
            platform=self.platform_name,
            success=True,
            verified=True,
            url=f"https://{self.platform_name}.example/post/1",
        )


def _run_publish_now(tmp_path, monkeypatch, text: str, dispatch):
    adapter = _FakeAdapter("x")
    state_path = tmp_path / "state.json"
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({"slot": "13:00", "text": text}), encoding="utf-8")

    monkeypatch.setattr(ledger, "STATE_PATH", state_path)
    monkeypatch.setattr(publish_now.settings, "get_active_adapters", lambda: [adapter])
    monkeypatch.setattr(publish_now, "check_connectivity", lambda **kwargs: True)
    monkeypatch.setattr(
        publish_now.notify_webhook,
        "dispatch_summary_card",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        publish_now.notify_webhook,
        "dispatch_webhook",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(publish_now, "_dispatch_worker", dispatch)
    monkeypatch.setattr(sys, "argv", ["publish_now.py", "--draft", str(draft)])
    return publish_now.main(), state_path


def test_dispatch_rejects_undersized(tmp_path, monkeypatch):
    calls: list[PublishPayload] = []

    def dispatch(adapter, payload, timeout):
        calls.append(payload)
        return PublishResult(platform="x", success=True, verified=True)

    code, state_path = _run_publish_now(
        tmp_path,
        monkeypatch,
        "short copy",
        dispatch,
    )

    assert code == 1
    assert calls == []
    state = ledger.load_state(state_path)
    record = ledger.get_platform_status(
        state,
        datetime.now().strftime("%Y-%m-%d"),
        "13:00",
        "x",
    )
    assert record is not None
    assert record["status"] == ledger.STATUS_FAILED
    assert "minimum" in str(record.get("error") or "")


def test_dispatch_fits_oversized(tmp_path, monkeypatch):
    calls: list[PublishPayload] = []

    def dispatch(adapter, payload, timeout):
        calls.append(payload)
        return PublishResult(
            platform="x",
            success=True,
            verified=True,
            url="https://x.example/post/1",
        )

    oversized = "A deterministic publishing guard should fit this copy on a word boundary. " * 10
    code, _ = _run_publish_now(tmp_path, monkeypatch, oversized, dispatch)

    assert code == 0
    assert len(calls) == 1
    measured = count_for("x", calls[0].text)
    assert LIMITS["x"]["min"] <= measured <= LIMITS["x"]["max"]
    assert calls[0].text.endswith("...")


def test_linkedin_carousel_contract(tmp_path, monkeypatch):
    pdf_path = tmp_path / "linkedin_deck.pdf"
    # Must clear the renderer's blank-stub floor (a real deck is 500KB+; the
    # failure mode this guards against was a 759-byte empty PDF).
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"%" * 6000)

    card_path = tmp_path / "card_1.png"
    card_path.write_bytes(b"\x89PNG\r\n\x1a\nstorybook")
    monkeypatch.setattr("render.cards.generate_topic_cards", lambda **kwargs: [card_path])
    monkeypatch.setattr(
        "scripts.repurpose.create_carousel_pdf",
        lambda **kwargs: pdf_path,
    )

    topic = rich_topic(
        carousel={
            "title": "Deterministic Publishing",
            "slides": [
                {"header": "01", "body": "Observable state transitions."},
                {"header": "02", "body": "Word-boundary truncation."},
            ],
        }
    )
    slot = repurpose_topic(topic, generate_media=True)
    linkedin = slot["linkedin"]

    assert linkedin["media_type"] == "carousel"
    assert linkedin["media"] == [str(pdf_path)]
    assert linkedin["document_title"] == "Deterministic Publishing"

    mode, selected = _select_linkedin_media(
        PublishPayload(
            text=linkedin["text"],
            media_paths=[pdf_path],
            media_type=linkedin["media_type"],
        )
    )
    assert mode == "document"
    assert selected == pdf_path

    with pytest.raises(MediaContractError):
        _select_linkedin_media(
            PublishPayload(text=linkedin["text"], media_paths=[], media_type="carousel")
        )

    image_path = tmp_path / "card.png"
    image_path.write_bytes(b"png")
    mode, selected = _select_linkedin_media(
        PublishPayload(
            text=linkedin["text"],
            media_paths=[image_path, pdf_path],
            media_type="carousel",
        )
    )
    assert mode == "images"
    assert selected is None

    with pytest.raises(MediaContractError):
        repurpose_topic(rich_topic(media_type="carousel"), generate_media=False)


def test_linkedin_image_contract():
    linkedin = repurpose_topic(rich_topic(), generate_media=False)["linkedin"]
    assert linkedin["media_type"] == "image"
    assert "document_title" not in linkedin

    image_path = Path("scratch/card.png")
    mode, selected = _select_linkedin_media(
        PublishPayload(
            text=linkedin["text"],
            media_paths=[image_path],
            media_type="image",
        )
    )
    assert mode == "images"
    assert selected is None


def test_copy_validation_requeues():
    plan = {
        "date": "2026-10-24",
        "slots": [{"slot": "13:00", "kind": "value", "text": ""}],
    }
    items = [
        {
            "title": "First candidate",
            "url": "https://example.com/first",
            "score": 100,
            "extra": "A detailed first candidate with deterministic state transitions.",
        },
        {
            "title": "Second candidate",
            "url": "https://example.com/second",
            "score": 90,
            "extra": "A detailed second candidate with observable publishing behavior.",
        },
    ]
    first_topic = {
        "headline": "First topic",
        "body": "First body with deterministic state transitions.",
        "points": ["First point", "Second point"],
        "takeaway": "First point",
        "category": "TECH",
    }
    second_topic = {
        "headline": "Second topic",
        "body": "Second body with observable publishing behavior.",
        "points": ["Third point", "Fourth point"],
        "takeaway": "Third point",
        "category": "TECH",
    }
    poly = {
        "x": {"text": "Second X copy", "media": [], "enabled": True},
        "bluesky": {"text": "Second Bluesky copy", "media": [], "enabled": True},
        "linkedin": {"text": "Second LinkedIn copy", "media": [], "enabled": True},
        "threads": {"text": "Second Threads copy", "media": [], "enabled": True},
    }

    with patch(
        "scripts.generate.generate_topic_from_items",
        side_effect=[first_topic, second_topic],
    ) as mock_generate, patch(
        "scripts.repurpose.repurpose_topic",
        side_effect=[
            CopyValidationError(
                "x copy is too short",
                platform="x",
                count=10,
                limits=LIMITS["x"],
            ),
            poly,
        ],
    ) as mock_repurpose:
        populated = populate_daily_plan(plan, items, force=True)

    assert mock_generate.call_count == 2
    assert mock_repurpose.call_count == 2
    assert populated["slots"][0]["text"] == "Second X copy"
    assert populated["slots"][0]["platforms"] == poly


def test_no_hardcoded_slices():
    repurpose_source = Path("scripts/repurpose.py").read_text(encoding="utf-8")
    publish_source = Path("scripts/publish_now.py").read_text(encoding="utf-8")

    assert "text[:" not in repurpose_source
    assert "[:292]" not in repurpose_source
    assert "[:2950]" not in repurpose_source
    assert "text[:" not in publish_source
    assert "post_text[:" not in publish_source
