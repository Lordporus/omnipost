"""Unit tests for OmniPost Hard Rules and Enforcement-First Guard Rails."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scripts.validator import (
    GuardRailError,
    CharacterLimitNotMeasuredError,
    EngagementBaitError,
    FabricatedClaimError,
    DuplicatePostError,
    HandleMismatchError,
    AccountWarmupError,
    HumanityGateError,
    HUMANITY_THRESHOLD,
    score_humanity,
    engagement_bait_pattern_detected,
    verify_character_ceiling_measured,
    check_duplicate_post,
    verify_source_trace,
    check_account_warmup,
    validate_draft_guardrails,
)


class TestGuardRails(unittest.TestCase):
    """Test suite verifying strict enforcement of all 6 OmniPost Hard Rules."""

    def test_engagement_bait_detection_positive(self):
        bait_samples = [
            "AI agents are taking over software engineering. What do you think?",
            "Autonomous browser automation is the future. Agree?",
            "Like if you are building in public with Claude!",
            "Drop a comment below with your favorite LLM stack.",
            "I wrote a comprehensive breakdown of CDP protocol. Thoughts?",
            "Follow for more updates on autonomous publishing.",
            "Retweet if you agree with this take.",
            "Save this for later before you deploy your next agent.",
        ]
        for sample in bait_samples:
            detected, msg = engagement_bait_pattern_detected(sample)
            self.assertTrue(detected, f"Failed to detect bait in: {sample}")
            self.assertIn("Forbidden engagement bait", msg)

    def test_engagement_bait_detection_negative(self):
        clean_samples = [
            "We measured CDP latency on Chromium v122: 45ms average event dispatch.",
            "PostgreSQL 16 logical replication slots now support failover replication.",
            "Building zero-dependency Python tools: websockets directly to DevTools protocol.",
            "The release candidate is published to PyPI under v2.1.0.",
        ]
        for sample in clean_samples:
            detected, _ = engagement_bait_pattern_detected(sample)
            self.assertFalse(detected, f"False positive bait detected in: {sample}")

    def test_character_limit_unmeasured_raises(self):
        unmeasured_cfg = {"max_chars": 280, "max_chars_verified": False}
        unmeasured_state = {"posts": [], "verified_character_ceiling": None}

        # Should return False
        self.assertFalse(verify_character_ceiling_measured("x", unmeasured_cfg, unmeasured_state))

        # validate_draft_guardrails should raise CharacterLimitNotMeasuredError
        with self.assertRaises(CharacterLimitNotMeasuredError):
            validate_draft_guardrails(
                draft={"text": "Clean test post that would otherwise pass."},
                cfg=unmeasured_cfg,
                state=unmeasured_state,
                platform="x",
                raise_on_error=True,
            )

    def test_character_limit_measured_passes(self):
        measured_cfg = {"max_chars": 280, "max_chars_verified": True}
        measured_state = {"posts": []}

        self.assertTrue(verify_character_ceiling_measured("x", measured_cfg, measured_state))

        ok, errors = validate_draft_guardrails(
            draft={"text": "Clean test post with measured ceiling."},
            cfg=measured_cfg,
            state=measured_state,
            platform="x",
            raise_on_error=True,
        )
        self.assertTrue(ok)
        self.assertEqual(errors, [])

    def test_duplicate_post_detection(self):
        state = {
            "posts": [
                {
                    "date": "2026-10-01",
                    "at": "2026-10-01T12:00:00Z",
                    "text": "Chrome DevTools Protocol enables direct socket manipulation without Selenium.",
                }
            ]
        }

        # Exact match
        is_dup, msg = check_duplicate_post(
            "Chrome DevTools Protocol enables direct socket manipulation without Selenium.",
            state,
        )
        self.assertTrue(is_dup)
        self.assertIn("Duplicate content", msg)

        # Normalized match (different casing, trailing punct, extra spacing)
        is_dup, msg = check_duplicate_post(
            "  chrome devtools protocol enables direct socket manipulation without selenium!  ",
            state,
        )
        self.assertTrue(is_dup)

        # Unique text passes
        is_dup, _ = check_duplicate_post(
            "Completely novel insight about SQLite WAL mode concurrency.",
            state,
        )
        self.assertFalse(is_dup)

    def test_duplicate_post_raises(self):
        cfg = {"max_chars_verified": True}
        state = {
            "posts": [
                {
                    "date": "2026-10-01",
                    "text": "Existing post already in the immutable ledger.",
                }
            ]
        }
        with self.assertRaises(DuplicatePostError):
            validate_draft_guardrails(
                draft={"text": "Existing post already in the immutable ledger."},
                cfg=cfg,
                state=state,
                platform="x",
                raise_on_error=True,
            )

    def test_engagement_bait_raises(self):
        cfg = {"max_chars_verified": True}
        state = {"posts": []}
        with self.assertRaises(EngagementBaitError):
            validate_draft_guardrails(
                draft={"text": "New Python async framework released. Agree?"},
                cfg=cfg,
                state=state,
                platform="x",
                raise_on_error=True,
            )

    def test_account_warmup_enforcement(self):
        # State with only 3 posts, 1 already published today
        state_warmup = {
            "posts": [
                {"at": "2026-10-05T10:00:00Z", "text": "Post 1"},
                {"at": "2026-10-05T14:00:00Z", "text": "Post 2"},
                # Simulate today's post
                {"at": "2026-10-06T12:00:00Z", "text": "Post 3 today"},
            ]
        }

        with patch("scripts.validator.datetime") as mock_dt:
            from datetime import datetime, timezone
            mock_dt.now.return_value = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            ok, msg = check_account_warmup(state_warmup, max_posts_per_day=1)
            self.assertFalse(ok)
            self.assertIn("warm-up period", msg)

            cfg = {"max_chars_verified": True}
            with self.assertRaises(AccountWarmupError):
                validate_draft_guardrails(
                    draft={"text": "Trying to post a second time today during warmup."},
                    cfg=cfg,
                    state=state_warmup,
                    platform="x",
                    raise_on_error=True,
                    check_warmup=True,
                )

    def test_source_trace_verification(self):
        # Explicit unverified claim fails
        draft_unverified = {
            "text": "99% of developers use Python now.",
            "unverified_claims": True,
        }
        with self.assertRaises(FabricatedClaimError):
            validate_draft_guardrails(
                draft=draft_unverified,
                cfg={"max_chars_verified": True},
                state={"posts": []},
                platform="x",
                raise_on_error=True,
            )

    def test_handle_mismatch_guard_in_post_py(self):
        from scripts.post import require_session

        with patch("scripts.post.asyncio.run") as mock_asyncio_run, patch("scripts.post.session_info"):
            mock_asyncio_run.return_value = {"logged_in": True, "handle": "wrong_user"}
            with self.assertRaises(HandleMismatchError):
                require_session(expect="target_user")


SLOP_SAMPLE = (
    "In today's fast-paced world, we must delve into the tapestry of innovation. "
    "It's not just a game-changer, it's a testament to seamless collaboration. "
    "Let us leverage this robust framework to unlock unprecedented growth, synergy, and transformation."
)

HUMAN_SAMPLE = (
    "We cut the publish path from 11 seconds to 3. "
    "The fix was boring: one Postgres index on the ledger table. "
    "No rewrite. No new service."
)


class TestHumanityGate(unittest.TestCase):
    """Task 3/4: measurable AI tells, and the fail-closed / fail-open policy."""

    def test_slop_sample_scores_below_threshold(self):
        score, violations = score_humanity(SLOP_SAMPLE)
        self.assertLess(score, HUMANITY_THRESHOLD)
        self.assertTrue(violations)

    def test_human_sample_passes(self):
        score, violations = score_humanity(HUMAN_SAMPLE)
        self.assertGreaterEqual(score, HUMANITY_THRESHOLD)
        self.assertEqual(violations, [])

    def test_banned_phrase_is_a_violation(self):
        score, violations = score_humanity(
            "We leverage the platform every day. It ships fast."
        )
        self.assertLess(score, 100)
        self.assertTrue(any("leverage" in v for v in violations))

    def test_em_dash_density_is_a_violation(self):
        text = " ".join(["Ship it — then check it"] * 12)
        _, violations = score_humanity(text)
        self.assertTrue(any("Em-dash" in v for v in violations))

    def test_missing_short_sentence_is_a_violation(self):
        text = (
            "This sentence has more than eight words in it. "
            "This one also has more than eight words."
        )
        _, violations = score_humanity(text)
        self.assertTrue(any("rhythm" in v for v in violations))

    def test_hashtag_and_emoji_are_violations(self):
        _, violations = score_humanity("Shipped 3 fixes today 🚀🔥 #buildinpublic")
        self.assertTrue(any("Hashtag" in v for v in violations))
        self.assertTrue(any("emoji" in v for v in violations))

    def test_missing_concrete_token_is_a_violation(self):
        _, violations = score_humanity("Short. Very short. Nothing concrete here at all.")
        self.assertTrue(any("concrete token" in v for v in violations))

    def test_abstract_tricolon_is_a_violation(self):
        _, violations = score_humanity("We chase innovation, synergy, and growth. Short line.")
        self.assertTrue(any("tricolon" in v for v in violations))

    def test_gate_fails_closed_on_low_score(self):
        with self.assertRaises(HumanityGateError):
            validate_draft_guardrails(
                {"text": SLOP_SAMPLE[:270]}, platform="bluesky", raise_on_error=True
            )

    def test_gate_fails_open_when_scorer_breaks(self):
        with patch("scripts.validator.score_humanity", side_effect=RuntimeError("boom")):
            ok, errors = validate_draft_guardrails(
                {"text": HUMAN_SAMPLE}, platform="bluesky", raise_on_error=True
            )
        self.assertTrue(ok)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
