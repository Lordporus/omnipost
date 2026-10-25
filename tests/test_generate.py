import pytest

from scripts.errors import NoRelevantTopic
from scripts.generate import (
    extract_key_takeaways,
    generate_heuristic_topic,
    generate_platform_native_drafts,
    generate_topic_from_items,
    load_daily_swipe,
)


def test_extract_key_takeaways():
    sample_text = "Modern autonomous agents require deterministic execution. State machines beat raw prompt chaining every single time."
    points = extract_key_takeaways(sample_text)
    assert len(points) >= 1
    assert any("deterministic" in p.lower() or "state" in p.lower() for p in points)


def test_generate_topic_from_items_returns_valid_structure():
    items = [
        {
            "source": "hn",
            "title": "State Machines for Reliable LLM Workflows",
            "url": "https://example.com/state-machines",
            "score": 350,
            "extra": "A deep dive into why cyclic graph state machines eliminate hallucination loops in autonomous workflows."
        }
    ]
    topic = generate_topic_from_items("value", items)
    assert "headline" in topic
    assert "body" in topic
    assert "points" in topic
    assert isinstance(topic["points"], list)
    assert len(topic["points"]) > 0
    assert "takeaway" in topic


def test_generate_topic_from_items_empty_fails_closed():
    with pytest.raises(NoRelevantTopic):
        generate_topic_from_items("value", [])


def test_load_daily_swipe_missing(tmp_path, monkeypatch):
    from scripts import generate
    monkeypatch.setattr(generate, "ROOT", tmp_path)
    res = generate.load_daily_swipe("2099-01-01")
    assert res == []


def test_generate_platform_native_drafts_heuristic_bounds():
    """Validates that generate_platform_native_drafts adheres to character bounds and archetypes."""
    items = [
        {
            "source": "hn",
            "title": "Kubernetes distributed database latency architecture",
            "url": "https://example.com/kubernetes-latency",
            "score": 350,
            "extra": (
                "The database planner now handles distributed joins with lower latency. "
                "Teams can reduce query latency by using better statistics and avoiding "
                "unnecessary distributed scans."
            ),
        }
    ]
    drafts = generate_platform_native_drafts(kind="ai_update", items=items, use_llm=False)
    
    # 4 distinct platform texts
    assert "x" in drafts
    assert len(drafts["x"]) <= 280
    assert "#" not in drafts["x"]  # Zero hashtags rule for X hook

    assert "bluesky" in drafts
    assert len(drafts["bluesky"]) <= 300

    assert "threads" in drafts
    assert len(drafts["threads"]) <= 500
    assert drafts["threads"].strip().endswith("?")  # Engagement question rule

    assert "linkedin" in drafts
    assert len(drafts["linkedin"]) >= 200
    assert "3 Architecture Rules" in drafts["linkedin"] or "▸" in drafts["linkedin"]

    # Carousel metadata
    assert "carousel" in drafts
    assert "title" in drafts["carousel"]
    assert "slides" in drafts["carousel"]
    assert len(drafts["carousel"]["slides"]) == 4
    for slide in drafts["carousel"]["slides"]:
        assert "header" in slide
        assert "body" in slide

    # Unified platforms dictionary
    assert "platforms" in drafts
    assert drafts["platforms"]["x"] == drafts["x"]
    assert drafts["platforms"]["bluesky"] == drafts["bluesky"]
    assert drafts["platforms"]["threads"] == drafts["threads"]
    assert drafts["platforms"]["linkedin"] == drafts["linkedin"]


def test_generate_platform_native_drafts_with_items():
    """Validates platform-native synthesis from real swipe items."""
    items = [
        {
            "source": "hn",
            "title": "Kernel-Level Memory Optimization for Autonomous Agent Swarms",
            "url": "https://news.ycombinator.com/item?id=12345",
            "score": 420,
            "extra": "Benchmarking memory pools in distributed agent swarms shows 40% reduced latency."
        }
    ]
    drafts = generate_platform_native_drafts(kind="tech_insight", items=items, use_llm=False)
    assert len(drafts["x"]) <= 280
    assert len(drafts["bluesky"]) <= 300
    assert len(drafts["threads"]) <= 500
    assert drafts["threads"].strip().endswith("?")
    assert len(drafts["carousel"]["slides"]) == 4


def test_repurpose_preserves_platform_native_texts():
    """Native copy is preserved when it already fits the platform contract."""
    from scripts.repurpose import repurpose_topic
    from tests.copy_fixtures import valid_text

    native_x = valid_text("x")
    native_bluesky = valid_text("bluesky")
    native_threads = valid_text("threads")
    native_linkedin = valid_text("linkedin")
    custom_native = {
        "headline": "Sovereign AI Infrastructure",
        "body": "Detailed body text...",
        "points": ["Point 1", "Point 2"],
        "takeaway": "Build sovereign.",
        "category": "INFRASTRUCTURE",
        "x": native_x,
        "bluesky": native_bluesky,
        "threads": native_threads,
        "linkedin": native_linkedin,
    }
    slot_dict = repurpose_topic(custom_native, generate_media=False)
    assert slot_dict["x"]["text"] == native_x
    assert slot_dict["bluesky"]["text"] == native_bluesky
    assert slot_dict["threads"]["text"] == native_threads
    assert slot_dict["linkedin"]["text"] == native_linkedin

