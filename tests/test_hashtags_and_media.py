"""Per-platform hashtag caps and media-required guardrails."""
from __future__ import annotations

from scripts import settings
from scripts.platform_limits import (
    LIMITS,
    MAX_HASHTAGS,
    TARGETS,
    count_for,
    count_hashtags,
    normalise_hashtags,
)
from scripts.repurpose import DEFAULT_HASHTAGS, hashtags_for, with_hashtags
from scripts.validator import score_humanity

BODY = "Shipped 3 fixes today. Small change, real result."


def _tag_violation(text: str, platform: str) -> bool:
    _, violations = score_humanity(text, platform=platform)
    return any("Hashtag cap" in v for v in violations)


def test_hashtag_caps_match_decisions():
    assert MAX_HASHTAGS == {"x": 0, "bluesky": 3, "threads": 0, "linkedin": 5}


def test_hashtag_cap_is_per_platform():
    tags = ["#AI", "#Agents", "#Python", "#LLM", "#Tools", "#Build"]
    assert _tag_violation(f"{BODY} {' '.join(tags[:5])}", "linkedin") is False
    assert _tag_violation(f"{BODY} {' '.join(tags)}", "linkedin") is True
    assert _tag_violation(f"{BODY} {' '.join(tags[:3])}", "bluesky") is False
    assert _tag_violation(f"{BODY} {' '.join(tags[:4])}", "bluesky") is True
    assert _tag_violation(f"{BODY} #AI", "x") is True
    assert _tag_violation(f"{BODY} #AI", "threads") is True


def test_url_fragment_still_not_a_hashtag():
    _, violations = score_humanity(
        "Read https://example.com/#install before shipping. 2 lines.", platform="x"
    )
    assert not any("Hashtag" in v for v in violations)


def test_normalise_hashtags_dedupes_caps_and_strips():
    assert normalise_hashtags(["#ai", "AI", "agents", "  # LLM  "], "bluesky") == [
        "#Ai",
        "#Agents",
        "#LLM",
    ]
    assert normalise_hashtags(["#AI"], "x") == []
    assert normalise_hashtags(["a" * 40], "linkedin") == []


def test_with_hashtags_fits_body_before_appending():
    body = "x " * LIMITS["linkedin"]["max"]
    text = with_hashtags("linkedin", body, ["#One", "#Two", "#Three"])
    assert count_for("linkedin", text) <= LIMITS["linkedin"]["max"]
    assert text.rstrip().endswith("#One #Two #Three")
    assert count_hashtags(text) == 3


def test_with_hashtags_skips_tags_that_break_the_minimum():
    body = "x " * 240
    tags = ["#" + "A" * 24, "#" + "B" * 24, "#" + "C" * 24]
    assert with_hashtags("bluesky", body, tags) == body


def test_hashtags_for_honours_configured_source(monkeypatch):
    topic = {"category": "AI ARCHITECTURE", "hashtags": {"linkedin": ["#Agents"]}}

    monkeypatch.setattr(settings, "load", lambda: {"hashtags": {"source": "llm"}})
    assert hashtags_for(topic, "linkedin", "10:00") == (["#Agents"], "llm")

    monkeypatch.setattr(settings, "load", lambda: {"hashtags": {"source": "category"}})
    assert hashtags_for(topic, "linkedin", "10:00") == (
        ["#AI", "#SystemDesign", "#Architecture"],
        "category",
    )


def test_hashtags_for_auto_alternates_by_slot_and_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "load", lambda: {"hashtags": {"source": "auto"}})
    empty = {"category": "UNKNOWN"}
    expected = normalise_hashtags(DEFAULT_HASHTAGS, "bluesky")
    # The model returns no tags for this topic, so the recorded source is the
    # category fallback, not the requested one.
    assert hashtags_for(empty, "bluesky", "20:00") == (expected, "category")
    assert hashtags_for(empty, "bluesky", "21:00") == (expected, "category")
    assert hashtags_for(empty, "x", "20:00") == ([], "none")


def test_linkedin_target_band():
    assert TARGETS["linkedin"] == (1300, 1800)
    assert TARGETS["linkedin"][1] < LIMITS["linkedin"]["max"]


def test_slot_media_falls_back_to_rendered_cards(tmp_path, monkeypatch):
    from scripts import publish_now

    monkeypatch.setattr(publish_now, "ROOT", tmp_path)
    card_dir = tmp_path / "scratch" / "cards"
    card_dir.mkdir(parents=True)
    cards = [card_dir / f"card_20261111_2000_card_{i}.png" for i in (1, 2)]
    for card in cards:
        card.write_bytes(b"png")
    assert publish_now.slot_media("x", "2026-11-11", "20:00") == cards
    assert publish_now.slot_media("bluesky", "2026-11-11", "13:00") == []


def test_slot_media_prefers_linkedin_carousel_pdf(tmp_path, monkeypatch):
    from scripts import publish_now

    monkeypatch.setattr(publish_now, "ROOT", tmp_path)
    pdf = tmp_path / "scratch" / "carousels" / "linkedin_20261111_2000.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"pdf")
    assert publish_now.slot_media("linkedin", "2026-11-11", "20:00") == [pdf]


def test_text_only_is_blocked_when_media_is_required():
    from scripts import publish_now

    assert publish_now.text_only_blocked([], True, False) is True
    assert publish_now.text_only_blocked([], True, True) is False
    assert publish_now.text_only_blocked([], False, False) is False
    assert publish_now.text_only_blocked([__file__], True, False) is False
