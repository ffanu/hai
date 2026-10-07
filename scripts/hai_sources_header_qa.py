#!/usr/bin/env python3
"""Local QA for X-HAI-Sources header size budget."""

from __future__ import annotations

import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app  # noqa: E402


def main() -> int:
    long_sources = [
        {
            "url": f"https://example.com/{index}/" + ("a" * 2500),
            "title": "Contoh sumber panjang " + ("judul " * 80),
            "snippet": "Ringkasan sumber " + ("sangat panjang " * 120),
            "source": "web",
        }
        for index in range(20)
    ]
    encoded = app._encode_sources_header(long_sources)
    decoded = json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")) if encoded else []
    checks = [
        {
            "name": "header_under_budget",
            "ok": bool(encoded and len(encoded) <= app.SOURCE_HEADER_MAX_BYTES),
            "encoded_bytes": len(encoded),
            "budget": app.SOURCE_HEADER_MAX_BYTES,
        },
        {
            "name": "item_count_limited",
            "ok": 0 < len(decoded) <= app.SOURCE_HEADER_MAX_ITEMS,
            "count": len(decoded),
            "limit": app.SOURCE_HEADER_MAX_ITEMS,
        },
        {
            "name": "url_length_limited",
            "ok": all(len(item.get("url", "")) <= app.SOURCE_HEADER_MAX_URL for item in decoded),
            "max_url": max((len(item.get("url", "")) for item in decoded), default=0),
            "limit": app.SOURCE_HEADER_MAX_URL,
        },
        {
            "name": "snippet_length_limited",
            "ok": all(len(item.get("snippet", "")) <= app.SOURCE_HEADER_MAX_SNIPPET for item in decoded),
            "max_snippet": max((len(item.get("snippet", "")) for item in decoded), default=0),
            "limit": app.SOURCE_HEADER_MAX_SNIPPET,
        },
    ]
    library_encoded = app._encode_sources_header([{
        "title": "Dokumen Library QA",
        "source": "library",
        "snippet": "Cuplikan dari Library tanpa URL publik.",
    }])
    library_decoded = json.loads(base64.urlsafe_b64decode(library_encoded.encode("ascii")).decode("utf-8")) if library_encoded else []
    checks.append({
        "name": "url_less_library_source_allowed",
        "ok": (
            len(library_decoded) == 1
            and library_decoded[0].get("source") == "library"
            and library_decoded[0].get("url") == ""
            and "Library" in library_decoded[0].get("title", "")
        ),
        "decoded": library_decoded,
    })
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
