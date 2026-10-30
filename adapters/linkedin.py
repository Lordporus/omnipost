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
    AdapterError,
    ComposerOpenError,
    PlatformAdapter,
    PlatformCapabilities,
    PublishPayload,
    PublishResult,
    RateLimitError,
    SelectorError,
    capture_failure_artifacts,
)
from scripts import browser, settings
from scripts.browser import CDPError, Session

try:  # package import (tests, publish worker)
    from scripts.errors import MediaContractError
except ImportError:  # direct script execution
    from errors import MediaContractError

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state.json"

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _parse_iso_utc(value: Any) -> datetime:
    """Parse an ISO timestamp, treating naive values as UTC."""
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("empty timestamp")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _last_linkedin_post_at(state: dict[str, Any]) -> datetime | None:
    """Return the newest v3 LinkedIn platform timestamp in *state*.

    Only ``posts[*].platforms.linkedin.at`` is authoritative. Legacy
    ``outcomes`` and entry-level ``platform``/``at`` fields are ignored.
    """
    if not isinstance(state, dict):
        raise ValueError("state root must be a JSON object")
    posts = state.get("posts", [])
    if not isinstance(posts, list):
        raise ValueError("state.posts must be a list")

    latest: datetime | None = None
    for entry in posts:
        if not isinstance(entry, dict):
            continue
        platforms = entry.get("platforms")
        if not isinstance(platforms, dict):
            continue
        record = platforms.get("linkedin")
        if not isinstance(record, dict):
            continue
        at_value = record.get("at")
        if not at_value:
            continue
        try:
            parsed = _parse_iso_utc(at_value)
        except Exception as exc:
            raise RateLimitError(
                f"LinkedIn rate-limit timestamp is invalid: {at_value!r}",
                platform="linkedin",
                stage="rate_limit",
                last_at=str(at_value),
                context={
                    "state_path": str(STATE_PATH),
                    "at": str(at_value),
                    "error": str(exc),
                },
            ) from exc
        if latest is None or parsed > latest:
            latest = parsed
    return latest


def _trigger_diagnostics(value: Any) -> dict[str, Any]:
    """Normalize the composer-trigger result from mocked or real CDP eval."""
    if isinstance(value, dict):
        return {
            "result": str(value.get("result") or value.get("status") or ""),
            "selector": value.get("selector"),
            "candidates": int(value.get("candidates") or 0),
        }
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            return _trigger_diagnostics(parsed)
        return {"result": text, "selector": None, "candidates": 0}
    return {"result": "not_found", "selector": None, "candidates": 0}


def _focus_status(value: Any) -> str:
    """Normalize the editor-focus result from mocked or real CDP eval."""
    if isinstance(value, dict):
        return str(value.get("status") or value.get("result") or "")
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            return _focus_status(parsed)
        return text
    return ""


def _select_linkedin_media(payload: PublishPayload) -> tuple[str, Path | None]:
    """Resolve LinkedIn's media precedence without touching the browser.

    D-07: images win whenever they are attached. A PDF is selected only when
    ``media_type == "carousel"`` and no images are attached. A carousel request
    without a PDF is a contract error, not a silent text-only fallback.
    """
    image_targets = [
        path for path in payload.media_paths if path.suffix.lower() in _IMAGE_SUFFIXES
    ]
    if image_targets:
        return "images", None

    pdf_targets = [
        path for path in payload.media_paths if path.suffix.lower() == ".pdf"
    ]
    if payload.media_type == "carousel":
        if not pdf_targets:
            raise MediaContractError(
                "LinkedIn carousel requested but no .pdf path was provided.",
                platform="linkedin",
                stage="media_contract",
            )
        return "document", pdf_targets[0]

    if pdf_targets:
        raise MediaContractError(
            "LinkedIn image payload contains a PDF path; set media_type='carousel'.",
            platform="linkedin",
            stage="media_contract",
        )
    return "text", None


