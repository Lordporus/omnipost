"""Polymorphic Content Repurposer for OmniPost V2.

Transforms a single research insight/topic into 4 distinct channel formats:
1. X (Twitter): 220-275 weighted chars + punchy bullets + optional 16:9 card
2. Bluesky: 240-295 graphemes + byte-facet friendly URLs
3. LinkedIn: 1,500-2,500 code points + optional 1080x1080 PDF carousel
4. Meta Threads: 350-480 code points (hard ceiling 500) + conversational CTA
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from render import create_carousel_pdf

try:  # package import (tests, pipeline)
    from scripts.errors import CopyValidationError, MediaContractError, RenderError
    from scripts.platform_limits import LIMITS, count_for, fit, truncate_words, validate
except ImportError:  # direct script execution
    from errors import CopyValidationError, MediaContractError, RenderError
    from platform_limits import LIMITS, count_for, fit, truncate_words, validate


def format_x(headline: str, points: list[str]) -> str:
    """Format for X: 220-275 weighted characters with punchy bullets."""
    clean_hl = str(headline or "").strip()
    bullet_lines = [f"• {str(point).strip()}" for point in points[:3] if str(point).strip()]
    body = "\n".join(bullet_lines)

    text = f"{clean_hl}\n\n{body}".strip()
    return fit("x", text)


def format_bluesky(headline: str, points: list[str]) -> str:
    """Format for Bluesky: 240-295 graphemes with technical depth."""
    clean_hl = str(headline or "").strip()
    bullets = " ".join(
        f"({idx + 1}) {str(point).strip()}"
        for idx, point in enumerate(points[:3])
        if str(point).strip()
    )
    text = f"{clean_hl} {bullets}".strip()
    return fit("bluesky", text)


def format_linkedin(
    headline: str,
    body: str,
    points: list[str],
    takeaway: str = "",
    media_type: str | None = None,
) -> str:
    """Format for LinkedIn using only topic-derived context, changes, and takeaway."""
    clean_hl = str(headline or "").strip()
    clean_body = str(body or "").strip()
    clean_points = [
        str(point).strip().lstrip("•-*▸ ")
        for point in points
        if str(point).strip()
    ]
    clean_tk = str(takeaway or "").strip()

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
        lines.extend(f"▸ {point}" for point in clean_points)
    if clean_tk:
        lines.extend(["", f"Bottom line: {clean_tk}"])

    if media_type == "carousel":
        lines.extend(["", "See the carousel below for the full visual breakdown."])
    elif media_type == "image":
        lines.extend(["", "See the visual breakdown above."])

    text = "\n".join(lines).strip()
    return fit("linkedin", text)


def format_threads(
    headline: str,
    takeaway: str = "",
    body: str = "",
    points: list[str] | None = None,
) -> str:
    """Format for Meta Threads: 350-480 characters with the CTA included."""
    clean_hl = str(headline or "").strip()
    clean_tk = str(takeaway or "").strip()
    clean_body = str(body or "").strip()
    clean_points = [str(point).strip() for point in (points or []) if str(point).strip()]

    sections = [clean_hl]
    if clean_body:
        sections.append(clean_body)
    if clean_points:
        sections.append("\n".join(f"• {point}" for point in clean_points[:3]))
    if clean_tk:
        sections.append(clean_tk)
    insight = "\n\n".join(section for section in sections if section).strip()

    cta = "What architectural tradeoffs have you seen in your stack?"
    cta_suffix = f"\n\n{cta}"
    cta_cost = count_for("threads", cta_suffix)
    insight_budget = LIMITS["threads"]["max"] - cta_cost
    if count_for("threads", insight) > insight_budget:
        insight = truncate_words(insight, insight_budget, "threads")

    return fit("threads", f"{insight}{cta_suffix}".strip())


def _calibrated_native_text(platform: str, text: str) -> str:
    """Return native copy only when it already satisfies the platform limits."""
    candidate = str(text or "").strip()
    if not candidate:
        return ""
    try:
        if count_for(platform, candidate) > LIMITS[platform]["max"]:
            candidate = fit(platform, candidate)
        validate(platform, candidate)
        return candidate
    except CopyValidationError:
        return ""


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
        generate_media: If True, renders 9:16 storybook cards and carousel PDF to disk.
        author: Attribution handle.
        slot: Specific slot string (e.g. 20:00) for unique asset naming.
        
    Returns:
        Polymorphic slot dictionary ready for drafts/YYYY-MM-DD.json.
    """
    headline = str(topic_data.get("headline") or "Engineering Insight").strip()
    body = str(topic_data.get("body") or "")
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

    carousel = topic_data.get("carousel")
    if not isinstance(carousel, dict):
        carousel = {}
    carousel_slides = carousel.get("slides") if isinstance(carousel.get("slides"), list) else []
    explicit_media_type = str(topic_data.get("media_type") or "").strip().lower()
    requested_carousel = explicit_media_type == "carousel" or (
        explicit_media_type not in ("image", "carousel")
        and generate_media
        and bool(carousel_slides)
    )
    link_media_type = "carousel" if requested_carousel else "image"

    # Calibrated synthesis for each platform. Native copy is preserved only when
    # it already fits the platform contract; otherwise the formatter rebuilds it.
    x_text = _calibrated_native_text("x", native_text("x")) or format_x(headline, points)
    bsky_text = _calibrated_native_text("bluesky", native_text("bluesky")) or format_bluesky(
        headline, points
    )
    link_text = _calibrated_native_text(
        "linkedin", native_text("linkedin")
    ) or format_linkedin(
        headline,
        body,
        points,
        takeaway,
        media_type=link_media_type,
    )
    thrd_text = _calibrated_native_text(
        "threads", native_text("threads")
    ) or format_threads(headline, takeaway, body, points)

    media_map: dict[str, Any] = {
        "x": [],
        "bluesky": [],
        "linkedin": [],
        "threads": [],
    }
    date_tag = (date_str or "daily").replace("-", "")
    slot_tag = (slot or "default").replace(":", "")

    if generate_media:
        # Generate 1 to 3 topic-derived 9:16 storybook cards. A render failure
        # raises RenderError and blocks the draft; there is no silent text-only
        # fallback.
        from render.cards import generate_topic_cards

        card_dir = ROOT / "scratch" / "cards"
        card_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"card_{date_tag}_{slot_tag}"

        rendered_cards = generate_topic_cards(
            topic_data=topic_data,
            base_name=base_name,
            output_dir=card_dir,
            author=author,
        )

        rel_card_paths: list[str] = []
        for rendered in rendered_cards:
            card_path = Path(rendered)
            if card_path.is_file() and card_path.stat().st_size > 0:
                try:
                    rel_card_paths.append(str(card_path.relative_to(ROOT)))
                except ValueError:
                    rel_card_paths.append(str(card_path))

        if not rel_card_paths:
            raise RenderError("no_renderable_media")

        media_map["x"] = rel_card_paths
        media_map["bluesky"] = rel_card_paths
        media_map["threads"] = rel_card_paths
        if not requested_carousel:
            media_map["linkedin"] = rel_card_paths

    document_title = ""
    if requested_carousel:
        if not generate_media:
            raise MediaContractError(
                "LinkedIn carousel requested but media generation is disabled.",
                platform="linkedin",
                stage="media_contract",
            )
        if not carousel_slides:
            raise MediaContractError(
                "LinkedIn carousel requested but no carousel slides are available.",
                platform="linkedin",
                stage="media_contract",
            )

        carousel_title = str(carousel.get("title") or headline).strip() or "OmniPost Carousel"
        pdf_dir = ROOT / "scratch" / "carousels"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_dir / f"linkedin_{date_tag}_{slot_tag}.pdf"
        try:
            generated_pdf = create_carousel_pdf(
                slides=carousel_slides,
                title=carousel_title,
                tag=category,
                author=author,
                output_path=pdf_path,
            )
        except Exception as exc:
            raise MediaContractError(
                f"LinkedIn carousel rendering failed: {exc}",
                platform="linkedin",
                stage="media_contract",
            ) from exc

        generated_path = Path(generated_pdf)
        if generated_path.suffix.lower() != ".pdf":
            raise MediaContractError(
                "LinkedIn carousel rendering did not produce a PDF path.",
                platform="linkedin",
                stage="media_contract",
            )
        try:
            media_path = str(generated_path.relative_to(ROOT))
        except ValueError:
            media_path = str(generated_path)
        media_map["linkedin"] = [media_path]
        document_title = carousel_title

    linkedin_payload: dict[str, Any] = {
        "enabled": True,
        "text": link_text,
        "media": media_map.get("linkedin", []),
        "media_type": link_media_type,
    }
    if link_media_type == "carousel":
        linkedin_payload["document_title"] = document_title

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
        "linkedin": linkedin_payload,
        "threads": {
            "enabled": True,
            "text": thrd_text,
            "media": media_map.get("threads", []),
            "media_type": "image",
        },
    }
