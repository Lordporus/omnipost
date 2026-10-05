"""Programmatic dark-mode 16:9 infocard generator for OmniPost.

Uses Pillow (PIL) to generate 1200x675 PNG cards with typography,
category badges, and clean border accents without external cloud services.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent

# Standard 16:9 canvas dimensions
WIDTH = 1200
HEIGHT = 675

# Color Palette (Dark Developer Slate)
BG_COLOR = (11, 15, 25)         # #0b0f19
CARD_BG = (24, 32, 47)          # #18202f
BORDER_COLOR = (51, 65, 85)     # #334155
ACCENT_COLOR = (56, 189, 248)   # #38bdf8 (Sky blue)
TEXT_TITLE = (248, 250, 252)    # #f8fafc
TEXT_BODY = (203, 213, 225)     # #cbd5e1
TEXT_MUTED = (148, 163, 184)    # #94a3b8
BADGE_BG = (15, 23, 42)         # #0f172a


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Safely loads a system TrueType font or falls back to Pillow's default font."""
    font_candidates = []
    if os.name == "nt":  # Windows
        win_dir = os.environ.get("WINDIR", r"C:\Windows")
        fonts_dir = Path(win_dir) / "Fonts"
        if bold:
            font_candidates.extend([
                fonts_dir / "segoeuib.ttf",
                fonts_dir / "arialbd.ttf",
                fonts_dir / "calibrib.ttf",
            ])
        else:
            font_candidates.extend([
                fonts_dir / "segoeui.ttf",
                fonts_dir / "arial.ttf",
                fonts_dir / "calibri.ttf",
            ])
    else:  # Linux / macOS
        font_candidates.extend([
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/System/Library/Fonts/HelveticaNeue.ttc"),
            Path("/Library/Fonts/Arial.ttf"),
        ])

    for font_path in font_candidates:
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size)
            except Exception:
                continue

    # Fallback to default bitmap/scalable font
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Wraps text so lines don't exceed max_width."""
    lines: List[str] = []
    paragraphs = text.split("\n")

    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split(" ")
        current_line = []
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
            if line_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))

    return lines


def create_infocard(
    title: str,
    body: str,
    tag: str = "INSIGHT",
    author: str = "@Lordporus • OmniPost",
    output_path: Path | str | None = None,
) -> Path:
    """Generates a 16:9 (1200x675) dark-mode PNG infocard.
    
    Args:
        title: Headline text (displayed large, up to 2-3 lines).
        body: Core insight or bullet points.
        tag: Category badge text in top header.
        author: Branding handle in footer.
        output_path: Destination file path. If None, saves to scratch/infocards/card.png.
        
    Returns:
        Path to the saved PNG card.
    """
    if output_path is None:
        out_file = ROOT / "scratch" / "infocards" / "card.png"
    else:
        out_file = Path(output_path)

    out_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Canvas Setup
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 2. Main Card Container (Outer Margin 48px)
    margin = 48
    card_rect = [margin, margin, WIDTH - margin, HEIGHT - margin]
    draw.rounded_rectangle(card_rect, radius=24, fill=CARD_BG, outline=BORDER_COLOR, width=2)

    # Top accent glowing line on the card
    draw.line([(margin + 32, margin), (margin + 180, margin)], fill=ACCENT_COLOR, width=4)

    # 3. Fonts
    font_badge = _load_font(20, bold=True)
    font_title = _load_font(42, bold=True)
    font_body = _load_font(26, bold=False)
    font_footer = _load_font(20, bold=False)

    content_x = margin + 48
    content_y = margin + 40
    max_content_width = WIDTH - (margin * 2) - 96

    # 4. Header: Category Badge
    if tag:
        tag_str = tag.upper().strip()
        tag_bbox = draw.textbbox((0, 0), tag_str, font=font_badge)
        tag_w = tag_bbox[2] - tag_bbox[0]
        tag_h = tag_bbox[3] - tag_bbox[1]

        badge_box = [content_x, content_y, content_x + tag_w + 24, content_y + tag_h + 16]
        draw.rounded_rectangle(badge_box, radius=8, fill=BADGE_BG, outline=ACCENT_COLOR, width=1)
        draw.text((content_x + 12, content_y + 8), tag_str, font=font_badge, fill=ACCENT_COLOR)
        content_y += tag_h + 36
    else:
        content_y += 16

    # 5. Headline Text
    title_lines = _wrap_text(title, font_title, max_content_width, draw)[:3]  # Limit to 3 lines
    for line in title_lines:
        draw.text((content_x, content_y), line, font=font_title, fill=TEXT_TITLE)
        content_y += 54
    content_y += 18

    # Subtle separator line
    draw.line([(content_x, content_y), (content_x + 100, content_y)], fill=BORDER_COLOR, width=2)
    content_y += 24

    # 6. Body Text
    body_lines = _wrap_text(body, font_body, max_content_width, draw)
    # Available height before footer
    max_body_y = HEIGHT - margin - 70
    for line in body_lines:
        if content_y >= max_body_y:
            break
        draw.text((content_x, content_y), line, font=font_body, fill=TEXT_BODY)
        content_y += 38

    # 7. Footer: Branding
    footer_y = HEIGHT - margin - 44
    draw.text((content_x, footer_y), author, font=font_footer, fill=TEXT_MUTED)

    # Watermark indicator
    draw.text((WIDTH - margin - 150, footer_y), "ENGINEERING LOG", font=font_badge, fill=(71, 85, 105))

    img.save(out_file, format="PNG")
    return out_file
