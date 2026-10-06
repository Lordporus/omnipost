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


def generate_topic_from_items(kind: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Generates a structured topic dictionary from a list of collected swipe items."""
    if not items:
        # High-signal fallback aligned with AI/Engineering theme
        return {
            "headline": "Why Deterministic Execution Wins in Autonomous Agent Architecture",
            "body": "Engineering autonomous syndicates requires rock-solid reliability. Relying solely on raw prompt engineering creates brittle workflows. Combining state machines with atomic ledgers ensures zero duplicate posts and transparent retries.",
            "points": [
                "Atomic JSON ledgers prevent duplicate posts during partial outages.",
                "Direct CDP automation eliminates costly 3rd party API subscriptions.",
                "Polymorphic repurposing converts 1 technical insight into 4 channel formats.",
            ],
            "takeaway": "Build deterministic foundations before scaling autonomous agents.",
            "category": "AI ARCHITECTURE",
        }

    # Sort items by score/relevance
    sorted_items = sorted(items, key=lambda x: int(x.get("score") or 0), reverse=True)
    top_item = sorted_items[0]
    title = str(top_item.get("title") or "Engineering Update")
    raw_extra = top_item.get("extra")
    if isinstance(raw_extra, str):
        summary = raw_extra
    elif isinstance(raw_extra, dict):
        summary = str(raw_extra.get("summary") or raw_extra.get("text") or raw_extra.get("title") or title)
    else:
        summary = str(top_item.get("summary") or title)
    points = extract_key_takeaways(summary)

    category = "AI UPDATE" if kind == "ai_update" else "TECH INSIGHT"

    return {
        "headline": title[:90],
        "body": summary[:300] if len(summary) > 20 else f"{title}. Key engineering analysis and practical implications for production systems.",
        "points": points,
        "takeaway": f"Read more on {top_item.get('source', 'source').upper()}: {top_item.get('url', '')}".strip(),
        "category": category,
    }


def load_daily_swipe(date_str: str) -> list[dict[str, Any]]:
    """Loads swipe items collected for the specified date."""
    swipe_file = ROOT / "swipe" / f"{date_str}.json"
    if not swipe_file.exists():
        return []
    try:
        return json.loads(swipe_file.read_text(encoding="utf-8"))
    except Exception:
        return []
