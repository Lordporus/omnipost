"""Core adapter contracts and data schemas for OmniPost platforms."""
from __future__ import annotations

import base64
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.errors import (
        AdapterError,
        ComposerOpenError,
        RateLimitError,
        SelectorError,
        VerificationError,
    )
except ImportError:  # direct script execution from the scripts/ directory
    from errors import (  # type: ignore[no-redef]
        AdapterError,
        ComposerOpenError,
        RateLimitError,
        SelectorError,
        VerificationError,
    )

ROOT = Path(__file__).resolve().parent.parent
SHOTS_DIR = ROOT / "shots"
ARTIFACT_RETENTION = 20
_LOG = logging.getLogger(__name__)


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the isolated publish-worker JSON contract."""
        return {
            "text": self.text,
            "media_paths": [str(path) for path in self.media_paths],
            "media_type": self.media_type,
            "extra_metadata": dict(self.extra_metadata or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PublishPayload":
        """Deserialize a publish-worker payload."""
        return cls(
            text=str(data.get("text") or ""),
            media_paths=[Path(path) for path in (data.get("media_paths") or [])],
            media_type=str(data.get("media_type") or "image"),
            extra_metadata=dict(data.get("extra_metadata") or {}),
        )


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

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the isolated publish-worker result file."""
        return {
            "platform": self.platform,
            "success": bool(self.success),
            "post_id": self.post_id,
            "url": self.url,
            "verified": bool(self.verified),
            "error": self.error,
            "artifacts": dict(self.artifacts or {}),
            "raw_response": dict(self.raw_response or {}),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PublishResult":
        """Deserialize a publish-worker result."""
        return cls(
            platform=str(data.get("platform") or ""),
            success=bool(data.get("success", False)),
            post_id=data.get("post_id"),
            url=data.get("url"),
            verified=bool(data.get("verified", False)),
            error=data.get("error"),
            artifacts=dict(data.get("artifacts") or {}),
            raw_response=dict(data.get("raw_response") or {}),
        )


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*")
_COOKIE_RE = re.compile(r"(?i)\b(set-cookie|cookie)\b\s*:\s*[^\r\n]+")
_AUTH_HEADER_RE = re.compile(
    r"(?i)\b(authorization|proxy-authorization|x-csrf-token|csrf[-_]?token|"
    r"session(?:id)?|access[-_]?token|refresh[-_]?token|token)\b\s*[:=]\s*"
    r"([^\s,;\"'<>]{4,})"
)
_LONG_SECRET_RE = re.compile(r"\b[A-Za-z0-9+/=_-]{32,}\b")
_SCRIPT_RE = re.compile(r"(?is)<script\b[^>]*>.*?</script>")
_INPUT_VALUE_RE = re.compile(r'(?is)(<input\b[^>]*\bvalue=")([^"]*)(")')
_TEXTAREA_RE = re.compile(r"(?is)(<textarea\b[^>]*>)(.*?)(</textarea>)")


def redact_text(text: str) -> str:
    """Redact known PII and secrets from arbitrary text."""
    if not text:
        return ""
    out = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    out = _BEARER_RE.sub("Bearer [REDACTED]", out)
    out = _COOKIE_RE.sub(lambda m: f"{m.group(1)}: [REDACTED]", out)
    out = _AUTH_HEADER_RE.sub(lambda m: f"{m.group(1)}: [REDACTED]", out)
    out = _LONG_SECRET_RE.sub("[REDACTED_SECRET]", out)
    return out


def redact_html(html: str) -> str:
    """Redact scripts, form values, and secrets from a captured DOM dump."""
    if not html:
        return ""
    out = _SCRIPT_RE.sub("<script>[REDACTED]</script>", html)
    out = _INPUT_VALUE_RE.sub(lambda m: f"{m.group(1)}[REDACTED]{m.group(3)}", out)
    out = _TEXTAREA_RE.sub(r"\1[REDACTED]\3", out)
    return redact_text(out)


def _enforce_retention(platform: str, keep: int = ARTIFACT_RETENTION) -> None:
    """Keep only the newest *keep* artifact files for *platform*."""
    try:
        files = sorted(
            (p for p in SHOTS_DIR.glob(f"{platform}_*") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except OSError as exc:
        _LOG.warning("artifact_retention_scan_failed: %s", exc)
        return
    for stale in files[keep:]:
        try:
            stale.unlink()
        except OSError as exc:
            _LOG.warning("artifact_retention_delete_failed: %s", exc)


async def capture_failure_artifacts(page: Any, platform: str) -> dict[str, str]:
    """Capture a redacted screenshot and DOM dump under ``ROOT/shots``.

    Artifacts are never written to a CWD-relative path, known PII/secrets are
    redacted before writing, and only the newest ``ARTIFACT_RETENTION`` files
    per platform are kept. Capture failures are logged and never mask the
    adapter error that triggered the capture.

    Returns a short summary plus any artifact paths; it never returns raw DOM.
    """
    artifacts: dict[str, str] = {"summary": f"{platform} publish failure"}
    try:
        SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _LOG.warning("artifact_dir_unavailable: %s", exc)
        return artifacts

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    base = f"{platform}_{stamp}"
    shot_path = SHOTS_DIR / f"{base}.png"
    html_path = SHOTS_DIR / f"{base}.html"

    try:
        data = await page.send("Page.captureScreenshot", format="png")
        if isinstance(data, dict) and data.get("data"):
            shot_path.write_bytes(base64.b64decode(data["data"]))
            artifacts["screenshot"] = str(shot_path)
    except Exception as exc:  # capture must not mask the original failure
        _LOG.warning("artifact_screenshot_failed: %s", exc)

    try:
        content = await page.eval("document.documentElement.outerHTML")
        if content:
            html_path.write_text(redact_html(str(content)), encoding="utf-8")
            artifacts["html"] = str(html_path)
    except Exception as exc:  # capture must not mask the original failure
        _LOG.warning("artifact_html_failed: %s", exc)

    _enforce_retention(platform)
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
