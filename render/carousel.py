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
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts import browser, settings
from scripts.browser import Session

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"

# Scalable SVG Icons
SVG_CHEVRON = (
    '<svg class="bullet-icon-svg" width="20" height="20" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="9 18 15 12 9 6"></polyline></svg>'
)
SVG_CHECK = (
    '<svg class="check-icon-svg" width="22" height="22" viewBox="0 0 24 24" fill="none" '
    'stroke="var(--accent-emerald)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="20 6 9 17 4 12"></polyline></svg>'
)
SVG_SWIPE = (
    '<svg class="swipe-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
    '<line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>'
)


def _clean_text(val: str) -> str:
    """Strips extraneous whitespace, markdown bold markers, and edge quotes."""
    s = val.strip()
    s = re.sub(r"^\*+|\*+$", "", s).strip()
    s = re.sub(r'^["\']|["\']$', "", s).strip()
    return s


def _clean_bullet(val: str) -> str:
    """Strips bullet glyphs (▸, •, -, *, 1.) and surrounding spaces."""
    s = val.strip()
    s = re.sub(r"^([▸•\-\*]|\d+\.)\s*", "", s).strip()
    return _clean_text(s)


def parse_linkedin_payload(payload: str | dict[str, Any]) -> dict[str, Any]:
    """Extracts non-overlapping semantic segments from a LinkedIn payload.
    
    Supports:
      1. Structured topic dict (from scripts/repurpose.py or direct generation)
      2. Monolithic raw text string (from drafts/*.json platforms.linkedin.text)
    """
    if isinstance(payload, dict):
        headline = payload.get("headline") or payload.get("title", "Engineering Insight")
        body = payload.get("body", "")
        raw_points = payload.get("points") or []
        takeaway = payload.get("takeaway", "")
        category = payload.get("category", "SYSTEMS DESIGN")

        # If points are missing and body contains concatenated markers, parse body text
        if (not raw_points or len(raw_points) == 0) and (
            "Key Engineering Takeaways:" in body or "▸" in body or "\n\n" in body
        ):
            composite = f"{headline}\n\n{body}"
            parsed = parse_linkedin_payload(composite)
            parsed["category"] = category.upper()
            return parsed

        # Derive dynamic points and context if missing, without ANY hardcoded strings
        clean_hl_val = _clean_text(headline)
        clean_points = [_clean_bullet(p) for p in raw_points if str(p).strip() and _clean_bullet(p) != clean_hl_val]
        
        ctx = _clean_text(body)
        if not clean_points:
            sentences = [s.strip() for s in re.split(r'[\n.·•►▸;]', ctx) if len(s.strip()) > 15]
            clean_points = [s for s in sentences if s != clean_hl_val][:3]
        if not clean_points:
            clean_points = [f"Core engineering analysis for {clean_hl_val}"]

        dyn_takeaway = _clean_text(takeaway)
        if not dyn_takeaway:
            dyn_takeaway = clean_points[-1] if clean_points else f"Key implementation principle for {clean_hl_val}."

        return {
            "headline": clean_hl_val,
            "problem_context": ctx or f"System architecture deep dive into {clean_hl_val}.",
            "points": clean_points,
            "takeaway": dyn_takeaway,
            "category": str(category).upper(),
        }

    # Monolithic string parsing (from format_linkedin)
    text = str(payload).strip()

    # 1. Strip trailing swipe CTA
    text = re.sub(
        r"(?i)\n*swipe\s+through\s+the\s+architecture\s+carousel.*$",
        "",
        text,
    ).strip()

    # 2. Extract Bottom line / takeaway
    takeaway = ""
    bottom_match = re.search(r"(?i)\n+bottom\s+line:\s*(.+)$", text)
    if bottom_match:
        takeaway = _clean_text(bottom_match.group(1))
        text = text[: bottom_match.start()].strip()

    # 3. Extract Bullet Points / Key Takeaways section
    points: list[str] = []
    takeaways_split = re.split(r"(?i)\n+key\s+(?:engineering\s+)?takeaways:\s*\n*", text)
    if len(takeaways_split) > 1:
        text_before_bullets = takeaways_split[0].strip()
        bullet_block = takeaways_split[1].strip()
        for raw_line in bullet_block.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            cleaned = _clean_bullet(line)
            if cleaned:
                points.append(cleaned)
    else:
        text_before_bullets = text

    # 4. Extract Headline and Problem Context from text_before_bullets
    paragraphs = [p.strip() for p in text_before_bullets.split("\n\n") if p.strip()]
    if len(paragraphs) >= 2:
        headline = paragraphs[0]
        problem_context = " ".join(paragraphs[1:])
    elif len(paragraphs) == 1:
        lines = [line.strip() for line in paragraphs[0].split("\n") if line.strip()]
        headline = lines[0] if lines else "Engineering Architecture"
        problem_context = " ".join(lines[1:]) if len(lines) > 1 else ""
    else:
        headline = "Engineering Architecture"
        problem_context = ""

    # Clean out any leftover headline substring from problem_context
    clean_hl = _clean_text(headline)
    if problem_context.startswith(clean_hl):
        problem_context = problem_context[len(clean_hl) :].strip()

    # Filter out any points that literally repeat the headline
    points = [p for p in points if p != clean_hl]

    if not problem_context:
        problem_context = f"Production architecture deep dive and engineering breakdown for {clean_hl}."

    if not points:
        sentences = [s.strip() for s in re.split(r'[\n.·•►▸;]', text_before_bullets) if len(s.strip()) > 15]
        points = [s for s in sentences if s != clean_hl][:3]
    if not points:
        points = [f"Core system design consideration for {clean_hl}"]

    if not takeaway:
        takeaway = points[-1] if points else f"Production implementation takeaway for {clean_hl}."

    return {
        "headline": clean_hl,
        "problem_context": _clean_text(problem_context),
        "points": points,
        "takeaway": takeaway,
        "category": "TECH ARCHITECTURE",
    }


