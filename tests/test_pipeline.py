import json
from pathlib import Path
from unittest.mock import patch, MagicMock
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
    def fake_gen(kind, items, voice_profile=None, rhetorical_move=None):
        from scripts.llm import RHETORICAL_MOVES

        assert rhetorical_move in RHETORICAL_MOVES
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


SLOP_DRAFT = "In today's fast-paced world, we delve into the tapestry of innovation and leverage it."
GOOD_DRAFT = "We cut latency from 11 seconds to 3. The fix was one index. No rewrite."


def _poly(text):
    return {
        "x": {"text": text, "enabled": True},
        "bluesky": {"text": text, "enabled": True},
        "linkedin": {"text": text, "enabled": True},
        "threads": {"text": text, "enabled": True},
    }


TOPIC = {
    "headline": "Ledger Index Cut Latency",
    "body": "One index replaced a table scan.",
    "points": ["Add the index", "Measure again"],
    "takeaway": "Measure before rewriting",
    "category": "TECH",
}


def _one_slot_plan():
    return {
        "date": "2026-10-06",
        "slots": [{"slot": "13:00", "kind": "value", "text": "", "due_at": "2026-10-06T13:15:00"}],
    }


def test_humanity_gate_regenerates_once_then_publishes():
    with patch("scripts.pipeline.generate.generate_topic_from_items", return_value=TOPIC) as mock_gen, \
         patch("scripts.pipeline.repurpose.repurpose_topic", side_effect=[_poly(SLOP_DRAFT), _poly(GOOD_DRAFT)]), \
         patch("scripts.pipeline.dispatch_webhook") as mock_alert:
        updated = populate_daily_plan(_one_slot_plan(), swipe_items=[{"title": "Ledger", "score": 100}])

    assert updated["slots"][0]["text"] == GOOD_DRAFT
    assert mock_gen.call_args.kwargs["revise_feedback"]
    assert mock_alert.call_count == 0


def test_humanity_gate_drops_slot_after_two_failures():
    with patch("scripts.pipeline.generate.generate_topic_from_items", return_value=TOPIC), \
         patch("scripts.pipeline.repurpose.repurpose_topic", return_value=_poly(SLOP_DRAFT)), \
         patch("scripts.pipeline.dispatch_webhook") as mock_alert:
        updated = populate_daily_plan(_one_slot_plan(), swipe_items=[{"title": "Ledger", "score": 100}])

    assert updated["slots"][0]["skipped"] == "humanity_gate"
    assert updated["slots"][0]["text"] == ""
    assert mock_alert.call_count == 1
    assert mock_alert.call_args.kwargs["event_type"] == "humanity_gate_drop"

