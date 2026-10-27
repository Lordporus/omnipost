import asyncio
import sys
from pathlib import Path
from typing import Any

from adapters.base import (
    AdapterError,
    PlatformAdapter,
    PlatformCapabilities,
    PublishPayload,
    PublishResult,
)
from scripts import browser, post, settings
from scripts.browser import CDPError


class XAdapter(PlatformAdapter):
    """Adapter for X (Twitter) using Chrome/Edge DevTools Protocol automation."""

    def __init__(self, port: int | None = None):
        cfg = settings.load()
        browser_cfg = cfg.get("browser", {})
        self._port = port or int(browser_cfg.get("port", 9444) if isinstance(browser_cfg, dict) else 9444)

    @property
    def platform_name(self) -> str:
        return "x"

    @property
    def capabilities(self) -> PlatformCapabilities:
        limits = settings.limit()
        return PlatformCapabilities(
            max_characters=limits.get("chars", 280),
            supports_markdown=False,
            supports_images=True,
            max_images=4,
            supports_pdf_carousel=False,
            requires_public_image_url=False,
        )

    def check_session(self) -> dict[str, Any]:
        """Check active session for X via CDP."""
        try:
            info = asyncio.run(post.session_info())
            handle = info.get("handle")
            return {
                "ok": bool(handle),
                "platform": "x",
                "handle": handle,
                "tier": info.get("tier", "free"),
                "error": None if handle else "No active X session or handle found",
            }
        except Exception as exc:
            return {
                "ok": False,
                "platform": "x",
                "handle": None,
                "tier": "unknown",
                "error": str(exc),
            }

    def publish(self, payload: PublishPayload) -> PublishResult:
        """Publish post to X via CDP composer automation.

        Every rendered card is passed through in order, up to the platform's
        four-image cap. A single image keeps the original ``image=`` call path.
        """
        browser.ensure_chrome()
        media_paths = [Path(path) for path in payload.media_paths[: self.capabilities.max_images]]
        try:
            if len(media_paths) > 1:
                print(
                    f"  [X] Attaching {len(media_paths)} cards (cap {self.capabilities.max_images})",
                    file=sys.stderr,
                    flush=True,
                )
                res = asyncio.run(
                    post.do_post(
                        text=payload.text,
                        images=media_paths,
                    )
                )
            else:
                image_path: Path | None = media_paths[0] if media_paths else None
                res = asyncio.run(
                    post.do_post(
                        text=payload.text,
                        image=image_path,
                    )
                )

            success = bool(res.get("posted"))
            err = res.get("error")
            if not success and not err:
                if res.get("toast_sent"):
                    err = "Post was submitted, but timeline readback verification timed out"
                else:
                    err = "Post submission failed or timed out"

            return PublishResult(
                platform="x",
                success=success,
                url=res.get("tweet_url"),
                verified=bool(res.get("verified")),
                error=err,
                raw_response=res,
            )
        except AdapterError:
            raise
        except (CDPError, OSError, asyncio.TimeoutError) as exc:
            return PublishResult(
                platform="x",
                success=False,
                error=f"{type(exc).__name__}: {exc}",
            )

    def verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Verify post is live by inspecting recent profile timeline."""
        try:
            posts = asyncio.run(post._read_profile())
            head = post._norm(text_snippet)[:40]
            for p in posts:
                if head in post._norm(p.get("text", "")):
                    return True
            return False
        except (CDPError, OSError, asyncio.TimeoutError, ValueError):
            return False
