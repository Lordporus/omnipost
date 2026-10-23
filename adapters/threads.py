"""Meta Threads platform adapter driving dedicated browser automation over CDP.

Operates with stealth configurations (masking navigator.webdriver),
contenteditable DOM input injection, and native local image file attachment,
eliminating the need for Meta developer API keys or public image hosting.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from adapters.base import (
    PlatformAdapter,
    PlatformCapabilities,
    PublishPayload,
    PublishResult,
    capture_failure_artifacts,
)
from scripts import browser, settings
from scripts.browser import CDPError, Session

ROOT = Path(__file__).resolve().parent.parent

# Stealth script to mask automated browser flags
STEALTH_JS = r"""
Object.defineProperty(navigator, 'webdriver', {
  get: () => undefined
});
window.chrome = {
  runtime: {}
};
"""

THREADS_BASE_URL = "https://www.threads.net/"

CHECK_SESSION_JS = r"""
(() => {
  const url = location.href;
  const isFeed = url.includes('threads.net') || url.includes('threads.com');
  const loginBtn = document.querySelector('a[href*="/login"], button[type="button"][aria-label*="Log in"], [role="button"][aria-label*="Log in"]');
  const profileLink = document.querySelector('a[href*="/@"]') || document.querySelector('a[href*="/activity"]');
  const composeBtn = document.querySelector('div[role="button"][aria-label*="Create" i], div[role="button"][aria-label*="New thread" i], svg[aria-label*="Create" i], svg[aria-label*="New thread" i], a[href*="/compose"]');
  const navBar = document.querySelector('nav') || document.querySelector('div[role="navigation"]');

  let handle = null;
  if (profileLink && profileLink.href) {
    const m = profileLink.href.match(/@([a-zA-Z0-9_.-]+)/);
    if (m) handle = m[1];
  }

  if (!handle) {
    const allLinks = Array.from(document.querySelectorAll('a[href]')).map(a => a.getAttribute('href') || '');
    const userLink = allLinks.find(href => href.startsWith('/@') && !href.includes('/post/'));
    if (userLink) {
      handle = userLink.replace(/^\/@/, '').split('/')[0];
    }
  }

  const logged_in = !loginBtn && (!!profileLink || !!composeBtn || !!handle || (navBar && !loginBtn));

  return JSON.stringify({
    url: url,
    logged_in: logged_in,
    handle: handle,
    title: document.title
  });
})()
"""

# JavaScript to open the post composer
TRIGGER_COMPOSER_JS = r"""
(() => {
  // If composer editor is already visible and editable, no need to trigger again
  const existingEd = document.querySelector('div[contenteditable="true"]');
  if (existingEd && existingEd.offsetParent !== null) return 'already_open';

  const btn = document.querySelector('svg[aria-label*="Create" i]')?.closest('div[role="button"], a, button')
    || document.querySelector('svg[aria-label*="New thread" i]')?.closest('div[role="button"], a, button')
    || document.querySelector('div[role="button"][aria-label*="Create" i]')
    || document.querySelector('div[role="button"][aria-label*="New thread" i]')
    || document.querySelector('a[href*="/compose"]')
    || document.querySelector('div[aria-label*="Empty text field"]')
    || document.querySelector('div[role="button"][aria-label*="Start a thread" i]')
    || [...document.querySelectorAll('div[role="button"], button')].find(d => {
         const t = (d.innerText || '').toLowerCase();
         return t.includes('what’s new') || t.includes("what's new") || t.includes('start a thread') || t.includes('new thread');
       });
  if (btn) {
    btn.click();
    return 'clicked';
  }
  return 'not_found';
})()
"""

FOCUS_EDITOR_JS = r"""
(() => {
  const ed = document.querySelector('div[contenteditable="true"][role="textbox"]')
    || document.querySelector('div[data-lexical-editor="true"]')
    || document.querySelector('div.notranslate[contenteditable="true"]')
    || document.querySelector('div[role="combobox"][contenteditable="true"]')
    || document.querySelector('div[contenteditable="true"]')
    || document.querySelector('div[role="textbox"]')
    || document.querySelector('p[data-placeholder*="thread" i]');
  if (!ed) return JSON.stringify({status: 'no_editor'});

  ed.scrollIntoView({block: 'center', inline: 'nearest'});
  const r = ed.getBoundingClientRect();
  const coords = {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2)};

  ed.focus();
  try {
    ed.click();
    ed.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, clientX: coords.x, clientY: coords.y, view: window}));
    ed.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, clientX: coords.x, clientY: coords.y, view: window}));
    ed.dispatchEvent(new Event('focus', { bubbles: true }));
    const range = document.createRange();
    range.selectNodeContents(ed);
    range.collapse(false);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  } catch (e) {}

  return JSON.stringify({
    status: 'focused',
    coords: coords,
    is_active: document.activeElement === ed
  });
})()
"""

SUBMIT_POST_JS = r"""
(() => {
  const postBtn = [...document.querySelectorAll('div[role="button"], button')].find(b => (b.innerText || '').trim().toLowerCase() === 'post')
    || document.querySelector('div[role="button"][aria-label*="Post"]');
  if (!postBtn) return JSON.stringify({error: 'post_btn_not_found'});
  const disabled = postBtn.getAttribute('aria-disabled') === 'true' || postBtn.disabled;
  if (disabled) return JSON.stringify({error: 'post_btn_disabled'});
  postBtn.click();
  return JSON.stringify({clicked: true});
})()
"""


class ThreadsAdapter(PlatformAdapter):
    """Adapter for Meta Threads using Chrome/Edge DevTools Protocol automation."""

    def __init__(self, port: int | None = None, handle: str | None = None):
        cfg = settings.load()
        browser_cfg = cfg.get("browser", {})
        self._port = port or int(browser_cfg.get("port", 9444) if isinstance(browser_cfg, dict) else 9444)
        threads_cfg = cfg.get("platforms", {}).get("threads", {})
        self._handle = handle or threads_cfg.get("handle", "")

    @property
    def platform_name(self) -> str:
        return "threads"

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            max_characters=500,
            supports_markdown=False,
            supports_images=True,
            max_images=10,
            supports_pdf_carousel=False,
            requires_public_image_url=False,
        )

    def get_base_url(self) -> str:
        """Determines active base URL for Threads, checking configuration and open browser tabs."""
        cfg = settings.load()
        explicit = cfg.get("platforms", {}).get("threads", {}).get("base_url")
        if explicit and explicit.strip():
            base = explicit.strip()
            return base if base.endswith("/") else f"{base}/"

        if browser.alive():
            try:
                for t in browser.list_tabs():
                    url = t.get("url", "").lower()
                    if "threads.com" in url:
                        return "https://www.threads.com/"
                    if "threads.net" in url:
                        return "https://www.threads.net/"
            except Exception:
                pass

        return THREADS_BASE_URL

    async def _open_stealth(self, url: str) -> Session:
        """Opens a CDP session and injects stealth webdriver masking scripts."""
        ws = await browser.open_page(url)
        sess = Session(ws)
        page = await sess.__aenter__()
        await page.send("Page.enable")
        await page.send("Runtime.enable")
        await page.send(
            "Page.addScriptToEvaluateOnNewDocument",
            source=STEALTH_JS,
        )
        return page

    async def _attach_media(self, page: Session, file_paths: list[Path] | Path) -> bool:
        """Attaches 1-3 local images to Threads composer via CDP DOM file input with polling retries."""
        paths = [file_paths] if isinstance(file_paths, Path) else file_paths
        valid_files = [str(p.resolve()) for p in paths if p.exists()]
        if not valid_files:
            return False

        # Poll with retries up to 12 attempts (~6.0s) for composer modal hydration
        for _ in range(12):
            try:
                doc = await page.send("DOM.getDocument", depth=-1)
                root_id = doc.get("root", {}).get("nodeId", 0)
                if not root_id:
                    await asyncio.sleep(0.5)
                    continue

                for sel in ['input[type="file"][accept*="image"]', 'input[type="file"]']:
                    try:
                        inp = await page.send(
                            "DOM.querySelector",
                            nodeId=root_id,
                            selector=sel,
                        )
                        node_id = inp.get("nodeId")
                        if node_id:
                            await page.send(
                                "DOM.setFileInputFiles",
                                files=valid_files,
                                nodeId=node_id,
                            )
                            await asyncio.sleep(2.5)
                            return True
                    except Exception:
                        continue
            except Exception:
                pass
            await asyncio.sleep(0.5)

        return False

    async def _async_check_session(self) -> dict[str, Any]:
        browser.ensure_chrome()
        base_url = self.get_base_url()
        page = await self._open_stealth(base_url)
        try:
            await browser.settle_page(page, 2.5)
            # Poll for hydration up to 8 seconds
            logged_in = False
            h = None
            for _ in range(16):
                try:
                    res_str = await page.eval(CHECK_SESSION_JS)
                    data = json.loads(res_str or "{}")
                    if data.get("logged_in"):
                        logged_in = True
                        h = data.get("handle") or self._handle
                        break
                except (CDPError, OSError, asyncio.TimeoutError, Exception):
                    pass
                await asyncio.sleep(0.5)

            return {
                "ok": logged_in,
                "platform": "threads",
                "handle": h or ("logged_in_user" if logged_in else None),
                "error": None if logged_in else "Not logged in to Threads in automation browser window",
            }
        finally:
            await page.__aexit__(None, None, None)

    def check_session(self) -> dict[str, Any]:
        """Check whether Threads session is active in the automation browser."""
        try:
            return asyncio.run(self._async_check_session())
        except Exception as exc:
            return {
                "ok": False,
                "platform": "threads",
                "handle": None,
                "error": str(exc),
            }

    async def _async_publish(self, payload: PublishPayload) -> PublishResult:
        browser.ensure_chrome()
        base_url = self.get_base_url()
        page = await self._open_stealth(base_url)
        try:
            await browser.settle_page(page, 4.0)

            # Trigger composer (retry for hydration)
            trig = "not_found"
            for _ in range(10):
                trig = await page.eval(TRIGGER_COMPOSER_JS)
                if trig in ("clicked", "already_open"):
                    break
                await asyncio.sleep(0.5)

            if trig not in ("clicked", "already_open"):
                arts = await capture_failure_artifacts(page, "threads")
                return PublishResult(
                    platform="threads",
                    success=False,
                    error="Could not find 'Start a thread' button on threads.net",
                    artifacts=arts,
                )

            await asyncio.sleep(1.5)

            # 1. Focus editor with retry loop for animation
            foc_data = {}
            for _ in range(15):
                raw_foc = await page.eval(FOCUS_EDITOR_JS)
                try:
                    foc_data = json.loads(raw_foc or "{}")
                except Exception:
                    foc_data = {}
                if foc_data.get("status") == "focused":
                    break
                await asyncio.sleep(0.5)

            if foc_data.get("status") != "focused":
                arts = await capture_failure_artifacts(page, "threads")
                return PublishResult(
                    platform="threads",
                    success=False,
                    error="Could not focus Threads post composer editor",
                    artifacts=arts,
                )

            # Additional CDP level mouse dispatch if coordinates were detected
            coords = foc_data.get("coords")
            if coords and isinstance(coords, dict):
                cx, cy = coords.get("x", 0), coords.get("y", 0)
                if cx > 0 and cy > 0:
                    try:
                        await page.send(
                            "Input.dispatchMouseEvent",
                            type="mousePressed",
                            x=cx,
                            y=cy,
                            button="left",
                            clickCount=1,
                        )
                        await page.send(
                            "Input.dispatchMouseEvent",
                            type="mouseReleased",
                            x=cx,
                            y=cy,
                            button="left",
                            clickCount=1,
                        )
                    except Exception:
                        pass

            # 2. Inject text via CDP Input.insertText
            await page.send("Input.insertText", text=payload.text)
            await asyncio.sleep(1.0)

            # 3. Attach media if provided (after editor is active and populated)
            if payload.media_paths:
                attached = await self._attach_media(page, payload.media_paths)
                if not attached:
                    print(
                        f"  [WARN] Threads: Failed to attach images {payload.media_paths}. Proceeding with text-only thread.",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    await asyncio.sleep(2.0)

            # Submit
            sub_res_str = await page.eval(SUBMIT_POST_JS)
            sub_res = json.loads(sub_res_str or "{}")
            if sub_res.get("error"):
                arts = await capture_failure_artifacts(page, "threads")
                return PublishResult(
                    platform="threads",
                    success=False,
                    error=f"Threads post submission error: {sub_res.get('error')}",
                    artifacts=arts,
                )

            # Settle after clicking Post
            await asyncio.sleep(4.0)

            # Read back verification
            verified = await self._async_verify(None, payload.text)

            clean_h = self._handle.lstrip("@") if self._handle else ""
            post_url = f"{base_url}@{clean_h}" if clean_h else base_url

            return PublishResult(
                platform="threads",
                success=True,
                url=post_url,
                verified=verified,
                raw_response={"submitted": True},
            )
        finally:
            await page.__aexit__(None, None, None)

    def publish(self, payload: PublishPayload) -> PublishResult:
        """Publish post text and media to Threads via CDP."""
        try:
            return asyncio.run(self._async_publish(payload))
        except Exception as exc:
            return PublishResult(
                platform="threads",
                success=False,
                error=str(exc),
            )

    async def _async_verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Read-back verification on user profile timeline."""
        base_url = self.get_base_url()
        clean_h = self._handle.lstrip("@") if self._handle else ""
        target_url = (
            f"{base_url}@{clean_h}"
            if clean_h
            else base_url
        )
        try:
            page = await self._open_stealth(target_url)
            try:
                deadline = time.time() + 30.0
                norm_snippet = re.sub(r"\s+", " ", text_snippet[:35]).strip().lower()

                check_js = r"""
                (() => {
                  const posts = [...document.querySelectorAll('div[data-pressable-container="true"], div.x1i10hfl')];
                  return JSON.stringify(posts.slice(0, 6).map(p => (p.innerText || '')));
                })()
                """

                while time.time() < deadline:
                    await browser.settle_page(page, 3.5)
                    try:
                        raw = await page.eval(check_js)
                        posts = json.loads(raw or "[]")
                    except Exception:
                        posts = []

                    for p_text in posts:
                        if norm_snippet in re.sub(r"\s+", " ", p_text).lower():
                            return True
                    await asyncio.sleep(2.5)
                return False
            finally:
                await page.__aexit__(None, None, None)
        except Exception:
            return False

    def verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Synchronous wrapper for Threads verification."""
        try:
            return asyncio.run(self._async_verify(post_id, text_snippet))
        except Exception:
            return False
