"""Unified Command Line Interface for OmniPost V2.0.

Provides simple, human-friendly commands for all OmniPost operations:
  omnipost post              # Autonomously harvest, draft, and publish
  omnipost post --dry-run    # Preview generated post in terminal
  omnipost post --topic "..."# Turn a specific topic or URL into multi-platform posts
  omnipost doctor            # Check environment, browser, and accounts readiness
  omnipost setup             # Interactive setup and onboarding wizard
  omnipost browser start     # Launch automation browser session
  omnipost browser status    # Check browser CDP status and open tabs
  omnipost plan              # View or generate today's schedule plan
  omnipost daemon            # Run background scheduled autoposting
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))


def _cmd_post(args: argparse.Namespace) -> int:
    """Execute the flagship post workflow."""
    from scripts import due, generate, llm, publish_now, repurpose, settings, validator
    from scripts.browser_daemon import ensure_browser_running
    from scripts.platform_limits import LIMITS, count_for, validate

    cfg = settings.load()
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # 1. Custom text direct publish
    if args.text:
        return publish_now.main_with_args(
            text=args.text,
            dry_run=args.dry_run,
            platforms=args.platforms,
            force=args.force,
            allow_text_only=True,
        )

    # 2. Existing draft publish
    if args.draft:
        return publish_now.main_with_args(
            draft=args.draft,
            slot=args.slot,
            dry_run=args.dry_run,
            platforms=args.platforms,
            force=args.force,
            allow_text_only=True,
        )

    # 3. Custom Topic or Full Autonomous Harvest -> Draft -> Post
    print("=" * 60)
    print("OmniPost Autonomous Engine")
    print("=" * 60)

    if not args.dry_run:
        print("[1/4] Ensuring browser CDP automation is online...")
        ensure_browser_running()

    print("[2/4] Sourcing intelligence & selecting high-friction topic...")
    topic_data: dict[str, Any] | None = None
    voice_profile = llm.load_voice_profile()

    if args.topic:
        print(f"  -> Using custom topic input: {args.topic[:80]}...")
        topic_title = args.topic.strip()
        custom_item = {
            "title": topic_title[:120],
            "source": "custom_user_topic",
            "url": topic_title if topic_title.startswith(("http://", "https://")) else "https://omnipost.local",
            "score": 250,
            "summary": (
                f"Engineering analysis and practical production lessons on {topic_title}. "
                "How real-world systems fail, how to design resilience, and the architectural principles "
                "that actually work in high-scale production environments."
            ),
        }
        ok, res = llm.generate_topic_with_llm(
            items=[custom_item],
            kind="tech_insight",
            voice_profile=voice_profile,
        )
        if ok and isinstance(res, dict):
            topic_data = res
        else:
            print("  -> LLM generation offline or unavailable; applying deterministic synthesis...")
            try:
                topic_data = generate.generate_heuristic_topic("tech_insight", [custom_item])
            except Exception:
                topic_data = {
                    "headline": topic_title[:100],
                    "category": "TECH INSIGHT",
                    "body": (
                        f"Most teams approach {topic_title} from theoretical assumptions.\n\n"
                        "In production, distributed race conditions, missing timeout bounds, and "
                        "untracked state corruption quickly expose brittle designs."
                    ),
                    "points": [
                        "Never trust external I/O without strict timeouts and atomic retries.",
                        "Enforce deterministic state machines over unbounded heuristic loops.",
                        "Verify every step with live read-back verification before proceeding.",
                    ],
                    "takeaway": f"Robust engineering with {topic_title} comes down to verified state and fail-closed safety.",
                }
    else:
        # Autonomous discovery from swipe
        swipe_items = generate.load_daily_swipe(today)
        if not swipe_items:
            print("  -> Harvesting live intelligence from Hacker News & RSS feeds...")
            try:
                from scripts import research
                res_data = research.collect(hours=36, skip=("x", "reddit"))
                swipe_items = res_data.get("items", [])
                if swipe_items:
                    swipe_path = research.SWIPE / f"{today}.json"
                    swipe_path.parent.mkdir(parents=True, exist_ok=True)
                    swipe_path.write_text(json.dumps(res_data, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"  -> Harvested {len(swipe_items)} intelligence candidates from feeds.")
            except Exception as e:
                print(f"  -> Live harvest error ({e}), falling back to cached swipe...")
                swipe_items = []

        if not swipe_items:
            print("  -> No feed items available; utilizing high-friction builder patterns...")
            fallback_seed = {
                "title": "Why deterministic state machines beat unbounded LLM loops in production",
                "source": "curated_builder_signal",
                "url": "https://omnipost.local/patterns",
                "score": 300,
                "summary": (
                    "Why deterministic finite state machines beat unbounded LLM loops in production. "
                    "How real systems fail when agents loop without terminal states, and why explicit "
                    "state transition ledgers are required for multi-platform reliability."
                ),
            }
            swipe_items = [fallback_seed]

        print(f"  -> {len(swipe_items)} intelligence candidates evaluated.")
        # Pick best item passing viral friction score
        topic_data = generate.generate_topic_from_items(
            kind="tech_insight",
            items=swipe_items,
            use_llm=True,
            voice_profile=voice_profile,
        )

    if not topic_data:
        print("[FAIL] Failed to generate structured topic data.")
        return 1

    headline = str(topic_data.get("headline") or "High-Performance Engineering Architecture")
    body = str(topic_data.get("body") or "")
    points = topic_data.get("points") or []
    takeaway = str(topic_data.get("takeaway") or "")
    category = str(topic_data.get("category") or "TECH INSIGHT")

    print(f"\n[3/4] Synthesizing platform-native copy for '{headline}'...")
    raw_platforms = topic_data.get("platforms") or {}

    x_copy = raw_platforms.get("x") or topic_data.get("x") or repurpose.format_x(headline, body, points, takeaway)
    bsky_copy = raw_platforms.get("bluesky") or topic_data.get("bluesky") or repurpose.format_bluesky(headline, body, points, takeaway)
    li_copy = raw_platforms.get("linkedin") or topic_data.get("linkedin") or repurpose.format_linkedin(headline, body, points, takeaway)
    threads_copy = raw_platforms.get("threads") or topic_data.get("threads")
    if not threads_copy or count_for("threads", str(threads_copy)) < 250:
        try:
            threads_copy = repurpose.format_threads(headline, takeaway, body, points)
        except Exception:
            threads_copy = str(threads_copy or f"{headline}\n\n{body[:250]}\n\n{takeaway}")

    # Validate and fit limits
    draft_payload = {
        "slot": args.slot or "manual",
        "headline": headline,
        "topic": topic_data,
        "platforms": {
            "x": {"enabled": True, "text": x_copy, "media": [], "media_type": "image"},
            "bluesky": {"enabled": True, "text": bsky_copy, "media": [], "media_type": "image", "tag_source": "category"},
            "linkedin": {"enabled": True, "text": li_copy, "media": [], "media_type": "image", "tag_source": "category"},
            "threads": {"enabled": True, "text": threads_copy, "media": [], "media_type": "image"},
        },
    }

    # Save to active draft file
    draft_file = ROOT / "drafts" / f"{today}_live.json"
    draft_file.parent.mkdir(parents=True, exist_ok=True)
    draft_file.write_text(json.dumps(draft_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Display preview table
    print("\n" + "=" * 60)
    print("Content Preview & Humanity Gate")
    print("=" * 60)
    for p_name in ("x", "bluesky", "threads", "linkedin"):
        text = draft_payload["platforms"][p_name]["text"]
        cnt = count_for(p_name, text)
        lim = LIMITS[p_name]
        try:
            validate(p_name, text)
            valid_str = "VALID"
        except Exception as e:
            valid_str = f"INVALID ({e})"
        h_score, _ = validator.score_humanity(text, platform=p_name)
        print(f"[{p_name.upper():<8}] {cnt:>4}/{lim['max']} units | Humanity: {h_score}/100 | {valid_str}")
        print("-" * 60)
        print(text[:280] + ("..." if len(text) > 280 else ""))
        print("-" * 60)

    if args.dry_run:
        print("\n[DRY RUN] Simulation complete. No posts were published.")
        print(f"Draft saved to: {draft_file}")
        return 0

    print("\n[4/4] Broadcasting live to all connected platforms...")
    return publish_now.main_with_args(
        draft=str(draft_file),
        slot=args.slot,
        platforms=args.platforms,
        force=args.force,
        allow_text_only=True,
    )


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Run system diagnostics."""
    from scripts import doctor
    argv = []
    if getattr(args, "live", True):
        argv.append("--live")
    if getattr(args, "json", False):
        argv.append("--json")
    if getattr(args, "healthcheck", False):
        argv.append("--healthcheck")
    return doctor.main(argv)


