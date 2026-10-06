"""Live Credential, Multi-LLM Ping, and Webhook Validation Engine for OmniPost.

Provides zero-external-dependency validation routines using standard Python
library (urllib.request, json) to test platform credentials, LLM API keys,
and webhook notification endpoints before saving configuration.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
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


# ------------------------------------------------------------------ Guard Rails
class GuardRailError(Exception):
    """Base exception for all publishing guard rail violations."""
    pass


class CharacterLimitNotMeasuredError(GuardRailError):
    """Raised when posting or queuing without an empirically measured character limit."""
    pass


class EngagementBaitError(GuardRailError):
    """Raised when draft text matches forbidden engagement bait patterns."""
    pass


class FabricatedClaimError(GuardRailError):
    """Raised when claims or citations do not trace to verified research sources."""
    pass


class DuplicatePostError(GuardRailError):
    """Raised when text has already been published in ledger history."""
    pass


class HandleMismatchError(GuardRailError):
    """Raised when session handle does not match configured target handle."""
    pass


class AccountWarmupError(GuardRailError):
    """Raised when excessive post volume is attempted during account warmup period."""
    pass


ENGAGEMENT_BAIT_PATTERNS = [
    r"\b(what do you think|what are your thoughts)",
    r"\b(agree\?|do you agree|\bagree\?)",
    r"\b(like if you|retweet if you|rt if you)",
    r"\b(comment below|drop a comment|leave a comment)",
    r"\b(follow for more|follow me for more)",
    r"\b(share this post|repost this|retweet this)",
    r"\b(save this for later|bookmark this)",
    r"\b(let me know in the comments)",
    r"\bthoughts\?",
    r"\bsmash that like",
    r"type ['\"][a-z]+['\"] below",
]



def engagement_bait_pattern_detected(text: str) -> tuple[bool, str]:
    """Detects engagement bait phrases forbidden by platform spam algorithms."""
    if not text:
        return False, ""
    lowered = text.lower()
    for pat in ENGAGEMENT_BAIT_PATTERNS:
        m = re.search(pat, lowered, flags=re.IGNORECASE)
        if m:
            return True, f"Forbidden engagement bait pattern detected: '{m.group(0)}'"
    return False, ""


def verify_character_ceiling_measured(
    platform: str = "x",
    cfg: dict | None = None,
    state: dict | None = None,
) -> bool:
    """Verifies that the platform character ceiling was empirically measured."""
    p = (platform or "x").lower()
    # Non-X platforms have fixed protocol maximums (Bluesky 300, LinkedIn 3000, Threads 500)
    if p != "x":
        return True

    c = cfg or {}
    st = state or {}

    # Check state first (written by post.py measure --save)
    if st.get("verified_character_ceiling") or st.get("max_chars_verified"):
        return True

    # Check top-level config
    if c.get("max_chars_verified"):
        return True

    # Check platform-specific config
    plat_cfg = c.get("platforms", {}).get("x", {})
    if plat_cfg.get("max_chars_verified"):
        return True

    # Fall back to settings module check if available
    try:
        from scripts import settings
        lim = settings.limit(c)
        if lim.get("verified"):
            return True
    except Exception:
        pass

    return False


def _normalize_text_for_comparison(text: str) -> str:
    """Normalizes text for duplicate content detection."""
    if not text:
        return ""
    # Strip URLs
    no_urls = re.sub(r"https?://\S+", "", text)
    # Lowercase and remove punctuation/special characters
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", no_urls.lower())
    # Collapse whitespace
    return re.sub(r"\s+", " ", cleaned).strip()


def check_duplicate_post(
    text: str,
    state: dict | None = None,
) -> tuple[bool, str]:
    """Checks whether the text (or near-identical normalized text) has already been published."""
    norm_candidate = _normalize_text_for_comparison(text)
    if len(norm_candidate) < 15:
        return False, ""

    st = state or {}
    posts = st.get("posts", [])
    for entry in posts:
        # Check top-level text
        hist_text = entry.get("text", "")
        if hist_text and _normalize_text_for_comparison(hist_text) == norm_candidate:
            date_str = entry.get("at") or entry.get("date") or "history"
            return True, f"Duplicate content: matches previous post from {date_str}"

        # Check polymorphic platforms text
        platforms = entry.get("platforms", {})
        for plat_name, p_data in platforms.items():
            if isinstance(p_data, dict):
                p_text = p_data.get("text", "")
                if p_text and _normalize_text_for_comparison(p_text) == norm_candidate:
                    date_str = p_data.get("at") or entry.get("date") or "history"
                    return True, f"Duplicate content: matches previous {plat_name} post from {date_str}"

    return False, ""


def verify_source_trace(
    draft: dict,
    swipe_dir: Path | None = None,
) -> tuple[bool, str]:
    """Hard Rule 3b: Read Before You Write. Verifies claims trace to scraped sources."""
    if not isinstance(draft, dict):
        return True, ""

    # If the draft explicitly flags an unverified claim, reject immediately
    if draft.get("unverified_claims"):
        return False, "Post contains unverified claim. Drop it."

    source_url = draft.get("source_url") or draft.get("source")
    # If source_url is given, verify it exists in swipe records if swipe_dir exists
    if source_url and swipe_dir and swipe_dir.exists():
        found = False
        for p in swipe_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                for it in data.get("items", []):
                    if it.get("url") == source_url or it.get("source") == source_url:
                        found = True
                        break
                if found:
                    break
            except Exception:
                continue
        if not found:
            return False, f"Source URL '{source_url}' does not trace to any scraped research in {swipe_dir}."

    return True, "Source verified"


def check_account_warmup(
    state: dict | None = None,
    max_posts_per_day: int = 1,
) -> tuple[bool, str]:
    """Ensures new accounts don't trigger platform spam filters by posting too fast."""
    st = state or {}
    posts = st.get("posts", [])
    total_posts = len(posts)

    if total_posts >= 15:
        return True, "Account warm-up complete (>15 posts)."

    # Count verified posts today (UTC)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = 0
    for p in posts:
        at_val = p.get("at") or p.get("date") or ""
        if at_val.startswith(today_str):
            today_count += 1

    if today_count >= max_posts_per_day:
        return (
            False,
            f"Account in warm-up period ({total_posts}/15 total posts). "
            f"Already published {today_count} post(s) today. Capped at {max_posts_per_day}/day.",
        )

    return True, f"Warm-up active: {today_count}/{max_posts_per_day} posts today."


