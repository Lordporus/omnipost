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
    capture_failure_artifacts,
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
  const ed = document.querySelector('div[role="dialog"] div[contenteditable="true"]')
    || document.querySelector('div.artdeco-modal div[contenteditable="true"]')
    || document.querySelector('div.tiptap.ProseMirror')
    || document.querySelector('div.editor-content div[contenteditable="true"]')
    || document.querySelector('div[role="textbox"][contenteditable="true"]');
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

TOAST_QUERY_JS = r"""
(() => {
  const toastLink = document.querySelector('a[href*="/feed/update/urn:li:activity:"]')
    || document.querySelector('a[href*="urn:li:activity:"]')
    || document.querySelector('div[role="alert"] a')
    || document.querySelector('.artdeco-toast-item a');
  if (toastLink && toastLink.href) return toastLink.href;
  const toastSpan = [...document.querySelectorAll('span, div')].find(s => {
    const t = (s.innerText || '').toLowerCase();
    return t.includes('post successful') || t.includes('your post was shared') || t.includes('view post');
  });
  if (toastSpan) return 'success_toast_detected';
  return null;
})()
"""

TRIGGER_DOCUMENT_MODAL_JS = r"""
(() => {
  // 1. Direct document button on composer toolbar
  const docBtn = document.querySelector('button[aria-label*="Add a document" i]')
    || document.querySelector('button[aria-label*="Document" i]')
    || document.querySelector('button[data-view-name*="document" i]')
    || document.querySelector('button.share-promoted-detour-button[aria-label*="document" i]')
    || [...document.querySelectorAll('button')].find(b => {
         const label = (b.getAttribute('aria-label') || b.innerText || '').toLowerCase();
         return label.includes('document') || label.includes('pdf');
       });
  if (docBtn) {
    docBtn.scrollIntoView({block: 'center', inline: 'nearest'});
    docBtn.click();
    return 'clicked';
  }

  // 2. Overflow / More options button (...) on toolbar
  const overflowBtn = document.querySelector('button[aria-label*="More" i]')
    || document.querySelector('button[aria-label*="Add to your post" i]')
    || document.querySelector('button.share-box-footer__overflow-btn')
    || document.querySelector('button[data-control-name*="overflow" i]')
    || document.querySelector('svg[data-test-icon*="overflow"]')?.closest('button')
    || document.querySelector('svg[data-test-icon*="more"]')?.closest('button');

  if (overflowBtn) {
    overflowBtn.click();
    return 'overflow_clicked';
  }

  return 'not_found';
})()
"""

