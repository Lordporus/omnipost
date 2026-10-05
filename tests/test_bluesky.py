"""Unit tests for BlueskyAdapter facet calculations and ATProto XRPC interactions."""
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error

from adapters.base import PublishPayload
from adapters.bluesky import BlueskyAdapter, extract_facets


class TestBlueskyFacets(unittest.TestCase):
    """Test suite for ATProto rich text facet extraction."""

    def test_single_url_facet(self):
        text = "Visit https://omnipost.dev for details"
        facets = extract_facets(text)
        self.assertEqual(len(facets), 1)
        f = facets[0]
        self.assertEqual(f["$type"], "app.bsky.richtext.facet")
        self.assertEqual(f["features"][0]["$type"], "app.bsky.richtext.facet#link")
        self.assertEqual(f["features"][0]["uri"], "https://omnipost.dev")
        self.assertEqual(f["index"]["byteStart"], 6)
        self.assertEqual(f["index"]["byteEnd"], 26)

    def test_unicode_and_emojis_byte_slices(self):
        # 🚀 is 4 bytes in UTF-8
        text = "🚀 Launching https://example.com now!"
        facets = extract_facets(text)
        self.assertEqual(len(facets), 1)
        f = facets[0]
        # "🚀 " is 4 + 1 = 5 bytes
        # "Launching " is 10 bytes -> start at 15
        expected_start = len("🚀 Launching ".encode("utf-8"))
        expected_end = len("🚀 Launching https://example.com".encode("utf-8"))
        self.assertEqual(f["index"]["byteStart"], expected_start)
        self.assertEqual(f["index"]["byteEnd"], expected_end)

    def test_trailing_punctuation_in_url(self):
        text = "Check out https://github.com/Lordporus/omnipost. Cool, right?"
        facets = extract_facets(text)
        self.assertEqual(len(facets), 1)
        self.assertEqual(facets[0]["features"][0]["uri"], "https://github.com/Lordporus/omnipost")

    def test_mention_facet(self):
        text = "Hello @lordporus.bsky.social welcome!"
        facets = extract_facets(text)
        self.assertEqual(len(facets), 1)
        f = facets[0]
        self.assertEqual(f["features"][0]["$type"], "app.bsky.richtext.facet#mention")
        self.assertEqual(f["features"][0]["did"], "lordporus.bsky.social")


class TestBlueskyAdapter(unittest.TestCase):
    """Test suite for BlueskyAdapter auth and record creation."""

    def setUp(self):
        self.adapter = BlueskyAdapter(
            identifier="test.bsky.social",
            app_password="test-app-password-123",
        )

    def test_capabilities(self):
        caps = self.adapter.capabilities
        self.assertEqual(caps.max_characters, 300)
        self.assertTrue(caps.supports_images)
        self.assertEqual(caps.max_images, 4)

    @patch("adapters.bluesky.urllib.request.urlopen")
    def test_check_session_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "accessJwt": "jwt.test.token",
            "handle": "test.bsky.social",
            "did": "did:plc:12345678",
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = self.adapter.check_session()
        self.assertTrue(res["ok"])
        self.assertEqual(res["handle"], "test.bsky.social")
        self.assertEqual(res["did"], "did:plc:12345678")

    @patch("adapters.bluesky.urllib.request.urlopen")
    def test_check_session_failure(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://bsky.social/xrpc/com.atproto.server.createSession",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=MagicMock(read=lambda: b'{"message": "Invalid identifier or password"}'),
        )
        res = self.adapter.check_session()
        self.assertFalse(res["ok"])
        self.assertIn("Invalid identifier or password", res["error"])

    @patch.object(BlueskyAdapter, "_ensure_session")
    @patch.object(BlueskyAdapter, "_request")
    @patch.object(BlueskyAdapter, "verify")
    def test_publish_text_success(self, mock_verify, mock_request, mock_session):
        mock_session.return_value = {
            "accessJwt": "fake_jwt",
            "did": "did:plc:9999",
            "handle": "test.bsky.social",
        }
        mock_request.return_value = {
            "uri": "at://did:plc:9999/app.bsky.feed.post/3kxyz123",
            "cid": "bafyreitest123",
        }
        mock_verify.return_value = True

        payload = PublishPayload(text="Automated test post from OmniPost V2")
        result = self.adapter.publish(payload)

        self.assertEqual(result.platform, "bluesky")
        self.assertTrue(result.success)
        self.assertEqual(result.post_id, "3kxyz123")
        self.assertEqual(result.url, "https://bsky.app/profile/test.bsky.social/post/3kxyz123")
        self.assertTrue(result.verified)

    @patch.object(BlueskyAdapter, "_ensure_session")
    @patch.object(BlueskyAdapter, "upload_blob")
    @patch.object(BlueskyAdapter, "_request")
    @patch.object(BlueskyAdapter, "verify")
    def test_publish_with_image(self, mock_verify, mock_request, mock_upload_blob, mock_session):
        mock_session.return_value = {
            "accessJwt": "fake_jwt",
            "did": "did:plc:9999",
            "handle": "test.bsky.social",
        }
        mock_upload_blob.return_value = {
            "$type": "blob",
            "ref": {"$link": "cid123"},
            "mimeType": "image/png",
            "size": 5000,
        }
        mock_request.return_value = {
            "uri": "at://did:plc:9999/app.bsky.feed.post/3kxyz999",
            "cid": "bafyreiblobpost",
        }
        mock_verify.return_value = True

        dummy_img = Path("shots/sample.png")
        payload = PublishPayload(
            text="Post with attached image",
            media_paths=[dummy_img],
            extra_metadata={"alt_text": "Sample graph"},
        )
        result = self.adapter.publish(payload)

        self.assertTrue(result.success)
        mock_upload_blob.assert_called_once_with(dummy_img)


if __name__ == "__main__":
    unittest.main()