def validate_draft_guardrails(
    draft: dict | str,
    cfg: dict | None = None,
    state: dict | None = None,
    platform: str = "x",
    raise_on_error: bool = True,
    swipe_dir: Path | None = None,
    check_warmup: bool = False,
) -> tuple[bool, list[str]]:
    """Runs all enforcement-first guard rail checks on a candidate post draft."""
    errors: list[str] = []

    # 1. Extract text
    if isinstance(draft, str):
        text = draft
        draft_dict = {"text": draft}
    else:
        draft_dict = draft or {}
        # Try platform-specific text or root text
        plat_dict = draft_dict.get("platforms", {}).get(platform, {})
        text = (
            plat_dict.get("text")
            if isinstance(plat_dict, dict) and plat_dict.get("text")
            else draft_dict.get("text", "")
        )

    text = (text or "").strip()
    if not text:
        errors.append("Draft text is empty.")
        if raise_on_error:
            raise GuardRailError("Draft text is empty.")
        return False, errors

    # 2. Character ceiling measured
    if not verify_character_ceiling_measured(platform, cfg, state):
        msg = f"Character limit not measured for platform '{platform}'. Run post.py measure --save first."
        errors.append(msg)
        if raise_on_error:
            raise CharacterLimitNotMeasuredError(msg)

    # 3. Text length vs measured limit
    max_c = 280
    if cfg:
        try:
            from scripts import settings
            max_c = settings.limit(cfg)["chars"]
        except Exception:
            max_c = cfg.get("max_chars", 280)
    if len(text) > max_c:
        msg = f"Draft length ({len(text)} chars) exceeds measured limit ({max_c} chars)."
        errors.append(msg)
        if raise_on_error:
            raise GuardRailError(msg)

    # 4. Engagement bait detection
    has_bait, bait_msg = engagement_bait_pattern_detected(text)
    if has_bait:
        errors.append(bait_msg)
        if raise_on_error:
            raise EngagementBaitError(f"{bait_msg} No engagement bait: platforms rank these as spam.")

    # 5. Duplicate post check
    is_dup, dup_msg = check_duplicate_post(text, state)
    if is_dup:
        errors.append(dup_msg)
        if raise_on_error:
            raise DuplicatePostError(dup_msg)

    # 6. Source trace check
    has_trace, trace_msg = verify_source_trace(draft_dict, swipe_dir)
    if not has_trace:
        errors.append(trace_msg)
        if raise_on_error:
            raise FabricatedClaimError(trace_msg)

    # 7. Account warm-up check (optional or during live dispatch)
    if check_warmup:
        warm_ok, warm_msg = check_account_warmup(state)
        if not warm_ok:
            errors.append(warm_msg)
            if raise_on_error:
                raise AccountWarmupError(warm_msg)

    if errors:
        return False, errors
    return True, []


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
