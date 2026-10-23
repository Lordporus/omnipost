"""Core adapter contracts and data schemas for OmniPost platforms."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PlatformCapabilities:
    """Declared capabilities and constraints for a social platform."""
    max_characters: int
    supports_markdown: bool = False
    supports_images: bool = True
    max_images: int = 1
    supports_pdf_carousel: bool = False
    requires_public_image_url: bool = False


@dataclass
class PublishPayload:
    """Standardized input payload for cross-platform publishing."""
    text: str
    media_paths: list[Path] = field(default_factory=list)
    media_type: str = "image"  # "image" | "carousel"
    extra_metadata: dict[str, Any] = field(default_factory=dict)


import base64

@dataclass
class PublishResult:
    """Standardized outcome of a platform publish attempt."""
    platform: str
    success: bool
    post_id: str | None = None
    url: str | None = None
    verified: bool = False
    error: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)


async def capture_failure_artifacts(page: Any, platform: str) -> dict[str, str]:
    """Capture viewport screenshot and DOM dump upon publishing failure."""
    shots_dir = Path("shots")
    shots_dir.mkdir(parents=True, exist_ok=True)
    shot_path = shots_dir / f"{platform}_fail.png"
    html_path = shots_dir / f"{platform}_fail.html"
    artifacts: dict[str, str] = {}
    try:
        data = await page.send("Page.captureScreenshot", format="png")
        if data and "data" in data:
            shot_path.write_bytes(base64.b64decode(data["data"]))
            artifacts["screenshot"] = str(shot_path)
    except Exception:
        pass
    try:
        content = await page.eval("document.documentElement.outerHTML")
        if content:
            html_path.write_text(content, encoding="utf-8")
            artifacts["html"] = str(html_path)
    except Exception:
        pass
    return artifacts


class PlatformAdapter(ABC):
    """Abstract Base Class for all social platform adapters."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Unique identifier of the platform (e.g. 'x', 'bluesky', 'linkedin')."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> PlatformCapabilities:
        """Returns the capabilities and constraints of the platform."""
        pass

    @abstractmethod
    def check_session(self) -> dict[str, Any]:
        """Verify authentication/session readiness.
        
        Returns:
            dict containing status information (e.g. {'ok': True, 'account': ...}).
        """
        pass

    @abstractmethod
    def publish(self, payload: PublishPayload) -> PublishResult:
        """Publish content to the platform.
        
        Args:
            payload: PublishPayload containing text and optional media.
            
        Returns:
            PublishResult with status, post_id, url, and verification.
        """
        pass

    @abstractmethod
    def verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Read-back verification that the post is live on the user's public feed/profile.
        
        Args:
            post_id: Identifier of the post if available.
            text_snippet: Text prefix or substring to verify on profile.
            
        Returns:
            True if post is verified live, False otherwise.
        """
        pass
