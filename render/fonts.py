"""Vendored offline font loader for OmniPost renders."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from scripts.errors import RenderError

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

# Vendored, OFL-1.1 licensed Geist faces. Keys are the CSS family/weight pairs.
FONT_FILES: tuple[tuple[str, str, str, str], ...] = (
    ("Geist", "400", "normal", "Geist-Regular.woff2"),
    ("Geist", "600", "normal", "Geist-SemiBold.woff2"),
    ("Geist Mono", "400", "normal", "GeistMono-Regular.woff2"),
)


@lru_cache(maxsize=1)
def get_font_css() -> str:
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


# Alias for backward compatibility
_font_css = get_font_css
