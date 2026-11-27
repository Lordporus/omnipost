"""Unit tests for scripts.profile_audit (CDP analytics sync & Viral Radar)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scripts.profile_audit import (
    AUTO_END,
    AUTO_START,
    parse_metric_score,
    run_analytics,
    run_radar,
    sync_voice_samples,
)


def test_parse_metric_score_weights_and_compact_units():
    assert parse_metric_score("") == 0.0
    assert parse_metric_score("1 reply, 2 likes, 100 views") == 1 * 5.0 + 2 * 3.0 + 100 * 0.05
    assert parse_metric_score("604 impressions • 4 engagements") == round(604 * 0.05, 2)
    assert parse_metric_score("1.5K likes, 2M views") == 1500 * 3.0 + 2_000_000 * 0.05


def test_sync_voice_samples_preserves_manual_header_and_ranks(tmp_path: Path):
    sample_file = tmp_path / "voice-samples.md"
    sample_file.write_text(
        f"# Header Note\nKeep me.\n\n{AUTO_START}\nold stuff\n{AUTO_END}\n\n# Footer\n",
        encoding="utf-8",
    )
    posts = {
        "linkedin": [
            {"text": "Dry arXiv abstract summary", "metrics": "17 impressions", "score": 0.85},
            {"text": "Anthropic CI distillation post", "metrics": "604 impressions", "score": 30.2},
        ],
        "x": [
            {"text": "Zero-view tweet", "metrics": "4 views", "score": 0.2},
        ],
    }

    out = sync_voice_samples(posts, path=sample_file)
    content = out.read_text(encoding="utf-8")
    assert "# Header Note" in content
    assert "# Footer" in content
    assert "old stuff" not in content
    assert "Anthropic CI distillation post" in content
    assert "Anti-Patterns / Do Not Emulate" in content
    assert "Dry arXiv abstract summary" in content


def test_run_analytics_offline_returns_one():
    with patch("scripts.profile_audit.browser.alive", return_value=False):
        assert run_analytics() == 1


def test_run_analytics_online_syncs_samples(tmp_path: Path):
    fake_data = {
        "x": {"followers": "10 Followers", "posts": [{"text": "Winning X post", "metrics": "5 likes", "score": 15.0}]},
        "linkedin": {"impressions_7d": "1,155", "posts": []},
        "threads": {"followers": "15 followers", "recent_views": "13.2K recent views", "posts": []},
        "bluesky": {"followers": "50 followers", "posts": []},
    }
    target = tmp_path / "references" / "voice-samples.md"

    async def fake_collect(cfg):
        return fake_data

    with patch("scripts.profile_audit.browser.alive", return_value=True), \
         patch("scripts.profile_audit.settings.load", return_value={}), \
         patch("scripts.profile_audit._collect_all_metrics", side_effect=fake_collect), \
         patch("scripts.profile_audit.ROOT", tmp_path):
        code = run_analytics(sync_samples=True)

    assert code == 0
    assert target.exists()
    assert "Winning X post" in target.read_text(encoding="utf-8")


def test_run_radar_offline_and_online(capsys):
    with patch("scripts.profile_audit.browser.alive", return_value=False):
        assert run_radar() == 1

    fake_items = [
        {"text": "Voice AI agent latency dropped to 400ms", "url": "https://x.com/builder/status/1", "metrics": "10 likes", "score": 30.0},
    ]

    async def fake_radar(limit=5, own_handle="Lordporus"):
        return fake_items

    with patch("scripts.profile_audit.browser.alive", return_value=True), \
         patch("scripts.profile_audit.settings.load", return_value={}), \
         patch("scripts.profile_audit._scrape_x_radar", side_effect=fake_radar):
        assert run_radar(limit=5) == 0

    captured = capsys.readouterr().out
    assert "Voice AI agent latency" in captured
