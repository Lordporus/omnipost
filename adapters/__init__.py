"""OmniPost platform adapters package."""
from adapters.base import (
    PlatformAdapter,
    PlatformCapabilities,
    PublishPayload,
    PublishResult,
)

from adapters.linkedin import LinkedInAdapter
from adapters.x import XAdapter
from adapters.bluesky import BlueskyAdapter

__all__ = [
    "PlatformAdapter",
    "PlatformCapabilities",
    "PublishPayload",
    "PublishResult",
    "XAdapter",
    "BlueskyAdapter",
    "LinkedInAdapter",
]
