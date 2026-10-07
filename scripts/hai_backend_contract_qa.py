#!/usr/bin/env python3
"""Backend contract smoke checks for public HAI endpoints.

This intentionally avoids successful model/image generation calls. The checks
exercise malformed request handling so production regressions fail fast without
spending model quota.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def post_json(base_url: str, path: str, payload: dict, timeout: float = 8.0) -> tuple[int, dict, str]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 HAI-Backend-Contract-QA/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", "replace")
        status = error.code
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {}
    return status, parsed, raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://hai.harmonika.id")
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    malformed_cases = [
        {
            "name": "chat_conversation_content_object",
            "path": "/chat",
            "payload": {"message": "hai", "conversation": [{"role": "assistant", "content": {"raw": "x"}}]},
        },
        {
            "name": "chat_conversation_missing_role",
            "path": "/chat",
            "payload": {"message": "hai", "conversation": [{"content": "tanpa role"}]},
        },
        {
            "name": "continue_conversation_content_object",
            "path": "/continue_generation",
            "payload": {"conversation": [{"role": "assistant", "content": {"raw": "x"}}]},
        },
    ]

    results = []
    ok = True
    for case in malformed_cases:
        status, parsed, raw = post_json(args.base_url, case["path"], case["payload"], args.timeout)
        case_ok = (
            status == 400
            and parsed.get("ok") is False
            and parsed.get("error") == "invalid_conversation"
            and "text/html" not in raw.lower()
        )
        results.append({
            "name": case["name"],
            "ok": case_ok,
            "status": status,
            "error": parsed.get("error"),
            "message": parsed.get("message"),
            "detail": parsed.get("detail"),
        })
        ok = ok and case_ok

    payload = {
        "ok": ok,
        "base_url": args.base_url.rstrip("/"),
        "passed": sum(1 for item in results if item["ok"]),
        "total_run": len(results),
        "results": results,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
