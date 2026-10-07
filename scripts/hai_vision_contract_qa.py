#!/usr/bin/env python3
"""Vision/image input contract QA for hai.harmonika.id.

The check sends a tiny generated red PNG through the same multimodal `/chat`
payload used by the web client. If `/api/capabilities` advertises
`image_input=true`, the assistant must answer that the dominant color is red
without leaking base64, data URLs, terminal text, or legacy public media links.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


BASE64_LEAK_RE = re.compile(r"data:image/|iVBOR|base64", re.I)
TERMINAL_LEAK_RE = re.compile(r"(\$ mkdir|mkdir -p|←\s*Write|Wrote file successfully|file manager|/data/|/srv/|/tmp/|terminal ubuntu)", re.I)
PUBLIC_MEDIA_RE = re.compile(r"https?://(?:chat|hai)\.harmonika\.id/(?:media|download|downloads?|files?)/[^\s<)]+", re.I)
VISION_UNAVAILABLE_RE = re.compile(r"(tidak bisa|belum bisa|cannot|can't|unable).{0,80}(melihat|membaca|view|see|image|gambar)", re.I)
RED_RE = re.compile(r"\b(merah|red)\b", re.I)


def png_data_url(width: int = 32, height: int = 32, rgb: tuple[int, int, int] = (255, 0, 0)) -> str:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


class Client:
    def __init__(self, base_url: str, timeout: float = 80.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(self, method: str, path: str, body: Any | None = None, headers: dict[str, str] | None = None):
        data = None
        req_headers = dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        req_headers.setdefault("Accept", "application/json")
        req_headers.setdefault("User-Agent", "Mozilla/5.0 HAI-Vision-Contract-QA/1.0")
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=req_headers, method=method)
        started = time.time()
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
                return {
                    "status": response.status,
                    "headers": dict(response.headers.items()),
                    "body": raw,
                    "duration_ms": int((time.time() - started) * 1000),
                }
        except urllib.error.HTTPError as error:
            raw = error.read()
            return {
                "status": error.code,
                "headers": dict(error.headers.items()),
                "body": raw,
                "duration_ms": int((time.time() - started) * 1000),
            }


def decode_json(result: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(result["body"].decode("utf-8"))
    except Exception as exc:
        return {"_json_error": str(exc), "_raw": result["body"][:500].decode("utf-8", "replace")}


def run(base_url: str, json_out: str | None = None) -> int:
    client = Client(base_url)
    checks: list[dict[str, Any]] = []

    capabilities_result = client.request("GET", "/api/capabilities")
    capabilities = decode_json(capabilities_result)
    features = capabilities.get("features") if isinstance(capabilities.get("features"), dict) else {}
    limits = capabilities.get("limits") if isinstance(capabilities.get("limits"), dict) else {}
    accepted = limits.get("accepted_mime_types") if isinstance(limits.get("accepted_mime_types"), list) else []
    image_input = bool(features.get("image_input"))
    mime_ok = all(mime in accepted for mime in ("image/png", "image/jpeg", "image/webp"))
    checks.append({
        "name": "capabilities_vision_contract",
        "ok": bool(capabilities_result["status"] == 200 and capabilities.get("ok") is True and (not image_input or mime_ok)),
        "status": capabilities_result["status"],
        "image_input": image_input,
        "mime_ok": mime_ok,
        "accepted_image_mimes": [mime for mime in accepted if str(mime).startswith("image/")],
    })

    if not image_input:
        summary = {
            "ok": all(check["ok"] for check in checks),
            "base_url": base_url.rstrip("/"),
            "image_input": False,
            "skipped": True,
            "reason": "image_input_disabled",
            "passed": sum(1 for check in checks if check["ok"]),
            "total_run": len(checks),
            "checks": checks,
        }
        if json_out:
            Path(json_out).parent.mkdir(parents=True, exist_ok=True)
            Path(json_out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["ok"] else 1

    payload = {
        "message": [
            {"type": "text", "text": "Gambar ini warna dominannya apa? Jawab satu kata dalam bahasa Indonesia."},
            {"type": "image_url", "image_url": {"url": png_data_url()}},
        ],
        "conversation": [],
    }
    chat_result = client.request("POST", "/chat", payload, headers={"Accept": "text/event-stream"})
    text = chat_result["body"].decode("utf-8", "replace")
    headers = {str(k).lower(): v for k, v in chat_result.get("headers", {}).items()}
    text_without_think = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S).strip()
    checks.append({
        "name": "chat_vision_red_png_contract",
        "ok": bool(
            chat_result["status"] == 200
            and headers.get("x-hai-intent") == "text"
            and RED_RE.search(text_without_think)
            and BASE64_LEAK_RE.search(text) is None
            and TERMINAL_LEAK_RE.search(text) is None
            and PUBLIC_MEDIA_RE.search(text) is None
            and VISION_UNAVAILABLE_RE.search(text) is None
        ),
        "status": chat_result["status"],
        "duration_ms": chat_result["duration_ms"],
        "x_hai_intent": headers.get("x-hai-intent"),
        "answer": text_without_think[:240],
        "has_red_answer": bool(RED_RE.search(text_without_think)),
        "base64_leak": bool(BASE64_LEAK_RE.search(text)),
        "terminal_leak": bool(TERMINAL_LEAK_RE.search(text)),
        "public_media_leak": bool(PUBLIC_MEDIA_RE.search(text)),
        "vision_unavailable": bool(VISION_UNAVAILABLE_RE.search(text)),
    })

    summary = {
        "ok": all(check["ok"] for check in checks),
        "base_url": base_url.rstrip("/"),
        "image_input": image_input,
        "passed": sum(1 for check in checks if check["ok"]),
        "total_run": len(checks),
        "checks": checks,
    }
    if json_out:
        Path(json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(json_out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--json-out")
    args = parser.parse_args()
    return run(args.base_url, args.json_out)


if __name__ == "__main__":
    sys.exit(main())
