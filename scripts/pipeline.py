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
    from scripts import validator
    from scripts.browser_daemon import ensure_browser_running
    from scripts.errors import (
        CopyValidationError,
        DuplicateTopic,
        NoRelevantTopic,
        TopicRejected,
    )
    from scripts.llm import load_voice_profile, rhetorical_move_for
    from scripts.notify_webhook import dispatch_webhook
    from scripts.relevance import score_candidates
except ImportError:
    import settings
    import due
    import generate
    import repurpose
    import validator
    from browser_daemon import ensure_browser_running
    from errors import CopyValidationError, DuplicateTopic, NoRelevantTopic, TopicRejected
    from llm import load_voice_profile, rhetorical_move_for
    from notify_webhook import dispatch_webhook
    from relevance import score_candidates


HUMANITY_PLATFORMS = ("x", "bluesky", "threads", "linkedin")


def _humanity_violations(
    poly_data: dict[str, Any],
    active_platforms: set[str] | None = None,
) -> list[str]:
    """Gate every drafted platform. A broken scorer fails open, not closed."""
    active = active_platforms or set(HUMANITY_PLATFORMS)
    violations: list[str] = []
    for platform in HUMANITY_PLATFORMS:
        if platform not in active:
            continue
        text = ((poly_data or {}).get(platform) or {}).get("text") or ""
        if not text.strip():
            continue
        try:
            score, issues = validator.score_humanity(text)
        except Exception as exc:
            print(
                f"[PIPELINE] Humanity gate error on {platform}, failing open: {exc}",
                file=sys.stderr,
            )
            continue
        if score < validator.HUMANITY_THRESHOLD:
            violations.extend(f"{platform}: {issue}" for issue in issues)
    return violations


def _drop_slot(
    plan: dict[str, Any],
    slot_data: dict[str, Any],
    reason: str,
    violations: list[str],
) -> None:
    slot = str(slot_data.get("slot") or "unknown-slot")
    detail = "; ".join(violations)[:900]
    slot_data["skipped"] = reason
    print(f"[PIPELINE] Dropping slot {slot}: failed {reason} twice. {detail}")
    dispatch_webhook(
        event_type=f"{reason}_drop",
        title="OmniPost dropped a slot",
        message=(
            f"Slot {slot} on {plan.get('date')} failed {reason} twice. "
            "Nothing was published."
        ),
        metadata={"slot": slot, "date": plan.get("date"), "reason": reason, "violations": detail},
    )


def _guardrail_violations(
    poly_data: dict[str, Any],
    active_platforms: set[str] | None = None,
    cfg: dict | None = None,
    state: dict | None = None,
) -> list[str]:
    """Run the hard guardrails on every drafted platform, not just X."""
    active = active_platforms or set(HUMANITY_PLATFORMS)
    violations: list[str] = []
    for platform in HUMANITY_PLATFORMS:
        if platform not in active:
            continue
        plat = (poly_data or {}).get(platform) or {}
        if plat.get("enabled") is False:
            continue
        text = plat.get("text") or ""
        if not text.strip():
            continue
        ok, errs = validator.validate_draft_guardrails(
            draft={"text": text},
            cfg=cfg,
            state=state,
            platform=platform,
            raise_on_error=False,
            check_measured=False,
        )
        if not ok:
            violations.extend(f"{platform}: {err}" for err in errs)
    return violations


