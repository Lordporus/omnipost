#!/usr/bin/env python
"""Isolated publish worker for OmniPost.

The parent process runs this module in a subprocess so a per-platform timeout can
kill the underlying work. Input arrives as JSON on stdin and the authoritative
result is written atomically to the file passed via --result-file. Adapter stdout
is redirected to stderr because some adapters print progress messages.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from scripts import settings
except ImportError:  # direct script execution
    import settings

from adapters.base import PublishPayload, PublishResult


def _write_result(result_path: Path, payload: dict[str, Any]) -> None:
    result_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = result_path.parent / (
        f"{result_path.name}.tmp.{os.getpid()}.{time.time_ns()}"
    )
    try:
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        os.replace(tmp_path, result_path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _failure_result(platform: str, error: str) -> dict[str, Any]:
    return PublishResult(
        platform=platform,
        success=False,
        verified=False,
        error=error,
    ).to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-file", required=True)
    args = parser.parse_args()
    result_path = Path(args.result_file)

    platform = ""
    try:
        raw_input = sys.stdin.read()
        data = json.loads(raw_input) if raw_input.strip() else {}
        platform = str(data.get("platform") or "").lower()
        if not platform:
            raise ValueError("missing platform")

        payload = PublishPayload.from_dict(data)
        adapters = settings.get_active_adapters()
        adapter = next(
            (
                candidate
                for candidate in adapters
                if candidate.platform_name.lower() == platform
            ),
            None,
        )
        if adapter is None:
            raise RuntimeError(f"no active adapter for platform '{platform}'")

        # Adapters may print to stdout; never let that corrupt the JSON contract.
        with contextlib.redirect_stdout(sys.stderr):
            result = adapter.publish(payload)

        _write_result(result_path, result.to_dict())
        return 0
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        print(f"[publish_worker] {error}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        _write_result(result_path, _failure_result(platform, error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
