import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from scripts.pipeline import run_daily_pipeline, populate_daily_plan


def test_populate_daily_plan_fills_empty_slots():
    plan_data = {
        "date": "2026-10-06",
        "slots": [
            {"slot": "13:00", "kind": "value", "text": "", "due_at": "2026-10-06T13:15:00"},
            {"slot": "16:00", "kind": "ai_update", "text": "", "due_at": "2026-10-06T16:20:00"},
        ]
    }
    sample_topics = [
        {
            "headline": "Autonomous Engineering",
            "body": "System details",
            "points": ["Point A", "Point B"],
            "takeaway": "Takeaway C",
            "category": "TECH",
        },
        {
            "headline": "Distributed Database Latency",
            "body": "Different system details",
            "points": ["Point D", "Point E"],
            "takeaway": "Takeaway F",
            "category": "TECH",
        },
    ]
    with patch("scripts.generate.generate_topic_from_items", side_effect=sample_topics), \
         patch("scripts.repurpose.repurpose_topic") as mock_repurpose:
        mock_repurpose.return_value = {
            "x": {"text": "X text", "enabled": True},
            "bluesky": {"text": "Bsky text", "enabled": True},
            "linkedin": {"text": "LI text", "enabled": True},
            "threads": {"text": "Threads text", "enabled": True},
        }
        updated = populate_daily_plan(plan_data, swipe_items=[])
        assert updated["slots"][0]["text"] == "X text"
        assert "platforms" in updated["slots"][0]
        assert updated["slots"][0]["platforms"]["bluesky"]["text"] == "Bsky text"


def test_populate_daily_plan_skips_already_populated_slots():
    plan_data = {
        "date": "2026-10-06",
        "slots": [
            {
                "slot": "13:00",
                "kind": "value",
                "text": "Already populated text",
                "platforms": {"x": {"text": "Already populated text"}},
                "due_at": "2026-10-06T13:15:00"
            }
        ]
    }
    with patch("scripts.generate.generate_topic_from_items") as mock_gen:
        updated = populate_daily_plan(plan_data, swipe_items=[])
        mock_gen.assert_not_called()
        assert updated["slots"][0]["text"] == "Already populated text"


def test_run_daily_pipeline(tmp_path):
    target_date = "2026-10-07"
    fake_plan = {
        "date": target_date,
        "slots": [
            {"slot": "13:00", "kind": "value", "text": "", "due_at": f"{target_date}T13:15:00"}
        ]
    }

    with patch("scripts.pipeline.ROOT", tmp_path), \
         patch("scripts.pipeline.ensure_browser_running") as mock_browser, \
         patch("scripts.generate.load_daily_swipe", return_value=[{"title": "News Item", "score": 100}]), \
         patch("scripts.due.make_plan") as mock_make_plan, \
         patch("scripts.pipeline.populate_daily_plan") as mock_populate:

        # Set up drafts directory in tmp_path
        drafts_dir = tmp_path / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        plan_file = drafts_dir / f"{target_date}.json"

        def fake_make_plan(d):
            plan_file.write_text(json.dumps(fake_plan), encoding="utf-8")
            return fake_plan

        mock_make_plan.side_effect = fake_make_plan

        def fake_populate(plan, items, force=False):
            plan["slots"][0]["text"] = "Populated text"
            return plan

        mock_populate.side_effect = fake_populate

        out_path = run_daily_pipeline(target_date)

        assert mock_browser.called
        assert out_path == plan_file
        assert out_path.exists()
        saved = json.loads(out_path.read_text(encoding="utf-8"))
        assert saved["slots"][0]["text"] == "Populated text"


def test_run_daily_pipeline_harvests_swipe_if_empty(tmp_path):
    target_date = "2026-10-08"
    fake_plan = {
        "date": target_date,
        "slots": [
            {"slot": "13:00", "kind": "value", "text": "", "due_at": f"{target_date}T13:15:00"}
        ]
    }

    with patch("scripts.pipeline.ROOT", tmp_path), \
         patch("scripts.pipeline.ensure_browser_running"), \
         patch("scripts.generate.load_daily_swipe", return_value=[]), \
         patch("scripts.research.hn", return_value=[{"title": "HN Item", "score": 150}]) as mock_hn, \
         patch("scripts.research.rss", return_value=([], {})), \
         patch("scripts.due.make_plan") as mock_make_plan, \
         patch("scripts.pipeline.populate_daily_plan") as mock_populate:

        drafts_dir = tmp_path / "drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        plan_file = drafts_dir / f"{target_date}.json"

        def fake_make_plan(d):
            plan_file.write_text(json.dumps(fake_plan), encoding="utf-8")
            return fake_plan

        mock_make_plan.side_effect = fake_make_plan
        mock_populate.return_value = fake_plan

        out_path = run_daily_pipeline(target_date)

        assert mock_hn.called
        assert out_path == plan_file


