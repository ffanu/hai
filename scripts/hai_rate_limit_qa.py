#!/usr/bin/env python3
"""Offline QA for Harmonika AI rate-limit storage.

This validates the file-backed limiter used in production so gunicorn workers
share one quota bucket instead of each worker having its own in-memory counter.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as hai_app  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out")
    args = parser.parse_args()

    original_storage = hai_app.RATE_LIMIT_STORAGE
    original_file = hai_app.RATE_LIMIT_FILE_PATH
    checks = []

    with tempfile.TemporaryDirectory() as tmpdir:
        hai_app.RATE_LIMIT_STORAGE = "file"
        hai_app.RATE_LIMIT_FILE_PATH = str(pathlib.Path(tmpdir) / "rate-limits.json")
        try:
            with hai_app.app.test_request_context("/chat", environ_base={"REMOTE_ADDR": "203.0.113.10"}):
                first = hai_app._check_rate_limit("qa", (2, 60))
                second = hai_app._check_rate_limit("qa", (2, 60))
                third = hai_app._check_rate_limit("qa", (2, 60))
            data = json.loads(pathlib.Path(hai_app.RATE_LIMIT_FILE_PATH).read_text(encoding="utf-8"))
            buckets = data.get("buckets", {}) if isinstance(data, dict) else {}
            checks.append({
                "name": "file_storage_enforces_limit",
                "ok": first == (True, 0) and second == (True, 0) and third[0] is False and third[1] > 0,
                "first": first,
                "second": second,
                "third": third,
            })
            checks.append({
                "name": "file_storage_persists_bucket",
                "ok": bool(buckets) and all(isinstance(value, list) for value in buckets.values()),
                "bucket_count": len(buckets),
            })
        finally:
            hai_app.RATE_LIMIT_STORAGE = original_storage
            hai_app.RATE_LIMIT_FILE_PATH = original_file

    ok = all(item["ok"] for item in checks)
    summary = {
        "ok": ok,
        "checks": checks,
        "passed": sum(1 for item in checks if item["ok"]),
        "total_run": len(checks),
    }
    if args.json_out:
        out = pathlib.Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
