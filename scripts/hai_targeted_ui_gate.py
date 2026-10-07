#!/usr/bin/env python3
"""Targeted production UI gate for the latest HAI chat polish.

This gate is intentionally small and repeatable. It mirrors the Phase 274
evidence that `/api/readiness.production.gate` points to:

- release audit / readiness contract
- realtime loading states on desktop and mobile
- rich Markdown/code/table rendering on desktop and mobile
- live mobile chat smoke

It does not replace the larger `hai_production_qa.py --public-release-gate`.
It is the fast gate used after UI polish-only releases.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]


@dataclass
class GateCheck:
    name: str
    command: list[str]
    timeout: int


def run_check(check: GateCheck) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(
            check.command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=check.timeout,
        )
        duration_ms = int((time.time() - started) * 1000)
        child = extract_json(proc.stdout)
        return {
            "name": check.name,
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "duration_ms": duration_ms,
            "child_ok": child.get("ok") if child else None,
            "child_passed": child.get("passed") if child else None,
            "child_total_run": child.get("total_run") if child else None,
            "stdout": "" if proc.returncode == 0 else proc.stdout[-3000:],
            "stderr": proc.stderr[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.time() - started) * 1000)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return {
            "name": check.name,
            "ok": False,
            "returncode": None,
            "duration_ms": duration_ms,
            "child_ok": None,
            "child_passed": None,
            "child_total_run": None,
            "stdout": stdout[-3000:],
            "stderr": (stderr[-3000:] + f"\nTimed out after {check.timeout}s").strip(),
            "timed_out": True,
        }


def extract_json(stdout: str) -> dict:
    text = (stdout or "").strip()
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append(value)
    if not candidates:
        return {}
    for candidate in reversed(candidates):
        if candidate.get("ok") in {True, False}:
            return candidate
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://hai.harmonika.id")
    parser.add_argument("--expected-asset-marker", default="20261007-phase317")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    python = sys.executable
    base_url = args.base_url.rstrip("/")
    checks = [
        GateCheck(
            "release_audit",
            [
                python,
                "scripts/hai_release_audit.py",
                "--base-url",
                base_url,
                "--expected-asset-marker",
                args.expected_asset_marker,
            ],
            80,
        ),
        GateCheck(
            "streaming_states_desktop",
            [
                python,
                "scripts/hai_browser_qa.py",
                "--url",
                f"{base_url}/",
                "--viewport",
                "desktop",
                "--flow",
                "streaming-states",
                "--timeout",
                "45",
            ],
            90,
        ),
        GateCheck(
            "streaming_states_mobile",
            [
                python,
                "scripts/hai_browser_qa.py",
                "--url",
                f"{base_url}/",
                "--viewport",
                "mobile",
                "--flow",
                "streaming-states",
                "--timeout",
                "45",
            ],
            90,
        ),
        GateCheck(
            "markdown_rich_desktop",
            [
                python,
                "scripts/hai_browser_qa.py",
                "--url",
                f"{base_url}/",
                "--viewport",
                "desktop",
                "--flow",
                "markdown-rich",
                "--timeout",
                "45",
            ],
            90,
        ),
        GateCheck(
            "markdown_rich_mobile",
            [
                python,
                "scripts/hai_browser_qa.py",
                "--url",
                f"{base_url}/",
                "--viewport",
                "mobile",
                "--flow",
                "markdown-rich",
                "--timeout",
                "45",
            ],
            90,
        ),
        GateCheck(
            "chat_text_mobile",
            [
                python,
                "scripts/hai_browser_qa.py",
                "--url",
                f"{base_url}/",
                "--viewport",
                "mobile",
                "--flow",
                "chat-text",
                "--timeout",
                "70",
            ],
            120,
        ),
    ]

    results = [run_check(check) for check in checks]
    summary = {
        "ok": all(item["ok"] for item in results),
        "base_url": base_url,
        "gate": "phase287-realtime-loading-gate",
        "expected_asset_marker": args.expected_asset_marker,
        "results": results,
        "passed": sum(1 for item in results if item["ok"]),
        "total_run": len(results),
    }
    if args.json_out:
        out = pathlib.Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