def _cmd_setup(args: argparse.Namespace) -> int:
    """Run interactive setup wizard."""
    from scripts import wizard
    return wizard.main()


def _cmd_browser(args: argparse.Namespace) -> int:
    """Manage automation browser session."""
    import urllib.request
    from scripts import browser_daemon, settings

    cfg = settings.get_browser_config()
    port = cfg.get("port", 9444)
    raw_action = getattr(args, "action", "status")
    action = "status" if raw_action in ("status", "info") else ("close" if raw_action in ("close", "stop") else "start")

    if action == "start":
        print(f"Starting browser on port {port}...")
        ok = browser_daemon.ensure_browser_running()
        if ok:
            print(f"[OK] Browser is online and listening on http://127.0.0.1:{port}")
            return 0
        print("[FAIL] Failed to start browser. Run 'omnipost doctor' for diagnostics.")
        return 1

    elif action == "status":
        running = browser_daemon.is_browser_running(port=port)
        if not running:
            print(f"[OFFLINE] No browser is currently listening on port {port}.")
            print("Run 'omnipost browser start' to launch it.")
            return 1
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3) as resp:
                v_data = json.loads(resp.read().decode())
                print(f"[ONLINE] {v_data.get('Browser')} is active on port {port}.")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3) as resp:
                tabs = json.loads(resp.read().decode())
                pages = [t for t in tabs if t.get("type") == "page"]
                print(f"Open pages ({len(pages)}):")
                for p in pages:
                    print(f"  • {p.get('title', 'Untitled')} -> {p.get('url')}")
            return 0
        except Exception as e:
            print(f"[WARN] Port {port} responded, but error querying CDP: {e}")
            return 1

    elif action == "close":
        print(f"Stopping browser processes on port {port}...")
        browser_daemon.stop_browser_processes(port=port)
        print("[OK] Closed.")
        return 0

    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    """Show or generate daily schedule plan."""
    from scripts import due
    if getattr(args, "make", False):
        argv = ["make-plan"]
        if args.date:
            argv.extend(["--date", args.date])
        return due.main(argv) or 0
    argv = ["show"]
    if args.date:
        argv.extend(["--date", args.date])
    return due.main(argv) or 0