def _draft_violations(
    poly_data: dict[str, Any],
    active_platforms: set[str] | None = None,
) -> tuple[list[str], str]:
    """Humanity first (it owns the regenerate path), then the hard guardrails."""
    violations = _humanity_violations(poly_data, active_platforms)
    if violations:
        return violations, "humanity_gate"
    violations = _guardrail_violations(
        poly_data,
        active_platforms,
        cfg=settings.load(),
        state=due.load_state(),
    )
    return violations, ("guardrails" if violations else "")


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
    slot_order = [str(s.get("slot") or "") for s in plan.get("slots", [])]
    configured = settings.load().get("platforms") or {}
    active_platforms = {
        name for name, conf in configured.items() if (conf or {}).get("enabled", name == "x")
    } or set(HUMANITY_PLATFORMS)
    seen_content: set[str] = set()
    seen_bullets: set[str] = set()

    for idx, slot_data in enumerate(plan.get("slots", [])):
        # If text is already populated, skip overwriting unless force is True
        if not force and slot_data.get("text") and slot_data.get("platforms"):
            continue

        kind = slot_data.get("kind", "value")
        # Sub-slice swipe items so each slot gets distinct material, but allow falling back to full swipe pool
        slice_candidates = list(swipe_items[idx * 3: (idx + 1) * 3]) if swipe_items else []
        candidates = list(slice_candidates)
        pool_expanded = False
        attempted_empty = False
        topic: dict[str, Any] | None = None
        poly_data: dict[str, Any] | None = None
        dropped = False
        content_hash = ""
        bullet_hash = ""
        rejections: list[str] = []
        duplicate_seen = False

        while candidates or not attempted_empty or (swipe_items and not pool_expanded):
            if not candidates and not pool_expanded and swipe_items:
                # If the 3-item slice had no accepted candidates, expand search to all swipe items
                candidates = [c for c in swipe_items if c not in slice_candidates]
                pool_expanded = True
                if not candidates:
                    break
            attempted_empty = True
            try:
                topic = generate.generate_topic_from_items(
                    kind,
                    candidates,
                    voice_profile=voice_profile,
                    rhetorical_move=rhetorical_move_for(
                        plan.get("date"), slot_data.get("slot"), slot_order
                    ),
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
                if not pool_expanded and swipe_items:
                    candidates = [c for c in swipe_items if c not in slice_candidates]
                    pool_expanded = True
                    if candidates:
                        continue
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

            try:
                poly_data = repurpose.repurpose_topic(
                    topic_data=topic,
                    date_str=plan.get("date"),
                    generate_media=True,
                    author=f"@{settings.load().get('handle', 'Lordporus')} • OmniPost",
                    slot=slot_data.get("slot"),
                )
            except CopyValidationError as exc:
                headline = str(topic.get("headline") or "")[:80]
                rejections.append(f"copy_validation:{exc}")
                print(
                    f"[PIPELINE] Copy validation rejected candidate for slot "
                    f"{slot_data.get('slot')}: {exc} ({headline})"
                )
                _drop_candidate(candidates, None, voice_profile)
                topic = None
                poly_data = None
                continue

            violations, reason = _draft_violations(poly_data, active_platforms)
            if violations:
                print(
                    f"[PIPELINE] {reason} rejected slot {slot_data.get('slot')}, "
                    f"regenerating once: {violations}"
                )
                try:
                    topic = generate.generate_topic_from_items(
                        kind,
                        candidates,
                        voice_profile=voice_profile,
                        rhetorical_move=rhetorical_move_for(
                            plan.get("date"), slot_data.get("slot"), slot_order
                        ),
                        revise_feedback="\n".join(violations),
                    )
                    poly_data = repurpose.repurpose_topic(
                        topic_data=topic,
                        date_str=plan.get("date"),
                        generate_media=True,
                        author=f"@{settings.load().get('handle', 'Lordporus')} • OmniPost",
                        slot=slot_data.get("slot"),
                    )
                    content_hash = generate.content_fingerprint(topic)
                    bullet_hash = generate.bullet_fingerprint(topic)
                except Exception as exc:
                    print(
                        f"[PIPELINE] Regeneration failed for slot "
                        f"{slot_data.get('slot')}: {exc}"
                    )

                violations, reason = _draft_violations(poly_data, active_platforms)
                if violations:
                    _drop_slot(plan, slot_data, reason, violations)
                    topic = None
                    poly_data = None
                    dropped = True
                    break
            break

        if dropped:
            continue

        if topic is None or poly_data is None:
            date = plan.get("date") or "unknown-date"
            slot = slot_data.get("slot") or "unknown-slot"
            if duplicate_seen and not any(not item.startswith("duplicate_slot_content:") for item in rejections):
                raise DuplicateTopic(f"duplicate_slot_content: date={date} slot={slot}")
            reasons = "; ".join(rejections) or "no_candidates"
            raise NoRelevantTopic(
                f"no_publishable_candidate_for_slot: date={date} slot={slot} reasons={reasons}"
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
            swipe_items = research.hn(points=100, hours=24) or []
            try:
                rss_items, _ = research.rss(hours=48)
                swipe_items += (rss_items or [])
            except Exception as rss_err:
                print(f"[PIPELINE] RSS collection notice: {rss_err}")
        except Exception as exc:
            print(f"[PIPELINE] Swipe collection notice: {exc}")
            swipe_items = []

        if swipe_items:
            try:
                swipe_file = ROOT / "swipe" / f"{target_date}.json"
                swipe_file.parent.mkdir(parents=True, exist_ok=True)
                swipe_file.write_text(json.dumps(swipe_items, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

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
