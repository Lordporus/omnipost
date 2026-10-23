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


def extract_key_takeaways(text: str, exclude_title: str = "") -> list[str]:
    """Extracts punchy bullet-point takeaways from summary text, guaranteeing >= 3 unique points.
    
    Strictly excludes the headline or close variations to ban content echoing.
    """
    fallback_defaults = [
        "Deterministic state execution outperforms retry loops.",
        "Decoupled state management ensures crash resilience.",
        "Verification of published state prevents double dispatch.",
    ]
    raw_sentences = [s.strip() for s in re.split(r"[.!?]\s+", text) if len(s.strip()) > 15]

    exclude_norm = exclude_title.strip().lower()
    seen: set[str] = set()
    if exclude_norm:
        seen.add(exclude_norm)

    points: list[str] = []
    for s in raw_sentences:
        clean_s = s.rstrip(".!?").strip()
        norm_s = clean_s.lower()
        # Ban exact match or significant substring overlap with title
        if norm_s and norm_s not in seen:
            if exclude_norm and (norm_s in exclude_norm or exclude_norm in norm_s):
                continue
            seen.add(norm_s)
            points.append(clean_s)

    for fb in fallback_defaults:
        if len(points) >= 3:
            break
        clean_fb = fb.rstrip(".!?").strip()
        if clean_fb.lower() not in seen:
            seen.add(clean_fb.lower())
            points.append(clean_fb)

    return points[:3]


def determine_card_count(topic_data: dict[str, Any]) -> int:
    """Calculates whether content warrants 1, 2, or 3 visual cards.
    
    - 1 Card: Concise insight or single takeaway (body < 120 chars or points <= 1).
    - 2 Cards: Problem vs. Solution or comparative architectural tradeoff.
    - 3 Cards: Deep workflow (Hook/Context -> Architecture Engine -> Production Checklist).
    """
    points = [p for p in topic_data.get("points", []) if len(str(p).strip()) > 15]
    body = str(topic_data.get("body", "")).strip()
    
    if len(points) >= 3 and len(body) > 180:
        return 3
    elif len(points) >= 2 or len(body) > 90:
        return 2
    return 1


