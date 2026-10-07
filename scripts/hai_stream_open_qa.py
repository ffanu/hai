#!/usr/bin/env python3
"""Local QA for immediate streaming open frames.

The browser consumes chat streams as text chunks, but the backend sends a small
SSE comment frame first so proxies and users get immediate feedback while the AI
engine or image bridge starts. This check verifies the first emitted chunk is the
private HAI control comment for both text and image intent paths.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import app as hai_app


def first_chunk_for(payload: dict) -> str:
    client = hai_app.app.test_client()
    response = client.post(
        "/chat",
        data=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        headers={"Accept": "text/event-stream"},
        buffered=False,
    )
    chunk = next(response.response, b"")
    return chunk.decode("utf-8", "replace")

def chunks_for(payload: dict, count: int) -> list[str]:
    client = hai_app.app.test_client()
    response = client.post(
        "/chat",
        data=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        headers={"Accept": "text/event-stream"},
        buffered=False,
    )
    chunks = []
    for chunk in response.response:
        chunks.append(chunk.decode("utf-8", "replace"))
        if len(chunks) >= count:
            break
    return chunks


def main() -> int:
    original_client = hai_app.openai_client
    original_heartbeat = hai_app.STREAM_HEARTBEAT_SECONDS
    original_image_response = hai_app._image_response_for_prompt
    try:
        # Force the text path to stop after the opening control frame, avoiding
        # dependency on a live upstream engine for this local contract check.
        hai_app.openai_client = None
        checks = []
        hai_app.STREAM_HEARTBEAT_SECONDS = 0.05
        def slow_image_response(_prompt: str):
            time.sleep(0.12)
            return "Pembuatan gambar belum tersedia.", "qa"
        hai_app._image_response_for_prompt = slow_image_response
        for name, payload in [
            ("text_stream_open_frame", {"message": "qa stream open text"}),
            ("image_stream_open_frame", {"message": "buat gambar qa stream open"}),
        ]:
            chunk = first_chunk_for(payload)
            checks.append(
                {
                    "name": name,
                    "ok": chunk == hai_app.STREAM_OPEN_COMMENT,
                    "first_chunk": chunk,
                }
            )
        heartbeat_chunks = chunks_for({"message": "buat gambar qa heartbeat stream"}, 2)
        checks.append(
            {
                "name": "image_stream_heartbeat_before_result",
                "ok": heartbeat_chunks[:2] == [hai_app.STREAM_OPEN_COMMENT, hai_app.STREAM_HEARTBEAT_COMMENT],
                "chunks": heartbeat_chunks,
            }
        )
    finally:
        hai_app.openai_client = original_client
        hai_app.STREAM_HEARTBEAT_SECONDS = original_heartbeat
        hai_app._image_response_for_prompt = original_image_response

    ok = all(item["ok"] for item in checks)
    print(json.dumps({"ok": ok, "passed": sum(1 for item in checks if item["ok"]), "total_run": len(checks), "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
