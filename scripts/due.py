#!/usr/bin/env python
"""The schedule gate: decide what is due right now.

Cron cannot express "post at a random time each day", so the plan assigns every
slot a random minute inside its window, and this script is what a cron job
monitors. It is deliberately dumb and free:

  * nothing due  -> prints IDLE, byte-identical every tick, so a cron monitor
                    suppresses the agent and idle ticks cost nothing
  * something due -> prints the draft plus an ever-incrementing tick counter,
                    which guarantees the agent wakes AND that a failed run is
                    retried on the next tick instead of stalling silently

CLI:
  python due.py make-plan [--date YYYY-MM-DD]   # random due times, empty texts
  python due.py show                            # today's plan + slot status
  python due.py check                           # IDLE | due draft JSON  (cron)
  python due.py fill --slot 16:00 --file t.txt  # write a draft's text
  python due.py mark --slot 16:00 --url ...     # record a successful post
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import settings

try:
    import ledger
    import validator
    from notify_webhook import dispatch_webhook
except ImportError:
    from scripts import ledger, validator
    from scripts.notify_webhook import dispatch_webhook

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PLANS = ROOT / "drafts"
STATE = ROOT / "state.json"
TICK_FILE = ROOT / ".tick"

MAX_LAG_HOURS = 6.0        # a slot this overdue is stale - never post it late
LOOKBACK_DAYS = 2          # scan today's and yesterday's plan (00:00 slots)


def now_tz() -> datetime:
    return datetime.now(settings.tzinfo())


def plan_path(date: str) -> Path:
    return PLANS / f"{date}.json"


def load_state() -> dict:
    return ledger.load_state()


def compute_slot_jitter(
    date_str: str,
    anchor: str,
    min_minutes: int = 7,
    max_minutes: int = 15,
    attempt: int = 0,
) -> int:
    """Deterministic jitter in minutes for a given date and slot anchor.
    Returns an integer offset in [-max_minutes, -min_minutes] U [min_minutes, max_minutes],
    or 0 if max_minutes <= 0.
    """
    if max_minutes <= 0:
        return 0
    min_m = max(0, min(min_minutes, max_minutes))
    seed_str = f"jitter:{date_str}:{anchor}:{attempt}"
    digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    val = int(digest[:8], 16)
    sign = 1 if (val & 1) else -1
    spread = max_minutes - min_m + 1
    magnitude = min_m + ((val >> 1) % spread)
    return sign * magnitude


def make_plan(date: str | None = None, allow_skip: bool | None = None) -> dict:
    """Assign every slot a deterministic jittered due time, keeping them a minimum gap apart."""
    c = settings.load()
    tz = settings.tzinfo()
    day = (datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tz) if date
           else now_tz().replace(hour=0, minute=0, second=0, microsecond=0))
    date_str = day.strftime("%Y-%m-%d")

    jitter_min = int(c.get("jitter_min_minutes", c.get("jitter_min", 7)))
    configured_max = c.get("jitter_max_minutes", c.get("jitter_max"))
    if configured_max is not None:
        jitter_max = int(configured_max)
    else:
        legacy_jitter = c.get("jitter_minutes")
        jitter_max = int(legacy_jitter) if (legacy_jitter is not None and legacy_jitter != 45) else 15
    jitter_min = max(0, min(jitter_min, jitter_max))

    gap = float(c.get("min_gap_hours", 2.5))
    ai_slot = c.get("ai_update_slot", "16:00")

    if allow_skip is None:
        allow_skip = bool(c.get("allow_skipped_slots", c.get("skip_slot_enabled", False)))
    skip_chance = float(c.get("skip_slot_chance", 0.25))

    raw_slots = c.get("slots") or ["13:00"]
    skipped_anchor = None
    if allow_skip and len(raw_slots) > 1:
        day_seed = int(hashlib.sha256(f"skip_day:{date_str}".encode("utf-8")).hexdigest()[:8], 16)
        if (day_seed % 100) < int(skip_chance * 100):
            eligible = [s for s in raw_slots if str(s) != str(ai_slot)]
            if eligible:
                skipped_anchor = str(eligible[(day_seed >> 8) % len(eligible)])

    # Check for existing plan to preserve written text or posted status
    existing_slots = {}
    p_path = plan_path(date_str)
    if p_path.exists():
        try:
            old_plan = json.loads(p_path.read_text(encoding="utf-8"))
            for s in old_plan.get("slots", []):
                if "slot" in s:
                    existing_slots[s["slot"]] = s
        except Exception:
            pass

    slots, prev = [], None
    for anchor in raw_slots:
        hh, mm = (int(x) for x in str(anchor).split(":"))
        base = day + timedelta(hours=hh, minutes=mm)
        if hh == 0 and mm == 0:                    # the late post belongs to today's run
            base += timedelta(days=1)
        when = base
        for attempt in range(40):
            j = compute_slot_jitter(date_str, str(anchor), jitter_min, jitter_max, attempt)
            when = base + timedelta(minutes=j)
            if prev is None or (when - prev) >= timedelta(hours=gap):
                break
        prev = when
        is_ai = (str(anchor) == str(ai_slot) and c.get("ai_update_enabled", True))
        existing = existing_slots.get(anchor, {})
        slot_item = {
            "slot": anchor,
            "kind": existing.get("kind") or ("ai_update" if is_ai else "value"),
            "due_at": when.isoformat(),
            "text": existing.get("text", ""),
            "image": existing.get("image", None),
            "posted": existing.get("posted", False),
            "tweet_url": existing.get("tweet_url", None),
        }
        if str(anchor) == str(skipped_anchor):
            slot_item["skipped"] = "deterministic_schedule_skip"
        elif "skipped" in existing:
            slot_item["skipped"] = existing["skipped"]
        slots.append(slot_item)

    plan = {"date": date_str, "created_at": now_tz().isoformat(),
            "handle": c.get("handle", ""), "slots": slots}
    PLANS.mkdir(parents=True, exist_ok=True)
    p_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False),
                      encoding="utf-8")
    return plan


def _load_plans() -> list[tuple[Path, dict]]:
    out = []
    today = now_tz().date()
    for p in sorted(PLANS.glob("*.json")):
        try:
            d = datetime.strptime(p.stem, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - d).days > LOOKBACK_DAYS or (d - today).days > 1:
            continue
        try:
            out.append((p, json.loads(p.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return out


def _posted_slots(st: dict, date: str) -> set[str]:
    """Slots already published on `date` per the ledger (the ground truth)."""
    tz = settings.tzinfo()
    c = settings.load()
    platforms_cfg = settings.get_platforms(c)
    enabled_platforms = [p for p, data in platforms_cfg.items() if data.get("enabled", True)]

    done = set()
    for p in st.get("posts", []):
        try:
            at = datetime.fromisoformat(str(p["at"]).replace("Z", "+00:00")).astimezone(tz).strftime("%Y-%m-%d")
        except Exception:
            continue
        if at == date:
            p_platforms = p.get("platforms")
            if p_platforms:
                # If target platforms are known or any enabled platform is in p_platforms:
                target_keys = [k for k in enabled_platforms if k in p_platforms] or list(p_platforms.keys())
                all_done = bool(target_keys) and all(
                    p_platforms.get(k, {}).get("status") == ledger.STATUS_PUBLISHED_VERIFIED
                    for k in target_keys
                )
                if all_done:
                    done.add(p.get("slot"))
            elif p.get("tweet_url") and p.get("verified"):
                done.add(p.get("slot"))
    return done


def due(max_lag: float = MAX_LAG_HOURS) -> dict | None:
    """The single oldest unposted, not-too-late slot, or None."""
    st = load_state()
    now = now_tz()
    best: tuple[datetime, Path, dict, dict] | None = None
    for path, plan in _load_plans():
        done = _posted_slots(st, plan.get("date", ""))
        for slot in plan.get("slots", []):
            if slot.get("posted") or slot.get("slot") in done:
                continue
            if slot.get("skipped"):
                continue
            has_text = bool((slot.get("text") or "").strip())
            try:
                when = datetime.fromisoformat(slot["due_at"])
            except Exception:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=now.tzinfo)
            if when > now:
                continue
            if (now - when) > timedelta(hours=max_lag):
                if has_text:
                    slot["posted"] = True         # too stale: retire, don't post late
                    slot["skipped"] = f"overdue by {now - when}"
                    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
                continue

            if not has_text:
                # Slot is due but text has not been synthesized yet; return it so caller can trigger pipeline
                key = (when, path, plan, slot)
                if best is None or key[0] < best[0]:
                    best = key
                continue

            # Guardrail check: do not queue posts that violate hard rules or warmup caps.
            # Every platform in the slot is checked; a slot is only as valid as its worst copy.
            cfg_now = settings.load()
            valid = True
            errs: list[str] = []
            for plat, plat_cfg in (slot.get("platforms") or {"x": None}).items():
                if isinstance(plat_cfg, dict) and plat_cfg.get("enabled") is False:
                    continue
                plat_valid, plat_errs = validator.validate_draft_guardrails(
                    draft=slot,
                    cfg=cfg_now,
                    state=st,
                    platform=plat,
                    raise_on_error=False,
                    check_warmup=True,
                )
                if not plat_valid:
                    valid = False
                    errs.extend(f"{plat}: {err}" for err in plat_errs)
            if not valid:
                slot["guardrail_blocked"] = errs
                if not slot.get("guardrail_alerted"):
                    slot["guardrail_alerted"] = True
                    try:
                        path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
                    except Exception:
                        pass
                    dispatch_webhook(
                        event_type="guardrail_drop",
                        title="OmniPost blocked a slot",
                        message=(
                            f"Slot {slot.get('slot')} on {plan.get('date')} was blocked by "
                            "guardrails. Nothing will be published."
                        ),
                        metadata={
                            "slot": slot.get("slot"),
                            "date": plan.get("date"),
                            "violations": "; ".join(errs)[:900],
                        },
                    )
                continue

            key = (when, path, plan, slot)

            if best is None or key[0] < best[0]:
                best = key
    if not best:
        return None
    when, path, plan, slot = best
    plan_date = plan.get("date")
    if not plan_date and path.exists():
        try:
            plan_date = json.loads(path.read_text(encoding="utf-8")).get("date")
        except Exception:
            pass
    return {"date": plan_date,
            "slot": slot["slot"], "kind": slot["kind"], "due_at": slot["due_at"],
            "text": slot["text"], "image": slot.get("image"),
            "minutes_late": round((now - when).total_seconds() / 60, 1)}


def tick() -> int:
    n = 0
    if TICK_FILE.exists():
        try:
            n = int(TICK_FILE.read_text().strip() or "0")
        except Exception:
            n = 0
    n += 1
    TICK_FILE.write_text(str(n))
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="check",
                    choices=["make-plan", "show", "check", "fill", "mark", "reset-tick"])
    ap.add_argument("--date", default=None)
    ap.add_argument("--slot", default=None)
    ap.add_argument("--text", default=None)
    ap.add_argument("--file", default=None)
    ap.add_argument("--url", default=None)
    ap.add_argument("--image", default=None)
    ap.add_argument("--allow-skip", action="store_true", default=None,
                    help="Allow deterministic optional slot skip")
    a = ap.parse_args()

    if a.cmd == "make-plan":
        p = make_plan(a.date, allow_skip=a.allow_skip)
        print(json.dumps({"date": p["date"],
                          "slots": [{"slot": s["slot"], "kind": s["kind"], "due_at": s["due_at"]}
                                    for s in p["slots"]]}, indent=2))
        return

    if a.cmd == "show":
        if a.date and plan_path(a.date).exists():
            print(json.dumps(json.loads(plan_path(a.date).read_text(encoding="utf-8")),
                             indent=2, ensure_ascii=False)[:4000])
            return
        st = load_state()
        for path, plan in _load_plans():
            print(f"# {path.name}")
            for s in plan["slots"]:
                if s.get("posted"):
                    mark = "POSTED"
                elif s.get("text"):
                    mark = "ready"
                else:
                    mark = "empty"
                entry = ledger.get_slot_entry(st, plan.get("date", ""), s["slot"])
                plat_info = ""
                if entry and "platforms" in entry and entry["platforms"]:
                    statuses = [f"{p.upper()}:{data.get('status')}" for p, data in entry["platforms"].items()]
                    plat_info = f" [{', '.join(statuses)}]"
                print(f"  {s['slot']:>5} {s['kind']:<9} due {s['due_at'][11:16]}  {mark}{plat_info}")
        return

    if a.cmd == "check":
        d = due()
        if not d:
            print("IDLE")
            return
        d["tick"] = tick()
        print(json.dumps(d, ensure_ascii=False))
        return

    if a.cmd in ("fill", "mark"):
        if not a.slot:
            raise SystemExit("--slot required")
        text = a.text
        if a.file:
            text = Path(a.file).read_text(encoding="utf-8")
        text = (text or "").strip()

        c = settings.load()
        lim = settings.limit(c)
        limit = lim["chars"]
        if not lim["verified"]:
            print(json.dumps({
                "warning": "character ceiling is NOT verified on this account",
                "enforcing": limit, "source": lim["source"], "fix": lim["fix"],
                "note": "run the measure command before trusting any length decision"}), flush=True)
        if a.cmd == "fill" and text:
            # Enforce guardrails on filled text
            st = load_state()
            valid, errs = validator.validate_draft_guardrails(
                draft={"text": text},
                cfg=c,
                state=st,
                raise_on_error=False,
            )
            if not valid:
                raise SystemExit(json.dumps({
                    "error": "draft rejected by guardrails",
                    "violations": errs,
                }, indent=2))

            kind = None

            for _p, _pl in _load_plans():
                for s0 in _pl.get("slots", []):
                    if s0["slot"] == a.slot:
                        kind = s0.get("kind")
            if kind == "ai_update" and c.get("ai_update_enabled", True):
                header = c.get("ai_update_header") or "Daily AI updates | Day {day}"
                reserved = len(header.replace("{day}", "999")) + 2   # + blank line
                if len(text) > limit - reserved:
                    raise SystemExit(json.dumps({
                        "error": "too long for the ai_update slot",
                        "body_chars": len(text), "max_body": limit - reserved,
                        "detail": f"the header + blank line reserves {reserved} of {limit} chars"},
                        indent=2))
            if len(text) > limit:
                raise SystemExit(f"text is {len(text)} chars, limit is {limit}")

        touched = []
        for path, plan in _load_plans():
            for s in plan.get("slots", []):
                if s["slot"] != a.slot or s.get("posted") or s.get("tweet_url"):
                    continue
                if a.cmd == "fill":
                    s["text"] = text
                    if a.image:
                        s["image"] = a.image
                else:
                    s["posted"] = True
                    s["tweet_url"] = a.url
                touched.append(path.name)
                path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
                break
        print(json.dumps({"cmd": a.cmd, "slot": a.slot, "updated": touched, "chars": len(text)}))
        return

    if a.cmd == "reset-tick":
        TICK_FILE.write_text("0")
        print("tick reset")


if __name__ == "__main__":
    main()
