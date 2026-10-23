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


class StateError(Exception):
    """Base class for publish-state failures."""


class StateCorruptionError(StateError):
    """state.json is unreadable and no valid backup could be restored."""


class StateLockTimeout(StateError):
    """The cross-process state lock could not be acquired before the timeout."""