@pytest.mark.parametrize("failed_source", ["hn", "rss", None])
def test_swipe_sources_are_independent(tmp_path, failed_source):
    date = "2026-10-08"
    hn_items = [{"title": "HN item"}]
    rss_items = [{"title": "RSS item"}]
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    plan = {"date": date, "slots": []}
    (drafts / f"{date}.json").write_text(json.dumps(plan), encoding="utf-8")

    with patch("scripts.pipeline.ROOT", tmp_path), \
         patch("scripts.pipeline.ensure_browser_running"), \
         patch("scripts.generate.load_daily_swipe", return_value=[]), \
         patch("scripts.research.hn", return_value=hn_items,
               side_effect=RuntimeError("HN unavailable") if failed_source == "hn" else None) as hn, \
         patch("scripts.research.rss", return_value=(rss_items, {}),
               side_effect=RuntimeError("RSS unavailable") if failed_source == "rss" else None) as rss, \
         patch("scripts.pipeline.populate_daily_plan", return_value=plan) as populate:
        run_daily_pipeline(date)

    hn.assert_called_once_with(points=100, hours=24)
    rss.assert_called_once_with(hours=48)
    expected = ([] if failed_source == "hn" else [{"title": "HN item"}])
    expected += [] if failed_source == "rss" else rss_items
    assert populate.call_args.args[1] == expected
    saved = json.loads((tmp_path / "swipe" / f"{date}.json").read_text(encoding="utf-8"))
    assert saved == expected


def test_populate_daily_plan_expands_pool_when_initial_slice_fails():
    from scripts.errors import NoRelevantTopic
    plan_data = {
        "date": "2026-10-06",
        "slots": [
            {"slot": "13:00", "kind": "value", "text": "", "due_at": "2026-10-06T13:15:00"},
        ]
    }
    swipe_items = [
        {"title": "Politics News 1", "score": 10},
        {"title": "Politics News 2", "score": 10},
        {"title": "Politics News 3", "score": 10},
        {"title": "Postgres Internals Deep Dive", "score": 200},
    ]
    def fake_gen(kind, items, voice_profile=None):
        if len(items) == 3:
            raise NoRelevantTopic("no_relevant_items in slice")
        return {
            "headline": "Postgres Internals Deep Dive",
            "body": "System details",
            "points": ["Point A", "Point B"],
            "takeaway": "Takeaway C",
            "category": "TECH",
        }

    with patch("scripts.generate.generate_topic_from_items", side_effect=fake_gen), \
         patch("scripts.repurpose.repurpose_topic") as mock_repurpose:
        mock_repurpose.return_value = {
            "x": {"text": "Postgres deep dive on X", "enabled": True},
            "bluesky": {"text": "Postgres deep dive on Bsky", "enabled": True},
            "linkedin": {"text": "LI text", "enabled": True},
            "threads": {"text": "Threads text", "enabled": True},
        }
        updated = populate_daily_plan(plan_data, swipe_items=swipe_items)
        assert updated["slots"][0]["text"] == "Postgres deep dive on X"


def test_due_returns_unpopulated_slot_within_lag():
    from scripts import due
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    due_at = (now - timedelta(minutes=15)).isoformat()
    mock_plan = {
        "date": now.strftime("%Y-%m-%d"),
        "slots": [
            {"slot": "13:00", "kind": "value", "text": "", "due_at": due_at}
        ]
    }
    with patch("scripts.due._load_plans", return_value=[(Path("drafts/test.json"), mock_plan)]), \
         patch("scripts.due.load_state", return_value={}):
        res = due.due()
        assert res is not None
        assert res["slot"] == "13:00"
        assert res["text"] == ""


@pytest.mark.parametrize("reverse_order", [False, True])
def test_due_prefers_oldest_eligible_populated_slot_and_keeps_empty_fallback(tmp_path, reverse_order):
    from scripts import due
    from datetime import datetime, timezone, timedelta

    now = datetime(2026, 10, 8, 15, tzinfo=timezone.utc)
    slots = [
        {"slot": name, "kind": "value", "text": text,
         "due_at": (now - timedelta(minutes=minutes)).isoformat()}
        for name, text, minutes in (
            ("empty", "", 60),
            ("blocked", "blocked text", 50),
            ("ready", "oldest ready text", 40),
            ("later", "later ready text", 20),
            ("later-empty", "", 10),
        )
    ]
    if reverse_order:
        slots.reverse()
    plan = {"date": "2026-10-08", "slots": slots}

    def guardrails(draft, **kwargs):
        return (draft["slot"] != "blocked", [])

    with patch("scripts.due._load_plans", return_value=[(tmp_path / "plan.json", plan)]), \
         patch("scripts.due.load_state", return_value={}), \
         patch("scripts.due._posted_slots", return_value=set()), \
         patch("scripts.due.now_tz", return_value=now), \
         patch("scripts.due.settings.load", return_value={}), \
         patch("scripts.due.validator.validate_draft_guardrails", side_effect=guardrails):
        # Generation for the older empty slot cannot hold back ready drafts.
        assert due.due()["slot"] == "ready"
        next(slot for slot in slots if slot["slot"] == "ready")["posted"] = True
        assert due.due()["slot"] == "later"
        next(slot for slot in slots if slot["slot"] == "later")["posted"] = True
        # Once ready work is drained, request generation for the oldest empty slot.
        assert due.due()["slot"] == "empty"
