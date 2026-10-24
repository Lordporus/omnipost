"""CDP Retina PNG Storybook Renderer for OmniPost.

Generates 1 to 3 standalone 1080x1920 storybook cards (2160x3840 pixels at 2x
scale) using the running browser session over DevTools Protocol
(CDP Page.captureScreenshot).

Design contract:
- 9:16 storybook canvas (#0D1117) with emerald/violet/amber accents.
- Every slide is derived from the topic; there is no generic fallback copy.
- Fonts are vendored and embedded as base64 data URIs, so rendering is offline.
- Capture waits for real readiness (fonts + image decode) instead of sleeping.
- Any failure raises RenderError and blocks the draft; there is no text-only
  fallback.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import html
import re
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from scripts import browser, settings
from scripts.browser import Session
from scripts.errors import RenderError

ROOT = Path(__file__).resolve().parent.parent
CARD_TEMPLATE_PATH = Path(__file__).resolve().parent / "card_template.html"
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

CARD_WIDTH = 1080
CARD_HEIGHT = 1920
DEFAULT_SCALE = 2.0
READINESS_TIMEOUT_SECONDS = 10.0

# Vendored, OFL-1.1 licensed Geist faces. Keys are the CSS family/weight pairs.
FONT_FILES: tuple[tuple[str, str, str, str], ...] = (
    ("Geist", "400", "normal", "Geist-Regular.woff2"),
    ("Geist", "600", "normal", "Geist-SemiBold.woff2"),
    ("Geist Mono", "400", "normal", "GeistMono-Regular.woff2"),
)

SVG_CHEVRON = (
    '<svg class="bullet-icon-svg" width="22" height="22" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="9 18 15 12 9 6"></polyline></svg>'
)

READINESS_JS = """
(async () => {
  await document.fonts.ready;
  await Promise.all(Array.from(document.images).map(img => img.decode().catch(() => {})));
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  return true;
})()
"""

_ROLE_META: dict[str, tuple[str, str]] = {
    "CORE": ("KEY TAKEAWAY", "SUMMARY"),
    "CONTEXT": ("THE CONTEXT", "CONTEXT"),
    "MECHANISM": ("HOW IT WORKS", "MECHANISM"),
    "CHECKLIST": ("ACTION CHECKLIST", "CHECKLIST"),
}


def _clean_text(val: str) -> str:
    s = val.strip()
    s = re.sub(r"^\*+|\*+$", "", s).strip()
    s = re.sub(r'^["\']|["\']$', "", s).strip()
    return s


def _shorten(text: str, limit: int = 72) -> str:
    """Word-boundary truncation so a point can serve as a headline."""
    s = _clean_text(text)
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-.")
    return f"{cut}..."


def _join_points(points: list[str]) -> str:
    return " ".join(p.strip().rstrip(".") + "." for p in points if p.strip())


def _derive_source(topic_data: dict[str, Any]) -> str:
    raw = str(topic_data.get("source") or topic_data.get("url") or "").strip()
    if not raw:
        return "omnipost.local"
    candidate = raw if "://" in raw else f"https://{raw}"
    host = urlparse(candidate).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or raw


def _derive_timestamp(topic_data: dict[str, Any], date_str: str | None = None) -> str:
    raw = str(topic_data.get("timestamp") or "").strip()
    if raw:
        return raw
    if date_str:
        return date_str
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.strip().lower()
        if value.strip() and key not in seen:
            seen.add(key)
            out.append(value.strip())
    return out


def _validate_slides(slides: list[dict[str, Any]]) -> None:
    """Every slide must be substantive and distinct from its siblings."""
    seen_bodies: set[str] = set()
    seen_bullets: set[tuple[str, ...]] = set()
    for slide in slides:
        headline = str(slide.get("headline") or "").strip()
        body = str(slide.get("body") or "").strip()
        bullets = [str(b).strip() for b in slide.get("bullets") or [] if str(b).strip()]
        if not headline or not body or not bullets:
            raise RenderError("insufficient_slide_content")
        body_key = body.lower()
        bullet_key = tuple(b.lower() for b in bullets)
        if body_key in seen_bodies or bullet_key in seen_bullets:
            raise RenderError("insufficient_slide_content")
        seen_bodies.add(body_key)
        seen_bullets.add(bullet_key)


def build_card_slides(
    topic_data: dict[str, Any],
    count: int,
    author: str = "@Lordporus • OmniPost",
    date_str: str | None = None,
) -> list[dict[str, Any]]:
    """Synthesizes 1-3 topic-derived storybook slides.

    Slide roles are problem/context -> mechanism/evidence -> checklist/action.
    Content is taken only from the topic (headline, body, points, takeaway);
    when the topic cannot supply distinct, substantive slides this raises
    ``RenderError`` instead of substituting generic engineering copy.
    """
    headline = _clean_text(str(topic_data.get("headline") or ""))
    body = _clean_text(str(topic_data.get("body") or ""))
    category = str(topic_data.get("category") or "SYSTEMS DESIGN").upper().strip()
    points = [_clean_text(str(p)) for p in topic_data.get("points", []) if _clean_text(str(p))]
    takeaway = _clean_text(str(topic_data.get("takeaway") or ""))

    source = _derive_source(topic_data)
    timestamp = _derive_timestamp(topic_data, date_str)

    def slide(role: str, head: str, body_text: str, bullets: list[str]) -> dict[str, Any]:
        panel_tag, page_label = _ROLE_META[role]
        return {
            "role": role,
            "tag": category if role in ("CORE", "CONTEXT") else role,
            "panel_tag": panel_tag,
            "page_label": page_label,
            "headline": _clean_text(head),
            "body": _clean_text(body_text),
            "bullets": _dedupe(bullets),
            "source": source,
            "timestamp": timestamp,
        }

    slides: list[dict[str, Any]] = []

    if count <= 1:
        head = headline or _shorten(body) or _shorten(points[0] if points else "")
        body_text = body or takeaway or (points[0] if points else "")
        bullets = [points[0]] if points else [takeaway]
        slides.append(slide("CORE", head, body_text, bullets + ([takeaway] if takeaway else [])))

    elif count == 2:
        context_head = headline or _shorten(body) or _shorten(points[0] if points else "")
        context_body = body or takeaway or (points[0] if points else "")
        context_bullets = [points[0]] if points else [takeaway]
        slides.append(slide("CONTEXT", context_head, context_body, context_bullets))

        mech_points = points[1:3]
        mech_head = _shorten(mech_points[0] if mech_points else (takeaway or context_body))
        mech_body = _join_points(mech_points) or takeaway or context_body
        mech_bullets = mech_points or ([takeaway] if takeaway else [])
        slides.append(slide("MECHANISM", mech_head, mech_body, mech_bullets))

    else:
        context_head = headline or _shorten(body) or _shorten(points[0] if points else "")
        context_body = body or takeaway or (points[0] if points else "")
        context_bullets = [points[0]] if points else [takeaway]
        slides.append(slide("CONTEXT", context_head, context_body, context_bullets))

        mech_points = points[1:3]
        mech_head = _shorten(mech_points[0] if mech_points else (takeaway or context_body))
        mech_body = _join_points(mech_points) or takeaway or context_body
        mech_bullets = mech_points or ([takeaway] if takeaway else [])
        slides.append(slide("MECHANISM", mech_head, mech_body, mech_bullets))

        check_points = points[2:5]
        check_head = _shorten(takeaway) or _shorten(check_points[0] if check_points else "")
        check_body = takeaway or _join_points(check_points) or context_body
        check_bullets = check_points or ([takeaway] if takeaway else [])
        slides.append(slide("CHECKLIST", check_head, check_body, check_bullets))

    slides = slides[: max(1, min(3, count))]
    _validate_slides(slides)
    return slides


@lru_cache(maxsize=1)
def _font_css() -> str:
    """Return @font-face rules with the vendored fonts embedded as data URIs."""
    rules: list[str] = []
    for family, weight, style, filename in FONT_FILES:
        path = FONT_DIR / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise RenderError(f"missing_font_asset: {filename}")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        rules.append(
            "@font-face {"
            f'font-family: "{family}";'
            f"font-weight: {weight};"
            f"font-style: {style};"
            "font-display: block;"
            f'src: url(data:font/woff2;base64,{encoded}) format("woff2");'
            "}"
        )
    return "\n".join(rules)


def render_card_html(
    slide: dict[str, Any],
    current_idx: int,
    total_count: int,
    author: str,
    font_css: str | None = None,
) -> str:
    """Fills card_template.html for a single slide."""
    template = CARD_TEMPLATE_PATH.read_text(encoding="utf-8")

    counter_str = f"{current_idx + 1:02d} / {total_count:02d}"
    headline = html.escape(str(slide["headline"]))
    tag = html.escape(str(slide["tag"]))

    body_html = ""
    if slide.get("body"):
        body_html = f'<p class="card-body">{html.escape(str(slide["body"]))}</p>'

    panel_html = ""
    bullets = slide.get("bullets", [])
    if bullets or slide.get("panel_tag"):
        panel_tag = html.escape(str(slide.get("panel_tag", "KEY TAKEAWAYS")))
        bullet_items = "".join(
            f'<li class="bullet-item">{SVG_CHEVRON}<span>{html.escape(str(b))}</span></li>'
            for b in bullets
        )
        panel_html = (
            '<div class="panel panel-highlight">'
            '<div class="panel-tag">'
            '<span class="panel-pulse"></span>'
            f"<span>{panel_tag}</span>"
            "</div>"
            f'<ul class="bullets">{bullet_items}</ul>'
            "</div>"
        )

    res = template.replace("{{FONT_CSS}}", font_css if font_css is not None else _font_css())
    res = res.replace("{{TITLE}}", headline)
    res = res.replace("{{TAG}}", tag)
    res = res.replace("{{AUTHOR}}", html.escape(author))
    res = res.replace("{{COUNTER}}", counter_str)
    res = res.replace("{{HEADLINE}}", headline)
    res = res.replace("{{BODY_HTML}}", body_html)
    res = res.replace("{{PANEL_HTML}}", panel_html)
    res = res.replace("{{SOURCE}}", html.escape(str(slide.get("source") or "omnipost.local")))
    res = res.replace("{{TIMESTAMP}}", html.escape(str(slide.get("timestamp") or "")))
    res = res.replace(
        "{{PAGE_LABEL}}", html.escape(str(slide.get("page_label") or "STORYBOOK"))
    )

    return res


async def _capture_card_png(
    html_content: str,
    out_path: Path,
    port: int,
    scale: float = DEFAULT_SCALE,
) -> bool:
    """Loads HTML via data URL and captures a 9:16 PNG via CDP.

    At ``scale=1.0`` the PNG is 1080x1920; at ``scale=2.0`` it is 2160x3840.
    """
    b64_html = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")
    data_url = f"data:text/html;base64,{b64_html}"

    ws = await browser.open_page(data_url)
    sess = Session(ws)
    page = await sess.__aenter__()
    try:
        await page.send("Page.enable")
        await page.send(
            "Emulation.setDeviceMetricsOverride",
            width=CARD_WIDTH,
            height=CARD_HEIGHT,
            deviceScaleFactor=scale,
            mobile=False,
        )

        try:
            await asyncio.wait_for(
                page.send(
                    "Runtime.evaluate",
                    expression=READINESS_JS,
                    awaitPromise=True,
                    returnByValue=True,
                ),
                timeout=READINESS_TIMEOUT_SECONDS,
            )
        except Exception as exc:  # timeout or CDP failure
            raise RenderError("capture_not_ready") from exc

        try:
            shot = await page.send(
                "Page.captureScreenshot",
                format="png",
                clip={
                    "x": 0,
                    "y": 0,
                    "width": CARD_WIDTH,
                    "height": CARD_HEIGHT,
                    "scale": 1.0,
                },
            )
        except Exception as exc:
            raise RenderError(f"capture_failed: {out_path}: {exc}") from exc

        if not shot or "data" not in shot:
            raise RenderError(f"capture_failed: {out_path}: empty screenshot response")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(shot["data"]))
        if not out_path.is_file() or out_path.stat().st_size == 0:
            raise RenderError(f"capture_failed: {out_path}: empty file")
        return True
    finally:
        await page.__aexit__(None, None, None)


def generate_topic_cards(
    topic_data: dict[str, Any],
    base_name: str,
    output_dir: Path | None = None,
    author: str = "@Lordporus • OmniPost",
    explicit_count: int | None = None,
    scale: float = DEFAULT_SCALE,
    date_str: str | None = None,
) -> list[Path]:
    """Generates 1, 2, or 3 standalone 9:16 PNG cards for a topic.

    Raises ``RenderError`` when slide content is insufficient or capture fails;
    callers must not substitute a text-only fallback.
    """
    out_dir = output_dir or (ROOT / "scratch" / "cards")
    out_dir.mkdir(parents=True, exist_ok=True)

    from scripts import generate

    count = explicit_count or generate.determine_card_count(topic_data)
    count = max(1, min(3, count))
    slides = build_card_slides(topic_data, count=count, author=author, date_str=date_str)

    cdp_port = int((settings.load().get("browser") or {}).get("port") or 9444)
    browser.ensure_chrome()

    font_css = _font_css()
    created_paths: list[Path] = []
    for idx, slide in enumerate(slides):
        card_html = render_card_html(
            slide,
            current_idx=idx,
            total_count=len(slides),
            author=author,
            font_css=font_css,
        )
        preview_html = out_dir / f"{base_name}_card_{idx + 1}.html"
        preview_html.write_text(card_html, encoding="utf-8")

        target_png = out_dir / f"{base_name}_card_{idx + 1}.png"
        print(f"[CARDS] Rendering 9:16 card {idx + 1}/{len(slides)} -> {target_png.name}...")
        asyncio.run(_capture_card_png(card_html, target_png, port=cdp_port, scale=scale))
        created_paths.append(target_png)

    if not created_paths:
        raise RenderError("capture_failed: no cards were produced")
    return created_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Render 1-3 9:16 storybook PNG cards via CDP")
    parser.add_argument("--test", action="store_true", help="Generate test cards")
    parser.add_argument("--count", type=int, default=None, help="Explicit card count (1-3)")
    parser.add_argument("--scale", type=float, default=DEFAULT_SCALE, help="Device scale factor")
    args = parser.parse_args()

    sample_topic = {
        "headline": "Diffusion at Scale: Eliminating Coordination Bottlenecks",
        "body": "Standard retry loops introduce severe memory fragmentation and state drift under concurrent agent load.",
        "category": "AI ARCHITECTURE",
        "points": [
            "Atomic ledgers guarantee zero duplicate publishing",
            "Local CDP automation bypasses SaaS API pricing and rate limits",
            "Decoupled state machines survive worker thread restarts",
        ],
        "takeaway": "Measure the planner before adding more retries.",
        "url": "https://example.com/diffusion-at-scale",
    }

    cards = generate_topic_cards(
        topic_data=sample_topic,
        base_name="test_topic",
        explicit_count=args.count,
        scale=args.scale,
    )
    print(f"\n[PASS] Successfully generated {len(cards)} visual cards:")
    for c in cards:
        print(f"  - {c}")


if __name__ == "__main__":
    main()
