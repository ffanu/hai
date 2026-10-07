#!/usr/bin/env python3
"""Local QA for public URL fetch safety guards."""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402


BLOCKED = [
    "http://127.0.0.1/",
    "http://localhost/",
    "http://[::1]/",
    "http://10.0.0.1/",
    "http://172.16.0.1/",
    "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/",
]

ALLOWED = [
    "https://hai.harmonika.id/healthz",
    "https://example.com/",
]


def main() -> int:
    checks = []
    for url in BLOCKED:
        try:
            app._validate_public_http_url(url)
            ok = False
            error = ""
        except Exception as exc:
            ok = True
            error = str(exc)
        checks.append({"name": f"blocked:{url}", "ok": ok, "error": error})
    for url in ALLOWED:
        try:
            value = app._validate_public_http_url(url)
            ok = value == url
            error = ""
        except Exception as exc:
            ok = False
            error = str(exc)
        checks.append({"name": f"allowed:{url}", "ok": ok, "error": error})
    summary = {
        "ok": all(item["ok"] for item in checks),
        "passed": sum(1 for item in checks if item["ok"]),
        "total_run": len(checks),
        "checks": checks,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
