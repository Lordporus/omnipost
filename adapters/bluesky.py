"""Bluesky AT Protocol (XRPC) platform adapter for OmniPost.

Communicates directly over ATProto XRPC HTTP endpoints using Python standard library
(urllib) with zero heavy external dependencies.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from adapters.base import (
    PlatformAdapter,
    PlatformCapabilities,
    PublishPayload,
    PublishResult,
)
from scripts import settings

BSKY_PUBLIC_API = "https://bsky.social/xrpc"
URL_REGEX = re.compile(r"https?://[^\s<>\"'()]+")
MENTION_REGEX = re.compile(r"@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")


def extract_facets(text: str) -> list[dict[str, Any]]:
    """Extract RichText facets (links and mentions) using exact UTF-8 byte offsets.
    
    AT Protocol requires UTF-8 byte indices (byteStart, byteEnd) rather than
    Python string character offsets. This correctly handles multi-byte unicode
    characters (emojis, accented characters, devanagari, etc.).
    """
    facets: list[dict[str, Any]] = []
    text_bytes = text.encode("utf-8")

    # 1. URL extraction
    for match in URL_REGEX.finditer(text):
        url = match.group(0)
        # Strip trailing punctuation if accidentally matched
        while url and url[-1] in ".,!?:;":
            url = url[:-1]
        
        char_start = match.start()
        char_end = char_start + len(url)
        byte_start = len(text[:char_start].encode("utf-8"))
        byte_end = len(text[:char_end].encode("utf-8"))

        facets.append({
            "$type": "app.bsky.richtext.facet",
            "index": {
                "byteStart": byte_start,
                "byteEnd": byte_end,
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": url,
            }],
        })

    # 2. Mention extraction
    for match in MENTION_REGEX.finditer(text):
        handle = match.group(1)
        char_start = match.start()
        char_end = match.end()
        byte_start = len(text[:char_start].encode("utf-8"))
        byte_end = len(text[:char_end].encode("utf-8"))

        facets.append({
            "$type": "app.bsky.richtext.facet",
            "index": {
                "byteStart": byte_start,
                "byteEnd": byte_end,
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#mention",
                "did": handle,  # Handled as did/handle in client
            }],
        })

    # Sort facets by byteStart as required by ATProto
    facets.sort(key=lambda f: f["index"]["byteStart"])
    return facets


class BlueskyAdapter(PlatformAdapter):
    """Adapter for Bluesky social platform over native ATProto XRPC endpoints."""

    def __init__(
        self,
        identifier: str | None = None,
        app_password: str | None = None,
        pds_url: str = BSKY_PUBLIC_API,
    ):
        self.pds_url = pds_url.rstrip("/")
        cfg = settings.load()
        bsky_cfg = cfg.get("platforms", {}).get("bluesky", {})

        # Resolve credentials: args > env vars > config.json
        self.identifier = (
            identifier
            or os.environ.get("BSKY_IDENTIFIER")
            or bsky_cfg.get("identifier", "")
        )
        self.app_password = (
            app_password
            or os.environ.get("BSKY_APP_PASSWORD")
            or bsky_cfg.get("app_password", "")
        )

        self._session_cache: dict[str, Any] | None = None

    @property
    def platform_name(self) -> str:
        return "bluesky"

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(
            max_characters=300,
            supports_markdown=False,
            supports_images=True,
            max_images=4,
            supports_pdf_carousel=False,
            requires_public_image_url=False,
        )

    def _request(
        self,
        endpoint: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> dict[str, Any]:
        """Perform HTTP request to ATProto XRPC endpoint."""
        url = f"{self.pds_url}/{endpoint}"
        req_headers = headers.copy() if headers else {}
        if "Content-Type" not in req_headers and data is not None:
            req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(
            url,
            data=data,
            headers=req_headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                resp_bytes = resp.read()
                if not resp_bytes:
                    return {}
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("message", err_body)
            except Exception:
                msg = err_body
            raise RuntimeError(f"XRPC {endpoint} failed ({err.code}): {msg}") from err
        except Exception as exc:
            raise RuntimeError(f"XRPC {endpoint} connection error: {exc}") from exc

    def _ensure_session(self) -> dict[str, Any]:
        """Authenticate or return cached session."""
        if self._session_cache and "accessJwt" in self._session_cache:
            return self._session_cache

        if not self.identifier or not self.app_password:
            raise ValueError(
                "Bluesky credentials missing. Set BSKY_IDENTIFIER and BSKY_APP_PASSWORD "
                "in environment or configure in config.json."
            )

        payload = {
            "identifier": self.identifier,
            "password": self.app_password,
        }
        res = self._request(
            "com.atproto.server.createSession",
            data=json.dumps(payload).encode("utf-8"),
        )
        self._session_cache = res
        return res

    def check_session(self) -> dict[str, Any]:
        """Check whether credentials authenticate cleanly with ATProto."""
        try:
            session = self._ensure_session()
            return {
                "ok": True,
                "platform": "bluesky",
                "handle": session.get("handle"),
                "did": session.get("did"),
                "error": None,
            }
        except Exception as exc:
            return {
                "ok": False,
                "platform": "bluesky",
                "handle": self.identifier or None,
                "did": None,
                "error": str(exc),
            }

    def upload_blob(self, image_path: Path) -> dict[str, Any]:
        """Upload image blob to ATProto repo (com.atproto.repo.uploadBlob)."""
        session = self._ensure_session()
        token = session["accessJwt"]

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found at {image_path}")

        file_bytes = image_path.read_bytes()
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/png"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": mime_type,
        }

        res = self._request(
            "com.atproto.repo.uploadBlob",
            data=file_bytes,
            headers=headers,
            method="POST",
        )
        return res.get("blob", {})

    def publish(self, payload: PublishPayload) -> PublishResult:
        """Publish record to Bluesky feed (app.bsky.feed.post)."""
        try:
            session = self._ensure_session()
            token = session["accessJwt"]
            repo_did = session["did"]

            facets = extract_facets(payload.text)
            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            record: dict[str, Any] = {
                "$type": "app.bsky.feed.post",
                "text": payload.text,
                "createdAt": now_iso,
            }
            if facets:
                record["facets"] = facets

            # Handle media attachments (up to 4 images)
            if payload.media_paths:
                images_data = []
                for img_path in payload.media_paths[:4]:
                    blob = self.upload_blob(img_path)
                    images_data.append({
                        "alt": payload.extra_metadata.get("alt_text", "OmniPost image"),
                        "image": blob,
                    })

                if images_data:
                    record["embed"] = {
                        "$type": "app.bsky.embed.images",
                        "images": images_data,
                    }

            req_body = {
                "repo": repo_did,
                "collection": "app.bsky.feed.post",
                "record": record,
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            res = self._request(
                "com.atproto.repo.createRecord",
                data=json.dumps(req_body).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            uri = res.get("uri", "")  # e.g. at://did:plc:.../app.bsky.feed.post/3k...
            cid = res.get("cid", "")
            rkey = uri.split("/")[-1] if uri else None
            handle = session.get("handle") or self.identifier

            post_url = f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else None

            # Verify presence immediately
            verified = self.verify(rkey, payload.text)

            return PublishResult(
                platform="bluesky",
                success=True,
                post_id=rkey,
                url=post_url,
                verified=verified,
                raw_response={"uri": uri, "cid": cid},
            )
        except Exception as exc:
            return PublishResult(
                platform="bluesky",
                success=False,
                error=str(exc),
            )

    def verify(self, post_id: str | None, text_snippet: str) -> bool:
        """Verify published post via ATProto public getRecord."""
        if not post_id:
            return False
        try:
            session = self._ensure_session()
            repo_did = session.get("did")
            if not repo_did:
                return False

            url = (
                f"{self.pds_url}/com.atproto.repo.getRecord?"
                f"repo={urllib.parse.quote(repo_did)}&"
                f"collection=app.bsky.feed.post&"
                f"rkey={urllib.parse.quote(post_id)}"
            )

            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                val = data.get("value", {})
                return bool(val.get("text"))
        except Exception:
            return False
