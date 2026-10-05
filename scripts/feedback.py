#!/usr/bin/env python
"""Closed-Loop Feedback Engine for OmniPost.

Analyzes cross-platform engagement scores, classifies winning hook archetypes,
determines optimal content length, and updates `references/voice-profile.local.md`
to close the autonomous learning loop.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import analytics
    import ledger
except ImportError:
    from scripts import analytics, ledger

PROFILE_PATH = ROOT / "references" / "voice-profile.local.md"


def classify_hook(text: str) -> str:
    """Classify the hook archetype of a post based on its opening lines."""
    if not text:
        return "Declarative Insight"

    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]
    first_beat = lines[0] if lines else text.strip()

    # Question Hook
    if "?" in first_beat or re.match(r"^(why|how|what|is|are|do|does|can|should|will)\b", first_beat, re.I):
        return "Question"

    # Contrarian Hook
    contrarian_terms = (
        r"\b(isn't|aren't|don't|stop|never|myth|wrong|mistake|nobody|inverted|broken|failure|instead)\b"
    )
    if re.search(contrarian_terms, first_beat, re.I):
        return "Contrarian"

    # Numbered List / Framework Hook
    if re.search(r"\b\d+\s+(lessons|rules|steps|ways|things|pillars|reasons|mistakes|patterns)\b", first_beat, re.I) or re.search(r"^\d+[\.\)]", first_beat):
        return "Numbered Breakdown"

    return "Declarative Insight"


def analyze_performance(state_path: Path | None = None) -> dict[str, Any]:
    """Analyze engagement metrics across ledger to extract high-leverage patterns."""
    st = ledger.load_state(state_path)
    scored_items: list[dict[str, Any]] = []

    for post in st.get("posts", []):
        text = post.get("text", "")
        if not text:
            continue
        hook_type = classify_hook(text)
        char_len = len(text)

        platforms = post.get("platforms", {})
        for plat_name, p_data in platforms.items():
            if not isinstance(p_data, dict):
                continue
            metrics = p_data.get("metrics")
            score = analytics.calculate_engagement_score(metrics)

            scored_items.append({
                "date": post.get("date", ""),
                "slot": post.get("slot", ""),
                "platform": plat_name,
                "text": text,
                "hook_type": hook_type,
                "char_len": char_len,
                "score": score,
                "likes": metrics.get("likes", 0) if metrics else 0,
            })

    if not scored_items:
        return {
            "total_items": 0,
            "best_hook_archetype": "Declarative Insight",
            "optimal_char_length": 220,
            "archetype_scores": {},
            "top_posts": [],
        }

    scored_items.sort(key=lambda x: x["score"], reverse=True)

    # Group scores by hook type
    hook_scores: dict[str, list[float]] = {}
    for item in scored_items:
        hook_scores.setdefault(item["hook_type"], []).append(item["score"])

    archetype_averages: dict[str, float] = {
        h: round(sum(scores) / len(scores), 2) for h, scores in hook_scores.items()
    }

    # Best hook archetype
    best_hook = max(archetype_averages.items(), key=lambda kv: kv[1])[0]

    # Calculate optimal character length from above-average performing posts
    avg_score = sum(x["score"] for x in scored_items) / len(scored_items)
    high_performers = [x for x in scored_items if x["score"] >= avg_score] or scored_items
    optimal_len = int(sum(x["char_len"] for x in high_performers) / len(high_performers))

    return {
        "total_items": len(scored_items),
        "best_hook_archetype": best_hook,
        "optimal_char_length": optimal_len,
        "archetype_scores": archetype_averages,
        "top_posts": scored_items[:3],
    }


def update_voice_profile(analysis: dict[str, Any], profile_path: Path | None = None) -> str:
    """Update or append the Learned Algorithmic Preferences section in voice profile."""
    target = profile_path or PROFILE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    existing_content = target.read_text(encoding="utf-8") if target.exists() else "# Voice Profile\n"

    # Build the learned section
    best_hook = analysis.get("best_hook_archetype", "Declarative Insight")
    optimal_len = analysis.get("optimal_char_length", 220)
    archetype_scores = analysis.get("archetype_scores", {})
    top_posts = analysis.get("top_posts", [])

    lines = [
        "## Learned Algorithmic Preferences (Auto-Calibrated)",
        f"- **Top-Performing Hook Archetype:** {best_hook}",
        f"- **Calibrated Content Length:** ~{optimal_len} characters (empirically derived from highest engagement).",
        "- **Hook Archetype Performance:**",
    ]

    for arch, score in sorted(archetype_scores.items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"  * **{arch}:** {score} avg score")

    if top_posts:
        lines.append("- **High-Engagement Exemplars:**")
        for tp in top_posts:
            snippet = tp["text"].split("\n")[0]
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."
            lines.append(f"  * \"{snippet}\" (Platform: {tp['platform']}, Score: {tp['score']})")

    new_section = "\n".join(lines).strip()

    # If section already exists in profile, replace it
    pattern = r"## Learned Algorithmic Preferences.*?(?=\n## |\Z)"
    if re.search(pattern, existing_content, re.S):
        updated_content = re.sub(pattern, new_section + "\n", existing_content, flags=re.S)
    else:
        updated_content = existing_content.rstrip() + "\n\n" + new_section + "\n"

    target.write_text(updated_content, encoding="utf-8")
    return updated_content


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("cmd", nargs="?", default="analyze", choices=["analyze", "update-profile"])
    args = parser.parse_args()

    analysis = analyze_performance()
    if args.cmd == "analyze":
        print(json.dumps(analysis, indent=2))
        return

    if args.cmd == "update-profile":
        content = update_voice_profile(analysis)
        print("[SUCCESS] Successfully updated voice profile with learned algorithmic preferences:")
        print("-" * 60)
        # Print just the learned section
        section = re.search(r"## Learned Algorithmic Preferences.*", content, re.S)
        if section:
            print(section.group(0))


if __name__ == "__main__":
    main()
