"""Shared typed errors for OmniPost content generation and publish state.

Keeping these in one module prevents each pipeline stage from defining its own
near-identical exception class and lets callers catch a stable, meaningful type.
"""
from __future__ import annotations

from typing import Any


class ContentError(Exception):
    """Base class for content-generation failures."""


class TopicRejected(ContentError):
    """A candidate item cannot produce a publishable, relevant topic."""

    def __init__(self, reason: str, item: dict[str, Any] | None = None):
        self.reason = reason
        self.item = item
        title = ""
        if isinstance(item, dict):
            title = str(item.get("title") or "").strip()
        message = reason if not title else f"{reason}: {title}"
        super().__init__(message)


class NoRelevantTopic(ContentError):
    """No candidate item passed the relevance or content-integrity gate."""


class DuplicateTopic(ContentError):
    """A topic duplicates content already assigned to another slot."""


class CopyValidationError(ContentError):
    """Platform copy is outside its measured minimum or maximum limits.

    ``platform``, ``count``, and ``limits`` are kept as attributes so callers
    can log or requeue a candidate without parsing the message.
    """

    def __init__(
        self,
        message: str = "",
        *,
        platform: str = "",
        count: int | None = None,
        limits: dict[str, int] | None = None,
        **details: Any,
    ):
        self.platform = platform
        self.count = count
        self.limits: dict[str, int] = dict(limits or {})
        self.context: dict[str, Any] = dict(details)
        super().__init__(message)


class StateError(Exception):
    """Base class for publish-state failures."""


class StateCorruptionError(StateError):
    """state.json is unreadable and no valid backup could be restored."""


class StateLockTimeout(StateError):
    """The cross-process state lock could not be acquired before the timeout."""


class AdapterError(Exception):
    """Base class for actionable platform-adapter failures.

    The message is intentionally first so callers can write
    ``AdapterError("could not open composer", platform="linkedin")``.
    Platform, stage, and structured context are kept as attributes so the
    publish worker and operators can tell where a failure happened without
    parsing prose.
    """

    def __init__(
        self,
        message: str = "",
        *,
        platform: str = "",
        stage: str = "",
        context: dict[str, Any] | None = None,
        **details: Any,
    ):
        self.platform = platform
        self.stage = stage
        self.context: dict[str, Any] = dict(context or {})
        self.context.update(details)
        super().__init__(message)


class MediaContractError(AdapterError):
    """A payload's media type does not match the attached media paths."""

    def __init__(
        self,
        message: str = "",
        *,
        platform: str = "",
        stage: str = "media_contract",
        context: dict[str, Any] | None = None,
        **details: Any,
    ):
        super().__init__(
            message,
            platform=platform,
            stage=stage,
            context=context,
            **details,
        )


class SelectorError(AdapterError):
    """A browser selector could not find or use the required control."""

    def __init__(
        self,
        message: str = "",
        *,
        platform: str = "",
        stage: str = "",
        selector: str = "",
        selectors: list[str] | tuple[str, ...] | None = None,
        candidates: int | None = None,
        context: dict[str, Any] | None = None,
        **details: Any,
    ):
        ctx: dict[str, Any] = dict(context or {})
        if selector:
            ctx.setdefault("selector", selector)
        if selectors is not None:
            ctx.setdefault("selectors", list(selectors))
        if candidates is not None:
            ctx.setdefault("candidates", candidates)
        ctx.update(details)
        super().__init__(message, platform=platform, stage=stage, context=ctx)
        self.selector = selector
        self.selectors = list(selectors) if selectors is not None else ([selector] if selector else [])
        self.candidates = candidates


class ComposerOpenError(SelectorError):
    """The platform composer could not be opened or made ready for typing."""

    def __init__(
        self,
        message: str = "",
        *,
        platform: str = "",
        stage: str = "composer_open",
        selector: str = "",
        selectors: list[str] | tuple[str, ...] | None = None,
        candidates: int | None = None,
        artifacts: dict[str, str] | None = None,
        context: dict[str, Any] | None = None,
        **details: Any,
    ):
        ctx: dict[str, Any] = dict(context or {})
        if artifacts:
            ctx.setdefault("artifacts", dict(artifacts))
        super().__init__(
            message,
            platform=platform,
            stage=stage,
            selector=selector,
            selectors=selectors,
            candidates=candidates,
            context=ctx,
            **details,
        )
        self.artifacts = dict(artifacts or {})


class VerificationError(AdapterError):
    """A submitted post could not be verified by read-back."""

    def __init__(
        self,
        message: str = "",
        *,
        platform: str = "",
        stage: str = "verification",
        url: str | None = None,
        post_id: str | None = None,
        context: dict[str, Any] | None = None,
        **details: Any,
    ):
        ctx: dict[str, Any] = dict(context or {})
        if url is not None:
            ctx.setdefault("url", url)
        if post_id is not None:
            ctx.setdefault("post_id", post_id)
        ctx.update(details)
        super().__init__(message, platform=platform, stage=stage, context=ctx)
        self.url = url
        self.post_id = post_id


class RateLimitError(AdapterError):
    """A rate-limit decision could not be made safely."""

    def __init__(
        self,
        message: str = "",
        *,
        platform: str = "linkedin",
        stage: str = "rate_limit",
        last_at: str | None = None,
        min_gap_hours: float | None = None,
        context: dict[str, Any] | None = None,
        **details: Any,
    ):
        ctx: dict[str, Any] = dict(context or {})
        if last_at is not None:
            ctx.setdefault("last_at", last_at)
        if min_gap_hours is not None:
            ctx.setdefault("min_gap_hours", min_gap_hours)
        ctx.update(details)
        super().__init__(message, platform=platform, stage=stage, context=ctx)
        self.last_at = last_at
        self.min_gap_hours = min_gap_hours
