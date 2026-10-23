"""CDP Retina PNG Multi-Card Renderer for OmniPost.

Generates 1 to 3 standalone 1080x1080 retina PNG images (2160x2160 pixels at 2x scale)
using the running browser session over DevTools Protocol (CDP Page.captureScreenshot).
Conforms strictly to /gpt-taste design guidelines:
- Deep canvas (#080A0F) with singular precision accent (#00E599).
- Wide typography (Geist + Geist Mono) with max 2-line headings.
- Clean Bento panel cards with zero empty voids.
- Crisp author identity: @Lordporus • OmniPost.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

from scripts import browser, settings
from scripts.browser import Session

ROOT = Path(__file__).resolve().parent.parent
CARD_TEMPLATE_PATH = Path(__file__).resolve().parent / "card_template.html"

SVG_CHEVRON = (
    '<svg class="bullet-icon-svg" width="22" height="22" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="9 18 15 12 9 6"></polyline></svg>'
)


def _clean_text(val: str) -> str:
    s = val.strip()
    s = re.sub(r"^\*+|\*+$", "", s).strip()
    s = re.sub(r'^["\']|["\']$', "", s).strip()
    return s


def build_card_slides(topic_data: dict[str, Any], count: int, author: str = "@Lordporus • OmniPost") -> list[dict[str, Any]]:
    """Synthesizes exactly 1, 2, or 3 structured card definitions based on count."""
    headline = _clean_text(str(topic_data.get("headline") or "Engineering Architecture"))
    body = _clean_text(str(topic_data.get("body") or ""))
    category = str(topic_data.get("category") or "SYSTEMS DESIGN").upper()
    points = [_clean_text(str(p)) for p in topic_data.get("points", []) if _clean_text(str(p))]

    slides: list[dict[str, Any]] = []

    if count == 1:
        # Single Hero Card
        slides.append({
            "tag": category,
            "headline": headline,
            "body": body if len(body) > 20 else "Key architectural tradeoffs and production engineering principles.",
            "panel_tag": "CORE SPECIFICATION",
            "bullets": points[:3] if points else ["Deterministic state machine guarantees", "Decoupled execution boundaries"],
        })
    elif count == 2:
        # Card 1: Problem / Friction
        slides.append({
            "tag": category,
            "headline": headline,
            "body": body if len(body) > 20 else "The architectural bottleneck in high-concurrency production systems.",
            "panel_tag": "ARCHITECTURAL FRICTION",
            "bullets": [points[0]] if points else ["Uncoordinated state drift creates cascading failures"],
        })
        # Card 2: Solution / Takeaway
        slides.append({
            "tag": "SOLUTION PATTERN",
            "headline": "Engineering Implementation & Tradeoffs",
            "body": "How sovereign architectures eliminate failure modes through isolated execution.",
            "panel_tag": "PRODUCTION PRINCIPLES",
            "bullets": points[1:3] if len(points) > 1 else (points if points else ["Atomic state logging with local CDP execution"]),
        })
    else:
        # 3 Cards: Workflow
        slides.append({
            "tag": category,
            "headline": headline,
            "body": body if len(body) > 20 else "System context and production failure surface.",
            "panel_tag": "THE BOTTLENECK",
            "bullets": [points[0]] if points else ["Brittle abstractions fail under concurrent scale"],
        })
        slides.append({
            "tag": "IMPLEMENTATION",
            "headline": "Deterministic State Architecture",
            "body": "Decoupled state machines survive worker thread restarts and network jitter.",
            "panel_tag": "EXECUTION ENGINE",
            "bullets": [points[1]] if len(points) > 1 else ["Atomic state ledgers eliminate duplicate execution"],
        })
        slides.append({
            "tag": "VERIFICATION",
            "headline": "Production Reliability Checklist",
            "body": "Operational checklist for scaling sovereign distribution without SaaS bloat.",
            "panel_tag": "CHECKLIST",
            "bullets": points[2:4] if len(points) > 2 else [
                "Local CDP automation with isolated session profiles",
                "Automated DOM failure telemetry and readback verification",
            ],
        })

    return slides


def render_card_html(slide: dict[str, Any], current_idx: int, total_count: int, author: str) -> str:
    """Fills card_template.html for a single slide."""
    template = CARD_TEMPLATE_PATH.read_text(encoding="utf-8")

    counter_str = f"{current_idx + 1:02d} / {total_count:02d}"
    headline = html.escape(slide["headline"])
    tag = html.escape(slide["tag"])

    body_html = ""
    if slide.get("body"):
        body_html = f'<p class="card-body">{html.escape(slide["body"])}</p>'

    panel_html = ""
    bullets = slide.get("bullets", [])
    if bullets or slide.get("panel_tag"):
        panel_tag = html.escape(slide.get("panel_tag", "KEY TAKEAWAYS"))
        bullet_items = "".join([
            f'<li class="bullet-item">{SVG_CHEVRON}<span>{html.escape(b)}</span></li>'
            for b in bullets
        ])
        panel_html = f"""
        <div class="panel panel-highlight">
          <div class="panel-tag">
            <span class="panel-pulse"></span>
            <span>{panel_tag}</span>
          </div>
          <ul class="bullets">
            {bullet_items}
          </ul>
        </div>
        """

    res = template.replace("{{TITLE}}", headline)
    res = res.replace("{{TAG}}", tag)
    res = res.replace("{{AUTHOR}}", html.escape(author))
    res = res.replace("{{COUNTER}}", counter_str)
    res = res.replace("{{HEADLINE}}", headline)
    res = res.replace("{{BODY_HTML}}", body_html)
    res = res.replace("{{PANEL_HTML}}", panel_html)

    return res


async def _capture_card_png(html_content: str, out_path: Path, port: int) -> bool:
    """Loads HTML via data URL and captures 2160x2160 PNG at 2x scale factor via CDP."""
    b64_html = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")
    data_url = f"data:text/html;base64,{b64_html}"

    ws = await browser.open_page(data_url)
    sess = Session(ws)
    page = await sess.__aenter__()
    try:
        await page.send("Page.enable")
        # Set viewport to 1080x1080 with 2x device scale factor (resulting in 2160x2160 retina PNG)
        await page.send(
            "Emulation.setDeviceMetricsOverride",
            width=1080,
            height=1080,
            deviceScaleFactor=2.0,
            mobile=False,
        )
        await asyncio.sleep(1.2)  # Settle font rendering (Geist)

        shot = await page.send(
            "Page.captureScreenshot",
            format="png",
            clip={
                "x": 0,
                "y": 0,
                "width": 1080,
                "height": 1080,
                "scale": 1.0,
            },
        )

        if shot and "data" in shot:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(base64.b64decode(shot["data"]))
            return True
        return False
    finally:
        await page.__aexit__(None, None, None)


def generate_topic_cards(
    topic_data: dict[str, Any],
    base_name: str,
    output_dir: Path | None = None,
    author: str = "@Lordporus • OmniPost",
    explicit_count: int | None = None,
) -> list[Path]:
    """Generates 1, 2, or 3 standalone retina PNG cards for a topic."""
    out_dir = output_dir or (ROOT / "scratch" / "cards")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Determine card count
    try:
        from scripts import generate
        count = explicit_count or generate.determine_card_count(topic_data)
    except Exception:
        count = explicit_count or 2

    # Clamp between 1 and 3
    count = max(1, min(3, count))
    slides = build_card_slides(topic_data, count=count, author=author)

    cdp_port = int((settings.load().get("browser") or {}).get("port") or 9444)
    browser.ensure_chrome()

    created_paths: list[Path] = []
    for idx, slide in enumerate(slides):
        card_html = render_card_html(slide, current_idx=idx, total_count=count, author=author)
        preview_html = out_dir / f"{base_name}_card_{idx + 1}.html"
        preview_html.write_text(card_html, encoding="utf-8")

        target_png = out_dir / f"{base_name}_card_{idx + 1}.png"
        print(f"[CARDS] Rendering retina card {idx + 1}/{count} -> {target_png.name}...")
        try:
            ok = asyncio.run(_capture_card_png(card_html, target_png, port=cdp_port))
            if ok and target_png.exists():
                created_paths.append(target_png)
        except Exception as exc:
            print(f"[CARDS] Error rendering card {idx + 1}: {exc}", file=sys.stderr)

    return created_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Render 1 to 3 Retina PNG visual cards via CDP")
    parser.add_argument("--test", action="store_true", help="Generate test cards")
    parser.add_argument("--count", type=int, default=None, help="Explicit card count (1-3)")
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
    }

    cards = generate_topic_cards(
        topic_data=sample_topic,
        base_name="test_topic",
        explicit_count=args.count,
    )
    print(f"\n[PASS] Successfully generated {len(cards)} visual cards:")
    for c in cards:
        print(f"  - {c}")


if __name__ == "__main__":
    main()
