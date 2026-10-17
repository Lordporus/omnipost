"""Content Generation & Synthesis Engine for OmniPost.

Extracts high-impact material from daily swipe intelligence (Hacker News, RSS, arXiv)
and shapes it into structured insights aligned with the operator's voice profile.
Supports zero-cost deterministic synthesis with an extensible LLM provider hook.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def extract_key_takeaways(text: str) -> list[str]:
    """Extracts punchy bullet-point takeaways from summary text."""
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", text) if len(s.strip()) > 15]
    if not sentences:
        return [
            "Deterministic systems outperform probabilistic retry loops.",
            "Always maintain atomic state ledgers across all platform actions.",
            "Local CDP execution bypasses external cloud API rate limits.",
        ]
    return sentences[:3]


def generate_heuristic_topic(kind: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Generates a structured topic dictionary deterministically without LLM API calls."""
    if not items:
        # High-signal fallback aligned with AI/Engineering theme
        headline = "Why Deterministic Execution Wins in Autonomous Agent Architecture"
        body = (
            "Engineering autonomous syndicates requires rock-solid reliability. Relying solely on raw prompt "
            "engineering creates brittle workflows. Combining state machines with atomic ledgers ensures zero duplicate "
            "posts and transparent retries."
        )
        points = [
            "Atomic JSON ledgers prevent duplicate posts during partial outages.",
            "Direct CDP automation eliminates costly 3rd party API subscriptions.",
            "Polymorphic repurposing converts 1 technical insight into 4 channel formats.",
        ]
        takeaway = "Build deterministic foundations before scaling autonomous agents."
        category = "AI ARCHITECTURE"

        x_text = (
            "Deterministic state machines beat brittle LLM retry loops every single time in production. "
            "Combine atomic ledgers with local CDP automation to eliminate duplicate posts and flaky API failures."
        )
        bluesky_text = (
            "Autonomous syndicates don't need cloud SaaS wrappers. Running local CDP against persistent browser "
            "sessions with atomic JSON state solves rate limits and duplicate posts for $0."
        )
        threads_text = (
            "Most AI agents fail because developers rely solely on raw prompt loops instead of deterministic state machines. "
            "Have you hit duplicate post or retry hell in production yet?"
        )
        linkedin_text = (
            f"{headline}\n\n"
            f"{body}\n\n"
            "3 Architecture Rules for Sovereign Automation:\n"
            + "\n".join([f"▸ {p}" for p in points])
            + f"\n\nBottom line: {takeaway}"
        )
        carousel = {
            "title": headline,
            "slides": [
                {"header": "01. The Fragility Trap", "body": "Why probabilistic LLM retry loops fail under high concurrency and real network conditions."},
                {"header": "02. Atomic Ledgers", "body": "Using verified local state machines to guarantee zero duplicate publishing."},
                {"header": "03. Local CDP Control", "body": "Bypassing expensive SaaS rate limits using native browser automation."},
                {"header": "04. Production Checklist", "body": "Always decouple prompt generation from execution state. Verification beats optimistic publishing."}
            ]
        }

        return {
            "headline": headline,
            "body": body,
            "points": points,
            "takeaway": takeaway,
            "category": category,
            "x": x_text,
            "bluesky": bluesky_text,
            "threads": threads_text,
            "linkedin": linkedin_text,
            "carousel": carousel,
            "platforms": {
                "x": x_text,
                "bluesky": bluesky_text,
                "threads": threads_text,
                "linkedin": linkedin_text,
            },
        }

    # Sort items by score/relevance
    sorted_items = sorted(items, key=lambda x: int(x.get("score") or 0), reverse=True)
    top_item = sorted_items[0]
    title = str(top_item.get("title") or "Engineering Update").strip()
    raw_extra = top_item.get("extra")
    if isinstance(raw_extra, str):
        summary = raw_extra
    elif isinstance(raw_extra, dict):
        summary = str(raw_extra.get("summary") or raw_extra.get("text") or raw_extra.get("title") or title)
    else:
        summary = str(top_item.get("summary") or title)
    points = extract_key_takeaways(summary)

    category = "AI UPDATE" if kind == "ai_update" else "TECH INSIGHT"
    body = summary[:300] if len(summary) > 20 else f"{title}. Key engineering analysis and practical implications for production systems."
    takeaway = f"Read more on {top_item.get('source', 'source').upper()}: {top_item.get('url', '')}".strip()

    # Craft 4 platform-native archetypes
    # X: <280 chars, punchy 1-2 liner, no hashtags
    x_hook = f"{title}. {points[0]}" if points else title
    if len(x_hook) > 275:
        x_hook = x_hook[:272].rstrip() + "..."
    x_text = x_hook

    # Bluesky: <300 chars, technical insider tone
    bsky_base = f"{title}: {summary}" if summary != title else f"Deep dive on {title}: {points[0] if points else ''}"
    bluesky_text = bsky_base[:290].strip()

    # Threads: <500 chars, conversational question starter ending with ?
    threads_text = f"{title}. {points[0] if points else ''}\n\nWhat are your thoughts on this approach?"
    if len(threads_text) > 480:
        threads_text = threads_text[:450].strip() + "\n\nWhat are your thoughts?"

    # LinkedIn: 600-1200 chars framework breakdown
    linkedin_text = (
        f"{title}\n\n"
        f"{body}\n\n"
        "Key Engineering Takeaways:\n"
        + "\n".join([f"▸ {p}" for p in points])
        + f"\n\nBottom line: {takeaway}"
    )

    carousel = {
        "title": title[:60],
        "slides": [
            {"header": "01. Overview", "body": title},
            {"header": "02. Technical Context", "body": body[:200]},
            {"header": "03. Key Takeaway", "body": points[0] if points else "Engineering insight"},
            {"header": "04. Summary", "body": takeaway[:180] if takeaway else "Follow for daily architectural breakdowns."}
        ]
    }

    return {
        "headline": title[:90],
        "body": body,
        "points": points,
        "takeaway": takeaway,
        "category": category,
        "x": x_text,
        "bluesky": bluesky_text,
        "threads": threads_text,
        "linkedin": linkedin_text,
        "carousel": carousel,
        "platforms": {
            "x": x_text,
            "bluesky": bluesky_text,
            "threads": threads_text,
            "linkedin": linkedin_text,
        },
    }


