"""Live CDP Profile Analytics & Viral Radar for OmniPost.

Closes the feedback loop by reading real engagement metrics (views, impressions,
likes, replies) from X, LinkedIn, Bluesky, and Threads via the active CDP browser,
syncing top-performing hooks into references/voice-samples.md, and surfacing
high-velocity AI/automation posts for fast manual reply/quote distribution.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts import browser, settings
except ImportError:
    import browser
    import settings

AUTO_START = "<!-- auto-samples-start -->"
AUTO_END = "<!-- auto-samples-end -->"

RADAR_KEYWORD_RE = re.compile(
    r"\b(?:ai|llms?|agents?|voice|automation|bots?|rag|claude|gpt|gemini|mcp|coding|workflows?|n8n|cdp|dev)\b",
    re.IGNORECASE,
)


def _parse_compact_number(token: str) -> float:
    """Parse '1.2K', '3M', or '604' into a float."""
    raw = str(token or "").strip().upper().replace(",", "")
    if not raw:
        return 0.0
    mult = 1.0
    if raw.endswith("K"):
        mult = 1_000.0
        raw = raw[:-1]
    elif raw.endswith("M"):
        mult = 1_000_000.0
        raw = raw[:-1]
    try:
        return float(raw) * mult
    except ValueError:
        return 0.0


def parse_metric_score(metrics_text: str) -> float:
    """Convert platform metric strings into a weighted engagement score."""
    text = str(metrics_text or "").lower()
    if not text:
        return 0.0

    score = 0.0
    for label, weight in (
        ("repl", 5.0),
        ("comment", 5.0),
        ("repost", 4.0),
        ("retweet", 4.0),
        ("like", 3.0),
        ("reaction", 3.0),
        ("impression", 0.05),
        ("view", 0.05),
    ):
        match = re.search(rf"([\d,.]+[km]?)\s+{label}", text)
        if match:
            score += _parse_compact_number(match.group(1)) * weight
    return round(score, 2)


def _format_voice_samples_block(posts_by_platform: dict[str, list[dict[str, Any]]]) -> str:
    """Render ranked Winning Samples and Anti-Patterns markdown block."""
    winners: dict[str, list[str]] = {}
    anti_patterns: list[str] = []

    for platform, items in posts_by_platform.items():
        if not items:
            continue
        scored = sorted(
            items,
            key=lambda x: float(x.get("score") if x.get("score") is not None else parse_metric_score(x.get("metrics", ""))),
            reverse=True,
        )
        top = [
            str(it.get("text") or "").strip()
            for it in scored
            if str(it.get("text") or "").strip()
            and float(it.get("score") if it.get("score") is not None else parse_metric_score(it.get("metrics", ""))) > 0
        ][:3]
        if top:
            winners[platform] = top

        for it in reversed(scored):
            txt = str(it.get("text") or "").strip()
            sc = float(it.get("score") if it.get("score") is not None else parse_metric_score(it.get("metrics", "")))
            if txt and sc <= 1.0:
                snippet = re.sub(r"\s+", " ", txt)[:75]
                anti_patterns.append(f'- "{snippet}..." (Platform: {platform}, Score: {sc})')
            if len(anti_patterns) >= 8:
                break

    lines = [AUTO_START, "## Winning Samples", ""]
    if not winners:
        lines.append("_No high-engagement winners detected yet; keep posting and running `omnipost analytics`._")
    else:
        for platform in ("x", "bluesky", "threads", "linkedin"):
            samples = winners.get(platform)
            if not samples:
                continue
            lines.append(f"### {platform.capitalize()}")
            for idx, sample in enumerate(samples):
                if idx:
                    lines.extend(["", "---", ""])
                lines.append(sample)
            lines.append("")

    if anti_patterns:
        lines.append("## Anti-Patterns / Do Not Emulate (Low Engagement)")
        lines.extend(anti_patterns[:8])

    lines.append(AUTO_END)
    return "\n".join(lines)


def sync_voice_samples(
    posts_by_platform: dict[str, list[dict[str, Any]]],
    path: Path | None = None,
) -> Path:
    """Update references/voice-samples.md with ranked real-world posts."""
    target = path or (ROOT / "references" / "voice-samples.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    new_block = _format_voice_samples_block(posts_by_platform)

    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if AUTO_START in existing and AUTO_END in existing:
            pattern = re.compile(rf"{re.escape(AUTO_START)}.*?{re.escape(AUTO_END)}", re.DOTALL)
            updated = pattern.sub(new_block, existing, count=1)
        else:
            updated = existing.rstrip() + "\n\n" + new_block + "\n"
    else:
        updated = "# Operator Voice Samples\n\n" + new_block + "\n"

    target.write_text(updated, encoding="utf-8")
    return target


async def _scrape_x_profile(handle: str) -> dict[str, Any]:
    ws = await browser.open_page(f"https://x.com/{handle.lstrip('@')}")
    async with browser.Session(ws) as page:
        await page.send("Page.enable")
        await page.send("Runtime.enable")
        await browser.settle_page(page, 4.5)
        js = """
        (() => {
            const followers = document.querySelector('a[href$="/verified_followers"], a[href$="/followers"]')?.innerText || '';
            const posts = [];
            document.querySelectorAll('article[data-testid="tweet"]').forEach(art => {
                const text = art.querySelector('[data-testid="tweetText"]')?.innerText || '';
                const metrics = art.querySelector('[role="group"]')?.getAttribute('aria-label') || '';
                if (text.trim()) posts.push({ text: text.trim(), metrics });
            });
            return { followers, posts: posts.slice(0, 10) };
        })()
        """
        data = await page.eval(js) or {}
        for p in data.get("posts", []):
            p["score"] = parse_metric_score(p.get("metrics", ""))
        return data


async def _scrape_linkedin_analytics() -> dict[str, Any]:
    ws = await browser.open_page("https://www.linkedin.com/analytics/creator/content/")
    async with browser.Session(ws) as page:
        await page.send("Page.enable")
        await page.send("Runtime.enable")
        await browser.settle_page(page, 4.5)
        js = """
        (() => {
            const main = document.querySelector('main') || document.body;
            const text = ((main && main.innerText) || '').replace(/\\n+/g, ' | ');
            const impMatch = text.match(/([\\d,]+)\\s+Impressions/i);
            const topMatch = text.match(/(\\d+\\s+impressions\\s+•\\s+\\d+\\s+engagements?)\\s*\\|\\s*View analytics\\s*\\|\\s*Feed post\\s*\\|\\s*([^|]+)/i);
            const posts = [];
            if (topMatch) {
                posts.push({ text: topMatch[2].trim(), metrics: topMatch[1].trim() });
            }
            return {
                impressions_7d: impMatch ? impMatch[1] : '',
                posts,
            };
        })()
        """
        data = await page.eval(js) or {}
        for p in data.get("posts", []):
            p["score"] = parse_metric_score(p.get("metrics", ""))
        return data


async def _scrape_threads_profile(handle: str) -> dict[str, Any]:
    clean = handle.lstrip("@")
    ws = await browser.open_page(f"https://www.threads.com/@{clean}")
    async with browser.Session(ws) as page:
        await page.send("Page.enable")
        await page.send("Runtime.enable")
        await browser.settle_page(page, 4.5)
        js = """
        (() => {
            const main = document.querySelector('main') || document.body;
            const raw = ((main && main.innerText) || '').replace(/\\n+/g, ' | ');
            const folMatch = raw.match(/([\\d.,]+[KM]?\\s+followers)/i);
            const viewsMatch = raw.match(/([\\d.,]+[KM]?\\s+recent views)/i);
            return {
                followers: folMatch ? folMatch[1] : '',
                recent_views: viewsMatch ? viewsMatch[1] : '',
                posts: [],
            };
        })()
        """
        return await page.eval(js) or {}


async def _scrape_bluesky_profile(identifier: str) -> dict[str, Any]:
    ws = await browser.open_page(f"https://bsky.app/profile/{identifier.lstrip('@')}")
    async with browser.Session(ws) as page:
        await page.send("Page.enable")
        await page.send("Runtime.enable")
        await browser.settle_page(page, 4.5)
        js = """
        (() => {
            const raw = ((document.body && document.body.innerText) || '').replace(/\\n+/g, ' | ');
            const folMatch = raw.match(/([\\d.,]+[KM]?\\s+followers)/i);
            const posts = [];
            document.querySelectorAll('div[data-testid^="feedItem-"]').forEach(el => {
                const txt = (el.innerText || '').trim();
                if (txt.length > 30) posts.push({ text: txt.slice(0, 280), metrics: '' });
            });
            return {
                followers: folMatch ? folMatch[1] : '',
                posts: posts.slice(0, 8),
            };
        })()
        """
        return await page.eval(js) or {}


async def _collect_all_metrics(cfg: dict[str, Any]) -> dict[str, Any]:
    platforms = cfg.get("platforms") or {}
    results: dict[str, Any] = {}

    x_handle = (platforms.get("x") or {}).get("handle") or cfg.get("handle") or "Lordporus"
    bsky_id = (platforms.get("bluesky") or {}).get("identifier") or "lordporus.bsky.social"
    th_handle = (platforms.get("threads") or {}).get("handle") or "ig_lordporus"

    for key, coro in (
        ("x", _scrape_x_profile(x_handle)),
        ("linkedin", _scrape_linkedin_analytics()),
        ("threads", _scrape_threads_profile(th_handle)),
        ("bluesky", _scrape_bluesky_profile(bsky_id)),
    ):
        try:
            results[key] = await coro
        except Exception as exc:
            results[key] = {"error": str(exc), "posts": []}
    return results


async def _scrape_x_radar(limit: int = 5, own_handle: str = "Lordporus") -> list[dict[str, Any]]:
    ws = await browser.open_page("https://x.com/home")
    async with browser.Session(ws) as page:
        await page.send("Page.enable")
        await page.send("Runtime.enable")
        await browser.settle_page(page, 4.5)
        await page.eval("window.scrollBy(0, 900);")
        await asyncio.sleep(1.5)
        js = """
        (() => {
            const out = [];
            document.querySelectorAll('article[data-testid="tweet"]').forEach(art => {
                const text = art.querySelector('[data-testid="tweetText"]')?.innerText || '';
                const link = art.querySelector('a[href*="/status/"]')?.getAttribute('href') || '';
                const metrics = art.querySelector('[role="group"]')?.getAttribute('aria-label') || '';
                if (text.trim() && link) {
                    out.push({ text: text.trim().slice(0, 220), url: 'https://x.com' + link, metrics });
                }
            });
            return out;
        })()
        """
        raw = await page.eval(js) or []
        handle_lower = f"/{own_handle.lstrip('@').lower()}/"
        filtered = []
        for item in raw:
            url = re.sub(r"/analytics/?$", "", str(item.get("url") or ""))
            item["url"] = url
            if handle_lower in url.lower():
                continue
            low_txt = str(item.get("text") or "")
            if not RADAR_KEYWORD_RE.search(low_txt):
                continue
            score = parse_metric_score(item.get("metrics", ""))
            item["score"] = score
            filtered.append(item)
        filtered.sort(key=lambda x: x["score"], reverse=True)
        return filtered[:limit]


def run_analytics(sync_samples: bool = True) -> int:
    """Run live CDP analytics audit and optionally sync voice-samples.md."""
    if not browser.alive():
        print("[OFFLINE] Automation browser not running. Run 'omnipost browser start' first.")
        return 1

    cfg = settings.load()
    data = asyncio.run(_collect_all_metrics(cfg))

    print("\n" + "=" * 60)
    print("OmniPost Live CDP Profile Analytics")
    print("=" * 60)
    posts_by_platform: dict[str, list[dict[str, Any]]] = {}
    for plat, info in data.items():
        if info.get("error"):
            print(f"[{plat.upper():<8}] Error: {info['error']}")
            continue
        extra = info.get("followers") or info.get("impressions_7d") or "OK"
        if info.get("recent_views"):
            extra = f"{extra} | {info['recent_views']}"
        posts = info.get("posts") or []
        posts_by_platform[plat] = posts
        print(f"[{plat.upper():<8}] {extra} | Sampled posts: {len(posts)}")
        if posts:
            top = max(posts, key=lambda p: p.get("score", 0))
            print(f"           Top post (score {top.get('score', 0)}): {top.get('text', '')[:90]}...")

    if sync_samples and any(posts_by_platform.values()):
        out_path = sync_voice_samples(posts_by_platform)
        print(f"\n[SYNC] Updated winning samples in {out_path}")
    return 0


def run_radar(limit: int = 5) -> int:
    """Find high-velocity AI/automation posts on X for manual reply/quote growth."""
    if not browser.alive():
        print("[OFFLINE] Automation browser not running. Run 'omnipost browser start' first.")
        return 1

    cfg = settings.load()
    own_handle = ((cfg.get("platforms") or {}).get("x") or {}).get("handle") or cfg.get("handle") or "Lordporus"
    items = asyncio.run(_scrape_x_radar(limit=limit, own_handle=own_handle))

    print("\n" + "=" * 60)
    print(f"OmniPost Viral Radar (Top {len(items)} Reply/Quote Opportunities)")
    print("=" * 60)
    if not items:
        print("No high-signal AI/automation posts found on current X feed. Scroll/refresh X and retry.")
        return 0

    for idx, item in enumerate(items, 1):
        print(f"\n[{idx}] Score: {item['score']} | {item['url']}")
        print(f"    Metrics: {item['metrics']}")
        print(f"    Post:    {item['text']}")
        print("    Tip:     Drop a 1-2 line prod teardown or contrarian engineering reply here.")
    return 0