DOCUMENT_TITLE_JS = r"""
(title) => {
  const input = document.querySelector('input[id*="document-title"]')
    || document.querySelector('input[placeholder*="Title" i]')
    || document.querySelector('input[aria-label*="Title" i]')
    || document.querySelector('input[name="title"]')
    || document.querySelector('.share-document-card__title-input');
  if (input) {
    input.value = title;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }
  
  // Find Done/Next button in modal
  const doneBtn = document.querySelector('button.share-box-footer__primary-btn')
    || document.querySelector('button[data-view-name*="document-done"]')
    || document.querySelector('button.share-document-card__submit-btn')
    || [...document.querySelectorAll('button')].find(b => {
         const t = (b.innerText || '').trim().toLowerCase();
         return t === 'done' || t === 'next';
       });
  if (doneBtn) {
    doneBtn.click();
    return 'done_clicked';
  }
  return input ? 'title_filled_no_done' : 'no_title_input';
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

    async def _attach_images(self, page: Session, image_paths: list[Path]) -> bool:
        """Attaches 1-3 PNG images directly to LinkedIn post composer via the Media button."""
        valid_files = [str(p.resolve()) for p in image_paths if p.exists() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
        if not valid_files:
            return False

        # 1. Look for existing image input in composer
        node_id = None
        for _ in range(3):
            try:
                doc = await page.send("DOM.getDocument", depth=-1)
                root_id = doc.get("root", {}).get("nodeId", 0)
                if root_id:
                    inp = await page.send(
                        "DOM.querySelector",
                        nodeId=root_id,
                        selector='input[type="file"][accept*="image"], input[type="file"]',
                    )
                    node_id = inp.get("nodeId")
                    if node_id:
                        break
            except Exception:
                pass
            await asyncio.sleep(0.3)

        # 2. If no direct input, click the Media toolbar button
        if not node_id:
            click_media_js = """
            (() => {
                const btn = document.querySelector('button[aria-label*="Media" i]')
                    || document.querySelector('button.share-promoted-detour-button[aria-label*="photo" i]')
                    || document.querySelector('button[componentkey*="dda61378"]');
                if (btn) { btn.click(); return 'clicked'; }
                return 'not_found';
            })()
            """
            trig = await page.eval(click_media_js)
            await asyncio.sleep(1.0)
            for _ in range(6):
                try:
                    doc = await page.send("DOM.getDocument", depth=-1)
                    root_id = doc.get("root", {}).get("nodeId", 0)
                    if root_id:
                        inp = await page.send(
                            "DOM.querySelector",
                            nodeId=root_id,
                            selector='input[type="file"][accept*="image"], input[type="file"]',
                        )
                        node_id = inp.get("nodeId")
                        if node_id:
                            break
                except Exception:
                    pass
                await asyncio.sleep(0.4)

        if not node_id:
            return False

        # 3. Set files via CDP
        try:
            await page.send(
                "DOM.setFileInputFiles",
                files=valid_files,
                nodeId=node_id,
            )
        except Exception:
            return False

        await asyncio.sleep(2.0)

        # 4. In LinkedIn media preview dialog, wait for upload processing and click "Next" / "Done"
        click_next_js = """
        (() => {
            const btns = [...document.querySelectorAll('button, div[role="button"]')];
            const nextBtn = document.querySelector('button.share-box-footer__primary-btn')
                || document.querySelector('button[aria-label="Next"]')
                || document.querySelector('button[aria-label="Done"]')
                || btns.find(b => {
                     const t = (b.innerText || b.getAttribute('aria-label') || '').trim().toLowerCase();
                     return t === 'next' || t === 'done';
                   });
            if (nextBtn && !nextBtn.disabled && !nextBtn.getAttribute('aria-disabled')) {
                nextBtn.scrollIntoView({block: 'center'});
                nextBtn.click();
                return 'clicked';
            }
            return nextBtn ? 'disabled' : 'not_found';
        })()
        """
        for _ in range(15):
            res = await page.eval(click_next_js)
            if res == "clicked":
                break
            await asyncio.sleep(1.0)

        await asyncio.sleep(1.5)
        return True

    async def _attach_document(self, page: Session, pdf_path: Path, doc_title: str) -> bool:
        """Uploads a PDF document to LinkedIn using fast file input or drag-and-drop simulation."""
        if not pdf_path.exists():
            return False

        abs_pdf = str(pdf_path.resolve())

        # Fast-Path 1: Check if composer already has an active input[type="file"]
        node_id = None
        for _ in range(5):
            try:
                doc = await page.send("DOM.getDocument", depth=-1)
                root_id = doc.get("root", {}).get("nodeId", 0)
                if root_id:
                    inp = await page.send(
                        "DOM.querySelector",
                        nodeId=root_id,
                        selector='input[type="file"][accept*="pdf"], input[type="file"]',
                    )
                    node_id = inp.get("nodeId")
                    if node_id:
                        break
            except Exception:
                pass
            await asyncio.sleep(0.4)

        # Fast-Path 2: If no input found, synthesize document trigger
        if not node_id:
            trig = await page.eval(TRIGGER_DOCUMENT_MODAL_JS)
            if trig == "overflow_clicked":
                await asyncio.sleep(0.8)
                click_overflow_doc_js = """
                (() => {
                    const item = document.querySelector('li[data-control-name*="document"]')
                        || document.querySelector('button[aria-label*="document" i]')
                        || document.querySelector('div[role="button"][aria-label*="document" i]')
                        || [...document.querySelectorAll('button, div[role="button"], li, span')].find(el => {
                            const t = (el.getAttribute('aria-label') || el.innerText || '').toLowerCase();
                            return t.includes('document');
                        });
                    if (item) {
                        item.scrollIntoView({block: 'center', inline: 'nearest'});
                        item.click();
                        return 'clicked';
                    }
                    return 'item_not_found';
                })()
                """
                for _ in range(6):
                    sub_trig = await page.eval(click_overflow_doc_js)
                    if sub_trig == "clicked":
                        break
                    await asyncio.sleep(0.5)

            # Look for file input again in the opened document dialog
            for _ in range(8):
                try:
                    doc = await page.send("DOM.getDocument", depth=-1)
                    root_id = doc.get("root", {}).get("nodeId", 0)
                    if root_id:
                        inp = await page.send(
                            "DOM.querySelector",
                            nodeId=root_id,
                            selector='input[type="file"]',
                        )
                        node_id = inp.get("nodeId")
                        if node_id:
                            break
                except Exception:
                    pass
                await asyncio.sleep(0.4)

        if not node_id:
            await capture_failure_artifacts(page, "linkedin")
            return False

        try:
            await page.send(
                "DOM.setFileInputFiles",
                files=[abs_pdf],
                nodeId=node_id,
            )
            # Wait for PDF upload and processing with polling for title input & done button
            clean_title = (doc_title or pdf_path.stem).replace("\n", " ").strip()[:50]
            title_done = False
            for _ in range(12):
                await asyncio.sleep(1.0)
                res = await page.eval(f"({DOCUMENT_TITLE_JS})({json.dumps(clean_title)})")
                if res == "done_clicked":
                    title_done = True
                    break
            await asyncio.sleep(1.5)
            if not title_done:
                await capture_failure_artifacts(page, "linkedin")
            return title_done
        except Exception:
            await capture_failure_artifacts(page, "linkedin")
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
            click_js = """
            (() => {
                const btn = document.querySelector('button[id*="share-box"]')
                    || document.querySelector('button.share-box-feed-entry__trigger')
                    || document.querySelector('button.artdeco-button--tertiary')
                    || [...document.querySelectorAll('button, div[role="button"]')].find(b => (b.innerText || '').toLowerCase().includes('start a post'));
                if (!btn) return 'not_found';
                btn.scrollIntoView({block: 'center'});
                btn.click();
                return 'clicked';
            })()
            """

            trig = await page.eval(click_js)
            if trig != "clicked":
                trig = await page.eval(TRIGGER_COMPOSER_JS)
                if trig != "clicked":
                    artifacts = await capture_failure_artifacts(page, "linkedin")
                    return PublishResult(
                        platform="linkedin",
                        success=False,
                        error="Could not find 'Start a post' button on LinkedIn feed",
                        artifacts=artifacts,
                    )
            
            await asyncio.sleep(2.0)

            # 1. Attach Images if provided
            image_targets = [p for p in payload.media_paths if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
            if image_targets:
                attached_img = await self._attach_images(page, image_targets)
                if not attached_img:
                    artifacts = await capture_failure_artifacts(page, "linkedin")
                    print(f"  [WARN] LinkedIn: Failed to attach images. Proceeding with text post. Telemetry: {artifacts.get('screenshot')}", file=sys.stderr)
                    # Close any media modal overlay if open so main composer is visible
                    await page.eval("""
                    (() => {
                        const closeBtn = document.querySelector('button[aria-label="Dismiss"]')
                            || document.querySelector('button[aria-label="Close"]')
                            || document.querySelector('button.artdeco-modal__dismiss');
                        if (closeBtn) closeBtn.click();
                    })()
                    """)
                    await asyncio.sleep(1.0)
                else:
                    await asyncio.sleep(1.5)

            # 2. Attach Carousel PDF if requested or if .pdf file provided and no images attached
            has_pdf = bool(payload.media_paths and payload.media_paths[0].suffix.lower() == ".pdf")
            if not image_targets and (payload.media_type == "carousel" or has_pdf) and payload.media_paths:
                pdf_target = payload.media_paths[0]
                if pdf_target.suffix.lower() == ".pdf":
                    doc_title = payload.extra_metadata.get("document_title") or payload.text.split("\n")[0][:60]
                    attached = await self._attach_document(page, pdf_target, doc_title)
                    if not attached:
                        artifacts = await capture_failure_artifacts(page, "linkedin")
                        print(f"  [WARN] LinkedIn: Failed to attach PDF carousel document. Proceeding with text post. Telemetry: {artifacts.get('screenshot')}", file=sys.stderr)
                    else:
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

            # Ensure LinkedIn's Lexical/ProseMirror framework registers the content
            await page.eval("""
            (() => {
                const ed = document.querySelector('div[role="dialog"] div[contenteditable="true"]')
                    || document.querySelector('div.artdeco-modal div[contenteditable="true"]')
                    || document.querySelector('div.tiptap.ProseMirror')
                    || document.querySelector('div.editor-content div[contenteditable="true"]')
                    || document.querySelector('div[role="textbox"][contenteditable="true"]');
                if (ed) {
                    ed.dispatchEvent(new Event('input', { bubbles: true }));
                    ed.dispatchEvent(new Event('change', { bubbles: true }));
                }
            })()
            """)
            await asyncio.sleep(1.0)

            # Wait and submit with poll for enabled state
            sub_res = {"error": "post_btn_disabled"}
            for _ in range(10):
                sub_res_str = await page.eval(SUBMIT_POST_JS)
                sub_res = json.loads(sub_res_str or "{}")
                if not sub_res.get("error"):
                    break
                await asyncio.sleep(1.0)

            if sub_res.get("error"):
                artifacts = await capture_failure_artifacts(page, "linkedin")
                return PublishResult(
                    platform="linkedin",
                    success=False,
                    error=f"LinkedIn post submission error: {sub_res.get('error')}",
                    artifacts=artifacts,
                )

            # In-page toast verification loop (poll for up to 5 seconds)
            toast_url = None
            verified = False
            post_id = None
            for _ in range(5):
                await asyncio.sleep(1.0)
                try:
                    toast_res = await page.eval(TOAST_QUERY_JS)
                    if toast_res and toast_res != "null":
                        if "http" in toast_res or "urn:li:activity" in toast_res:
                            toast_url = toast_res
                            verified = True
                            m = re.search(r"urn:li:activity:(\d+)", toast_url)
                            if m:
                                post_id = m.group(1)
                            break
                        elif toast_res == "success_toast_detected":
                            verified = True
                            break
                except Exception:
                    pass

            # If toast was not detected, fall back to recent activity feed verification
            if not verified:
                verified = await self._async_verify(None, payload.text)

            return PublishResult(
                platform="linkedin",
                success=True,
                post_id=post_id,
                url=toast_url,
                verified=verified,
                raw_response={"submitted": True, "toast_url": toast_url},
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
                deadline = time.time() + 10.0
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
                    await asyncio.sleep(2.0)
                    try:
                        raw = await page.eval(check_js)
                        posts = json.loads(raw or "[]")
                    except Exception:
                        posts = []

                    for p in posts:
                        p_text = p.get("text", "")
                        if norm_snippet in re.sub(r"\s+", " ", p_text).lower():
                            return True
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
