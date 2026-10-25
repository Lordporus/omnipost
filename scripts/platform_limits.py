"""Shared platform copy limits and counting rules for OmniPost.

This module is the single source of truth for the target copy ranges and for
the platform-specific counting rules:

* X uses a weighted count. ASCII/URL characters count as 1, while CJK ranges and
  emoji count as 2. Combining marks, variation selectors, emoji modifiers, and
  ZWJ joiners add no weight.
* Bluesky uses grapheme clusters. The implementation is a stdlib-only
  approximation that handles combining marks, ZWJ sequences, emoji modifiers,
  keycaps, and regional-indicator flags.
* Threads and LinkedIn use Unicode code points (``len(text)``).

All truncation is word-boundary based and reserves room for the ellipsis. A
word is never split, including URLs, because whitespace-delimited tokens are
treated as indivisible.
"""
from __future__ import annotations

import re
import unicodedata

try:  # package import (tests, pipeline)
    from scripts.errors import CopyValidationError
except ImportError:  # direct script execution
    from errors import CopyValidationError


LIMITS: dict[str, dict[str, int]] = {
    "x": {"min": 220, "max": 275, "hard_max": 280},
    "bluesky": {"min": 240, "max": 295, "hard_max": 300},
    "threads": {"min": 350, "max": 480, "hard_max": 500},
    "linkedin": {"min": 500, "max": 2500, "hard_max": 3000},
}

_ALIASES = {
    "twitter": "x",
    "bsky": "bluesky",
}

# Ranges counted as 2 by X's weighted counter. These cover CJK ideographs,
# kana, Hangul, CJK compatibility/full-width forms, and emoji/symbol blocks.
_X_WEIGHT_2_RANGES: tuple[tuple[int, int], ...] = (
    (0x1100, 0x115F),  # Hangul Jamo
    (0x2600, 0x27BF),  # Miscellaneous symbols / dingbats
    (0x2E80, 0xA4CF),  # CJK radicals through Yi / CJK unified ideographs
    (0xA960, 0xA97F),  # Hangul Jamo Extended-A
    (0xAC00, 0xD7A3),  # Hangul syllables
    (0xF900, 0xFAFF),  # CJK compatibility ideographs
    (0xFE10, 0xFE19),  # Vertical forms
    (0xFE30, 0xFE6F),  # CJK compatibility forms
    (0xFF00, 0xFF60),  # Full-width forms
    (0xFFE0, 0xFFE6),  # Full-width signs
    (0x1F000, 0x1FAFF),  # Mahjong, playing cards, enclosed characters, emoji
    (0x20000, 0x2FA1F),  # CJK unified ideographs extensions
)

_ZERO_WEIGHT_CODEPOINTS = {
    0x200D,  # zero-width joiner
    0xFE0E,  # text variation selector
    0xFE0F,  # emoji variation selector
    0x20E3,  # combining enclosing keycap
}


def _normalise_platform(platform: str) -> str:
    key = str(platform or "").strip().lower()
    return _ALIASES.get(key, key)


def _limits_for(platform: str) -> tuple[str, dict[str, int]]:
    key = _normalise_platform(platform)
    if key not in LIMITS:
        raise ValueError(f"Unknown platform for copy limits: {platform!r}")
    return key, LIMITS[key]


def _is_zero_weight(ch: str) -> bool:
    cp = ord(ch)
    if cp in _ZERO_WEIGHT_CODEPOINTS:
        return True
    if 0x1F3FB <= cp <= 0x1F3FF:  # emoji skin-tone modifiers
        return True
    if 0xE0020 <= cp <= 0xE007F:  # emoji tag characters
        return True
    return unicodedata.category(ch) in ("Mn", "Me")


def _is_regional_indicator(ch: str) -> bool:
    return 0x1F1E6 <= ord(ch) <= 0x1F1FF


def _is_x_weight_2(ch: str) -> bool:
    cp = ord(ch)
    return any(start <= cp <= end for start, end in _X_WEIGHT_2_RANGES)


