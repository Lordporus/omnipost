from scripts.generate import extract_key_takeaways, generate_topic_from_items, load_daily_swipe


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


def test_generate_topic_from_items_empty_fallback():
    topic = generate_topic_from_items("value", [])
    assert "headline" in topic
    assert "points" in topic
    assert len(topic["points"]) > 0


def test_load_daily_swipe_missing(tmp_path, monkeypatch):
    from scripts import generate
    monkeypatch.setattr(generate, "ROOT", tmp_path)
    res = generate.load_daily_swipe("2099-01-01")
    assert res == []