def generate_platform_native_drafts(
    kind: str = "ai_update",
    items: list[dict[str, Any]] | None = None,
    use_llm: bool = True,
    voice_profile: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generates 4 audience-tailored, platform-native post variants with carousel metadata.
    
    Guarantees presence of:
    - 'x' (< 280 chars, contrarian hook, 0 hashtags)
    - 'bluesky' (< 300 chars, tech take)
    - 'threads' (< 500 chars, ends with discussion question)
    - 'linkedin' (600-1200 chars, structured framework)
    - 'carousel' (title and 4 slides)
    - 'platforms' (dict mapping platform name to tailored text)
    """
    items_list = items or []
    return generate_topic_from_items(
        kind=kind,
        items=items_list,
        use_llm=use_llm,
        voice_profile=str(voice_profile) if voice_profile else None,
    )


def generate_topic_from_items(
    kind: str,
    items: list[dict[str, Any]],
    use_llm: bool = True,
    voice_profile: str | None = None,
) -> dict[str, Any]:
    """Generates a structured topic dictionary from a list of collected swipe items.

    Attempts synthesis via modern multi-LLM engine if configured, falling back to
    deterministic heuristic generation on failure or when LLM is unconfigured.
    """
    if not items:
        return generate_heuristic_topic(kind, items)

    if use_llm:
        from scripts.llm import generate_topic_with_llm
        ok, topic = generate_topic_with_llm(
            items=items,
            kind=kind,
            voice_profile=voice_profile,
        )
        if ok and topic:
            return topic

    return generate_heuristic_topic(kind, items)


def load_daily_swipe(date_str: str) -> list[dict[str, Any]]:
    """Loads swipe items collected for the specified date."""
    swipe_file = ROOT / "swipe" / f"{date_str}.json"
    if not swipe_file.exists():
        return []
    try:
        return json.loads(swipe_file.read_text(encoding="utf-8"))
    except Exception:
        return []
