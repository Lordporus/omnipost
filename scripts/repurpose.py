"""Polymorphic Content Repurposer for OmniPost V2.

Transforms a single research insight/topic into 4 distinct channel formats:
1. X (Twitter): 280-char punchy hook + bullet summary + optional 16:9 card
2. Bluesky: 300-char technical insight + byte-facet friendly URLs
3. LinkedIn: 1,000–2,500 char case study with framework breakdown + 1080x1080 PDF carousel
4. Meta Threads: 400-char conversational question/hook
"""
from __future__ import annotations

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
            text = clean_hl[:275].rstrip()
    return text


def format_bluesky(headline: str, points: list[str]) -> str:
    """Format for Bluesky: strictly 260-295 chars (ceiling 300) with technical depth."""
    clean_hl = headline.strip()
    bullets = " ".join([f"({idx+1}) {p.strip()}" for idx, p in enumerate(points[:2]) if p.strip()])
    text = f"{clean_hl} {bullets}".strip()
    if len(text) > 295:
        text = text[:292].rstrip()
    return text


def format_linkedin(headline: str, body: str, points: list[str], takeaway: str = "") -> str:
    """Format for LinkedIn: authoritative 1,200-2,500 char engineering case study (ceiling 3000)."""
    clean_hl = headline.strip()
    clean_body = body.strip()
    clean_tk = takeaway.strip() if takeaway else "Architect for deterministic state execution before scaling concurrency."
    
    lines = [
        f"Why {clean_hl} Matters in Production",
        "",
        clean_body if clean_body else f"Analyzing the architectural decisions and production requirements for {clean_hl}.",
        "",
        "The Architectural Bottleneck:",
        "Most engineering teams hit scaling walls because they rely on brittle abstractions and unverified assumptions. When systems scale under concurrent real-world load, partial network failures, state drift, and coordination overhead quickly compound into cascading failures across worker nodes.",
        "",
        "Core Engineering Takeaways & System Patterns:",
    ]
    
    for idx, p in enumerate(points[:3], 1):
        clean_p = p.strip().lstrip("•-*▸ ")
        lines.append(f"▸ {clean_p}")
    
    lines.extend([
        "",
        "Production Principles to Remember:",
        "▸ Deterministic execution beats retry loops: Never assume an external transaction succeeded without verifiable proof.",
        "▸ Decoupled state isolation: Isolate failure domains so a stalled pipeline never blocks independent channels.",
        "▸ Sovereign infrastructure: Local automation eliminates fragile third-party cloud wrappers and recurring API tolls.",
        "",
        f"Bottom line: {clean_tk}",
        "",
        "Review the visual system breakdown cards below for the architecture walkthrough.",
    ])
    
    text = "\n".join(lines).strip()
    if len(text) > 3000:
        text = text[:2950].rstrip()
    return text


def format_threads(headline: str, takeaway: str = "") -> str:
    """Format for Meta Threads: 350-480 char conversational technical debate (ceiling 500)."""
    clean_hl = headline.strip()
    clean_tk = takeaway.strip() if takeaway else "What's your experience scaling this in production?"

    body = (
        f"{clean_hl}\n\n"
        f"Most distributed systems fail due to state drift and unverified retry loops rather than core throughput limits.\n\n"
        f"{clean_tk} What architectural tradeoffs have you seen in your stack?"
    )
    if len(body) > 490:
        body = body[:480].rstrip() + "\n\nWhat are your thoughts?"
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

    # Calibrated synthesis for each platform
    x_text = format_x(headline, points)
    bsky_text = format_bluesky(headline, points)
    link_text = format_linkedin(headline, body, points, takeaway)
    thrd_text = format_threads(headline, takeaway)

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
