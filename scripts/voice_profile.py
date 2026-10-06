#!/usr/bin/env python
"""Analyse the user's OWN best-performing posts to extract their voice.

This is the onboarding step that makes the writing theirs instead of generic.
The agent asks the user for posts they are proud of (ideally 100k+ impressions),
pastes them into a file, and this script measures the things that are actually
copyable:

  * length habit, and whether the account is on the 280 free-tier ceiling
  * how the hook is built (first 3-6 words) - the single highest-leverage thing
  * paragraph rhythm: how many blank-line-separated beats per post
  * emoji / hashtag / link / number / question usage
  * recurring topics, ranked by frequency across the corpus

It deliberately does NOT judge quality or invent a style - it reports what is
measurably there. The agent turns this into references/voice-profile.local.md.

Input (any of):
  * JSON list of strings
  * JSON list of objects with a text-ish key (text, tweet, content, body)
  * plain text, posts separated by a line of --- or by a blank line

  python voice_profile.py --in my_top_tweets.txt
  python voice_profile.py --in them.json --json
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

import settings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STOPWORDS = set("""
a about above after again against all am an and any are aren't as at be because been before being
below between both but by can cannot could couldn't did didn't do does doesn't doing don't down
during each few for from further had hadn't has hasn't have haven't having he he'd he'll he's her
here here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's
its itself let's me more most mustn't my myself no nor not of off on once only or other ought our
ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some such than
that that's the their theirs them themselves then there there's these they they'd they'll they're
they've this those through to too under until up very was wasn't we we'd we'll we're we've were
weren't what what's when when's where where's which while who who's whom why why's with won't would
wouldn't you you'd you'll you're you've your yours yourself yourselves just now get got one like
also new use using make makes made really thing things way still even much many lot
""".split())

TEXT_KEYS = ("text", "tweet", "content", "body", "post", "full_text")


def parse(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        raise SystemExit("input file is empty")

    if raw[0] in "[{":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as err:
            raise SystemExit(f"looks like JSON but will not parse: {err}")
        out: list[str] = []
        for item in data:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for k in TEXT_KEYS:
                    if isinstance(item.get(k), str) and item[k].strip():
                        out.append(item[k])
                        break
        if not out:
            raise SystemExit("JSON parsed, but no text field found "
                             f"(looked for {', '.join(TEXT_KEYS)})")
        return [t.strip() for t in out if t.strip()]

    # plain text: split on --- fences if present, else on blank lines
    if re.search(r"^\s*-{3,}\s*$", raw, re.M):
        parts = re.split(r"^\s*-{3,}\s*$", raw, flags=re.M)
    else:
        parts = re.split(r"\n\s*\n\s*\n+", raw)
    return [p.strip() for p in parts if len(p.strip()) > 15]


def chars(t: str) -> int:
    return len(t)


def words(t: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z'-]{1,}", t.lower()) if w not in STOPWORDS]


def analyse(posts: list[str]) -> dict:
    lengths = [chars(p) for p in posts]
    beats = [len([b for b in re.split(r"\n\s*\n", p) if b.strip()]) for p in posts]
    all_words = Counter()
    for p in posts:
        all_words.update(words(p))

    hooks = []
    for p in posts:
        first = p.strip().split("\n")[0].strip()
        hooks.append(" ".join(first.split()[:6]))

    opener_kinds = Counter()
    for p in posts:
        first = p.strip().split("\n")[0].strip()
        if not first:
            continue
        if first.endswith("?") or re.match(r"^(how|why|what|who|when|do you|are you|is |can )",
                                           first, re.I):
            opener_kinds["question"] += 1
        elif re.search(r"\d", first):
            opener_kinds["number / specific figure"] += 1
        elif re.match(r"^(stop|don't|never|everyone|nobody|most people|you )", first, re.I):
            opener_kinds["directive / addressed to the reader"] += 1
        else:
            opener_kinds["statement / claim"] += 1

    # Compare the user's own posts against THEIR account's ceiling, not a
    # hardcoded one: the limit differs per account and is measured, not assumed.
    lim = settings.limit()
    cap = lim["chars"]
    under = sum(1 for n in lengths if n <= cap)
    return {
        "posts_analysed": len(posts),
        "length": {
            "min": min(lengths), "median": int(statistics.median(lengths)), "max": max(lengths),
            "mean": round(statistics.mean(lengths)),
            f"under_{cap}": f"{under}/{len(lengths)}",
            "ceiling_used": cap,
            "ceiling_verified": lim["verified"],
            "verdict": (f"all posts fit the account's {cap}-char ceiling"
                        if max(lengths) <= cap else
                        f"some posts exceed the account's {cap}-char ceiling "
                        f"(they were posted anyway, so that ceiling is probably wrong)") +
                       ("" if lim["verified"] else
                        f" - ceiling NOT verified ({lim['fix']})"),
        },
        "structure": {
            "beats_per_post_median": int(statistics.median(beats)),
            "uses_blank_line_breaks": f"{sum(1 for b in beats if b > 1)}/{len(beats)}",
        },
        "devices": {
            "emoji_posts": sum(1 for p in posts if re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", p)),
            "hashtag_posts": sum(1 for p in posts if re.search(r"(^|\s)#\w+", p)),
            "hashtags_total": sum(len(re.findall(r"(^|\s)#\w+", p)) for p in posts),
            "link_posts": sum(1 for p in posts if re.search(r"https?://|t\.co/", p)),
            "number_posts": sum(1 for p in posts if re.search(r"\d", p)),
            "question_posts": sum(1 for p in posts if "?" in p),
            "emoji_total": sum(len(re.findall(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", p))
                               for p in posts),
        },
        "hook_openers": dict(opener_kinds.most_common()),
        "hook_first_words": [h for h in hooks],
        "recurring_topics": [{"term": w, "posts": c} for w, c in all_words.most_common(25)],
    }


def render(a: dict, path: str) -> str:
    L, S, D = a["length"], a["structure"], a["devices"]
    n = a["posts_analysed"]
    lines = [
        f"VOICE PROFILE — measured from {n} posts ({path})",
        "=" * 62,
        "",
        "LENGTH",
        f"  min {L['min']} | median {L['median']} | mean {L['mean']} | max {L['max']} chars",
        "  within the account's {}-char ceiling: {}   -> {}".format(
            L["ceiling_used"], L.get("under_" + str(L["ceiling_used"])), L["verdict"]),
        "",
        "STRUCTURE",
        f"  beats per post (blank-line separated): median {S['beats_per_post_median']}",
        f"  uses blank-line breaks: {S['uses_blank_line_breaks']}",
        "",
        "DEVICES (how many posts use each)",
        f"  numbers       {D['number_posts']}/{n}",
        f"  questions     {D['question_posts']}/{n}",
        f"  links         {D['link_posts']}/{n}",
        f"  hashtags      {D['hashtag_posts']}/{n} posts, {D['hashtags_total']} total",
        f"  emoji         {D['emoji_posts']}/{n} posts, {D['emoji_total']} total",
        "",
        "HOOK SHAPE — how they open",
    ]
    for k, v in a["hook_openers"].items():
        lines.append(f"  {v:>3}x  {k}")
    lines += ["", "THE ACTUAL FIRST 6 WORDS (pattern-match these):"]
    for i, h in enumerate(a["hook_first_words"], 1):
        lines.append(f"  {i:>2}. {h}")
    lines += ["", "RECURRING TOPICS (stopwords removed, by frequency):"]
    row = []
    for t in a["recurring_topics"]:
        row.append(f"{t['term']}({t['posts']})")
    lines.append("  " + "  ".join(row))
    lines += ["",
              "NEXT: your agent turns this into references/voice-profile.local.md, and every",
              "draft is written against it. This file is git-ignored - it is your voice, not",
              "part of the shared skill."]
ROOT = Path(__file__).resolve().parent.parent
VOICE_PROFILE_DEFAULT_PATH = ROOT / "references" / "voice-profile.local.md"

DEFAULT_DO_NOT_RULES = [
    "Never use corporate buzzwords: 'In today's fast-paced world', 'Game changer', 'Dive into', 'Excited to announce'.",
    "Never use hashtags in the post body.",
    "Never use exclamation marks in technical statements or analysis.",
    "Never use engagement bait questions ('Agree?', 'What do you think?', 'Comment below').",
    "Never end on preachy or moralizing wrap-up conclusions.",
    "Never use bulleted lists inside short-form X posts (use blank lines instead).",
    "Never post emojis as decorative padding or filler.",
]


def validate_voice_profile_exists(base: Path | None = None) -> bool:
    """Checks whether references/voice-profile.local.md exists and has substantive content."""
    p = (base or ROOT) / "references" / "voice-profile.local.md"
    if not p.exists() or not p.is_file():
        return False
    try:
        content = p.read_text(encoding="utf-8").strip()
        return len(content) > 50
    except Exception:
        return False


def enforce_do_not_list(profile_text: str | None = None, base: Path | None = None) -> tuple[bool, list[str]]:
    """Checks that voice profile has an explicit, non-empty DO-NOT list to prevent AI voice drift."""
    text = profile_text
    if text is None:
        p = (base or ROOT) / "references" / "voice-profile.local.md"
        if not p.exists():
            return False, []
        text = p.read_text(encoding="utf-8", errors="replace")

    # Look for DO NOT section
    m = re.search(r"##\s+(?:DO\s+NOT|Do-Not|Do\s+Not)[^\n]*\n(.*?)(?=\n##|\Z)", text, flags=re.S | re.I)
    if not m:
        return False, []

    section_body = m.group(1).strip()
    rules = [line.strip().lstrip("-* ").strip() for line in section_body.splitlines() if line.strip().startswith(("-", "*"))]
    if not rules:
        return False, []
    return True, rules


def generate_voice_profile_markdown(
    analysis: dict,
    do_not_list: list[str] | None = None,
    handle: str = "",
) -> str:
    """Generates a structured references/voice-profile.local.md document."""
    do_nots = do_not_list if (do_not_list and len(do_not_list) > 0) else DEFAULT_DO_NOT_RULES
    handle_str = f"@{handle.lstrip('@')}" if handle else "Your Account"
    D = analysis.get("devices", {})
    L = analysis.get("length", {})
    S = analysis.get("structure", {})
    n = analysis.get("posts_analysed", 0)

    lines = [
        f"# Voice Profile: {handle_str}",
        "",
        "> Measured empirically from your top-performing posts. Every draft is checked",
        "> against this profile. If this file is modified or removed, rerun the voice ritual.",
        "",
        "## Quantitative Habits",
        f"- **Median character count**: {L.get('median', 0)} characters",
        f"- **Max character length**: {L.get('max', 0)} characters",
        f"- **Median paragraph beats**: {S.get('beats_per_post_median', 0)} beats per post",
        f"- **Number usage**: {D.get('number_posts', 0)}/{n} posts lead or include concrete metrics",
        f"- **Question usage**: {D.get('question_posts', 0)}/{n} posts use rhetorical questions",
        f"- **Hashtag usage**: {D.get('hashtag_posts', 0)}/{n} posts (banned in body copy)",
        f"- **Emoji usage**: {D.get('emoji_posts', 0)}/{n} posts",
        "",
        "## Hook Patterns (First 6 Words)",
    ]

    for i, h in enumerate(analysis.get("hook_first_words", [])[:8], 1):
        lines.append(f"{i}. \"{h}\"")

    lines.extend([
        "",
        "## Recurring Core Topics",
    ])
    for t in analysis.get("recurring_topics", [])[:10]:
        lines.append(f"- **{t['term']}** ({t['posts']} posts)")

    lines.extend([
        "",
        "## DO NOT LIST (Enforced Hard Boundaries)",
        "The following styles and words are strictly forbidden to prevent synthetic AI drift:",
    ])
    for rule in do_nots:
        lines.append(f"- {rule}")

    lines.append("")
    return "\n".join(lines)


def run_voice_ritual(
    posts_input: list[str] | str | Path,
    do_not_input: list[str] | None = None,
    base: Path | None = None,
    handle: str = "",
) -> tuple[dict, Path]:
    """Runs the full voice ritual from top posts and writes references/voice-profile.local.md."""
    if isinstance(posts_input, Path):
        posts = parse(posts_input)
    elif isinstance(posts_input, str):
        # Plain text
        if re.search(r"^\s*-{3,}\s*$", posts_input, re.M):
            parts = re.split(r"^\s*-{3,}\s*$", posts_input, flags=re.M)
        else:
            parts = re.split(r"\n\s*\n\s*\n+", posts_input)
        posts = [p.strip() for p in parts if len(p.strip()) > 15]
    else:
        posts = [p.strip() for p in posts_input if isinstance(p, str) and len(p.strip()) > 15]

    if len(posts) < 3:
        raise ValueError(
            f"Voice ritual requires at least 3 sample posts (provided {len(posts)}). "
            "Provide 5-20 of your best-performing posts."
        )

    res = analyse(posts)
    target_dir = (base or ROOT) / "references"
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / "voice-profile.local.md"

    md = generate_voice_profile_markdown(res, do_not_list=do_not_input, handle=handle)
    out_file.write_text(md, encoding="utf-8")
    return res, out_file


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=False, default=None)
    ap.add_argument("--out", default=None, help="where to write the report (default: stdout)")
    ap.add_argument("--json", action="store_true", help="raw JSON instead of the report")
    ap.add_argument("--calibrate", action="store_true", help="calibrate voice profile from ledger engagement metrics")
    ap.add_argument("--ritual", action="store_true", help="run ritual and write references/voice-profile.local.md")
    ap.add_argument("--check-do-not", action="store_true", help="verify that DO-NOT list exists and is non-empty")
    a = ap.parse_args()

    if a.check_do_not:
        ok, rules = enforce_do_not_list()
        if not ok:
            print("[FAILURE] No DO-NOT list found in references/voice-profile.local.md")
            sys.exit(1)
        print(f"[SUCCESS] DO-NOT list verified with {len(rules)} rules.")
        sys.exit(0)

    if a.calibrate:
        try:
            import feedback
        except ImportError:
            from scripts import feedback
        analysis = feedback.analyze_performance()
        feedback.update_voice_profile(analysis)
        print("[SUCCESS] Voice profile successfully calibrated from ledger performance.")
        if not a.infile:
            return

    if not a.infile:
        ap.error("--in required unless using --calibrate or --check-do-not")

    path = Path(a.infile)
    if not path.exists():
        raise SystemExit(f"no such file: {path}")
    posts = parse(path)
    if len(posts) < 3:
        raise SystemExit(f"only found {len(posts)} posts - give me at least 3, ideally 10-20 "
                         "of your best. Separate them with a line of --- or a blank line.")
    result = analyse(posts)

    if a.ritual:
        _, profile_p = run_voice_ritual(posts)
        print(f"[SUCCESS] Voice profile ritual complete. Saved to {profile_p}")
        return

    text = json.dumps(result, indent=2, ensure_ascii=False) if a.json else render(result, path.name)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        print(text)



if __name__ == "__main__":
    main()
