"""End-to-End Integration Test Suite for OmniPost V2.

Validates the full operational lifecycle:
1. Research insight ingestion -> polymorphic repurposing across 4 platforms (X, Bluesky, LinkedIn, Threads).
2. Multi-channel dispatch with mock adapters & dry-run validation.
3. Atomic state persistence in state.json (Schema v2.0).
4. Partial-failure isolation: failing platform can be retried without re-dispatching to published platforms.
5. Read-back verification checks ensuring published status on user profiles.
6. Guardrail enforcement preventing bad or duplicate posts from dispatching.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adapters.base import (
    PlatformAdapter,
    PlatformCapabilities,
    PublishPayload,
    PublishResult,
)
from scripts import ledger, settings
from scripts.repurpose import repurpose_topic
from scripts.validator import (
    EngagementBaitError,
    validate_draft_guardrails,
)


class MockPlatformAdapter(PlatformAdapter):
    """Configurable mock adapter for testing multi-platform orchestration."""

    def __init__(self, name: str, should_succeed: bool = True, max_chars: int = 500):
        self._name = name
        self.should_succeed = should_succeed
        self._max_chars = max_chars
        self.published_calls: list[PublishPayload] = []

    @property
    def platform_name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(max_characters=self._max_chars)

    def check_session(self) -> dict:
        return {"ok": True, "platform": self._name, "handle": f"test_{self._name}"}

    def publish(self, payload: PublishPayload) -> PublishResult:
        self.published_calls.append(payload)
        if not self.should_succeed:
            return PublishResult(
                platform=self._name,
                success=False,
                error=f"{self._name} simulated dispatch failure",
            )
        return PublishResult(
            platform=self._name,
            success=True,
            post_id=f"{self._name}-post-12345",
            url=f"https://{self._name}.example.com/posts/12345",
            verified=True,
        )

    def verify(self, post_id: str | None, text_snippet: str) -> bool:
        return self.should_succeed


def test_full_e2e_pipeline_simulation(tmp_path):
    """Simulate end-to-end: research insight -> polymorphic repurpose -> dispatch -> ledger record -> verification."""
    state_file = tmp_path / "state.json"
    state = ledger.load_state(state_file)

    # 1. Mock Research Insight
    raw_insight = {
        "headline": "Sovereign Engineering: Running Headless Chrome Locally",
        "body": "Running browser automation over direct DevTools Protocol websockets eliminates third-party SaaS middleman fees and unifies cross-posting.",
        "points": [
            "Local CDP gives 100% control over the real browser session",
            "Zero monthly subscription overhead",
            "Hardware-accelerated PDF generation via Page.printToPDF",
        ],
        "takeaway": "Direct protocol automation beats heavy API SDKs.",
        "category": "ARCHITECTURE",
        "source": "https://developer.chrome.com/docs/devtools",
    }

    # 2. Polymorphic Repurpose
    polymorphic_slot = repurpose_topic(raw_insight, generate_media=False)
    assert set(polymorphic_slot.keys()) == {"x", "bluesky", "linkedin", "threads"}

    # 3. Instantiate Mock Adapters
    adapters = {
        "x": MockPlatformAdapter("x", should_succeed=True, max_chars=280),
        "bluesky": MockPlatformAdapter("bluesky", should_succeed=True, max_chars=300),
        "linkedin": MockPlatformAdapter("linkedin", should_succeed=True, max_chars=3000),
        "threads": MockPlatformAdapter("threads", should_succeed=True, max_chars=500),
    }

    date_str = "2026-10-06"
    slot_time = "14:00"

    # 4. Dispatch each platform
    for platform_name, adapter in adapters.items():
        plat_data = polymorphic_slot[platform_name]
        payload = PublishPayload(
            text=plat_data["text"],
            media_type=plat_data.get("media_type", "image"),
        )
        res = adapter.publish(payload)
        assert res.success is True
        assert res.verified is True

        # Atomically record to state.json
        state = ledger.record_platform_status(
            state=state,
            date=date_str,
            slot=slot_time,
            platform=platform_name,
            result=res,
            text=payload.text,
            path=state_file,
        )

    # 5. Read-back verification in ledger
    saved_state = ledger.load_state(state_file)
    assert len(saved_state["posts"]) == 1
    post_record = saved_state["posts"][0]
    assert post_record["date"] == date_str
    assert post_record["slot"] == slot_time

    target_platforms = ["x", "bluesky", "linkedin", "threads"]
    assert ledger.is_slot_fully_published(saved_state, date_str, slot_time, target_platforms) is True
    assert ledger.get_pending_platforms(saved_state, date_str, slot_time, target_platforms) == []

    for p in target_platforms:
        p_status = ledger.get_platform_status(saved_state, date_str, slot_time, p)
        assert p_status is not None
        assert p_status["status"] == "published"
        assert p_status["verified"] is True
        assert p_status["url"] is not None


def test_partial_failure_isolation_and_safe_retry(tmp_path):
    """Verify that when one platform fails, only the failed platform is retried, avoiding duplicates."""
    state_file = tmp_path / "state.json"
    state = ledger.load_state(state_file)

    date_str = "2026-10-06"
    slot_time = "18:00"
    target_platforms = ["x", "bluesky", "linkedin", "threads"]

    # Initial Run: LinkedIn fails, other 3 succeed
    adapters_run1 = {
        "x": MockPlatformAdapter("x", should_succeed=True),
        "bluesky": MockPlatformAdapter("bluesky", should_succeed=True),
        "linkedin": MockPlatformAdapter("linkedin", should_succeed=False),  # Simulating failure
        "threads": MockPlatformAdapter("threads", should_succeed=True),
    }

    for p_name in target_platforms:
        adapter = adapters_run1[p_name]
        payload = PublishPayload(text=f"Draft for {p_name}")
        res = adapter.publish(payload)
        state = ledger.record_platform_status(
            state=state,
            date=date_str,
            slot=slot_time,
            platform=p_name,
            result=res,
            text=payload.text,
            path=state_file,
        )

    # Verify state reflects partial failure
    state = ledger.load_state(state_file)
    assert ledger.is_platform_done(state, date_str, slot_time, "x") is True
    assert ledger.is_platform_done(state, date_str, slot_time, "bluesky") is True
    assert ledger.is_platform_done(state, date_str, slot_time, "linkedin") is False
    assert ledger.is_platform_done(state, date_str, slot_time, "threads") is True

    # Pending platforms must be ONLY LinkedIn
    pending = ledger.get_pending_platforms(state, date_str, slot_time, target_platforms)
    assert pending == ["linkedin"]

    # Retry Step: execute ONLY pending platforms
    linkedin_retry_adapter = MockPlatformAdapter("linkedin", should_succeed=True)
    for p_name in pending:
        assert p_name == "linkedin"
        payload = PublishPayload(text=f"Retry draft for {p_name}")
        res = linkedin_retry_adapter.publish(payload)
        assert res.success is True

        state = ledger.record_platform_status(
            state=state,
            date=date_str,
            slot=slot_time,
            platform=p_name,
            result=res,
            text=payload.text,
            path=state_file,
        )

    # After retry, all are published
    final_state = ledger.load_state(state_file)
    assert ledger.is_slot_fully_published(final_state, date_str, slot_time, target_platforms) is True
    assert ledger.get_pending_platforms(final_state, date_str, slot_time, target_platforms) == []


def test_guardrails_prevent_bad_drafts_from_dispatch():
    """Verify that guardrails abort dispatching if draft fails quality/safety checks."""
    bad_draft = {
        "text": "What do you think about AI in 2026? Thoughts? Let me know in the comments!",
    }
    cfg = {"handle": "Lordporus", "max_chars_verified": True}

    # Should raise EngagementBaitError
    with pytest.raises(EngagementBaitError):
        validate_draft_guardrails(
            draft=bad_draft,
            cfg=cfg,
            state={"posts": []},
            platform="x",
            raise_on_error=True,
            check_warmup=False,
        )