# Stealth script to mask automated browser flags
STEALTH_JS = r"""
(() => {
  try {
    Object.defineProperty(navigator, 'webdriver', {
      get: () => false,
      configurable: true,
    });
  } catch (e) {}
  window.chrome = window.chrome || { runtime: {} };
})()
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

# Scoped selectors are deliberately checked before any text/aria fallback. A
# generic tertiary artdeco button class is not used because it is shared by
# Like/Comment and other feed controls.
LINKEDIN_COMPOSER_SELECTORS = [
    'button[id*="share-box"]',
    'button.share-box-feed-entry__trigger',
    'div.share-box-feed-entry__wrapper',
    'div.share-box-feed-entry__wrapper button',
    'div.share-box-feed-entry__wrapper [role="button"]',
]

# JavaScript to trigger the post composer and return observable diagnostics.
TRIGGER_COMPOSER_JS = r"""
(() => {
  const scopedSelectors = [
    'button[id*="share-box"]',
    'button.share-box-feed-entry__trigger',
    'div.share-box-feed-entry__wrapper',
    'div.share-box-feed-entry__wrapper button',
    'div.share-box-feed-entry__wrapper [role="button"]'
  ];

  const clickNode = (node, selector, candidates) => {
    let target = node;
    if (!target.matches('button, [role="button"]')) {
      target = target.querySelector('button, [role="button"]')
        || target.closest('button, [role="button"]')
        || target;
    }
    if (!target || typeof target.click !== 'function') return null;
    try { target.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (e) {}
    target.click();
    return {result: 'clicked', selector: selector, candidates: candidates};
  };

  for (const selector of scopedSelectors) {
    const nodes = [...document.querySelectorAll(selector)];
    if (!nodes.length) continue;
    const clicked = clickNode(nodes[0], selector, nodes.length);
    if (clicked) return clicked;
  }

  const labelOf = (node) => (
    ((node.innerText || '') + ' ' + (node.getAttribute('aria-label') || '')).toLowerCase()
  );
  const isComposerTrigger = (node) => {
    const label = labelOf(node);
    return label.includes('start a post') || label.includes('create a post');
  };

  const candidates = [];
  const scan = (root) => {
    for (const node of root.querySelectorAll('button, [role="button"]')) {
      if (isComposerTrigger(node)) candidates.push(node);
    }
  };

  // Prefer the feed's share box, then fall back to a text/aria match. No
  // generic button class is ever used as a fallback.
  for (const root of document.querySelectorAll('div.share-box-feed-entry__wrapper, .share-box, div[role="main"]')) {
    scan(root);
    if (candidates.length) break;
  }
  if (!candidates.length) scan(document);

  if (candidates.length) {
    const clicked = clickNode(candidates[0], 'text:start-a-post', candidates.length);
    if (clicked) return clicked;
  }

  return {result: 'not_found', selector: null, candidates: candidates.length};
})()
"""

FOCUS_EDITOR_JS = r"""
(() => {
  // LinkedIn renders the composer as an inline overlay, not always inside
  // div[role="dialog"], so the editor is looked up directly.
  const dialog = document.querySelector('div[role="dialog"]')
    || document.querySelector('div.artdeco-modal')
    || document.querySelector('.share-box');

  let ed = null;
  for (const root of dialog ? [dialog, document] : [document]) {
    ed = root.querySelector('div.tiptap.ProseMirror')
      || root.querySelector('div[role="textbox"][contenteditable="true"]')
      || root.querySelector('div[contenteditable="true"]');
    if (ed) break;
  }
  if (!ed) return 'no_editor';

  const rect = ed.getBoundingClientRect();
  const style = window.getComputedStyle(ed);
  const visible = rect.width > 0 && rect.height > 0
    && style.display !== 'none'
    && style.visibility !== 'hidden'
    && style.opacity !== '0';
  if (!visible) return 'editor_not_visible';

  const enabled = !ed.disabled
    && ed.getAttribute('aria-disabled') !== 'true'
    && ed.getAttribute('contenteditable') !== 'false'
    && !ed.readOnly;
  if (!enabled) return 'editor_disabled';

  try { ed.scrollIntoView({block: 'center', inline: 'nearest'}); } catch (e) {}
  ed.focus();
  try { ed.click(); } catch (e) {}
  const active = document.activeElement === ed || ed.contains(document.activeElement);
  return active ? 'focused' : 'not_focused';
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

POINTER_CLICK_JS = r"""
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return 'not_found';
  const r = el.getBoundingClientRect();
  const o = {
    bubbles: true, cancelable: true, composed: true,
    clientX: r.left + r.width / 2, clientY: r.top + r.height / 2,
    button: 0, buttons: 1, pointerId: 1, pointerType: 'mouse', isPrimary: true,
  };
  el.dispatchEvent(new PointerEvent('pointerdown', o));
  el.dispatchEvent(new MouseEvent('mousedown', o));
  el.dispatchEvent(new PointerEvent('pointerup', {...o, buttons: 0}));
  el.dispatchEvent(new MouseEvent('mouseup', {...o, buttons: 0}));
  el.dispatchEvent(new MouseEvent('click', {...o, buttons: 0}));
  return 'clicked';
}
"""

# The composer header's "More" menu only offers Groups/Events/Newsletters, so it is
# never a fallback here.
EXPAND_CONTENT_TYPES_JS = f"({POINTER_CLICK_JS})('button[aria-label=\"Expand content types\"]')"

# After expanding, the document control is an <a>, not a <button>.
CLICK_DOCUMENT_ITEM_JS = f"({POINTER_CLICK_JS})('a[aria-label=\"Document\"], [aria-label=\"Document\"]')"

# "Choose file" creates the PDF input on demand and opens the OS dialog. Capture the
# input instead of letting the dialog open.
CAPTURE_FILE_INPUT_JS = r"""
(() => {
  window.__fileInput = null;
  const orig = HTMLInputElement.prototype.click;
  HTMLInputElement.prototype.click = function() {
    if (this.type === 'file') { window.__fileInput = this; return; }
    return orig.apply(this, arguments);
  };
  return 'patched';
})()
"""

CHOOSE_FILE_JS = r"""
(() => {
  const b = [...document.querySelectorAll('button')]
    .find(x => /choose file/i.test(x.innerText || ''));
  if (!b) return 'not_found';
  b.click();
  return 'clicked';
})()
"""

DOCUMENT_TITLE_JS = r"""
(title) => {
  const input = document.querySelector('input[placeholder*="descriptive title" i]')
    || document.querySelector('input[placeholder*="Title" i]')
    || document.querySelector('input[aria-label*="Title" i]')
    || document.querySelector('input[id*="document-title"]');
  if (input) {
    // React ignores a plain value assignment; go through the native setter.
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(input, title);
    if (input._valueTracker) input._valueTracker.setValue('');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  const doneBtn = [...document.querySelectorAll('button')].find(b => {
    const t = (b.innerText || '').trim().toLowerCase();
    return t === 'done' || t === 'next';
  });
  if (doneBtn && !doneBtn.disabled) {
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

    @staticmethod
    def _last_linkedin_post_at(state: dict[str, Any]) -> datetime | None:
        """Unit-testable alias for the module-level v3 timestamp helper."""
        return _last_linkedin_post_at(state)

    def _check_rate_limit(self) -> tuple[bool, str | None]:
        """Enforce minimum spacing using the v3 LinkedIn platform record.

        Reads ``posts[*].platforms.linkedin.at``. Any unreadable state or
        malformed timestamp fails closed with ``RateLimitError`` rather than
        silently allowing a post.
        """
        try:
            if not STATE_PATH.exists():
                return True, None
            st = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            last_dt = _last_linkedin_post_at(st)
            if last_dt is None:
                return True, None

            now = datetime.now(timezone.utc)
            diff_hours = (now - last_dt).total_seconds() / 3600.0
            if diff_hours < self._min_gap_hours:
                return False, (
                    "LinkedIn rate-limit guardrail: only "
                    f"{diff_hours:.1f}h elapsed since last post. "
                    f"Minimum {self._min_gap_hours}h required."
                )
            return True, None
        except RateLimitError:
            raise
        except Exception as exc:
            print(
                f"  [ERROR] LinkedIn rate-limit check failed: {exc}",
                file=sys.stderr,
                flush=True,
            )
            raise RateLimitError(
                f"LinkedIn rate-limit check failed: {exc}",
                platform="linkedin",
                stage="rate_limit",
                min_gap_hours=self._min_gap_hours,
                context={"state_path": str(STATE_PATH), "error": str(exc)},
            ) from exc

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
        # The script only applies to documents created after it is registered, so
        # the page must be (re)navigated here; otherwise the first load runs with
        # navigator.webdriver visible.
        await page.send("Page.navigate", url=url)
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
        except (CDPError, OSError, asyncio.TimeoutError, ValueError, RuntimeError) as exc:
            return {
                "ok": False,
                "platform": "linkedin",
                "handle": None,
                "error": str(exc),
            }

    async def _attach_images(self, page: Session, image_paths: list[Path]) -> bool:
        """Attaches 1-3 PNG images directly to LinkedIn post composer via the Media button."""
        valid_files = [browser.browser_file_path(p) for p in image_paths if p.exists() and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
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
            except (CDPError, OSError, asyncio.TimeoutError, ValueError):
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
                except (CDPError, OSError, asyncio.TimeoutError, ValueError):
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
        except (CDPError, OSError, ValueError):
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
        clicked = "not_found"
        for _ in range(15):
            clicked = await page.eval(click_next_js)
            if clicked == "clicked":
                break
            await asyncio.sleep(1.0)

        if clicked != "clicked":
            return False
        await asyncio.sleep(1.5)
        return True

    async def _attach_document(self, page: Session, pdf_path: Path, doc_title: str) -> bool:
        """Uploads a PDF through LinkedIn's document composer.

        The path was measured live on 2026-10-29: expand the content-type row, click
        the "Document" anchor (it navigates to the document composer), capture the
        on-demand PDF input, set the title, then Done returns to the post composer.
        """
        if not pdf_path.exists():
            return False

        abs_pdf = browser.browser_file_path(pdf_path)
        clean_title = (doc_title or pdf_path.stem).replace("\n", " ").strip()[:50]

        # Fast-Path: a PDF-accepting input already in the DOM (retry after a partial run)
        node_id = None
        for _ in range(5):
            try:
                doc = await page.send("DOM.getDocument", depth=-1)
                root_id = doc.get("root", {}).get("nodeId", 0)
                if root_id:
                    inp = await page.send(
                        "DOM.querySelector",
                        nodeId=root_id,
                        selector='input[type="file"][accept*="pdf"]',
                    )
                    node_id = inp.get("nodeId")
                    if node_id:
                        break
            except (CDPError, OSError, asyncio.TimeoutError, ValueError):
                pass
            await asyncio.sleep(0.4)

        if not node_id:
            if await page.eval(EXPAND_CONTENT_TYPES_JS) != "clicked":
                await capture_failure_artifacts(page, "linkedin")
                return False

            clicked = False
            for _ in range(16):
                await asyncio.sleep(0.5)
                if await page.eval(CLICK_DOCUMENT_ITEM_JS) == "clicked":
                    clicked = True
                    break
            if not clicked:
                await capture_failure_artifacts(page, "linkedin")
                return False

            # "Choose file" creates the input on demand; capture it so no OS dialog opens.
            await page.eval(CAPTURE_FILE_INPUT_JS)
            chosen = False
            for _ in range(20):
                await asyncio.sleep(0.5)
                if await page.eval(CHOOSE_FILE_JS) == "clicked":
                    chosen = True
                    break
            if not chosen:
                await capture_failure_artifacts(page, "linkedin")
                return False

        try:
            if node_id:
                await page.send("DOM.setFileInputFiles", files=[abs_pdf], nodeId=node_id)
            else:
                res = await page.send(
                    "Runtime.evaluate", expression="window.__fileInput", returnByValue=False
                )
                object_id = res.get("result", {}).get("objectId")
                if not object_id:
                    await capture_failure_artifacts(page, "linkedin")
                    return False
                await page.send("DOM.setFileInputFiles", files=[abs_pdf], objectId=object_id)

            # Upload processing, then the title + Done step
            title_done = False
            for _ in range(20):
                await asyncio.sleep(1.0)
                if await page.eval(f"({DOCUMENT_TITLE_JS})({json.dumps(clean_title)})") == "done_clicked":
                    title_done = True
                    break
            await asyncio.sleep(1.5)
            if not title_done:
                await capture_failure_artifacts(page, "linkedin")
                return False

            # Done lands back on the post composer; the caller types the text next.
            focused = False
            for _ in range(20):
                await asyncio.sleep(0.5)
                if await page.eval(FOCUS_EDITOR_JS) == "focused":
                    focused = True
                    break
            if not focused:
                await capture_failure_artifacts(page, "linkedin")
            return focused
        except (CDPError, OSError, asyncio.TimeoutError, ValueError):
            await capture_failure_artifacts(page, "linkedin")
            return False

    async def _trigger_composer(self, page: Session) -> dict[str, Any]:
        """Click the scoped share-box trigger and return selector diagnostics."""
        raw = await page.eval(TRIGGER_COMPOSER_JS)
        return _trigger_diagnostics(raw)

    async def _wait_for_composer_editor(
        self,
        page: Session,
        attempts: int = 20,
        interval: float = 0.5,
    ) -> str:
        """Poll for a visible, enabled, focused composer editor."""
        last_status = "no_dialog"
        for attempt in range(attempts):
            if attempt:
                await asyncio.sleep(interval)
            try:
                raw = await page.eval(FOCUS_EDITOR_JS)
            except (CDPError, OSError, asyncio.TimeoutError) as exc:
                last_status = f"eval_error:{exc}"
                continue
            last_status = _focus_status(raw)
            if last_status == "focused":
                return last_status
        return last_status

    async def _async_publish(self, payload: PublishPayload) -> PublishResult:
        # 1. Spacing check. A malformed state raises RateLimitError and fails closed.
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

            trigger = await self._trigger_composer(page)
            if trigger.get("result") != "clicked":
                artifacts = await capture_failure_artifacts(page, "linkedin")
                raise ComposerOpenError(
                    "Could not open the LinkedIn composer: "
                    f"result={trigger.get('result')!r}, "
                    f"selector={trigger.get('selector')!r}, "
                    f"candidates={trigger.get('candidates', 0)}, "
                    f"selectors={LINKEDIN_COMPOSER_SELECTORS}, "
                    f"screenshot={artifacts.get('screenshot')}",
                    platform="linkedin",
                    stage="composer_open",
                    selector=trigger.get("selector") or "",
                    selectors=LINKEDIN_COMPOSER_SELECTORS,
                    candidates=int(trigger.get("candidates") or 0),
                    artifacts=artifacts,
                    context={"trigger": trigger},
                )

            focus_status = await self._wait_for_composer_editor(page)
            if focus_status != "focused":
                artifacts = await capture_failure_artifacts(page, "linkedin")
                raise ComposerOpenError(
                    "LinkedIn composer dialog/editor did not become ready: "
                    f"status={focus_status!r}, selectors={LINKEDIN_COMPOSER_SELECTORS}, "
                    f"screenshot={artifacts.get('screenshot')}",
                    platform="linkedin",
                    stage="composer_ready",
                    selectors=LINKEDIN_COMPOSER_SELECTORS,
                    candidates=int(trigger.get("candidates") or 0),
                    artifacts=artifacts,
                    context={"trigger": trigger, "focus_status": focus_status},
                )

            # 2. Resolve media precedence, then attach exactly one media mode.
            media_mode, pdf_target = _select_linkedin_media(payload)
            image_targets = [
                p for p in payload.media_paths if p.suffix.lower() in _IMAGE_SUFFIXES
            ] if media_mode == "images" else []
            if media_mode == "images":
                attached_img = await self._attach_images(page, image_targets)
                if not attached_img:
                    artifacts = await capture_failure_artifacts(page, "linkedin")
                    raise MediaContractError(
                        "LinkedIn image attach failed; refusing to publish text-only",
                        platform="linkedin",
                        stage="media_attach",
                        context={"trigger": trigger, "artifacts": artifacts},
                    )
                await asyncio.sleep(1.5)
                focus_status = await self._wait_for_composer_editor(page, attempts=10)
                if focus_status != "focused":
                    artifacts = await capture_failure_artifacts(page, "linkedin")
                    raise ComposerOpenError(
                        "LinkedIn editor lost focus after image attachment: "
                        f"status={focus_status!r}",
                        platform="linkedin",
                        stage="composer_ready_after_media",
                        selectors=LINKEDIN_COMPOSER_SELECTORS,
                        candidates=int(trigger.get("candidates") or 0),
                        artifacts=artifacts,
                        context={"trigger": trigger, "focus_status": focus_status},
                    )

            # 3. Attach Carousel PDF only when the media contract selected it.
            elif media_mode == "document" and pdf_target is not None:
                doc_title = payload.extra_metadata.get("document_title") or payload.text.split("\n")[0][:60]
                attached = await self._attach_document(page, pdf_target, doc_title)
                if not attached:
                    artifacts = await capture_failure_artifacts(page, "linkedin")
                    return PublishResult(
                        platform="linkedin",
                        success=False,
                        error=(
                            "Failed to attach PDF carousel document; refusing to "
                            "publish a text-only substitute. "
                            f"screenshot={artifacts.get('screenshot')}"
                        ),
                        artifacts=artifacts,
                    )
                await asyncio.sleep(1.5)

            # Inject text via CDP Input.insertText.
            await page.send("Input.insertText", text=payload.text)
            await asyncio.sleep(1.0)

            # Ensure LinkedIn's Lexical/ProseMirror framework registers the content.
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

            # Wait and submit with poll for enabled state.
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

            # In-page toast verification loop (poll for up to 5 seconds).
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
                except (CDPError, OSError, asyncio.TimeoutError):
                    pass

            # If toast was not detected, fall back to recent activity feed verification.
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
        except AdapterError as exc:
            return PublishResult(
                platform="linkedin",
                success=False,
                error=str(exc),
                artifacts=dict(getattr(exc, "artifacts", {}) or {}),
                raw_response={
                    "error_type": type(exc).__name__,
                    "platform": exc.platform,
                    "stage": exc.stage,
                    "context": dict(exc.context),
                },
            )
        except (CDPError, OSError, asyncio.TimeoutError) as exc:
            return PublishResult(
                platform="linkedin",
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def _async_verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Read-back verification on recent activity page with retry polling."""
        profile = self._profile_url.strip().rstrip("/")
        if profile and not profile.startswith(("http://", "https://")):
            profile = f"https://{profile}"
        target_url = (
            f"{profile}/recent-activity/all/"
            if profile
            else "https://www.linkedin.com/feed/"
        )
        try:
            page = await self._open_stealth(target_url)
            try:
                await browser.settle_page(page, 4.0)
                deadline = time.time() + 10.0
                norm_snippet = re.sub(r"\s+", " ", text_snippet[:40]).strip().lower()

                # LinkedIn's post containers no longer use stable classes or
                # data-urn, so readback checks the rendered page text instead.
                check_js = "(() => document.body.innerText || '')()"

                while time.time() < deadline:
                    await asyncio.sleep(2.0)
                    try:
                        body = await page.eval(check_js)
                    except (CDPError, OSError, asyncio.TimeoutError, ValueError):
                        body = ""

                    if norm_snippet in re.sub(r"\s+", " ", body or "").lower():
                        return True
                return False

            finally:
                await page.__aexit__(None, None, None)
        except (CDPError, OSError, asyncio.TimeoutError, ValueError):
            return False

    def verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Synchronous wrapper for activity verification."""
        try:
            return asyncio.run(self._async_verify(post_id, text_snippet))
        except (CDPError, OSError, asyncio.TimeoutError, ValueError, RuntimeError):
            return False
