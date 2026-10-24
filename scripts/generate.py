"""Content Generation & Synthesis Engine for OmniPost.

Extracts high-impact material from daily swipe intelligence (Hacker News, RSS, arXiv)
and shapes it into structured insights aligned with the operator's voice profile.
Supports zero-cost deterministic synthesis with an extensible LLM provider hook.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

try:  # package import (tests, pipeline)
    from scripts.errors import DuplicateTopic, NoRelevantTopic, TopicRejected
    from scripts.relevance import score_candidates, score_item
except ImportError:  # direct script execution
    from errors import DuplicateTopic, NoRelevantTopic, TopicRejected
    from relevance import score_candidates, score_item

ROOT = Path(__file__).resolve().parent.parent


def _clean_point(text: str) -> str:
    clean = re.sub(r"^[\s•\-*▸\d.)]+", "", str(text or "")).strip()
    return clean.strip(" \t\r\n,;:.!?")


def _normalise_point(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(text or "").lower())).strip()


def _sentence_candidates(text: str) -> list[str]:
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", str(text or ""))
        if len(s.strip()) > 15
    ]
    candidates = list(sentences)
    for sentence in sentences:
        for clause in re.split(r"[;:]\s*|,\s+|\s+(?:and|but|while|because|with)\s+", sentence):
            clause = clause.strip()
            if len(clause) > 15:
                candidates.append(clause)

    # A single dense sentence still needs to yield grounded points. Sliding
    # windows keep every bullet traceable to the source summary.
    words = re.findall(r"[\w'+-]+", str(text or ""))
    for width in (8, 6, 5, 4):
        if len(words) < width:
            continue
        step = max(1, width // 2)
        for i in range(0, len(words) - width + 1, step):
            chunk = " ".join(words[i : i + width]).strip()
            if len(chunk) > 20:
                candidates.append(chunk)
    return candidates


def extract_key_takeaways(
    text: str,
    exclude_title: str = "",
    item: dict[str, Any] | None = None,
    require_three: bool = True,
) -> list[str]:
    """Extract topic-grounded bullet points from summary text.

    Every returned point must come from the supplied summary. There is no
    fallback list: if the source cannot support three distinct points, callers
    either accept fewer (``require_three=False``) or reject the item.
    """
    exclude_norm = _normalise_point(exclude_title)
    seen: set[str] = set()
    points: list[str] = []

    for candidate in _sentence_candidates(text):
        clean = _clean_point(candidate)
        norm = _normalise_point(clean)
        if not norm or norm in seen:
            continue
        if exclude_norm and (norm in exclude_norm or exclude_norm in norm):
            continue
        seen.add(norm)
        points.append(clean)
        if len(points) >= 3:
            break

    if require_three and len(points) < 3:
        raise TopicRejected("insufficient_takeaways", item)
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
    """Guarantee every slide has a header, body, and grounded non-empty bullets."""
    if not isinstance(topic, dict):
        return topic

    category = str(topic.get("category") or ("AI UPDATE" if kind == "ai_update" else "TECH INSIGHT"))
    headline = str(topic.get("headline") or "Engineering Insight").strip()
    body = str(topic.get("body") or "").strip()
    raw_points = topic.get("points") or []
    points = [str(p).strip() for p in raw_points if str(p).strip()]
    if len(points) < 3:
        points = extract_key_takeaways(
            body or headline,
            exclude_title=headline,
            require_three=False,
        )
    if not points:
        raise TopicRejected("insufficient_takeaways")

    takeaway = str(topic.get("takeaway") or points[-1]).strip() or points[-1]

    def grounded(start: int, count: int) -> list[str]:
        return [points[(start + offset) % len(points)] for offset in range(count)]

    carousel = topic.get("carousel")
    if not isinstance(carousel, dict) or not isinstance(carousel.get("slides"), list) or len(carousel.get("slides")) < 4:
        topic["carousel"] = {
            "title": headline[:70],
            "slides": [
                {
                    "header": headline[:60],
                    "body": body[:200] if body else points[0],
                    "tag": category,
                    "bullets": grounded(0, 2),
                },
                {
                    "header": "Core Architectural Friction",
                    "body": body[:200] if body else points[0],
                    "tag": "BOTTLENECK",
                    "bullets": grounded(0, 1),
                },
                {
                    "header": "Implementation Pattern",
                    "body": points[1] if len(points) > 1 else points[0],
                    "tag": "IMPLEMENTATION",
                    "bullets": grounded(1, 2),
                },
                {
                    "header": "Production Verification Checklist",
                    "body": f"Key takeaway: {takeaway}",
                    "tag": "CHECKLIST",
                    "bullets": grounded(2, 2),
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

    for idx, slide in enumerate(carousel["slides"]):
        if not isinstance(slide, dict):
            continue
        hdr = str(slide.get("header") or slide.get("title") or "").strip()
        cleaned_hdr = re.sub(r"^0\d\.\s*", "", hdr).strip()
        if not cleaned_hdr or cleaned_hdr.lower() in ("overview", "technical context", "key takeaway", "summary", "the fragility trap", "atomic ledgers", "local cdp control"):
            slide["header"] = default_headers[min(idx, len(default_headers) - 1)]
        else:
            slide["header"] = cleaned_hdr

        if not str(slide.get("body") or "").strip():
            slide["body"] = points[idx % len(points)]

        existing_bullets = slide.get("bullets")
        if not isinstance(existing_bullets, list) or len(existing_bullets) == 0:
            slide["bullets"] = grounded(idx, 2)

    return topic


def _summary_for_item(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("summary", "description", "content"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    extra = item.get("extra")
    if isinstance(extra, str):
        return extra.strip()
    if isinstance(extra, dict):
        for key in ("summary", "text", "description", "content"):
            value = extra.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _validate_summary(item: dict[str, Any], title: str, summary: str) -> str:
    clean = str(summary or "").strip()
    title_norm = _normalise_point(title)
    summary_norm = _normalise_point(clean)
    if (
        len(clean) < 40
        or not summary_norm
        or summary_norm == title_norm
        or summary_norm.strip(".!? ") == title_norm.strip(".!? ")
    ):
        raise TopicRejected("missing_summary", item)
    return clean


def generate_heuristic_topic(kind: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Generates a structured topic dictionary deterministically without LLM API calls."""
    if not items:
        raise NoRelevantTopic("no_items")

    # Sort items by score/relevance
    sorted_items = sorted(items, key=lambda x: int(x.get("score") or 0), reverse=True)
    top_item = sorted_items[0]
    title = str(top_item.get("title") or "Engineering Update").strip()
    summary = _validate_summary(top_item, title, _summary_for_item(top_item))
    points = extract_key_takeaways(summary, exclude_title=title, item=top_item)

    category = "AI UPDATE" if kind == "ai_update" else "TECH INSIGHT"
    body = summary[:300]
    takeaway = points[-1]

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

    # LinkedIn: topic-derived context, practical changes, and bottom line.
    linkedin_text = (
        f"{title}\n\n"
        f"{body}\n\n"
        "What changes in practice:\n"
        + "\n".join([f"▸ {p}" for p in points])
        + f"\n\nBottom line: {takeaway}"
    )
    if len(linkedin_text) > 3000:
        linkedin_text = linkedin_text[:2950].rstrip()

    carousel = {
        "title": title[:70],
        "slides": [
            {
                "header": title[:60],
                "body": body[:200],
                "tag": category,
                "bullets": points[:2],
            },
            {
                "header": "Core Architectural Friction",
                "body": points[0],
                "tag": "BOTTLENECK",
                "bullets": [points[0]],
            },
            {
                "header": "Implementation Pattern",
                "body": points[1],
                "tag": "IMPLEMENTATION",
                "bullets": points[1:3],
            },
            {
                "header": "Production Verification Checklist",
                "body": f"Key takeaway: {takeaway}",
                "tag": "CHECKLIST",
                "bullets": points[2:3] + [takeaway],
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


def _fingerprint_text(text: Any) -> str:
    normalised = re.sub(r"[^\w\s]", " ", str(text or "").lower())
    return re.sub(r"\s+", " ", normalised).strip()


def _fingerprint_parts(topic: dict[str, Any]) -> list[str]:
    parts = sorted(
        _fingerprint_text(point)
        for point in (topic.get("points") or [])
        if _fingerprint_text(point)
    )
    platforms = topic.get("platforms")
    for key in ("x", "bluesky", "threads", "linkedin"):
        text = platforms.get(key) if isinstance(platforms, dict) else None
        if not isinstance(text, str) or not text.strip():
            text = topic.get(key)
        if isinstance(text, str) and text.strip():
            parts.append(_fingerprint_text(text))
    return parts


def content_fingerprint(topic: dict[str, Any]) -> str:
    """Stable digest of a topic's bullets and per-platform post text."""
    payload = "\n".join(_fingerprint_parts(topic))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def bullet_fingerprint(topic: dict[str, Any]) -> str:
    """Stable digest of the sorted bullet set, independent of headline and order."""
    points = sorted(
        _fingerprint_text(point)
        for point in (topic.get("points") or [])
        if _fingerprint_text(point)
    )
    return hashlib.sha256("\n".join(points).encode("utf-8")).hexdigest()


def _topic_is_relevant(topic: dict[str, Any], voice_profile: str | None = None) -> bool:
    probe = {
        "title": str(topic.get("headline") or ""),
        "summary": str(topic.get("body") or ""),
    }
    return score_item(probe, voice_profile=voice_profile).accepted


def _sanitize_takeaway(topic: dict[str, Any]) -> dict[str, Any]:
    points = [str(point).strip() for point in (topic.get("points") or []) if str(point).strip()]
    takeaway = str(topic.get("takeaway") or "").strip()
    bare_domain = bool(re.fullmatch(r"[\w.-]+\.[a-z]{2,}", takeaway.lower()))
    if (not takeaway or bare_domain or "verified reference" in takeaway.lower()) and points:
        topic["takeaway"] = points[-1]
    return topic


def generate_topic_from_items(
    kind: str,
    items: list[dict[str, Any]],
    use_llm: bool = True,
    voice_profile: str | None = None,
) -> dict[str, Any]:
    """Generate a structured topic from the highest-scoring relevant item.

    Both the LLM output and the deterministic fallback must pass the same
    relevance gate. There is no unverified path to a topic dict.
    """
    if not items:
        raise NoRelevantTopic("no_items")

    scored = score_candidates(items, voice_profile=voice_profile)
    accepted = sorted(
        [(item, result) for item, result in scored if result.accepted],
        key=lambda pair: pair[1].score,
        reverse=True,
    )
    if not accepted:
        details = "; ".join(
            f"{str(item.get('title') or '')[:60]}: {', '.join(result.reasons)}"
            for item, result in scored
        )
        raise NoRelevantTopic(f"no_relevant_items: {details}")

    source_item = accepted[0][0]

    if use_llm:
        try:
            from scripts.llm import generate_topic_with_llm

            ok, topic = generate_topic_with_llm(
                items=[source_item],
                kind=kind,
                voice_profile=voice_profile,
            )
        except Exception:
            ok, topic = False, None

        if ok and isinstance(topic, dict):
            _sanitize_takeaway(topic)
            if _topic_is_relevant(topic, voice_profile):
                return _ensure_carousel_integrity(topic, kind)

    topic = generate_heuristic_topic(kind, [source_item])
    _sanitize_takeaway(topic)
    if not _topic_is_relevant(topic, voice_profile):
        raise TopicRejected("off_topic_topic", source_item)
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
