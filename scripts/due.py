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
except ImportError:
    from scripts import ledger, validator

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


def make_plan(date: str | None = None) -> dict:
    """Assign every slot a jittered due time, keeping them a minimum gap apart."""
    c = settings.load()
    tz = settings.tzinfo()
    day = (datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tz) if date
           else now_tz().replace(hour=0, minute=0, second=0, microsecond=0))
    jitter = int(c.get("jitter_minutes", 45))
    gap = float(c.get("min_gap_hours", 3))
    ai_slot = c.get("ai_update_slot", "16:00")

    slots, prev = [], None
    for anchor in (c.get("slots") or ["13:00"]):
        hh, mm = (int(x) for x in str(anchor).split(":"))
        base = day + timedelta(hours=hh, minutes=mm)
        if hh == 0 and mm == 0:                    # the late post belongs to today's run
            base += timedelta(days=1)
        when = base
        for _ in range(40):
            when = base + timedelta(minutes=random.randint(-jitter, jitter))
            if prev is None or (when - prev) >= timedelta(hours=gap):
                break
        prev = when
        slots.append({
            "slot": anchor,
            "kind": "ai_update" if anchor == ai_slot and c.get("ai_update_enabled", True) else "value",
            "due_at": when.isoformat(),
            "text": "", "image": None, "posted": False, "tweet_url": None,
        })
    plan = {"date": day.strftime("%Y-%m-%d"), "created_at": now_tz().isoformat(),
            "handle": c.get("handle", ""), "slots": slots}
    PLANS.mkdir(parents=True, exist_ok=True)
    plan_path(plan["date"]).write_text(json.dumps(plan, indent=2, ensure_ascii=False),
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
                    p_platforms.get(k, {}).get("status") == "published"
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
    best: tuple[datetime, Path, dict] | None = None
    for path, plan in _load_plans():
        done = _posted_slots(st, plan.get("date", ""))
        for slot in plan.get("slots", []):
            if slot.get("posted") or slot.get("slot") in done:
                continue
            if not (slot.get("text") or "").strip():
                continue                      # not written yet - not our problem
            try:
                when = datetime.fromisoformat(slot["due_at"])
            except Exception:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=now.tzinfo)
            if when > now:
                continue
            if (now - when) > timedelta(hours=max_lag):
                slot["posted"] = True         # too stale: retire, don't post late
                slot["skipped"] = f"overdue by {now - when}"
                path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
                continue

            # Guardrail check: do not queue posts that violate hard rules or warmup caps
            valid, errs = validator.validate_draft_guardrails(
                draft=slot,
                cfg=settings.load(),
                state=st,
                raise_on_error=False,
                check_warmup=True,
            )
            if not valid:
                slot["guardrail_blocked"] = errs
                continue

            key = (when, path, slot)

            if best is None or key[0] < best[0]:
                best = key
    if not best:
        return None
    when, path, slot = best
    return {"date": json.loads(path.read_text(encoding="utf-8")).get("date"),
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
    a = ap.parse_args()

    if a.cmd == "make-plan":
        p = make_plan(a.date)
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