def count_x_weighted(text: str) -> int:
    """Return X's approximate weighted length for *text*.

    ASCII and URL characters count as 1. CJK characters and emoji count as 2.
    Zero-width/combining characters add no weight. A regional-indicator pair
    (a flag) counts as one emoji (2 total).
    """
    total = 0
    previous_was_regional = False
    for ch in str(text or ""):
        if _is_zero_weight(ch):
            previous_was_regional = False
            continue
        if _is_regional_indicator(ch):
            if previous_was_regional:
                previous_was_regional = False
                continue
            total += 2
            previous_was_regional = True
            continue
        previous_was_regional = False
        total += 2 if _is_x_weight_2(ch) else 1
    return total


def count_graphemes(text: str) -> int:
    """Return an approximate grapheme-cluster count for *text*.

    This is intentionally stdlib-only. It handles the common cases that matter
    for social copy: combining marks, emoji modifiers, keycaps, ZWJ sequences,
    and regional-indicator flags. It is not a complete UAX #29 implementation
    (for example, Indic conjunct clusters may count as more than one).
    """
    count = 0
    previous_was_regional = False
    join_next = False
    previous_was_cr = False
    for ch in str(text or ""):
        cp = ord(ch)
        if ch == "\n" and previous_was_cr:
            previous_was_cr = False
            continue
        previous_was_cr = ch == "\r"
        if join_next:
            join_next = False
            previous_was_regional = False
            continue
        if ch == "\u200d":
            join_next = True
            previous_was_regional = False
            continue
        if _is_zero_weight(ch):
            if count == 0:
                count = 1
            previous_was_regional = False
            continue
        if _is_regional_indicator(ch):
            if previous_was_regional:
                previous_was_regional = False
                continue
            count += 1
            previous_was_regional = True
            continue
        previous_was_regional = False
        count += 1
    return count


def count_chars(text: str) -> int:
    """Return the Unicode code-point count for *text*."""
    return len(str(text or ""))


def count_for(platform: str, text: str) -> int:
    """Count *text* using the platform's real limit rule."""
    key = _normalise_platform(platform)
    if key == "x":
        return count_x_weighted(text)
    if key == "bluesky":
        return count_graphemes(text)
    if key in ("threads", "linkedin"):
        return count_chars(text)
    raise ValueError(f"Unknown platform for copy counting: {platform!r}")


def truncate_words(
    text: str,
    limit: int,
    platform: str,
    ellipsis: str = "...",
) -> str:
    """Truncate *text* to *limit* measured units on a word boundary.

    The limit is measured with the platform's counter, not as a raw character
    offset. The ellipsis is included in the budget, and whitespace-delimited
    tokens (including URLs) are never split.
    """
    raw = str(text or "")
    limit = int(limit)
    if limit <= 0:
        return ""
    if count_for(platform, raw) <= limit:
        return raw

    ellipsis_cost = count_for(platform, ellipsis)
    if ellipsis_cost > limit:
        return ""

    best = ""
    for match in re.finditer(r"\S+", raw):
        candidate = raw[: match.end()].strip()
        if not candidate:
            continue
        with_ellipsis = f"{candidate}{ellipsis}"
        if count_for(platform, with_ellipsis) <= limit:
            best = with_ellipsis
            continue
        break

    if best:
        return best
    return ellipsis


def validate(platform: str, text: str) -> None:
    """Raise :class:`CopyValidationError` when *text* is outside the limits."""
    key, limits = _limits_for(platform)
    measured = count_for(key, text)
    if measured < limits["min"] or measured > limits["hard_max"]:
        raise CopyValidationError(
            (
                f"{key} copy is {measured} units; expected "
                f"{limits['min']}-{limits['max']} (hard max {limits['hard_max']})"
            ),
            platform=key,
            count=measured,
            limits=limits,
        )


def fit(platform: str, text: str) -> str:
    """Fit *text* to the platform's target maximum without padding.

    If the source cannot reach the platform minimum after word-boundary
    truncation, raise :class:`CopyValidationError` rather than fabricating
    filler copy.
    """
    key, limits = _limits_for(platform)
    fitted = truncate_words(text, limits["max"], key)
    measured = count_for(key, fitted)
    if measured < limits["min"]:
        raise CopyValidationError(
            (
                f"{key} copy is only {measured} units after fitting; "
                f"minimum is {limits['min']}"
            ),
            platform=key,
            count=measured,
            limits=limits,
        )
    return fitted
