"""Unit tests for OmniPost platform adapter contracts and XAdapter."""
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from adapters.base import (
    PlatformAdapter,
    PlatformCapabilities,
    PublishPayload,
    PublishResult,
)
from adapters.x import XAdapter


class MockIncompleteAdapter(PlatformAdapter):
    """Subclass that deliberately fails to implement abstract methods."""
    pass


class MockCompleteAdapter(PlatformAdapter):
    """Subclass properly implementing all abstract methods."""

    @property
    def platform_name(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(max_characters=500, supports_markdown=True)

    def check_session(self) -> dict:
        return {"ok": True, "account": "mock_user"}

    def publish(self, payload: PublishPayload) -> PublishResult:
        return PublishResult(platform="mock", success=True, post_id="123")

    def verify(self, post_id: str | None, text_snippet: str) -> bool:
        return True


class TestAdapterContracts(unittest.TestCase):
    """Test suite for adapter ABC and dataclass contracts."""

    def test_abstract_class_cannot_be_instantiated_directly(self):
        with self.assertRaises(TypeError):
            PlatformAdapter()

    def test_incomplete_subclass_raises_type_error(self):
        with self.assertRaises(TypeError):
            MockIncompleteAdapter()

    def test_complete_subclass_instantiation(self):
        adapter = MockCompleteAdapter()
        self.assertEqual(adapter.platform_name, "mock")
        self.assertEqual(adapter.capabilities.max_characters, 500)
        self.assertTrue(adapter.capabilities.supports_markdown)
        self.assertTrue(adapter.check_session()["ok"])

    def test_publish_payload_defaults(self):
        payload = PublishPayload(text="Hello world")
        self.assertEqual(payload.text, "Hello world")
        self.assertEqual(payload.media_paths, [])
        self.assertEqual(payload.media_type, "image")
        self.assertEqual(payload.extra_metadata, {})

    def test_publish_payload_with_media(self):
        dummy_path = Path("/tmp/test.png")
        payload = PublishPayload(text="With media", media_paths=[dummy_path], media_type="image")
        self.assertEqual(payload.media_paths, [dummy_path])

    def test_publish_result_fields(self):
        res = PublishResult(
            platform="test",
            success=True,
            post_id="post_001",
            url="https://example.com/post_001",
            verified=True,
        )
        self.assertEqual(res.platform, "test")
        self.assertTrue(res.success)
        self.assertEqual(res.post_id, "post_001")
        self.assertEqual(res.url, "https://example.com/post_001")
        self.assertTrue(res.verified)
        self.assertIsNone(res.error)


class TestXAdapter(unittest.TestCase):
    """Test suite for XAdapter implementation."""

    def setUp(self):
        self.adapter = XAdapter(port=9444)

    def test_x_adapter_properties(self):
        self.assertEqual(self.adapter.platform_name, "x")
        self.assertIsInstance(self.adapter.capabilities, PlatformCapabilities)
        self.assertGreaterEqual(self.adapter.capabilities.max_characters, 280)
        self.assertTrue(self.adapter.capabilities.supports_images)
        self.assertEqual(self.adapter.capabilities.max_images, 4)

    @patch("scripts.post.session_info")
    def test_x_adapter_check_session_success(self, mock_session):
        async def fake_session():
            return {"handle": "OmniPostHQ", "tier": "free"}
        mock_session.side_effect = fake_session
        res = self.adapter.check_session()
        self.assertTrue(res["ok"])
        self.assertEqual(res["handle"], "OmniPostHQ")
        self.assertEqual(res["platform"], "x")

    @patch("scripts.post.session_info")
    def test_x_adapter_check_session_failure(self, mock_session):
        async def fake_session():
            return {"handle": None}
        mock_session.side_effect = fake_session
        res = self.adapter.check_session()
        self.assertFalse(res["ok"])
        self.assertIsNotNone(res["error"])

    @patch("scripts.post.do_post")
    def test_x_adapter_publish_delegates_to_do_post(self, mock_do_post):
        async def fake_do_post(text, image=None, **kwargs):
            return {
                "posted": True,
                "tweet_url": "https://x.com/OmniPostHQ/status/123456",
                "verified": True,
                "error": None,
            }
        mock_do_post.side_effect = fake_do_post
        payload = PublishPayload(text="Test automated post")
        res = self.adapter.publish(payload)

        self.assertEqual(res.platform, "x")
        self.assertTrue(res.success)
        self.assertEqual(res.url, "https://x.com/OmniPostHQ/status/123456")
        self.assertTrue(res.verified)
        mock_do_post.assert_called_once_with(text="Test automated post", image=None)

    @patch("scripts.post._read_profile")
    def test_x_adapter_verify_delegates(self, mock_read):
        async def fake_read_profile():
            return [{"text": "Test automated post"}]
        mock_read.side_effect = fake_read_profile
        self.assertTrue(self.adapter.verify(None, "Test automated post"))
        mock_read.assert_called_once()


if __name__ == "__main__":
    unittest.main()
