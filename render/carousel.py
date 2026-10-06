"""CDP HTML-to-PDF Carousel Renderer for OmniPost V2.

Generates 1080x1080 square vector PDF carousels using the running Chrome/Edge
browser session over DevTools Protocol (CDP Page.printToPDF).
Eliminates heavy C-libraries (WeasyPrint, Cairo, GTK) on Windows/Linux.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import html
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts import browser, settings
from scripts.browser import Session

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"


def generate_standard_slides(
    topic_data: dict[str, Any],
    author: str = "@Lordporus • OmniPost",
) -> list[dict[str, Any]]:
    """Builds a structured, high-density 5-slide carousel from raw topic intelligence."""
    headline = topic_data.get("headline", "AI Architecture Breakdown")
    body = topic_data.get("body", "Deep architectural analysis and system implications.")
    points = topic_data.get("points") or [
        "Deterministic execution outperforms probabilistic retries.",
        "Atomic state ledgers prevent duplicate posts across channels.",
        "Local CDP automation eliminates expensive 3rd-party SaaS fees.",
    ]
    takeaway = topic_data.get("takeaway", "Build sovereign infrastructure before scaling agents.")
    category = topic_data.get("category", "SYSTEMS DESIGN")

    # Slide 1: Hook & Hero
    s1 = {
        "type": "hero",
        "title": headline,
        "tag": category,
        "body": "A deep dive into production design patterns, failure recovery, and sovereign automation.",
    }

    # Slide 2: The Core Problem / Architectural Context
    s2 = {
        "type": "context",
        "title": "01. The Architectural Context",
        "tag": "PROBLEM SPACE",
        "body": body,
        "bullets": [
            "Why naive single-script loops break under production network strain.",
            "Coordination bottlenecks when scaling multi-platform distribution.",
        ],
    }

    # Slide 3: Deep Technical Breakdown / Code or Insight
    p1 = points[0] if len(points) > 0 else "State Machine Enforced Transitions"
    p2 = points[1] if len(points) > 1 else "Zero-Dependency Local CDP Sockets"
    s3 = {
        "type": "breakdown",
        "title": "02. Deep Technical Breakdown",
        "tag": "IMPLEMENTATION",
        "body": f"Core engineering patterns implemented in production:\n▸ {p1}",
        "code": (
            "// Deterministic State Engine Pattern\n"
            "class PublishingGate {\n"
            "  verify(slot: TimeSlot): boolean {\n"
            "    return ledger.isVerified(slot) && cdp.isHealthy();\n"
            "  }\n"
            "}"
        ),
        "bullets": [p2],
    }

    # Slide 4: Concrete Implementation Checklist
    remaining_points = points[2:] if len(points) > 2 else points
    s4 = {
        "type": "checklist",
        "title": "03. Implementation Checklist",
        "tag": "CHECKLIST",
        "body": "Key rules to enforce across your publishing infrastructure:",
        "bullets": remaining_points + [
            "Atomic state writing to prevent dual-post collisions.",
            "Independent failure isolation per platform channel.",
        ],
    }

    # Slide 5: Strategic CTA & Outro
    s5 = {
        "type": "outro",
        "title": "Sovereign Engineering",
        "tag": "CONCLUSION",
        "body": takeaway or "Build sovereign infrastructure before scaling agents.",
        "cta_label": "Follow for daily system architectures",
    }

    return [s1, s2, s3, s4, s5]


def build_carousel_html(
    slides: list[dict[str, Any]],
    title: str = "OmniPost Carousel",
    tag: str = "ARCHITECTURE",
    author: str = "@Lordporus • OmniPost",
) -> str:
    """Builds a self-contained HTML document containing 1080x1080 slide pages."""
    raw_template = TEMPLATE_PATH.read_text(encoding="utf-8")
    total_slides = len(slides)
    slides_markup = []

    for idx, slide in enumerate(slides, start=1):
        s_type = slide.get("type", "standard")
        s_title = html.escape(slide.get("title", f"Slide {idx}"))
        s_body = html.escape(slide.get("body", ""))
        s_tag = html.escape(slide.get("tag", tag))
        s_code = slide.get("code")

        is_last = (idx == total_slides)
        cta_text = "Connect & Share" if is_last else "Swipe ➔"

        bullets_html = ""
        bullets = slide.get("bullets", [])
        if bullets:
            b_items = []
            for b in bullets:
                b_items.append(
                    f'<li class="bullet-item"><span class="bullet-icon">▸</span>'
                    f'<span>{html.escape(str(b))}</span></li>'
                )
            bullets_html = f'<ul class="bullets">{"".join(b_items)}</ul>'

        code_html = ""
        if s_code:
            code_html = f'<pre class="code-panel"><code>{html.escape(s_code)}</code></pre>'

        if s_type == "hero":
            content_block = f"""
        <h1 class="slide-hero-title">{s_title}</h1>
        <div class="slide-body">{s_body}</div>
        <div class="card-panel">
          {bullets_html or '<div class="slide-body" style="margin:0">Slide deck breakdown of systems engineering patterns.</div>'}
        </div>"""
        elif s_type == "outro":
            cta_btn = slide.get("cta_label", "Connect & Share")
            content_block = f"""
        <div class="outro-card">
          <h1 class="outro-title">{s_title}</h1>
          <div class="outro-desc">{s_body}</div>
          <div class="outro-btn">{html.escape(cta_btn)}</div>
        </div>"""
        else:
            body_block = f'<div class="slide-body">{s_body}</div>' if s_body else ""
            panel_content = f"{code_html}\n{bullets_html}" if (code_html or bullets_html) else ""
            card_panel = f'<div class="card-panel">{panel_content}</div>' if panel_content else ""
            content_block = f"""
        <h1 class="slide-title">{s_title}</h1>
        {body_block}
        {card_panel}"""

        slide_html = f"""
    <section class="slide">
      <header class="header">
        <div class="badge-group">
          <span class="badge">{s_tag}</span>
          <span class="author-badge">{html.escape(author)}</span>
        </div>
        <span class="slide-counter">{idx} / {total_slides}</span>
      </header>
      <div class="content-container">
        {content_block}
      </div>
      <footer class="footer">
        <span class="author-handle"><span class="author-dot"></span>{html.escape(author)}</span>
        <span class="swipe-cta">{cta_text}</span>
      </footer>
    </section>"""
        slides_markup.append(slide_html)

    all_slides_html = "\n".join(slides_markup)
    doc = raw_template.replace("{{MAIN_TITLE}}", html.escape(title))
    doc = doc.replace("{{SLIDES_HTML}}", all_slides_html)
    return doc


async def _render_pdf_cdp(html_file: Path, output_pdf: Path, port: int) -> Path:
    """Invokes Chrome/Edge Page.printToPDF via websocket CDP."""
    browser.ensure_chrome()
    file_url = f"file:///{html_file.resolve().as_posix()}"

    ws = await browser.open_page(file_url)
    session = Session(ws)
    page = await session.__aenter__()

    try:
        await page.send("Page.enable")
        await browser.settle_page(page, 2.0)

        # 1080px at 96 DPI equals exactly 11.25 inches square
        pdf_res = await page.send(
            "Page.printToPDF",
            paperWidth=11.25,
            paperHeight=11.25,
            marginTop=0,
            marginBottom=0,
            marginLeft=0,
            marginRight=0,
            printBackground=True,
            preferCSSPageSize=True,
        )

        pdf_data = pdf_res.get("data")
        if not pdf_data:
            raise RuntimeError("CDP Page.printToPDF returned empty response")

        pdf_bytes = base64.b64decode(pdf_data)
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        output_pdf.write_bytes(pdf_bytes)
        return output_pdf
    finally:
        await page.__aexit__(None, None, None)


def create_carousel_pdf(
    slides: list[dict[str, Any]],
    title: str = "OmniPost Carousel",
    tag: str = "ARCHITECTURE",
    author: str = "@Lordporus • OmniPost",
    output_path: Path | str | None = None,
    port: int | None = None,
) -> Path:
    """Renders a structured list of slides into a multi-page vector PDF carousel."""
    if not slides:
        raise ValueError("Cannot create carousel with empty slides list")

    if output_path is None:
        out_pdf = ROOT / "scratch" / "carousels" / "architecture_carousel.pdf"
    else:
        out_pdf = Path(output_path)

    cfg = settings.load()
    browser_cfg = cfg.get("browser", {})
    cdp_port = port or int(browser_cfg.get("port", 9444) if isinstance(browser_cfg, dict) else 9444)

    # 1. Generate self-contained HTML
    html_content = build_carousel_html(slides=slides, title=title, tag=tag, author=author)

    tmp_dir = ROOT / "scratch" / "carousels"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_html = tmp_dir / "preview.html"
    tmp_html.write_text(html_content, encoding="utf-8")

    # 2. Render to PDF using CDP
    return asyncio.run(_render_pdf_cdp(html_file=tmp_html, output_pdf=out_pdf, port=cdp_port))


def main() -> None:
    """CLI Entrypoint for python -m render.carousel."""
    parser = argparse.ArgumentParser(description="Render LinkedIn PDF Carousels and HTML Previews")
    parser.add_argument("--date", help="Draft plan date (YYYY-MM-DD)")
    parser.add_argument("--draft", help="Explicit path to draft JSON file")
    parser.add_argument("--out", help="Output path for the generated PDF")
    parser.add_argument("--preview-only", action="store_true", help="Only render preview.html without PDF export")
    args = parser.parse_args()

    draft_path: Path | None = None
    if args.draft:
        draft_path = Path(args.draft)
    else:
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        candidate = ROOT / "drafts" / f"{date_str}.json"
        if candidate.exists():
            draft_path = candidate
        else:
            # Look for most recent draft
            drafts = sorted((ROOT / "drafts").glob("*.json"), reverse=True)
            if drafts:
                draft_path = drafts[0]

    topic_data: dict[str, Any] = {}
    author = f"@{settings.load().get('handle', 'Lordporus')} • OmniPost"

    if draft_path and draft_path.exists():
        try:
            plan = json.loads(draft_path.read_text(encoding="utf-8"))
            slots = plan.get("slots", [])
            if slots:
                first_slot = slots[0]
                headline = first_slot.get("headline") or first_slot.get("text", "AI Architecture")[:70]
                li_data = (first_slot.get("platforms") or {}).get("linkedin", {})
                topic_data = {
                    "headline": headline,
                    "body": li_data.get("text", headline),
                    "points": [p.strip() for p in first_slot.get("text", "").split("\n") if p.strip() and not p.startswith("http")][:4],
                    "category": "ARCHITECTURE",
                }
        except Exception as exc:
            print(f"[CAROUSEL] Warning loading draft: {exc}", file=sys.stderr)

    if not topic_data:
        topic_data = {
            "headline": "Autonomous Multi-Platform Distribution Architecture",
            "body": "How sovereign engineering teams scale content without SaaS bloat or API subscriptions.",
            "points": [
                "Deterministic state machine ensures zero dual-post bugs",
                "Chrome DevTools Protocol renders native vector PDFs locally",
                "Cross-channel polymorphic repurposing from a single insight",
            ],
            "category": "SYSTEMS DESIGN",
        }

    slides = generate_standard_slides(topic_data=topic_data, author=author)
    html_content = build_carousel_html(slides=slides, title=topic_data["headline"], author=author)

    carousels_dir = ROOT / "scratch" / "carousels"
    carousels_dir.mkdir(parents=True, exist_ok=True)
    preview_file = carousels_dir / "preview.html"
    preview_file.write_text(html_content, encoding="utf-8")
    print(f"[CAROUSEL] HTML preview generated: {preview_file}")

    if not args.preview_only:
        out_pdf = Path(args.out) if args.out else carousels_dir / "architecture_carousel.pdf"
        print(f"[CAROUSEL] Exporting vector PDF via CDP to: {out_pdf}...")
        try:
            create_carousel_pdf(
                slides=slides,
                title=topic_data["headline"],
                author=author,
                output_path=out_pdf,
            )
            print(f"[CAROUSEL] Success! PDF carousel rendered: {out_pdf}")
        except Exception as exc:
            print(f"[CAROUSEL] CDP PDF render notice: {exc}. (HTML preview is available at {preview_file})")


if __name__ == "__main__":
    main()
