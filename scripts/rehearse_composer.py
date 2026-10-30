#!/usr/bin/env python
"""Open a platform composer, attach media, assert the attach contract, dismiss.

Never clicks Post. This is the only way to exercise submit-adjacent composer
code (modal gating, file-input capture, upload settling) without publishing:
`post.py compose --dry-run` stops before the composer and `autoposter --dry-run`
returns before dispatch.

Exit code 0 only when the platform's own attach contract reports success:
`attached:<n>` for X, `True` for LinkedIn and Threads.

CLI:
  py -3.12 scripts/rehearse_composer.py --platform x        --media a.png,b.png
  py -3.12 scripts/rehearse_composer.py --platform linkedin --media deck.pdf
  py -3.12 scripts/rehearse_composer.py --platform threads  --media a.png
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from adapters.linkedin import LinkedInAdapter
from adapters.threads import (
    FOCUS_EDITOR_JS,
    HYDRATED_JS,
    TRIGGER_COMPOSER_JS,
    ThreadsAdapter,
    _threads_focus_data,
)
from scripts import browser, post


async def _dismiss(page) -> None:
    """Close the tab so no composer and no draft are left behind."""
    try:
        await page.send("Page.close")
    except Exception:
        pass


async def rehearse_x(paths: list[Path]) -> tuple[bool, str]:
    page = await post._open("https://x.com/compose/post")
    try:
        # open_page reuses a tab already on this URL without reloading it; a stale
        # dialog there never mounts an editor, so force a fresh document.
        await page.send("Page.navigate", url="https://x.com/compose/post")
        await browser.settle_page(page, 4.0)
        ready = "no-dialog"
        for _ in range(20):
            ready = await page.eval(post.COMPOSE_READY_JS)
            if ready == "ready":
                break
            await asyncio.sleep(0.5)
        if ready != "ready":
            return False, f"composer not ready: {ready}"
        status = await post._attach_images(page, paths)
        return status == f"attached:{len(paths)}", status
    finally:
        await _dismiss(page)


async def rehearse_linkedin(paths: list[Path]) -> tuple[bool, str]:
    adapter = LinkedInAdapter()
    page = await adapter._open_stealth("https://www.linkedin.com/feed/")
    try:
        await browser.settle_page(page, 4.0)
        trigger = await adapter._trigger_composer(page)
        if trigger.get("result") != "clicked":
            return False, f"trigger: {trigger}"
        focus = await adapter._wait_for_composer_editor(page)
        if focus != "focused":
            return False, f"editor: {focus}"
        pdfs = [p for p in paths if p.suffix.lower() == ".pdf"]
        if pdfs:
            ok = await adapter._attach_document(page, pdfs[0], pdfs[0].stem[:60])
            return ok, f"document attached={ok}"
        ok = await adapter._attach_images(page, paths)
        return ok, f"images attached={ok}"
    finally:
        await _dismiss(page)


async def rehearse_threads(paths: list[Path]) -> tuple[bool, str]:
    adapter = ThreadsAdapter()
    page = await adapter._open_stealth(adapter.get_base_url())
    try:
        await browser.settle_page(page, 4.0)
        state: dict = {}
        for _ in range(60):
            state = _threads_focus_data(await page.eval(HYDRATED_JS))
            if state.get("button") and not state.get("loading"):
                break
            await asyncio.sleep(0.5)
        else:
            return False, f"not hydrated: {state}"
        # Same retry as _async_publish: on a cold load the first click can be
        # swallowed, so a single attempt would report a failure the product recovers from.
        trigger = "not_found"
        focus: dict = {}
        for _ in range(3):
            trigger = await page.eval(TRIGGER_COMPOSER_JS)
            if trigger not in ("clicked", "already_open"):
                await asyncio.sleep(0.5)
                continue
            for _ in range(20):
                await asyncio.sleep(0.5)
                focus = _threads_focus_data(await page.eval(FOCUS_EDITOR_JS))
                if focus.get("status") == "focused":
                    break
            if focus.get("status") == "focused":
                break
        if trigger not in ("clicked", "already_open"):
            return False, f"trigger: {trigger}"
        if focus.get("status") != "focused":
            return False, f"editor: {focus.get('status')}"
        ok = await adapter._attach_media(page, paths)
        return ok, f"images attached={ok}"
    finally:
        await _dismiss(page)


REHEARSALS = {
    "x": rehearse_x,
    "linkedin": rehearse_linkedin,
    "threads": rehearse_threads,
}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--platform", required=True, choices=sorted(REHEARSALS))
    parser.add_argument("--media", required=True, help="comma-separated file paths")
    args = parser.parse_args()

    paths = [Path(p.strip()) for p in args.media.split(",") if p.strip()]
    missing = [str(p) for p in paths if not p.exists()]
    if not paths or missing:
        print(json.dumps({"ok": False, "error": f"missing media: {missing}"}))
        return 2

    browser.ensure_chrome()
    ok, detail = await REHEARSALS[args.platform](paths)
    print(json.dumps({
        "ok": ok,
        "platform": args.platform,
        "media": [str(p) for p in paths],
        "detail": detail,
        "posted": False,
    }))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
