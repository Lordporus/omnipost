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

# JavaScript to detect active Threads session
CHECK_SESSION_JS = r"""
(() => {
  const url = location.href;
  const isFeed = url.includes('threads.net');
  // Check for profile icon, user handle link, or write icon in navigation bar
  const profileLink = document.querySelector('a[href*="/@"]');
  const loginBtn = document.querySelector('a[href*="/login"], button[type="button"][aria-label*="Log in"]');
  const composeBtn = document.querySelector('div[role="button"][aria-label*="New thread"], svg[aria-label*="New thread"]');

  let handle = null;
  if (profileLink) {
    const m = profileLink.href.match(/@([a-zA-Z0-9_.-]+)/);
    if (m) handle = m[1];
  }

  const logged_in = !loginBtn && (!!profileLink || !!composeBtn);

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
  // Find "Start a thread" input prompt or navbar compose button
  const composeBtn = document.querySelector('div[role="button"][aria-label*="New thread"]')
    || document.querySelector('div.x1i10hfl[role="button"]')
    || [...document.querySelectorAll('div[role="button"]')].find(d => (d.innerText || '').toLowerCase().includes('start a thread'));
  if (composeBtn) {
    composeBtn.click();
    return 'clicked';
  }
  return 'not_found';
})()
"""

FOCUS_EDITOR_JS = r"""
(() => {
  const ed = document.querySelector('div[role="textbox"][contenteditable="true"]')
    || document.querySelector('div[data-lexical-editor="true"]')
    || document.querySelector('div.notranslate[contenteditable="true"]');
  if (!ed) return 'no_editor';
  ed.focus();
  return 'focused';
})()
"""

SUBMIT_POST_JS = r"""
(() => {
  const postBtn = [...document.querySelectorAll('div[role="button"]')].find(b => (b.innerText || '').trim().toLowerCase() === 'post')
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

    async def _attach_media(self, page: Session, file_path: Path) -> bool:
        """Attaches local image to Threads composer via CDP DOM file input."""
        if not file_path.exists():
            return False
        try:
            doc = await page.send("DOM.getDocument")
            root_id = doc["root"]["nodeId"]
            inp = await page.send(
                "DOM.querySelector",
                nodeId=root_id,
                selector='input[type="file"][accept*="image"]',
            )
            node_id = inp.get("nodeId")
            if not node_id:
                return False

            await page.send(
                "DOM.setFileInputFiles",
                files=[str(file_path.resolve())],
                nodeId=node_id,
            )
            await asyncio.sleep(2.5)
            return True
        except Exception:
            return False

    async def _async_check_session(self) -> dict[str, Any]:
        browser.ensure_chrome()
        page = await self._open_stealth("https://www.threads.net/")
        try:
            await browser.settle_page(page, 4.0)
            res_str = await page.eval(CHECK_SESSION_JS)
            data = json.loads(res_str or "{}")
            logged_in = bool(data.get("logged_in"))
            h = data.get("handle") or self._handle
            return {
                "ok": logged_in,
                "platform": "threads",
                "handle": h or ("logged_in_user" if logged_in else None),
                "error": None if logged_in else "Not logged in to threads.net in automation browser window",
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
        page = await self._open_stealth("https://www.threads.net/")
        try:
            await browser.settle_page(page, 4.0)

            # Trigger composer
            trig = await page.eval(TRIGGER_COMPOSER_JS)
            if trig != "clicked":
                return PublishResult(
                    platform="threads",
                    success=False,
                    error="Could not find 'Start a thread' button on threads.net",
                )

            await asyncio.sleep(1.5)

            # Attach media if provided
            if payload.media_paths:
                img_path = payload.media_paths[0]
                attached = await self._attach_media(page, img_path)
                if not attached:
                    return PublishResult(
                        platform="threads",
                        success=False,
                        error=f"Failed to attach image {img_path} to Threads composer",
                    )
                await asyncio.sleep(1.5)

            # Focus editor
            foc = await page.eval(FOCUS_EDITOR_JS)
            if foc != "focused":
                return PublishResult(
                    platform="threads",
                    success=False,
                    error="Could not focus Threads post composer editor",
                )

            # Inject text via CDP Input.insertText
            await page.send("Input.insertText", text=payload.text)
            await asyncio.sleep(1.0)

            # Submit
            sub_res_str = await page.eval(SUBMIT_POST_JS)
            sub_res = json.loads(sub_res_str or "{}")
            if sub_res.get("error"):
                return PublishResult(
                    platform="threads",
                    success=False,
                    error=f"Threads post submission error: {sub_res.get('error')}",
                )

            # Settle after clicking Post
            await asyncio.sleep(4.0)

            # Read back verification
            verified = await self._async_verify(None, payload.text)

            post_url = f"https://www.threads.net/@{self._handle}" if self._handle else "https://www.threads.net"

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
        target_url = (
            f"https://www.threads.net/@{self._handle}"
            if self._handle
            else "https://www.threads.net"
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
