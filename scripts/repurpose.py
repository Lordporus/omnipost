"""Polymorphic Content Repurposer for OmniPost V2.

Transforms a single research insight/topic into 4 distinct channel formats:
1. X (Twitter): 280-char punchy hook + bullet summary + optional 16:9 card
2. Bluesky: 300-char technical insight + byte-facet friendly URLs
3. LinkedIn: 1,000–2,500 char case study with framework breakdown + 1080x1080 PDF carousel
4. Meta Threads: 400-char conversational question/hook
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from render import create_carousel_pdf, create_infocard

ROOT = Path(__file__).resolve().parent.parent


def format_x(headline: str, points: list[str]) -> str:
    """Format for X (Twitter): maximum 280 characters with punchy bullets."""
    clean_hl = headline.strip()
    bullet_lines = [f"• {p.strip()}" for p in points[:2] if p.strip()]
    body = "\n".join(bullet_lines)

    text = f"{clean_hl}\n\n{body}".strip()
    if len(text) > 280:
        # Fall back to headline + first bullet or trim
        text = f"{clean_hl}\n\n• {points[0].strip()}" if points else clean_hl
        if len(text) > 280:
            text = text[:277] + "..."
    return text


def format_bluesky(headline: str, points: list[str]) -> str:
    """Format for Bluesky: maximum 300 characters with technical depth."""
    clean_hl = headline.strip()
    bullets = " ".join([f"({idx+1}) {p.strip()}" for idx, p in enumerate(points[:2]) if p.strip()])
    text = f"{clean_hl} {bullets}".strip()
    if len(text) > 300:
        text = text[:297] + "..."
    return text


def format_linkedin(headline: str, body: str, points: list[str], takeaway: str = "") -> str:
    """Format for LinkedIn: deep-dive case study with swipeable carousel CTA."""
    lines = [
        headline.strip(),
        "",
        body.strip(),
        "",
        "Key Engineering Takeaways:",
    ]
    for p in points:
        lines.append(f"▸ {p.strip()}")
    
    if takeaway:
        lines.extend(["", f"Bottom line: {takeaway.strip()}"])

    lines.extend(["", "Swipe through the architecture carousel below for the complete breakdown ➔"])
    return "\n".join(lines).strip()


def format_threads(headline: str, takeaway: str = "") -> str:
    """Format for Meta Threads: conversational question/hook up to 500 characters."""
    clean_hl = headline.strip()
    clean_tk = takeaway.strip() if takeaway else "What's your experience with this pattern?"

    text = f"{clean_hl}\n\n{clean_tk}"
    if len(text) > 500:
        text = text[:497] + "..."
    return text


def repurpose_topic(
    topic_data: dict[str, Any],
    date_str: str | None = None,
    generate_media: bool = True,
    author: str = "@Lordporus • OmniPost",
) -> dict[str, Any]:
    """Converts topic dict into a polymorphic slot structure with generated visual assets.
    
    Args:
        topic_data: Dict containing 'headline', 'body', 'points' (list), and optional 'takeaway'.
        date_str: Target date string (defaults to today).
        generate_media: If True, renders infocard PNG and carousel PDF to disk.
        author: Attribution handle.
        
    Returns:
        Polymorphic slot dictionary ready for drafts/YYYY-MM-DD.json.
    """
    headline = topic_data.get("headline", "Engineering Insight")
    body = topic_data.get("body", "")
    points = topic_data.get("points", [])
    takeaway = topic_data.get("takeaway", "")
    category = topic_data.get("category", "AI ARCHITECTURE")

    # Generate tailored text
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
        # 1. 16:9 Dark-mode infocard for X and Bluesky
        card_dir = ROOT / "scratch" / "infocards"
        card_dir.mkdir(parents=True, exist_ok=True)
        card_path = card_dir / "daily_card.png"
        try:
            create_infocard(
                title=headline,
                body="\n".join([f"• {p}" for p in points[:3]]),
                tag=category,
                author=author,
                output_path=card_path,
            )
            media_map["x"] = [str(card_path.relative_to(ROOT))]
            media_map["bluesky"] = [str(card_path.relative_to(ROOT))]
        except Exception as exc:
            pass

        # 2. 1080x1080 PDF Carousel for LinkedIn
        carousel_dir = ROOT / "scratch" / "carousels"
        carousel_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = carousel_dir / "architecture_carousel.pdf"
        try:
            from render.carousel import generate_standard_slides
            slides = generate_standard_slides(topic_data=topic_data, author=author)
            create_carousel_pdf(
                slides=slides,
                title=headline,
                tag=category,
                author=author,
                output_path=pdf_path,
            )
            media_map["linkedin"] = [str(pdf_path.relative_to(ROOT))]
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
            "media_type": "carousel",
            "document_title": headline[:50],
        },
        "threads": {
            "enabled": True,
            "text": thrd_text,
            "media": media_map.get("x", []),
            "media_type": "image",
        },
    }
