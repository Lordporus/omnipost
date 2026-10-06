"""LinkedIn platform adapter driving dedicated browser automation over CDP.

Operates with stealth configurations (masking navigator.webdriver),
ProseMirror contenteditable DOM input injection, and an anti-detection
minimum spacing constraint (default 4 hours between posts).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
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
STATE_PATH = ROOT / "state.json"

# Stealth script to mask automated browser flags
STEALTH_JS = r"""
Object.defineProperty(navigator, 'webdriver', {
  get: () => undefined
});
window.chrome = {
  runtime: {}
};
"""

# JavaScript to detect active LinkedIn session
CHECK_SESSION_JS = r"""
(() => {
  const url = location.href;
  const isFeed = url.includes('/feed');
  const profileLink = document.querySelector('a[href*="/in/"]');
  const navUser = document.querySelector('.global-nav__me, button[aria-label*="Me"]');
  const loginForm = document.querySelector('form.login__form, input#username, input#password');
  
  let handle = null;
  if (profileLink) {
    const m = profileLink.href.match(/\/in\/([^\/\?]+)/);
    if (m) handle = m[1];
  }
  
  return JSON.stringify({
    url: url,
    logged_in: !loginForm && (!!isFeed || !!navUser || !!handle),
    handle: handle,
    title: document.title
  });
})()
"""

# JavaScript to trigger and focus the post composer
TRIGGER_COMPOSER_JS = r"""
(() => {
  // Find Start a post button or div box
  const el = document.querySelector('*[aria-label*="Start a post"]')
    || [...document.querySelectorAll('div, button')].find(b => (b.innerText || '').trim().toLowerCase() === 'start a post')
    || document.querySelector('button[id*="share-box"]') 
    || document.querySelector('div.share-box-feed-entry__wrapper button');
  if (el) {
    const target = el.closest('div[role="button"]') || el;
    target.click();
    return 'clicked';
  }
  return 'not_found';
})()
"""

FOCUS_EDITOR_JS = r"""
(() => {
  const ed = document.querySelector('div.tiptap.ProseMirror')
    || document.querySelector('div[role="textbox"][contenteditable="true"]')
    || document.querySelector('div.ql-editor[contenteditable="true"]')
    || document.querySelector('div.editor-content div[contenteditable="true"]')
    || document.querySelector('div[role="textbox"]');
  if (!ed) return 'no_editor';
  ed.focus();
  return 'focused';
})()
"""

SUBMIT_POST_JS = r"""
(() => {
  const postBtn = [...document.querySelectorAll('button')].find(b => (b.innerText || '').trim().toLowerCase() === 'post')
    || document.querySelector('button.share-actions__primary-action')
    || document.querySelector('button.artdeco-button--primary')
    || document.querySelector('button[data-view-name*="post-button"]');
  if (!postBtn) return JSON.stringify({error: 'post_btn_not_found'});
  const disabled = postBtn.disabled || postBtn.getAttribute('aria-disabled') === 'true';
  if (disabled) return JSON.stringify({error: 'post_btn_disabled'});
  postBtn.click();
  return JSON.stringify({clicked: true});
})()
"""

TRIGGER_DOCUMENT_MODAL_JS = r"""
(() => {
  const docBtn = document.querySelector('button[aria-label*="Add a document"]')
    || document.querySelector('button[data-view-name*="document"]')
    || document.querySelector('button.share-promoted-detour-button[aria-label*="document"]');
  if (docBtn) {
    docBtn.click();
    return 'clicked';
  }
  return 'not_found';
})()
"""

DOCUMENT_TITLE_JS = r"""
(title) => {
  const input = document.querySelector('input[id*="document-title"]')
    || document.querySelector('input[placeholder*="Title"]')
    || document.querySelector('input[name="title"]');
  if (!input) return 'no_title_input';
  input.value = title;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  
  // Find Done/Next button in modal
  const doneBtn = document.querySelector('button.share-box-footer__primary-btn')
    || document.querySelector('button[data-view-name*="document-done"]')
    || [...document.querySelectorAll('button')].find(b => (b.innerText || '').trim().toLowerCase() === 'done' || (b.innerText || '').trim().toLowerCase() === 'next');
  if (doneBtn) {
    doneBtn.click();
    return 'done_clicked';
  }
  return 'done_not_found';
}
"""


class LinkedInAdapter(PlatformAdapter):
    """Adapter for LinkedIn using Chrome/Edge DevTools Protocol automation."""

    def __init__(self, port: int | None = None):
        cfg = settings.load()
        browser_cfg = cfg.get("browser", {})
        self._port = port or int(browser_cfg.get("port", 9444) if isinstance(browser_cfg, dict) else 9444)
        link_cfg = cfg.get("platforms", {}).get("linkedin", {})
        self._min_gap_hours = float(link_cfg.get("min_gap_hours", 4.0))
        self._profile_url = link_cfg.get("profile_url", "")

    @property
    def platform_name(self) -> str:
        return "linkedin"

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            max_characters=3000,
            supports_markdown=False,
            supports_images=True,
            max_images=9,
            supports_pdf_carousel=True,
            requires_public_image_url=False,
        )

    def _check_rate_limit(self) -> tuple[bool, str | None]:
        """Enforce minimum spacing constraint between consecutive LinkedIn posts."""
        if not STATE_PATH.exists():
            return True, None
        try:
            st = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            posts = st.get("posts", [])
            linkedin_posts = [
                p for p in posts 
                if (p.get("outcomes", {}).get("linkedin", {}).get("success")) 
                or (p.get("platform") == "linkedin" and p.get("verified"))
            ]
            if not linkedin_posts:
                return True, None

            last_at_str = linkedin_posts[-1].get("at")
            if not last_at_str:
                return True, None

            last_dt = datetime.fromisoformat(last_at_str)
            now = datetime.now(timezone.utc)
            diff_hours = (now - last_dt).total_seconds() / 3600.0

            if diff_hours < self._min_gap_hours:
                return False, f"LinkedIn rate-limit guardrail: only {diff_hours:.1f}h elapsed since last post. Minimum {self._min_gap_hours}h required."
            return True, None
        except Exception as exc:
            return True, None

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

    async def _async_check_session(self) -> dict[str, Any]:
        browser.ensure_chrome()
        page = await self._open_stealth("https://www.linkedin.com/feed/")
        try:
            await browser.settle_page(page, 4.0)
            res_str = await page.eval(CHECK_SESSION_JS)
            data = json.loads(res_str or "{}")
            logged_in = bool(data.get("logged_in"))
            return {
                "ok": logged_in,
                "platform": "linkedin",
                "handle": data.get("handle") or ("logged_in_user" if logged_in else None),
                "error": None if logged_in else "Not logged in to linkedin.com in automation browser window",
            }
        finally:
            await page.__aexit__(None, None, None)

    def check_session(self) -> dict[str, Any]:
        """Check whether LinkedIn session is active in the automation browser."""
        try:
            return asyncio.run(self._async_check_session())
        except Exception as exc:
            return {
                "ok": False,
                "platform": "linkedin",
                "handle": None,
                "error": str(exc),
            }

    async def _async_publish(self, payload: PublishPayload) -> PublishResult:
        # 1. Spacing check
        allowed, msg = self._check_rate_limit()
        if not allowed:
            return PublishResult(
                platform="linkedin",
                success=False,
                error=msg,
            )

    async def _attach_document(self, page: Session, pdf_path: Path, doc_title: str) -> bool:
        """Uploads a PDF document to LinkedIn using file input simulation."""
        if not pdf_path.exists():
            return False

        # 1. Click "Add a document" button
        trig = await page.eval(TRIGGER_DOCUMENT_MODAL_JS)
        if trig != "clicked":
            return False

        await asyncio.sleep(2.0)

        # 2. Attach PDF file via DOM file input
        try:
            # Query the file input element in document modal
            doc = await page.send("DOM.getDocument")
            root_id = doc["root"]["nodeId"]
            inp = await page.send(
                "DOM.querySelector",
                nodeId=root_id,
                selector='input[type="file"]',
            )
            node_id = inp.get("nodeId")
            if not node_id:
                return False

            await page.send(
                "DOM.setFileInputFiles",
                files=[str(pdf_path.resolve())],
                nodeId=node_id,
            )
            await asyncio.sleep(3.0)

            # 3. Fill Document Title
            res = await page.eval(f"({DOCUMENT_TITLE_JS})({json.dumps(doc_title)})")
            await asyncio.sleep(2.0)
            return True
        except Exception:
            return False

    async def _async_publish(self, payload: PublishPayload) -> PublishResult:
        # 1. Spacing check
        allowed, msg = self._check_rate_limit()
        if not allowed:
            return PublishResult(
                platform="linkedin",
                success=False,
                error=msg,
            )

        browser.ensure_chrome()
        page = await self._open_stealth("https://www.linkedin.com/feed/")
        try:
            await browser.settle_page(page, 4.0)
            
            # Click start a post button
            pos_js = """
            (() => {
                const el = document.querySelector('*[aria-label*="Start a post"]')
                    || [...document.querySelectorAll('div, button')].find(b => (b.innerText || '').trim().toLowerCase() === 'start a post');
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2)};
            })()
            """
            pos = await page.eval(pos_js)
            if pos and isinstance(pos, dict):
                await page.send("Input.dispatchMouseEvent", type="mousePressed", x=pos["x"], y=pos["y"], button="left", clickCount=1)
                await page.send("Input.dispatchMouseEvent", type="mouseReleased", x=pos["x"], y=pos["y"], button="left", clickCount=1)
            elif pos == "clicked":
                pass
            else:
                trig = await page.eval(TRIGGER_COMPOSER_JS)
                if trig != "clicked":
                    return PublishResult(
                        platform="linkedin",
                        success=False,
                        error="Could not find 'Start a post' button on LinkedIn feed",
                    )
            
            await asyncio.sleep(1.5)

            # Attach Carousel PDF if requested
            if payload.media_type == "carousel" and payload.media_paths:
                pdf_target = payload.media_paths[0]
                if pdf_target.suffix.lower() == ".pdf":
                    doc_title = payload.extra_metadata.get("document_title") or payload.text.split("\n")[0][:60]
                    attached = await self._attach_document(page, pdf_target, doc_title)
                    if not attached:
                        return PublishResult(
                            platform="linkedin",
                            success=False,
                            error="Failed to attach PDF carousel document to LinkedIn post",
                        )
                    await asyncio.sleep(1.5)
            
            # Focus editor with retry loop for animation
            foc = "no_editor"
            for _ in range(15):
                foc = await page.eval(FOCUS_EDITOR_JS)
                if foc == "focused":
                    break
                await asyncio.sleep(0.5)

            if foc != "focused":
                return PublishResult(
                    platform="linkedin",
                    success=False,
                    error="Could not focus LinkedIn post composer editor",
                )
            
            # Inject text via CDP Input.insertText
            await page.send("Input.insertText", text=payload.text)
            await asyncio.sleep(1.0)

            # Submit
            sub_res_str = await page.eval(SUBMIT_POST_JS)
            sub_res = json.loads(sub_res_str or "{}")
            if sub_res.get("error"):
                return PublishResult(
                    platform="linkedin",
                    success=False,
                    error=f"LinkedIn post submission error: {sub_res.get('error')}",
                )

            # Settle after clicking Post
            await asyncio.sleep(4.0)

            # Read back verification
            verified = await self._async_verify(None, payload.text)

            return PublishResult(
                platform="linkedin",
                success=True,
                verified=verified,
                raw_response={"submitted": True},
            )
        finally:
            await page.__aexit__(None, None, None)

    def publish(self, payload: PublishPayload) -> PublishResult:
        """Publish post text to LinkedIn via CDP."""
        try:
            return asyncio.run(self._async_publish(payload))
        except Exception as exc:
            return PublishResult(
                platform="linkedin",
                success=False,
                error=str(exc),
            )

    async def _async_verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Read-back verification on recent activity page with retry polling."""
        target_url = (
            f"{self._profile_url.rstrip('/')}/recent-activity/all/"
            if self._profile_url
            else "https://www.linkedin.com/feed/"
        )
        try:
            page = await self._open_stealth(target_url)
            try:
                deadline = time.time() + 35.0
                norm_snippet = re.sub(r"\s+", " ", text_snippet[:40]).strip().lower()

                check_js = r"""
                (() => {
                  const posts = [...document.querySelectorAll('div.feed-shared-update-v2, div[data-urn*="activity"]')];
                  return JSON.stringify(posts.slice(0, 5).map(p => {
                    const urn = p.getAttribute('data-urn') || '';
                    return {
                      text: p.innerText || '',
                      urn: urn
                    };
                  }));
                })()
                """

                while time.time() < deadline:
                    await browser.settle_page(page, 4.0)
                    try:
                        raw = await page.eval(check_js)
                        posts = json.loads(raw or "[]")
                    except Exception:
                        posts = []

                    for p in posts:
                        p_text = p.get("text", "")
                        if norm_snippet in re.sub(r"\s+", " ", p_text).lower():
                            return True
                    await asyncio.sleep(3.0)
                return False
            finally:
                await page.__aexit__(None, None, None)
        except Exception:
            return False

    def verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Synchronous wrapper for activity verification."""
        try:
            return asyncio.run(self._async_verify(post_id, text_snippet))
        except Exception:
            return False
