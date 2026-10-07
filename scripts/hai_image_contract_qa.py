#!/usr/bin/env python3
"""Contract QA for Harmonika AI image-generation safety.

This verifies the public web contract, not artwork quality. The invariant is
simple: image intent must never leak legacy terminal/file-manager output or
public /media and /download URLs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any


PROMPT = "Buat gambar poster sederhana kota solarpunk senja untuk QA kontrak gambar Harmonika AI."

TERMINAL_LEAK_RE = re.compile(
    r"(\$ mkdir|mkdir -p|←\s*Write|Wrote file successfully|file manager|/data/|/srv/|/tmp/|terminal ubuntu)",
    re.I,
)
PUBLIC_MEDIA_RE = re.compile(
    r"https?://(?:chat|hai)\.harmonika\.id/(?:media|download|downloads?|files?)/[^\s<)]+",
    re.I,
)
LEGACY_MARKDOWN_MEDIA_RE = re.compile(
    r"!\[[^\]]*\]\([^)]*(?:/media/|/download/|/downloads?/|/files?/)[^)]*\)",
    re.I,
)


class Client:
    def __init__(self, base_url: str, timeout: float = 150.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))

    def request(self, method: str, path: str, body: Any | None = None, headers: dict[str, str] | None = None):
        data = None
        req_headers = dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        req_headers.setdefault("Accept", "application/json")
        req_headers.setdefault("User-Agent", "Mozilla/5.0 HAI-Image-Contract-QA/1.0")
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=req_headers, method=method)
        started = time.time()
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
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


def safe_text(text: str) -> dict[str, Any]:
    return {
        "no_terminal_leak": TERMINAL_LEAK_RE.search(text) is None,
        "no_public_media_url": PUBLIC_MEDIA_RE.search(text) is None,
        "no_legacy_markdown_media": LEGACY_MARKDOWN_MEDIA_RE.search(text) is None,
        "has_private_preview_or_svg_or_disabled": bool(
            "/api/files/" in text
            or "```svg" in text
            or "<svg" in text
            or "Pembuatan gambar belum tersedia" in text
        ),
    }


def run(base_url: str, json_out: str | None = None) -> int:
    client = Client(base_url)
    checks: list[dict[str, Any]] = []

    # Production image quotas are scoped by Harmonika device cookie and fall
    # back to IP only before that cookie exists. Bootstrap a fresh QA device
    # first so repeatable contract checks do not share the public IP bucket.
    client.request("GET", "/api/history")

    capabilities_result = client.request("GET", "/api/capabilities")
    capabilities = decode_json(capabilities_result)
    features = capabilities.get("features") if isinstance(capabilities.get("features"), dict) else {}
    limits = capabilities.get("limits") if isinstance(capabilities.get("limits"), dict) else {}
    image_meta = capabilities.get("image_generation") if isinstance(capabilities.get("image_generation"), dict) else {}
    image_enabled = bool(features.get("image_generation"))
    mode = str(image_meta.get("mode") or "unknown")
    public_urls = image_meta.get("public_urls")

    checks.append({
        "name": "capabilities_image_contract",
        "ok": bool(
            capabilities_result["status"] == 200
            and capabilities.get("ok") is True
            and isinstance(features, dict)
            and isinstance(limits, dict)
            and public_urls is False
        ),
        "status": capabilities_result["status"],
        "image_enabled": image_enabled,
        "mode": mode,
        "public_urls": public_urls,
        "features": {
            key: features.get(key)
            for key in (
                "image_generation",
                "image_generation_sse",
                "image_preview",
                "image_download",
                "raster_image_generation",
                "member_ai_image_bridge",
            )
        },
    })

    empty_result = client.request("POST", "/api/images/generations", {"prompt": ""})
    empty_json = decode_json(empty_result)
    checks.append({
        "name": "image_generation_empty_prompt_error",
        "ok": bool(
            empty_result["status"] in (400, 503)
            and empty_json.get("ok") is False
            and empty_json.get("error") in ("invalid_prompt", "image_generation_disabled")
            and PUBLIC_MEDIA_RE.search(json.dumps(empty_json, ensure_ascii=False)) is None
        ),
        "status": empty_result["status"],
        "error": empty_json.get("error"),
        "message": empty_json.get("message"),
    })

    create_result = client.request("POST", "/api/images/generations", {"prompt": PROMPT, "count": 1, "size": "800x500"})
    create_json = decode_json(create_result)
    create_text = json.dumps(create_json, ensure_ascii=False)
    create_safe = safe_text(create_text)
    if image_enabled:
        has_svg_artifact = bool(create_json.get("artifact") and "svg" in json.dumps(create_json.get("artifact"), ensure_ascii=False).lower())
        images = create_json.get("images") if isinstance(create_json.get("images"), list) else []
        has_private_images = bool(images and all(isinstance(item, dict) and item.get("file_id") for item in images))
        create_ok = bool(
            create_result["status"] == 200
            and create_json.get("ok") is True
            and create_json.get("status") == "completed"
            and (has_svg_artifact or has_private_images)
            and all(create_safe.values())
        )
    else:
        create_ok = bool(
            create_result["status"] == 503
            and create_json.get("ok") is False
            and create_json.get("error") == "image_generation_disabled"
            and create_safe["no_terminal_leak"]
            and create_safe["no_public_media_url"]
            and create_safe["no_legacy_markdown_media"]
        )
    checks.append({
        "name": "image_generation_create_contract",
        "ok": create_ok,
        "status": create_result["status"],
        "mode": create_json.get("mode"),
        "error": create_json.get("error"),
        "has_artifact": bool(create_json.get("artifact")),
        "images_count": len(create_json.get("images") or []),
        **create_safe,
    })

    preview_checked = False
    preview_ok = True
    if image_enabled and isinstance(create_json.get("images"), list) and create_json["images"]:
        first_image = create_json["images"][0]
        file_id = first_image.get("file_id") if isinstance(first_image, dict) else ""
        if file_id:
            preview_checked = True
            preview_result = client.request("GET", f"/api/files/{file_id}/preview", headers={"Accept": "image/*"})
            download_result = client.request("GET", f"/api/files/{file_id}/download", headers={"Accept": "image/*,application/octet-stream"})
            preview_type = (preview_result.get("headers") or {}).get("Content-Type") or (preview_result.get("headers") or {}).get("content-type") or ""
            download_type = (download_result.get("headers") or {}).get("Content-Type") or (download_result.get("headers") or {}).get("content-type") or ""
            preview_ok = bool(
                preview_result["status"] == 200
                and download_result["status"] == 200
                and str(preview_type).startswith("image/")
                and str(download_type).startswith("image/")
                and len(preview_result["body"]) > 100
                and TERMINAL_LEAK_RE.search(preview_result["body"][:500].decode("utf-8", "replace")) is None
            )
            checks.append({
                "name": "image_generation_file_preview_download",
                "ok": preview_ok,
                "status_preview": preview_result["status"],
                "status_download": download_result["status"],
                "preview_type": preview_type,
                "download_type": download_type,
                "preview_bytes": len(preview_result["body"]),
                "download_bytes": len(download_result["body"]),
            })

    bogus_preview_result = client.request("GET", "/api/files/local-svg-bogus/preview", headers={"Accept": "application/json"})
    bogus_download_result = client.request("GET", "/api/files/local-svg-bogus/download", headers={"Accept": "application/json"})
    bogus_preview_json = decode_json(bogus_preview_result)
    bogus_download_json = decode_json(bogus_download_result)
    checks.append({
        "name": "image_generation_unknown_local_file_404",
        "ok": bool(
            bogus_preview_result["status"] == 404
            and bogus_download_result["status"] == 404
            and bogus_preview_json.get("error") == "file_not_found"
            and bogus_download_json.get("error") == "file_not_found"
        ),
        "status_preview": bogus_preview_result["status"],
        "status_download": bogus_download_result["status"],
        "preview_error": bogus_preview_json.get("error"),
        "download_error": bogus_download_json.get("error"),
    })

    chat_result = client.request("POST", "/chat", {"message": PROMPT, "conversation": []}, headers={"Accept": "text/event-stream"})
    chat_text = chat_result["body"].decode("utf-8", "replace")
    chat_safe = safe_text(chat_text)
    headers = {str(k).lower(): v for k, v in chat_result.get("headers", {}).items()}
    checks.append({
        "name": "chat_image_intent_stream_contract",
        "ok": bool(
            chat_result["status"] == 200
            and headers.get("x-hai-intent") == "image"
            and all(chat_safe.values())
        ),
        "status": chat_result["status"],
        "x_hai_intent": headers.get("x-hai-intent"),
        "x_hai_artifact_mode": headers.get("x-hai-artifact-mode"),
        "sample": chat_text[:500],
        **chat_safe,
    })

    summary = {
        "ok": all(check["ok"] for check in checks),
        "base_url": base_url.rstrip("/"),
        "image_enabled": image_enabled,
        "mode": mode,
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
