"""Live Credential, Multi-LLM Ping, and Webhook Validation Engine for OmniPost.

Provides zero-external-dependency validation routines using standard Python
library (urllib.request, json) to test platform credentials, LLM API keys,
and webhook notification endpoints before saving configuration.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_TIMEOUT = 8.0
USER_AGENT = "OmniPost-Validator/1.0"


def _extract_error_detail(err_body: str) -> str:
    """Attempt to parse structured error message from JSON error payload."""
    if not err_body:
        return "Unknown error"
    try:
        parsed = json.loads(err_body)
        if isinstance(parsed, dict):
            # Telegram: {"ok": false, "description": "..."}
            if "description" in parsed:
                return str(parsed["description"])
            # OpenAI / Anthropic: {"error": {"message": "..."}} or {"error": "..."}
            err_obj = parsed.get("error")
            if isinstance(err_obj, dict) and "message" in err_obj:
                return str(err_obj["message"])
            if isinstance(err_obj, str):
                return err_obj
            # ATProto / Bluesky / Discord: {"message": "..."}
            if "message" in parsed:
                return str(parsed["message"])
    except Exception:
        pass
    return err_body[:250]


def validate_bluesky_credentials(
    identifier: str,
    app_password: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[bool, str]:
    """Validates Bluesky handle and app password via ATProto server session endpoint."""
    ident = (identifier or "").strip()
    pwd = (app_password or "").strip()

    if not ident or not pwd:
        return False, "Bluesky handle and app password are required."

    url = "https://bsky.social/xrpc/com.atproto.server.createSession"
    payload = json.dumps({"identifier": ident, "password": pwd}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            parsed = json.loads(data.decode("utf-8")) if data else {}
            handle = parsed.get("handle", ident)
            return True, f"Bluesky credentials verified for @{handle}."
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        detail = _extract_error_detail(body)
        return False, f"Bluesky authentication failed ({err.code}): {detail}"
    except Exception as exc:
        return False, f"Bluesky connection error: {exc}"


def validate_llm_key(
    provider: str,
    api_key: str,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[bool, str]:
    """Validates Gemini, OpenAI, Claude, OpenRouter, or Local mode via 1-token / models endpoint."""
    p = (provider or "").strip().lower()
    key = (api_key or "").strip()

    # Local mode or empty provider defaults to zero-cost deterministic synthesis
    if p in ("", "local", "none", "deterministic"):
        return True, "Zero-cost local deterministic synthesis mode enabled."

    if not key:
        return False, f"API key is required for provider '{provider}'."

    headers: dict[str, str] = {
        "User-Agent": USER_AGENT,
    }

    if p == "gemini":
        display = "Gemini"
        encoded_key = urllib.parse.quote(key)
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={encoded_key}"
        req = urllib.request.Request(url, headers=headers, method="GET")

    elif p == "openai":
        display = "OpenAI"
        url = "https://api.openai.com/v1/models"
        headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(url, headers=headers, method="GET")

    elif p in ("claude", "anthropic"):
        display = "Claude"
        url = "https://api.anthropic.com/v1/models"
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
        req = urllib.request.Request(url, headers=headers, method="GET")

    elif p == "openrouter":
        display = "OpenRouter"
        url = "https://openrouter.ai/api/v1/auth/key"
        headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(url, headers=headers, method="GET")

    else:
        return False, f"Unsupported LLM provider: '{provider}'."

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            _ = resp.read()
            return True, f"{display} API key verified successfully."
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        detail = _extract_error_detail(body)
        return False, f"{display} API validation failed ({err.code}): {detail}"
    except Exception as exc:
        return False, f"{display} network error: {exc}"


def validate_webhook(
    service: str,
    url_or_token: str,
    chat_id: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[bool, str]:
    """Sends a minimal non-intrusive test message to Telegram or Discord."""
    svc = (service or "").strip().lower()
    val = (url_or_token or "").strip()

    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }

    if svc == "telegram":
        if not val:
            return False, "Telegram bot token is required."
        if not chat_id or not str(chat_id).strip():
            return False, "Telegram chat_id is required."

        target_chat_id = str(chat_id).strip()
        url = f"https://api.telegram.org/bot{val}/sendMessage"
        payload = json.dumps({
            "chat_id": target_chat_id,
            "text": "🤖 OmniPost webhook test notification.",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                parsed = json.loads(data.decode("utf-8")) if data else {}
                if parsed.get("ok"):
                    return True, "Telegram webhook verified successfully."
                desc = parsed.get("description", "Unknown Telegram error")
                return False, f"Telegram validation failed: {desc}"
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            detail = _extract_error_detail(body)
            return False, f"Telegram validation failed ({err.code}): {detail}"
        except Exception as exc:
            return False, f"Telegram connection error: {exc}"

    elif svc == "discord":
        if not val or not (val.startswith("http://") or val.startswith("https://")):
            return False, "A valid Discord webhook URL is required."

        payload = json.dumps({
            "content": "🤖 OmniPost webhook test notification.",
        }).encode("utf-8")
        req = urllib.request.Request(val, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _ = resp.read()
                # Discord returns 204 No Content or 200 on success
                return True, "Discord webhook verified successfully."
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", errors="replace")
            detail = _extract_error_detail(body)
            return False, f"Discord webhook validation failed ({err.code}): {detail}"
        except Exception as exc:
            return False, f"Discord webhook error: {exc}"

    else:
        return False, f"Unsupported webhook service: '{service}'."


def main() -> None:
    """CLI entrypoint for testing credentials interactively."""
    parser = argparse.ArgumentParser(description="OmniPost Credential & Webhook Validator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bsky_p = subparsers.add_parser("bluesky", help="Validate Bluesky credentials")
    bsky_p.add_argument("identifier", help="Handle or DID")
    bsky_p.add_argument("password", help="App password")

    llm_p = subparsers.add_parser("llm", help="Validate LLM API key")
    llm_p.add_argument("provider", help="gemini, openai, claude, openrouter, or local")
    llm_p.add_argument("api_key", nargs="?", default="", help="API key")

    wh_p = subparsers.add_parser("webhook", help="Validate webhook notification")
    wh_p.add_argument("service", choices=["telegram", "discord"], help="Service name")
    wh_p.add_argument("target", help="Webhook URL or Telegram bot token")
    wh_p.add_argument("--chat-id", default=None, help="Telegram chat ID")

    args = parser.parse_args()

    if args.command == "bluesky":
        ok, msg = validate_bluesky_credentials(args.identifier, args.password)
    elif args.command == "llm":
        ok, msg = validate_llm_key(args.provider, args.api_key)
    elif args.command == "webhook":
        ok, msg = validate_webhook(args.service, args.target, chat_id=args.chat_id)
    else:
        ok, msg = False, "Unknown command"

    status = "SUCCESS" if ok else "FAILURE"
    print(f"[{status}] {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
