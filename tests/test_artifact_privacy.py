"""Privacy and artifact regression tests for failure capture."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from adapters import base
from scripts.errors import SelectorError
from scripts.notify_webhook import dispatch_webhook


class FakePage:
    """Minimal CDP page double for artifact capture."""

    def __init__(
        self,
        html: str = "<html><body>ok</body></html>",
        fail_screenshot: bool = False,
        fail_eval: bool = False,
    ) -> None:
        self.html = html
        self.fail_screenshot = fail_screenshot
        self.fail_eval = fail_eval

    async def send(self, method: str, **kwargs):
        if self.fail_screenshot:
            raise RuntimeError("screenshot unavailable")
        return {"data": "aGVsbG8="}

    async def eval(self, expression: str):
        if self.fail_eval:
            raise RuntimeError("eval unavailable")
        return self.html


def test_artifacts_under_root(tmp_path, monkeypatch):
    shots = tmp_path / "shots"
    monkeypatch.setattr(base, "SHOTS_DIR", shots)

    raw_html = (
        "<html><body>"
        "contact user@example.com "
        "Authorization: Bearer abc123 "
        "<script>var token = 'secret';</script>"
        "</body></html>"
    )
    artifacts = asyncio.run(base.capture_failure_artifacts(FakePage(raw_html), "linkedin"))

    assert Path(artifacts["screenshot"]).parent == shots
    assert Path(artifacts["html"]).parent == shots
    assert Path(artifacts["screenshot"]).is_file()
    assert Path(artifacts["html"]).is_file()

    written = Path(artifacts["html"]).read_text(encoding="utf-8")
    assert "user@example.com" not in written
    assert "Bearer abc123" not in written
    assert "var token" not in written

    # The default writer is rooted at the repository, never the process CWD.
    assert base.ROOT / "shots" == Path(base.__file__).resolve().parent.parent / "shots"
    assert (base.ROOT / "shots").is_absolute()


def test_redacts_email():
    out = base.redact_text("contact user@example.com about the failure")
    assert "user@example.com" not in out
    assert "[REDACTED_EMAIL]" in out


def test_redacts_auth_headers():
    raw = (
        "Authorization: Bearer abc123\n"
        "Cookie: session=deadbeef; csrftoken=abc\n"
        "Set-Cookie: sid=xyz\n"
        "X-CSRF-Token: tok123\n"
        "token=shorttok\n"
    )
    out = base.redact_text(raw)

    for secret in ("abc123", "deadbeef", "csrftoken=abc", "sid=xyz", "tok123", "shorttok"):
        assert secret not in out


def test_redacts_long_secrets():
    token = "a1b2c3d4" * 5  # 40 characters
    out = base.redact_text(f"blob {token} end")
    assert token not in out
    assert "[REDACTED_SECRET]" in out


def test_retention_caps_files(tmp_path, monkeypatch):
    shots = tmp_path / "shots"
    shots.mkdir()
    monkeypatch.setattr(base, "SHOTS_DIR", shots)

    for index in range(25):
        (shots / f"linkedin_{index:02d}.html").write_text("artifact", encoding="utf-8")

    base._enforce_retention("linkedin", keep=20)

    assert len(list(shots.glob("linkedin_*"))) == 20


def test_notification_has_no_raw_dom(monkeypatch):
    captured: dict[str, dict] = {}

    def fake_telegram(**kwargs):
        captured["telegram"] = kwargs
        return True

    def fake_discord(**kwargs):
        captured["discord"] = kwargs
        return True

    monkeypatch.setattr("scripts.notify_webhook._dispatch_telegram", fake_telegram)
    monkeypatch.setattr("scripts.notify_webhook._dispatch_discord", fake_discord)
    monkeypatch.setattr(
        "scripts.notify_webhook._load_webhook_credentials",
        lambda: {
            "telegram": {"token": "test-token", "chat_id": "test-chat"},
            "discord": {"url": "https://example.invalid/hook"},
        },
    )

    summary = "linkedin selector failure; DOM redacted"
    artifact_path = "C:/repo/shots/linkedin_20260101T000000Z.png"
    ok = dispatch_webhook(
        "failure",
        "[LinkedIn] Publishing Failed",
        summary,
        {"platform": "linkedin", "artifact": artifact_path},
    )

    assert ok is True
    blob = repr(captured)
    assert "<html" not in blob.lower()
    assert "<!doctype" not in blob.lower()
    assert artifact_path in blob
    assert summary in blob


def test_capture_failure_does_not_mask(tmp_path, monkeypatch):
    shots = tmp_path / "shots"
    monkeypatch.setattr(base, "SHOTS_DIR", shots)

    page = FakePage(fail_screenshot=True, fail_eval=True)
    original = SelectorError(
        "linkedin selector miss: button.share-box",
        platform="linkedin",
        stage="composer_open",
        selector="button.share-box",
    )

    async def adapter_failure():
        try:
            raise original
        except SelectorError:
            await base.capture_failure_artifacts(page, "linkedin")
            raise

    with pytest.raises(SelectorError) as excinfo:
        asyncio.run(adapter_failure())

    assert excinfo.value is original
