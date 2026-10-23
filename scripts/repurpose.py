"""Polymorphic Content Repurposer for OmniPost V2.

Transforms a single research insight/topic into 4 distinct channel formats:
1. X (Twitter): 280-char punchy hook + bullet summary + optional 16:9 card
2. Bluesky: 300-char technical insight + byte-facet friendly URLs
3. LinkedIn: 1,000–2,500 char case study with framework breakdown + 1080x1080 PDF carousel
4. Meta Threads: 400-char conversational question/hook
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from render import create_carousel_pdf, create_infocard


def format_x(headline: str, points: list[str]) -> str:
    """Format for X (Twitter Free Tier): strictly 240-275 chars (ceiling 280) with punchy bullets."""
    clean_hl = headline.strip()
    bullet_lines = [f"• {p.strip()}" for p in points[:2] if p.strip()]
    body = "\n".join(bullet_lines)

    text = f"{clean_hl}\n\n{body}".strip()
    if len(text) > 280:
        # Fall back to headline + first bullet
        text = f"{clean_hl}\n\n• {points[0].strip()}" if points else clean_hl
        if len(text) > 280:
            text = clean_hl[:272].rstrip() + "..."
    return text


def format_bluesky(headline: str, points: list[str]) -> str:
    """Format for Bluesky: strictly 260-295 chars (ceiling 300) with technical depth."""
    clean_hl = headline.strip()
    bullets = " ".join([f"({idx+1}) {p.strip()}" for idx, p in enumerate(points[:2]) if p.strip()])
    text = f"{clean_hl} {bullets}".strip()
    if len(text) > 295:
        text = text[:292].rstrip() + "..."
    return text


def format_linkedin(
    headline: str,
    body: str,
    points: list[str],
    takeaway: str = "",
    media_type: str | None = None,
) -> str:
    """Format for LinkedIn using only topic-derived context, changes, and takeaway."""
    clean_hl = headline.strip()
    clean_body = body.strip()
    clean_points = [str(point).strip().lstrip("•-*▸ ") for point in points if str(point).strip()]
    clean_tk = takeaway.strip()

    looks_like_sentence = (
        clean_hl.endswith(("?", "!", "."))
        or clean_hl.lower().startswith(("why ", "how ", "what ", "when ", "where ", "who "))
        or len(clean_hl.split()) >= 7
        or bool(re.search(r"\b(?:is|are|was|were|has|have|can|could|will|would)\b", clean_hl, re.IGNORECASE))
    )
    hook = clean_hl if looks_like_sentence else f"{clean_hl}: production architecture and tradeoffs"

    lines = [hook]
    if clean_body:
        lines.extend(["", clean_body])
    if clean_points:
        lines.extend(["", "What changes in practice:"])
        lines.extend(f"▸ {point}" for point in clean_points[:3])
    if clean_tk:
        lines.extend(["", f"Bottom line: {clean_tk}"])

    if media_type == "carousel":
        lines.extend(["", "See the carousel below for the full visual breakdown."])
    elif media_type == "image":
        lines.extend(["", "See the visual breakdown above."])

    text = "\n".join(lines).strip()
    if len(text) > 3000:
        text = text[:2950].rstrip()
    return text


def format_threads(headline: str, takeaway: str = "") -> str:
    """Format for Meta Threads: topic takeaway plus a conversational question."""
    clean_hl = headline.strip()
    clean_tk = takeaway.strip()

    lines = [clean_hl]
    if clean_tk:
        lines.extend(
            ["", clean_tk, "", "What architectural tradeoffs have you seen in your stack?"]
        )
    else:
        lines.extend(["", f"What changes when you apply {clean_hl} in production?"])

    body = "\n".join(lines).strip()
    if len(body) > 490:
        body = body[:470].rstrip() + "\n\nWhat are your thoughts?"
    return body


def repurpose_topic(
    topic_data: dict[str, Any],
    date_str: str | None = None,
    generate_media: bool = True,
    author: str = "@Lordporus • OmniPost",
    slot: str | None = None,
) -> dict[str, Any]:
    """Converts topic dict into a polymorphic slot structure with generated visual assets.
    
    Args:
        topic_data: Dict containing 'headline', 'body', 'points' (list), and optional 'takeaway'.
        date_str: Target date string (defaults to today).
        generate_media: If True, renders infocard PNG and carousel PDF to disk.
        author: Attribution handle.
        slot: Specific slot string (e.g. 20:00) for unique asset naming.
        author: Attribution handle.
        
    Returns:
        Polymorphic slot dictionary ready for drafts/YYYY-MM-DD.json.
    """
    headline = topic_data.get("headline", "Engineering Insight")
    body = topic_data.get("body", "")
    raw_points = topic_data.get("points")
    if isinstance(raw_points, list):
        points = [str(p) for p in raw_points if str(p).strip()]
    elif raw_points:
        points = [str(raw_points).strip()]
    else:
        points = []
    takeaway = str(topic_data.get("takeaway") or "")
    category = str(topic_data.get("category") or "AI ARCHITECTURE")

    platforms = topic_data.get("platforms")
    if not isinstance(platforms, dict):
        platforms = {}

    def native_text(key: str) -> str:
        direct = topic_data.get(key)
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        value = platforms.get(key)
        if isinstance(value, dict):
            value = value.get("text")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return ""

    # Calibrated synthesis for each platform, preserving native copy when present.
    link_media_type = "image" if generate_media else None
    x_text = native_text("x") or format_x(headline, points)
    bsky_text = native_text("bluesky") or format_bluesky(headline, points)
    link_text = native_text("linkedin") or format_linkedin(
        headline,
        body,
        points,
        takeaway,
        media_type=link_media_type,
    )
    thrd_text = native_text("threads") or format_threads(headline, takeaway)

    media_map: dict[str, Any] = {
        "x": [],
        "bluesky": [],
        "linkedin": [],
    }

    if generate_media:
        date_tag = (date_str or "daily").replace("-", "")
        slot_tag = (slot or "default").replace(":", "")

        # Generate 1 to 3 retina PNG visual cards based on content depth
        card_dir = ROOT / "scratch" / "cards"
        card_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"card_{date_tag}_{slot_tag}"
        
        try:
            from render.cards import generate_topic_cards
            rendered_cards = generate_topic_cards(
                topic_data=topic_data,
                base_name=base_name,
                output_dir=card_dir,
                author=author,
            )
            rel_card_paths = [str(p.relative_to(ROOT)) for p in rendered_cards]
            media_map["x"] = rel_card_paths
            media_map["bluesky"] = rel_card_paths
            media_map["linkedin"] = rel_card_paths
            media_map["threads"] = rel_card_paths
        except Exception as exc:
            # Fallback to single 16:9 infocard
            card_dir = ROOT / "scratch" / "infocards"
            card_dir.mkdir(parents=True, exist_ok=True)
            card_path = card_dir / f"card_{date_tag}_{slot_tag}.png"
            try:
                create_infocard(
                    title=headline,
                    body="\n".join([f"• {p}" for p in points[:3]]),
                    tag=category,
                    author=author,
                    output_path=card_path,
                )
                rel_path = str(card_path.relative_to(ROOT))
                media_map["x"] = [rel_path]
                media_map["bluesky"] = [rel_path]
                media_map["linkedin"] = [rel_path]
                media_map["threads"] = [rel_path]
            except Exception:
                pass

    return {
        "x": {
            "enabled": True,
            "text": x_text,
            "media": media_map.get("x", []),
            "media_type": "image",
        },
        "bluesky": {
            "enabled": True,
            "text": bsky_text,
            "media": media_map.get("bluesky", []),
            "media_type": "image",
        },
        "linkedin": {
            "enabled": True,
            "text": link_text,
            "media": media_map.get("linkedin", []),
            "media_type": "image",
            "document_title": headline[:50],
        },
        "threads": {
            "enabled": True,
            "text": thrd_text,
            "media": media_map.get("threads", []),
            "media_type": "image",
        },
    }