def generate_standard_slides(
    topic_data: dict[str, Any] | str,
    author: str = "@Lordporus • OmniPost",
) -> list[dict[str, Any]]:
    """Builds a structured, high-density 4-slide carousel enforcing zero hardcoded text."""
    parsed = parse_linkedin_payload(topic_data)
    headline = parsed["headline"]
    problem_context = parsed["problem_context"]
    points = parsed["points"]
    takeaway = parsed["takeaway"]
    category = parsed["category"]

    if isinstance(topic_data, dict) and "carousel" in topic_data and isinstance(topic_data["carousel"], dict):
        raw_slides = topic_data["carousel"].get("slides", [])
        if raw_slides and isinstance(raw_slides, list) and len(raw_slides) >= 2:
            parsed_slides = []
            total = len(raw_slides)
            for idx, s in enumerate(raw_slides):
                s_header = str(s.get("header") or s.get("title") or f"Slide {idx+1}").strip()
                s_body = str(s.get("body") or "").strip()
                s_bullets = s.get("bullets") if isinstance(s.get("bullets"), list) else []
                if idx == 0:
                    s_type = "hero"
                    s_tag = category
                elif idx == total - 1:
                    s_type = "checklist_cta"
                    s_tag = "CHECKLIST"
                elif idx == 1:
                    s_type = "problem"
                    s_tag = "CONTEXT"
                else:
                    s_type = "solution"
                    s_tag = "FRAMEWORK"
                parsed_slides.append({
                    "type": s_type,
                    "title": s_header,
                    "tag": s_tag,
                    "body": s_body,
                    "bullets": s_bullets,
                })
            return parsed_slides

    # Slide 1: Hook & Hero (Headline ONLY in Slide 1)
    s1 = {
        "type": "hero",
        "title": headline,
        "tag": category,
        "body": problem_context[:160] if problem_context else f"An architectural deep dive into {headline}.",
    }

    # Slide 2: Architectural Bottleneck / Problem Space (Derived 100% dynamically)
    problem_sentences = [s.strip() for s in re.split(r'[\n.·•►▸;]', problem_context) if len(s.strip()) > 15]
    prob_bullets = problem_sentences[:3] if len(problem_sentences) >= 2 else (points[:2] if len(points) >= 2 else [f"Key technical challenges in {headline}"])
    s2 = {
        "type": "problem",
        "title": f"The Bottleneck in {headline[:35]}",
        "tag": "BOTTLENECK",
        "body": problem_context if len(problem_context) < 300 else problem_context[:297] + "...",
        "bullets": prob_bullets,
    }

    # Slide 3: Deep Technical Solution / Architecture (Derived 100% dynamically)
    sol_headline = points[0] if points else f"Architecture Design for {headline[:30]}"
    sol_bullets = points[1:3] if len(points) > 1 else ([problem_context[:120]] if problem_context else [headline])
    code_block = ""
    if isinstance(topic_data, dict):
        code_block = str(topic_data.get("code") or topic_data.get("code_snippet") or "")
    s3 = {
        "type": "solution",
        "title": "System Architecture",
        "tag": "IMPLEMENTATION",
        "body": sol_headline,
        "code": code_block,
        "bullets": sol_bullets,
    }

    # Slide 4: Production Checklist & Dynamic Outro (Derived 100% dynamically)
    checklist_points = points[2:] if len(points) > 2 else (points if points else [takeaway])
    s4 = {
        "type": "checklist_cta",
        "title": "Production Checklist",
        "tag": "CHECKLIST",
        "body": takeaway or f"Architectural foundation for {headline}.",
        "bullets": checklist_points,
        "cta_label": f"Follow for {category.title()} Architectures",
    }

    return [s1, s2, s3, s4]


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

        # Bullets formatting
        bullets = slide.get("bullets", [])
        bullets_html = ""
        if bullets:
            b_items = []
            for b in bullets:
                icon = SVG_CHECK if s_type == "checklist_cta" else SVG_CHEVRON
                b_items.append(
                    f'<li class="bullet-item">{icon}'
                    f'<span>{html.escape(str(b))}</span></li>'
                )
            bullets_html = f'<ul class="bullets">{"".join(b_items)}</ul>'

        # Code block formatting
        code_html = ""
        if s_code:
            code_html = f'<pre class="code-panel"><code>{html.escape(s_code)}</code></pre>'

        # Polymorphic slide body templates
        # Polymorphic slide body templates
        if s_type == "hero":
            hero_panel_inner = bullets_html if bullets_html else f"""
          <div class="hero-overview-badge">
            <span class="hero-pulse"></span>
            <span>PRODUCTION BLUEPRINT</span>
          </div>
          <div class="hero-subtext">{html.escape(s_body)}</div>"""
            content_block = f"""
        <h1 class="slide-hero-title">{s_title}</h1>
        <div class="slide-hero-subtitle">{s_body}</div>
        <div class="card-panel hero-card-panel">
          {hero_panel_inner}
        </div>"""
        elif s_type == "problem":
            card_panel = f'<div class="card-panel card-panel-amber">{bullets_html}</div>' if bullets_html else ""
            content_block = f"""
        <h1 class="slide-title">{s_title}</h1>
        <div class="slide-body">{s_body}</div>
        {card_panel}"""
        elif s_type == "solution":
            inner = f"{code_html}\n{bullets_html}".strip()
            card_panel = f'<div class="card-panel">{inner}</div>' if inner else ""
            content_block = f"""
        <h1 class="slide-title">{s_title}</h1>
        <div class="slide-body">{s_body}</div>
        {card_panel}"""
        elif s_type == "checklist_cta":
            cta_btn = slide.get("cta_label", "Follow for daily system architectures")
            card_panel = f'<div class="card-panel checklist-panel">{bullets_html}</div>' if bullets_html else ""
            content_block = f"""
        <h1 class="slide-title">{s_title}</h1>
        {card_panel}
        <div class="outro-banner">
          <div class="outro-takeaway-label">CORE TAKEAWAY</div>
          <div class="outro-takeaway">{s_body}</div>
          <div class="outro-btn">{html.escape(cta_btn)}</div>
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
            # Fallback for standard or generic slide definitions
            body_block = f'<div class="slide-body">{s_body}</div>' if s_body else ""
            panel_content = f"{code_html}\n{bullets_html}" if (code_html or bullets_html) else ""
            card_panel = f'<div class="card-panel">{panel_content}</div>' if panel_content else ""
            content_block = f"""
        <h1 class="slide-title">{s_title}</h1>
        {body_block}
        {card_panel}"""

        badge_class = "badge badge-amber" if s_type == "problem" else "badge"

        # Modern pagination pills (/taste-design clean indicators, no filler text)
        pills = []
        for p_idx in range(1, total_slides + 1):
            active_cls = " active" if p_idx == idx else ""
            pills.append(f'<span class="pagination-pill{active_cls}"></span>')
        pagination_html = f'<div class="slide-pagination">{"".join(pills)}</div>'

        slide_html = f"""
    <section class="slide">
      <header class="header">
        <div class="badge-group">
          <span class="{badge_class}">{s_tag}</span>
          <span class="author-badge">{html.escape(author)}</span>
        </div>
        <span class="slide-counter">{idx} / {total_slides}</span>
      </header>
      <div class="content-container">
        {content_block}
      </div>
      <footer class="footer">
        <span class="author-handle"><span class="author-dot"></span>{html.escape(author)}</span>
        {pagination_html}
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
    parser.add_argument("--slot", help="Specific slot to render (e.g. 20:00)")
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
            drafts = sorted((ROOT / "drafts").glob("*.json"), reverse=True)
            for d in drafts:
                try:
                    data = json.loads(d.read_text(encoding="utf-8"))
                    slots = data.get("slots", [])
                    if any((s.get("text") or s.get("headline") or (s.get("platforms", {}).get("linkedin", {}).get("text"))) for s in slots):
                        draft_path = d
                        break
                except Exception:
                    continue
            if not draft_path and drafts:
                draft_path = drafts[0]

    author = f"@{settings.load().get('handle', 'Lordporus')} • OmniPost"
    raw_payload: Any = None

    if draft_path and draft_path.exists():
        try:
            plan = json.loads(draft_path.read_text(encoding="utf-8"))
            slots = plan.get("slots", [])
            for s in slots:
                if getattr(args, "slot", None) and s.get("slot") != args.slot.strip():
                    continue
                li_data = (s.get("platforms") or {}).get("linkedin", {})
                if li_data.get("text") and li_data.get("text").strip():
                    raw_payload = li_data.get("text")
                    break
                elif s.get("headline") or s.get("text"):
                    raw_payload = s
                    break
        except Exception as exc:
            print(f"[CAROUSEL] Warning loading draft: {exc}", file=sys.stderr)

    if not raw_payload:
        raw_payload = {
            "headline": "Autonomous Multi-Platform Distribution Architecture",
            "body": "How sovereign engineering teams scale content without SaaS bloat or API subscriptions.",
            "points": [
                "Deterministic state machine ensures zero dual-post bugs",
                "Chrome DevTools Protocol renders native vector PDFs locally",
                "Cross-channel polymorphic repurposing from a single insight",
            ],
            "category": "SYSTEMS DESIGN",
        }

    slides = generate_standard_slides(topic_data=raw_payload, author=author)
    carousel_title = slides[0]["title"]
    html_content = build_carousel_html(slides=slides, title=carousel_title, author=author)

    carousels_dir = ROOT / "scratch" / "carousels"
    carousels_dir.mkdir(parents=True, exist_ok=True)
    preview_file = carousels_dir / "preview.html"
    preview_file.write_text(html_content, encoding="utf-8")
    print(f"[CAROUSEL] HTML preview generated: {preview_file}")

    if not args.preview_only:
        if args.out:
            out_pdf = Path(args.out)
        else:
            date_tag = args.date or (draft_path.stem if draft_path else datetime.now().strftime("%Y-%m-%d"))
            slot_tag = (args.slot or "default").replace(":", "")
            out_pdf = carousels_dir / f"carousel_{date_tag}_{slot_tag}.pdf"

        print(f"[CAROUSEL] Exporting vector PDF via CDP to: {out_pdf}...")
        try:
            create_carousel_pdf(
                slides=slides,
                title=carousel_title,
                author=author,
                output_path=out_pdf,
            )
            print(f"[CAROUSEL] Success! PDF carousel rendered: {out_pdf}")
        except Exception as exc:
            print(f"[CAROUSEL] CDP PDF render notice: {exc}. (HTML preview is available at {preview_file})")


if __name__ == "__main__":
    main()
