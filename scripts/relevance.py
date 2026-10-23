"""Deterministic relevance gate for OmniPost research items.

The gate is intentionally local and deterministic: it scores the title, summary,
and URL against an engineering taxonomy, rejects obvious general-news items, and
optionally rewards overlap with the operator's voice profile. It never calls an
LLM and never lets a voice match override a blocklist rejection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:  # package import (tests, pipeline)
    from scripts import settings
except ImportError:  # direct script execution
    import settings


DEFAULT_MIN_SCORE = 2

DEFAULT_BLOCKLIST = [
    "politics",
    "election",
    "president",
    "trump",
    "kushner",
    "celebrity",
    "sports",
    "movie",
    "music",
    "crypto price",
    "stock price",
    "weather",
    "crime",
    "war",
]

DEFAULT_TAXONOMY_STRONG = [
    "ai",
    "llm",
    "agent",
    "model",
    "inference",
    "training",
    "transformer",
    "rag",
    "embedding",
    "vector",
    "kubernetes",
    "docker",
    "container",
    "database",
    "postgres",
    "sqlite",
    "distributed",
    "concurrency",
    "latency",
    "throughput",
    "reliability",
    "observability",
    "compiler",
    "rust",
    "python",
    "typescript",
    "api",
    "architecture",
    "state machine",
    "queue",
    "retry",
    "deployment",
    "security",
    "autonomous",
    "workflow",
    "swarm",
    "deterministic",
]

DEFAULT_TAXONOMY_WEAK = [
    "engineering",
    "production",
    "system",
    "scale",
    "performance",
    "design",
    "code",
    "software",
]

# Small stopword set used only to turn a voice profile into topic keywords.
VOICE_STOPWORDS = set(
    """
    a about above after again against all am an and any are as at be because been
    before being below between both but by can could did do does doing down during
    each few for from further had has have having he her here hers herself him
    himself his how i if in into is it its itself just me more most my myself no
    nor not now of off on once only or other our ours ourselves out over own same
    she should so some such than that the their theirs them themselves then there
    these they this those through to too under until up very was we were what when
    where which while who whom why will with would you your yours yourself
    """.split()
)


@dataclass
class RelevanceResult:
    """The outcome of scoring one research item."""

    accepted: bool
    score: int
    reasons: list[str] = field(default_factory=list)
    matched_terms: list[str] = field(default_factory=list)
    voice_alignment: int = 0


def _tokens(text: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _token_matches(token: str, expected: str) -> bool:
    if token == expected:
        return True
    if len(expected) > 3 and token == f"{expected}s":
        return True
    if len(token) > 3 and expected == f"{token}s":
        return True
    return False


def _phrase_in_tokens(tokens: list[str], phrase: str) -> bool:
    phrase_tokens = _tokens(phrase)
    if not phrase_tokens:
        return False
    if len(phrase_tokens) == 1:
        return any(_token_matches(token, phrase_tokens[0]) for token in tokens)
    width = len(phrase_tokens)
    for i in range(len(tokens) - width + 1):
        window = tokens[i : i + width]
        if all(_token_matches(token, expected) for token, expected in zip(window, phrase_tokens)):
            return True
    return False


def _summary_for(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("summary", "description", "content"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    extra = item.get("extra")
    if isinstance(extra, str):
        return extra.strip()
    if isinstance(extra, dict):
        for key in ("summary", "text", "description", "content"):
            value = extra.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _relevance_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is None:
        try:
            raw = settings.load().get("content", {}).get("relevance", {}) or {}
        except Exception:
            raw = {}
    elif isinstance(config, dict):
        if "content" in config and isinstance(config.get("content"), dict):
            raw = config["content"].get("relevance", {}) or {}
        elif "relevance" in config and isinstance(config.get("relevance"), dict):
            raw = config["relevance"] or {}
        else:
            raw = config
    else:
        raw = {}

    def pick_list(key: str, default: list[str]) -> list[str]:
        value = raw.get(key)
        return list(value) if isinstance(value, list) else list(default)

    try:
        min_score = int(raw.get("min_score", DEFAULT_MIN_SCORE))
    except (TypeError, ValueError):
        min_score = DEFAULT_MIN_SCORE

    return {
        "min_score": max(0, min_score),
        "blocklist": pick_list("blocklist", DEFAULT_BLOCKLIST),
        "taxonomy_strong": pick_list("taxonomy_strong", DEFAULT_TAXONOMY_STRONG),
        "taxonomy_weak": pick_list("taxonomy_weak", DEFAULT_TAXONOMY_WEAK),
    }


def _voice_keywords(voice_profile: str | None) -> set[str]:
    if not voice_profile:
        return set()
    return {
        token
        for token in _tokens(voice_profile)
        if len(token) > 2 and token not in VOICE_STOPWORDS
    }


def score_item(
    item: dict[str, Any],
    config: dict[str, Any] | None = None,
    voice_profile: str | None = None,
) -> RelevanceResult:
    """Score one research item against the deterministic relevance gate."""
    cfg = _relevance_config(config)
    title = str(item.get("title") or "") if isinstance(item, dict) else ""
    summary = _summary_for(item) if isinstance(item, dict) else ""
    url = str(item.get("url") or "") if isinstance(item, dict) else ""

    title_summary_tokens = _tokens(f"{title} {summary}")
    scoring_tokens = _tokens(f"{title} {summary} {url}")

    blocked = [
        phrase
        for phrase in cfg["blocklist"]
        if _phrase_in_tokens(title_summary_tokens, phrase)
    ]
    if blocked:
        return RelevanceResult(
            accepted=False,
            score=0,
            reasons=[f"blocklist:{phrase}" for phrase in blocked],
            matched_terms=blocked,
            voice_alignment=0,
        )

    strong = [
        term
        for term in cfg["taxonomy_strong"]
        if _phrase_in_tokens(scoring_tokens, term)
    ]
    weak = [
        term
        for term in cfg["taxonomy_weak"]
        if _phrase_in_tokens(scoring_tokens, term)
    ]
    score = len(strong) + len(weak)

    voice_alignment = 0
    if voice_profile:
        overlap = _voice_keywords(voice_profile) & set(scoring_tokens)
        voice_alignment = min(3, len(overlap))

    reasons: list[str] = []
    accepted = False
    if not strong:
        reasons.append("no_engineering_terms")
    else:
        enough_signal = len(strong) >= 2 or (len(strong) >= 1 and len(weak) >= 2)
        if enough_signal and score >= cfg["min_score"]:
            accepted = True
        else:
            reasons.append("insufficient_relevance")

    reasons.append(f"score:{score}")
    if voice_alignment:
        reasons.append(f"voice:{voice_alignment}")

    matched_terms = sorted(set(strong + weak))
    return RelevanceResult(
        accepted=accepted,
        score=score,
        reasons=reasons,
        matched_terms=matched_terms,
        voice_alignment=voice_alignment,
    )


def score_candidates(
    items: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    voice_profile: str | None = None,
) -> list[tuple[dict[str, Any], RelevanceResult]]:
    """Score every candidate in order, returning item/result pairs."""
    return [
        (item, score_item(item, config=config, voice_profile=voice_profile))
        for item in items
    ]
