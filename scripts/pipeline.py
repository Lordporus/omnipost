"""Daily Autonomous Pipeline Orchestrator.

Orchestrates the entire daily preparation flow:
1. Ensures Edge browser daemon is active.
2. Harvests daily swipe intelligence via research.py.
3. Generates the jittered daily plan via due.py make-plan.
4. Generates tailored, voice-aligned polymorphic content for every slot.
5. Renders 16:9 infocard PNGs and 1080x1080 PDF carousels.
6. Writes the ready-to-publish draft plan to drafts/YYYY-MM-DD.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from scripts import settings
    from scripts import due
    from scripts import generate
    from scripts import repurpose
    from scripts.browser_daemon import ensure_browser_running
    from scripts.errors import DuplicateTopic, NoRelevantTopic, TopicRejected
    from scripts.llm import load_voice_profile
    from scripts.relevance import score_candidates
except ImportError:
    import settings
    import due
    import generate
    import repurpose
    from browser_daemon import ensure_browser_running
    from errors import DuplicateTopic, NoRelevantTopic, TopicRejected
    from llm import load_voice_profile
    from relevance import score_candidates


def _drop_candidate(
    candidates: list[dict[str, Any]],
    item: dict[str, Any] | None,
    voice_profile: str,
) -> None:
    """Remove the rejected item, or the highest-scoring accepted item."""
    if item is not None:
        for index, candidate in enumerate(candidates):
            if candidate is item or candidate == item:
                candidates.pop(index)
                return

    scored = score_candidates(candidates, voice_profile=voice_profile)
    accepted = sorted(
        [(candidate, result) for candidate, result in scored if result.accepted],
        key=lambda pair: pair[1].score,
        reverse=True,
    )
    if accepted:
        target = accepted[0][0]
        for index, candidate in enumerate(candidates):
            if candidate is target:
                candidates.pop(index)
                return
    if candidates:
        candidates.pop(0)


def populate_daily_plan(plan: dict[str, Any], swipe_items: list[dict[str, Any]], force: bool = False) -> dict[str, Any]:
    """Populate every empty slot with unique, relevant, voice-aligned content."""
    voice_profile = load_voice_profile()
    seen_content: set[str] = set()
    seen_bullets: set[str] = set()

    for idx, slot_data in enumerate(plan.get("slots", [])):
        # If text is already populated, skip overwriting unless force is True
        if not force and slot_data.get("text") and slot_data.get("platforms"):
            continue

        kind = slot_data.get("kind", "value")
        # Sub-slice swipe items so each slot gets distinct material.
        candidates = list(swipe_items[idx * 3: (idx + 1) * 3]) if swipe_items else []
        attempted_empty = False
        topic: dict[str, Any] | None = None
        content_hash = ""
        bullet_hash = ""
        rejections: list[str] = []
        duplicate_seen = False

        while candidates or not attempted_empty:
            attempted_empty = True
            try:
                topic = generate.generate_topic_from_items(
                    kind,
                    candidates,
                    voice_profile=voice_profile,
                )
            except TopicRejected as exc:
                title = str((exc.item or {}).get("title") or "unknown")[:80]
                rejections.append(f"{exc.reason}:{title}")
                print(
                    f"[PIPELINE] Rejected candidate for slot {slot_data.get('slot')}: "
                    f"{exc.reason} ({title})"
                )
                _drop_candidate(candidates, exc.item, voice_profile)
                continue
            except NoRelevantTopic as exc:
                rejections.append(str(exc))
                break

            content_hash = generate.content_fingerprint(topic)
            bullet_hash = generate.bullet_fingerprint(topic)
            if content_hash in seen_content or bullet_hash in seen_bullets:
                headline = str(topic.get("headline") or "")[:80]
                duplicate_seen = True
                rejections.append(f"duplicate_slot_content:{headline}")
                print(
                    f"[PIPELINE] Duplicate content rejected for slot {slot_data.get('slot')}: "
                    f"{headline}"
                )
                _drop_candidate(candidates, None, voice_profile)
                topic = None
                continue
            break

        if topic is None:
            date = plan.get("date") or "unknown-date"
            slot = slot_data.get("slot") or "unknown-slot"
            if duplicate_seen and not any(not item.startswith("duplicate_slot_content:") for item in rejections):
                raise DuplicateTopic(f"duplicate_slot_content: date={date} slot={slot}")
            reasons = "; ".join(rejections) or "no_candidates"
            raise NoRelevantTopic(
                f"no_publishable_candidate_for_slot: date={date} slot={slot} reasons={reasons}"
            )

        poly_data = repurpose.repurpose_topic(
            topic_data=topic,
            date_str=plan.get("date"),
            generate_media=True,
            author=f"@{settings.load().get('handle', 'Lordporus')} • OmniPost",
            slot=slot_data.get("slot"),
        )

        seen_content.add(content_hash)
        seen_bullets.add(bullet_hash)
        slot_data["text"] = poly_data["x"]["text"]
        slot_data["headline"] = topic["headline"]
        slot_data["platforms"] = poly_data
        slot_data["content_hash"] = content_hash
        if poly_data["x"].get("media"):
            slot_data["image"] = poly_data["x"]["media"][0]

    return plan


def run_daily_pipeline(date_str: str | None = None, force: bool = False) -> Path:
    """Executes the complete daily preparation pipeline."""
    target_date = date_str or datetime.now().strftime("%Y-%m-%d")
    print(f"[PIPELINE] Running daily autonomous pipeline for {target_date}...")

    # 1. Health check browser daemon
    ensure_browser_running()

    # 2. Collect swipe intelligence if missing
    swipe_items = generate.load_daily_swipe(target_date)
    if not swipe_items:
        print("[PIPELINE] Collecting fresh intelligence from HN, RSS, and tech feeds...")
        try:
            try:
                from scripts import research
            except ImportError:
                import research
            swipe_items = research.hn(points=100, hours=24)
        except Exception as exc:
            print(f"[PIPELINE] Swipe collection notice: {exc}")
            swipe_items = []

    # 3. Ensure plan exists
    plan_file = ROOT / "drafts" / f"{target_date}.json"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    if not plan_file.exists():
        print(f"[PIPELINE] Creating jittered slot plan for {target_date}...")
        due.make_plan(target_date)

    plan_data = json.loads(plan_file.read_text(encoding="utf-8"))

    # 4. Populate slots with polymorphic content & media
    print("[PIPELINE] Synthesizing polymorphic content and rendering media cards...")
    updated_plan = populate_daily_plan(plan_data, swipe_items, force=force)

    plan_file.write_text(json.dumps(updated_plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[PIPELINE] Successfully generated and stored daily plan: {plan_file}")
    return plan_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Target date YYYY-MM-DD (defaults to today)")
    parser.add_argument("--force", action="store_true", help="Force re-generation of all slots even if already populated")
    args = parser.parse_args()
    run_daily_pipeline(args.date, force=args.force)