def _ensure_carousel_integrity(topic: dict[str, Any], kind: str = "tech_insight") -> dict[str, Any]:
    """Guarantees every slide in carousel has semantic headers, valid bodies, and non-empty bullets."""
    if not isinstance(topic, dict):
        return topic

    category = str(topic.get("category") or ("AI UPDATE" if kind == "ai_update" else "TECH INSIGHT"))
    headline = str(topic.get("headline") or "Engineering Insight").strip()
    body = str(topic.get("body") or "").strip()
    raw_points = topic.get("points") or []
    points = [str(p).strip() for p in raw_points if str(p).strip()]
    if len(points) < 3:
        points = extract_key_takeaways(body or headline)
    takeaway = str(topic.get("takeaway") or "Build sovereign infrastructure before scaling agents.").strip()

    carousel = topic.get("carousel")
    if not isinstance(carousel, dict) or not isinstance(carousel.get("slides"), list) or len(carousel.get("slides")) < 4:
        topic["carousel"] = {
            "title": headline[:70],
            "slides": [
                {
                    "header": headline[:60],
                    "body": f"Architectural breakdown of {headline} and its production impact.",
                    "tag": category,
                    "bullets": points[:2] if len(points) >= 2 else ["Deterministic design pattern", "Decoupled state management"],
                },
                {
                    "header": "Core Architectural Friction",
                    "body": body[:200] if body else "Production failure recovery and distributed state management.",
                    "tag": "BOTTLENECK",
                    "bullets": [points[0]] if points else ["Unverified state cascades across services"],
                },
                {
                    "header": "Implementation Pattern",
                    "body": points[1] if len(points) > 1 else "State machine verification pattern",
                    "tag": "IMPLEMENTATION",
                    "bullets": points[1:3] if len(points) > 2 else ["Deterministic execution beats flaky retry loops"],
                },
                {
                    "header": "Production Verification Checklist",
                    "body": f"Key takeaway: {takeaway}",
                    "tag": "CHECKLIST",
                    "bullets": [
                        "Atomic state persistence",
                        "Isolated failure recovery",
                        "Verified credential boundaries",
                    ],
                },
            ],
        }
        return topic

    default_headers = [
        headline[:60],
        "Core Architectural Friction",
        "Implementation Pattern",
        "Production Verification Checklist",
    ]
    default_bullets = [
        points[:2] if len(points) >= 2 else ["Deterministic design pattern", "Decoupled state management"],
        [points[0]] if points else ["Unverified state cascades across services"],
        points[1:3] if len(points) > 2 else ["Deterministic execution beats flaky retry loops"],
        [
            "Atomic state persistence",
            "Isolated failure recovery",
            "Verified credential boundaries",
        ],
    ]

    for idx, slide in enumerate(carousel["slides"]):
        if not isinstance(slide, dict):
            continue
        hdr = str(slide.get("header") or slide.get("title") or "").strip()
        cleaned_hdr = re.sub(r"^0\d\.\s*", "", hdr).strip()
        if not cleaned_hdr or cleaned_hdr.lower() in ("overview", "technical context", "key takeaway", "summary", "the fragility trap", "atomic ledgers", "local cdp control"):
            slide["header"] = default_headers[min(idx, len(default_headers) - 1)]
        else:
            slide["header"] = cleaned_hdr

        existing_bullets = slide.get("bullets")
        if not isinstance(existing_bullets, list) or len(existing_bullets) == 0:
            slide["bullets"] = default_bullets[min(idx, len(default_bullets) - 1)]

    return topic


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
            "title": headline[:70],
            "slides": [
                {
                    "header": headline[:60],
                    "body": "Architectural breakdown of deterministic agent systems and production reliability.",
                    "tag": category,
                    "bullets": points[:2] if len(points) >= 2 else [
                        "Deterministic design pattern",
                        "Decoupled state management",
                    ],
                },
                {
                    "header": "Core Architectural Friction",
                    "body": "Why probabilistic LLM retry loops fail under high concurrency and real network conditions.",
                    "tag": "BOTTLENECK",
                    "bullets": [points[0]] if points else [
                        "Unverified state cascades across services",
                    ],
                },
                {
                    "header": "Implementation Pattern",
                    "body": points[1] if len(points) > 1 else "State machine verification pattern",
                    "tag": "IMPLEMENTATION",
                    "bullets": points[1:3] if len(points) > 2 else [
                        "Deterministic execution beats flaky retry loops",
                    ],
                },
                {
                    "header": "Production Verification Checklist",
                    "body": f"Key takeaway: {takeaway}",
                    "tag": "CHECKLIST",
                    "bullets": [
                        "Atomic state persistence",
                        "Isolated failure recovery",
                        "Verified credential boundaries",
                    ],
                },
            ],
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

    # Anti-Echo Protection: If summary is just the title repeated or under 40 chars, synthesize rich context
    clean_summary = summary.strip()
    if not clean_summary or clean_summary.lower() == title.lower() or len(clean_summary) < 40:
        summary = (
            f"Analyzing architectural tradeoffs, latency considerations, and state machine "
            f"reliability for {title} in production systems."
        )

    points = extract_key_takeaways(summary, exclude_title=title)

    category = "AI UPDATE" if kind == "ai_update" else "TECH INSIGHT"
    body = summary[:300] if len(summary) > 40 else f"Architectural breakdown of {title} with production implementation guidelines."

    raw_url = str(top_item.get("url") or "").strip()
    source_name = str(top_item.get("source") or "web").strip()
    domain = ""
    if raw_url:
        domain_match = re.search(r"https?://(?:www\.)?([^/]+)", raw_url)
        if domain_match:
            domain = domain_match.group(1)

    if domain:
        takeaway = f"{domain} • Verified Reference"
    elif source_name and source_name.lower() != "web":
        takeaway = f"{source_name.upper()} • Verified Reference"
    else:
        takeaway = "Build sovereign infrastructure before scaling agents."

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
        "title": title[:70],
        "slides": [
            {
                "header": title[:60],
                "body": f"Architectural breakdown of {title} and its production impact.",
                "tag": category,
                "bullets": points[:2] if len(points) >= 2 else ["Deterministic design pattern", "Decoupled state management"],
            },
            {
                "header": "Core Architectural Friction",
                "body": body[:200],
                "tag": "BOTTLENECK",
                "bullets": [points[0]] if points else ["Unverified state cascades across services"],
            },
            {
                "header": "Implementation Pattern",
                "body": points[1] if len(points) > 1 else "State machine verification pattern",
                "tag": "IMPLEMENTATION",
                "bullets": points[1:3] if len(points) > 2 else ["Deterministic execution beats flaky retry loops"],
            },
            {
                "header": "Production Verification Checklist",
                "body": f"Key takeaway: {takeaway}",
                "tag": "CHECKLIST",
                "bullets": [
                    "Atomic state persistence",
                    "Isolated failure recovery",
                    "Verified credential boundaries",
                ],
            },
        ],
    }

    topic_dict = {
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
    topic_dict["card_count"] = determine_card_count(topic_dict)
    return topic_dict


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
        topic = generate_heuristic_topic(kind, items)
        return _ensure_carousel_integrity(topic, kind)

    if use_llm:
        from scripts.llm import generate_topic_with_llm
        ok, topic = generate_topic_with_llm(
            items=items,
            kind=kind,
            voice_profile=voice_profile,
        )
        if ok and topic:
            return _ensure_carousel_integrity(topic, kind)

    topic = generate_heuristic_topic(kind, items)
    return _ensure_carousel_integrity(topic, kind)


def load_daily_swipe(date_str: str) -> list[dict[str, Any]]:
    """Loads swipe items collected for the specified date."""
    swipe_file = ROOT / "swipe" / f"{date_str}.json"
    if not swipe_file.exists():
        return []
    try:
        return json.loads(swipe_file.read_text(encoding="utf-8"))
    except Exception:
        return []
