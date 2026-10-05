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


@dataclass
class PublishResult:
    """Standardized outcome of a platform publish attempt."""
    platform: str
    success: bool
    post_id: str | None = None
    url: str | None = None
    verified: bool = False
    error: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


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
