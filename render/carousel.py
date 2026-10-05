"""CDP HTML-to-PDF Carousel Renderer for OmniPost.

Generates 1080x1080 square vector PDF carousels using the running Chrome/Edge
browser session over DevTools Protocol (CDP Page.printToPDF).
Eliminates heavy C-libraries (WeasyPrint, Cairo, GTK) on Windows/Linux.
"""
from __future__ import annotations

import asyncio
import base64
import html
import json
from pathlib import Path
from typing import Any

from scripts import browser, settings
from scripts.browser import Session

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"


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
        s_title = html.escape(slide.get("title", f"Slide {idx}"))
        s_body = html.escape(slide.get("body", ""))
        s_tag = html.escape(slide.get("tag", tag))

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

        is_last = idx == total_slides
        cta_text = "Connect & Share" if is_last else "Swipe ➔"

        body_html = f'<div class="slide-body">{s_body}</div>' if s_body else ""

        slide_html = f"""
    <section class="slide">
      <header class="header">
        <span class="badge">{s_tag}</span>
        <span class="slide-counter">{idx} / {total_slides}</span>
      </header>
      <div class="content-container">
        <h1 class="slide-title">{s_title}</h1>
        {body_html}
        {bullets_html}
      </div>
      <footer class="footer">
        <span class="author-handle">{html.escape(author)}</span>
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
    """Renders a structured list of slides into a multi-page vector PDF carousel.
    
    Args:
        slides: List of dictionaries each with 'title', optional 'body', and optional 'bullets'.
        title: Metadata carousel title.
        tag: Category label.
        author: Attribution footer.
        output_path: Output .pdf file location.
        port: Browser CDP debugging port (defaults to configured port).
        
    Returns:
        Path to generated PDF file.
    """
    if not slides:
        raise ValueError("Cannot create carousel with empty slides list")

    if output_path is None:
        out_pdf = ROOT / "scratch" / "carousels" / "carousel.pdf"
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