def _cmd_daemon(args: argparse.Namespace) -> int:
    """Run continuous scheduled autoposting daemon."""
    from scripts import autoposter
    print("Starting OmniPost continuous scheduler daemon...")
    return autoposter.main()


def build_parser() -> argparse.ArgumentParser:
    """Build the root argument parser."""
    parser = argparse.ArgumentParser(
        prog="omnipost",
        description="Autonomous Multi-Platform Thought Leadership Engine for Builders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # post
    p_post = subparsers.add_parser("post", help="Harvest, synthesize, and publish a post across platforms")
    p_post.add_argument("--dry-run", action="store_true", help="Simulate generation and preview in terminal without publishing")
    p_post.add_argument("--topic", help="Custom topic, seed idea, or URL to synthesize into multi-platform posts")
    p_post.add_argument("--text", help="Uniform text to publish directly")
    p_post.add_argument("--draft", help="Path to draft JSON file to publish")
    p_post.add_argument("--slot", help="Time slot identifier (e.g. 13:00)")
    p_post.add_argument("--platforms", help="Comma-separated platforms to target (e.g. x,linkedin,bluesky,threads)")
    p_post.add_argument("--archetype", choices=["war_story", "contrarian", "framework"], help="Content archetype")
    p_post.add_argument("--force", action="store_true", help="Override idempotency reservations")
    p_post.set_defaults(func=_cmd_post)

    # drop (alias for post)
    p_drop = subparsers.add_parser("drop", help="Alias for 'post'")
    p_drop.add_argument("--dry-run", action="store_true")
    p_drop.add_argument("--topic")
    p_drop.add_argument("--text")
    p_drop.add_argument("--draft")
    p_drop.add_argument("--slot")
    p_drop.add_argument("--platforms")
    p_drop.add_argument("--archetype", choices=["war_story", "contrarian", "framework"], help="Content archetype")
    p_drop.add_argument("--force", action="store_true")
    p_drop.set_defaults(func=_cmd_post)

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Check system readiness, environment, and browser credentials")
    p_doc.add_argument("--no-live", dest="live", action="store_false", help="Skip live network and CDP probes")
    p_doc.add_argument("--json", action="store_true", help="Output JSON results")
    p_doc.add_argument("--healthcheck", action="store_true", help="Exit code 1 if any check fails")
    p_doc.set_defaults(func=_cmd_doctor)

    # setup
    p_setup = subparsers.add_parser("setup", help="Interactive setup and credential onboarding wizard")
    p_setup.set_defaults(func=_cmd_setup)

    # browser
    p_browser = subparsers.add_parser("browser", help="Manage automation browser session and CDP port")
    p_browser.add_argument("action", choices=["start", "status", "info", "close", "stop"], help="Browser action")
    p_browser.set_defaults(func=_cmd_browser)

    # plan
    p_plan = subparsers.add_parser("plan", help="View or generate today's schedule plan")
    p_plan.add_argument("--date", help="Target date YYYY-MM-DD")
    p_plan.add_argument("--make", "--make-plan", dest="make", action="store_true", help="Generate or regenerate the plan for date")
    p_plan.set_defaults(func=_cmd_plan)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run the continuous scheduler autoposter service")
    p_daemon.set_defaults(func=_cmd_daemon)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI Entrypoint dispatcher."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        print("\n[CANCELLED] Operation aborted by user.")
        return 130
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
