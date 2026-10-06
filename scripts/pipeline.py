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
except ImportError:
    import settings
    import due
    import generate
    import repurpose
    from browser_daemon import ensure_browser_running


def populate_daily_plan(plan: dict[str, Any], swipe_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Iterates through slots in a plan, generating topics, polymorphic drafts, and assets."""
    for idx, slot_data in enumerate(plan.get("slots", [])):
        # If text is already populated, skip overwriting
        if slot_data.get("text") and slot_data.get("platforms"):
            continue

        kind = slot_data.get("kind", "value")
        # Sub-slice swipe items so each slot gets distinct material
        item_slice = swipe_items[idx * 3: (idx + 1) * 3] if swipe_items else []
        topic = generate.generate_topic_from_items(kind, item_slice)

        poly_data = repurpose.repurpose_topic(
            topic_data=topic,
            date_str=plan.get("date"),
            generate_media=True,
            author=f"@{settings.load().get('handle', 'Lordporus')} • OmniPost",
        )

        slot_data["text"] = poly_data["x"]["text"]
        slot_data["headline"] = topic["headline"]
        slot_data["platforms"] = poly_data
        if poly_data["x"].get("media"):
            slot_data["image"] = poly_data["x"]["media"][0]

    return plan


def run_daily_pipeline(date_str: str | None = None) -> Path:
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
    updated_plan = populate_daily_plan(plan_data, swipe_items)

    plan_file.write_text(json.dumps(updated_plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[PIPELINE] Successfully generated and stored daily plan: {plan_file}")
    return plan_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Target date YYYY-MM-DD (defaults to today)")
    args = parser.parse_args()
    run_daily_pipeline(args.date)
