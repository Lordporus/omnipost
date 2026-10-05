import asyncio
from pathlib import Path
from typing import Any

from adapters.base import (
    PlatformAdapter,
    PlatformCapabilities,
    PublishPayload,
    PublishResult,
)
from scripts import post, settings


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
        """Publish post to X via CDP composer automation."""
        image_path: Path | None = None
        if payload.media_paths:
            image_path = payload.media_paths[0]

        try:
            res = asyncio.run(
                post.do_post(
                    text=payload.text,
                    image=image_path,
                )
            )

            return PublishResult(
                platform="x",
                success=bool(res.get("posted")),
                url=res.get("tweet_url"),
                verified=bool(res.get("verified")),
                error=res.get("error"),
                raw_response=res,
            )
        except Exception as exc:
            return PublishResult(
                platform="x",
                success=False,
                error=str(exc),
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
        except Exception:
            return False
