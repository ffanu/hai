#!/usr/bin/env python3
"""Validate Harmonika AI server-side engine routing policy.

The public web UI must stay simple: browser calls only `/chat`, while backend
routes internally. Product policy:

- Google Mode is primary for normal Q&A, casual chat/story, general analysis,
  web grounding, and file/image understanding.
- Codex is only for explicit heavy technical/development work and the private
  image-generation bridge. Casual uses of the word "kode" such as promo codes
  must stay on Google Mode. Light technical explanations/questions also stay on
  Google Mode unless the user asks for real implementation/debug/deploy work.
  Clear technical failure symptoms such as 502, force close, crash, or exit
  code are treated as heavy technical work even when phrased as a complaint.

This script intentionally tests the pure routing function so it is fast,
deterministic, and does not consume chat/image quota.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as hai_app  # noqa: E402


CASES = [
    {
        "name": "general_business_idea",
        "message": "Promosi apa yang bagus untuk usaha makanan rumahan?",
        "attachments": [],
        "expected": "google",
    },
    {
        "name": "casual_story_friend",
        "message": "Saya lagi sedih, temani cerita sebentar ya.",
        "attachments": [],
        "expected": "google",
    },
    {
        "name": "simple_api_question",
        "message": "Apa itu endpoint API? Jelaskan sederhana untuk orang awam.",
        "attachments": [],
        "expected": "google",
    },
    {
        "name": "light_technical_question",
        "message": "Apa itu bug dalam aplikasi? Jelaskan singkat tanpa debugging.",
        "attachments": [],
        "expected": "google",
    },
    {
        "name": "light_api_analysis",
        "message": "Analisa manfaat API untuk usaha kecil, jangan buat kode.",
        "attachments": [],
        "expected": "google",
    },
    {
        "name": "general_analysis",
        "message": "Analisa 3 ide promosi makanan rumahan yang cocok untuk ibu rumah tangga.",
        "attachments": [],
        "expected": "google",
    },
    {
        "name": "promo_code_not_programming",
        "message": "Buatkan kode promo diskon yang menarik untuk pelanggan makanan rumahan.",
        "attachments": [],
        "expected": "google",
    },
    {
        "name": "file_understanding",
        "message": "Tolong jelaskan isi lampiran ini dengan bahasa sederhana.",
        "attachments": ["file_demo"],
        "expected": "google",
    },
    {
        "name": "file_log_understanding_not_debug",
        "message": "Baca file log terlampir dan ringkas isinya dulu, jangan debug.",
        "attachments": ["log_file_demo"],
        "expected": "google",
    },
    {
        "name": "image_understanding",
        "message": "Baca gambar ini dan jelaskan apa yang terlihat.",
        "attachments": ["image_demo"],
        "expected": "google",
    },
    {
        "name": "explicit_codex",
        "message": "Codex tolong audit bug backend Flask ini.",
        "attachments": [],
        "expected": "codex",
    },
    {
        "name": "technical_debug_action",
        "message": "Tolong debug error backend Flask ini dari log berikut.",
        "attachments": [],
        "expected": "codex",
    },
    {
        "name": "technical_build_action",
        "message": "Buatkan endpoint API Flask untuk upload file dan unit test-nya.",
        "attachments": [],
        "expected": "codex",
    },
    {
        "name": "heavy_backend_fix_action",
        "message": "Perbaiki bug 500 di backend Flask ini, audit log, lalu buat patch kodenya.",
        "attachments": [],
        "expected": "codex",
    },
    {
        "name": "technical_complaint_nginx_502",
        "message": "Nginx 502 bad gateway, gimana?",
        "attachments": [],
        "expected": "codex",
    },
    {
        "name": "technical_complaint_android_force_close",
        "message": "Aplikasi Android saya force close terus saat dibuka.",
        "attachments": [],
        "expected": "codex",
    },
    {
        "name": "technical_complaint_docker_exit_code",
        "message": "Docker container saya exit code 137.",
        "attachments": [],
        "expected": "codex",
    },
    {
        "name": "technical_complaint_server_down",
        "message": "Server produksi down, log penuh error 502.",
        "attachments": [],
        "expected": "codex",
    },
    {
        "name": "technical_complaint_database_slow",
        "message": "Database saya lambat sekali akhir-akhir ini.",
        "attachments": [],
        "expected": "codex",
    },
    {
        "name": "stacktrace",
        "message": "Traceback (most recent call last):\n  File \"app.py\", line 17\nValueError: bad input",
        "attachments": [],
        "expected": "codex",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out")
    args = parser.parse_args()

    # Normalize routing config for deterministic QA, independent of the shell
    # that runs this script. These are the production values expected by
    # `/api/capabilities`.
    hai_app.MEMBER_AI_CHAT_MODE = "google"
    hai_app.MEMBER_AI_CODEX_MODE = "codex"
    hai_app.MEMBER_AI_IMAGE_MODE = "codex"
    hai_app.MEMBER_AI_ROUTE_CODEX = True

    checks = []
    for case in CASES:
        actual = hai_app._member_ai_route_mode(case["message"], case["attachments"])
        checks.append({
            "name": case["name"],
            "ok": actual == case["expected"],
            "expected": case["expected"],
            "actual": actual,
        })

    document_payload = hai_app._member_ai_text_payload(
        "Baca lampiran dan sebutkan kode verifikasi saja.\n\n"
        "[Document: hai-ui-attachment.txt]\n\n"
        "Dokumen QA Harmonika AI. Kode verifikasi: HAI-UI-ATTACH-ROUTING-QA",
        [],
    )
    checks.append({
        "name": "member_ai_payload_latest_document_isolation",
        "ok": (
            "Instruksi isolasi untuk chat web publik" in document_payload
            and "Abaikan riwayat/session internal backend lain" in document_payload
            and "[Document: hai-ui-attachment.txt]" in document_payload
            and "HAI-UI-ATTACH-ROUTING-QA" in document_payload
        ),
        "expected": "latest payload isolated and document-preserving",
        "actual": document_payload[:260],
    })

    original_reset_flag = hai_app.MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST
    original_token_for_chat = hai_app.MEMBER_AI_TOKEN
    original_chat_bridge = hai_app.MEMBER_AI_CHAT_BRIDGE
    original_chat_mode = hai_app.MEMBER_AI_CHAT_MODE
    original_stream_chat = hai_app._member_ai_stream_chat_payload
    original_delete = hai_app.httpx.delete
    chat_calls: list[dict[str, Any]] = []

    class FakeDeleteResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    def fake_delete(url: str, *, headers: dict[str, str] | None = None, timeout: float | None = None, **_: Any) -> FakeDeleteResponse:
        chat_calls.append({"kind": "reset", "url": url, "headers": headers or {}, "timeout": timeout})
        return FakeDeleteResponse()

    def fake_stream(payload: dict[str, Any], emit: Any) -> bool:
        chat_calls.append({"kind": "stream", "payload": dict(payload)})
        emit("OK")
        return True

    try:
        hai_app.MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST = True
        hai_app.MEMBER_AI_TOKEN = "qa-token"
        hai_app.MEMBER_AI_CHAT_BRIDGE = True
        hai_app.MEMBER_AI_CHAT_MODE = "google"
        hai_app.httpx.delete = fake_delete
        hai_app._member_ai_stream_chat_payload = fake_stream
        emitted_chunks: list[str] = []
        emitted = hai_app._member_ai_emit_chat(
            "Baca lampiran terbaru.\n\n[Document: qa.txt]\n\nKode QA-SESSION-LOCK",
            [],
            emitted_chunks.append,
        )
    finally:
        hai_app.MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST = original_reset_flag
        hai_app.MEMBER_AI_TOKEN = original_token_for_chat
        hai_app.MEMBER_AI_CHAT_BRIDGE = original_chat_bridge
        hai_app.MEMBER_AI_CHAT_MODE = original_chat_mode
        hai_app.httpx.delete = original_delete
        hai_app._member_ai_stream_chat_payload = original_stream_chat

    checks.append({
        "name": "member_ai_chat_bridge_resets_shared_session_before_stream",
        "ok": (
            emitted is True
            and emitted_chunks == ["OK"]
            and len(chat_calls) >= 2
            and chat_calls[0]["kind"] == "reset"
            and chat_calls[0]["url"].endswith("/chat/session")
            and chat_calls[1]["kind"] == "stream"
            and chat_calls[1]["payload"].get("mode") == "google"
            and "QA-SESSION-LOCK" in chat_calls[1]["payload"].get("message", "")
        ),
        "expected": "shared member-AI web bridge resets session before streaming latest payload",
        "actual": chat_calls,
    })

    original_token = hai_app.MEMBER_AI_TOKEN
    original_bridge = hai_app.MEMBER_AI_IMAGE_BRIDGE
    original_base_url = hai_app.MEMBER_AI_BASE_URL
    original_post = hai_app.httpx.post
    image_calls: list[dict[str, Any]] = []

    class FakeImageResponse:
        def __init__(self, status_code: int, body: dict[str, Any]):
            self.status_code = status_code
            self._body = body
            self.request = hai_app.httpx.Request("POST", "https://chat.harmonika.id/v1/member-ai/images/generations")

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise hai_app.httpx.HTTPStatusError("strict image body", request=self.request, response=self)

        def json(self) -> dict[str, Any]:
            return self._body

    def fake_image_post(url: str, *, headers: dict[str, str] | None = None, json: dict[str, Any] | None = None, timeout: float | None = None, **_: Any) -> FakeImageResponse:
        image_calls.append({"url": url, "headers": headers or {}, "json": json or {}, "timeout": timeout})
        if len(image_calls) == 1:
            return FakeImageResponse(400, {"ok": False, "error": "invalid_request"})
        return FakeImageResponse(200, {
            "ok": True,
            "images": [{
                "file_id": "qa-image-codex-mode",
                "mime_type": "image/png",
                "width": 800,
                "height": 500,
                "size_bytes": 12345,
                "status": "ready",
                "source_prompt": "QA image",
                "requested_size": "800x500",
            }],
        })

    try:
        hai_app.MEMBER_AI_TOKEN = "qa-token"
        hai_app.MEMBER_AI_IMAGE_BRIDGE = True
        hai_app.MEMBER_AI_BASE_URL = "https://chat.harmonika.id/v1/member-ai"
        hai_app.httpx.post = fake_image_post
        images = hai_app._member_ai_generate_image("Buat gambar QA routing", "800x500", 1)
    finally:
        hai_app.MEMBER_AI_TOKEN = original_token
        hai_app.MEMBER_AI_IMAGE_BRIDGE = original_bridge
        hai_app.MEMBER_AI_BASE_URL = original_base_url
        hai_app.httpx.post = original_post

    checks.append({
        "name": "image_generation_codex_mode_signal_with_strict_body_retry",
        "ok": (
            len(image_calls) == 2
            and image_calls[0]["json"].get("mode") == "codex"
            and image_calls[0]["headers"].get("X-Harmonika-Mode") == "codex"
            and image_calls[0]["headers"].get("X-Harmonika-Task") == "image_generation"
            and "mode" not in image_calls[1]["json"]
            and image_calls[1]["headers"].get("X-Harmonika-Mode") == "codex"
            and images
            and images[0].get("file_id") == "qa-image-codex-mode"
        ),
        "expected": "image creation asks member-AI for codex mode, retries strict v1 body safely",
        "actual": {
            "calls": len(image_calls),
            "first_payload_keys": sorted(image_calls[0]["json"].keys()) if image_calls else [],
            "retry_payload_keys": sorted(image_calls[1]["json"].keys()) if len(image_calls) > 1 else [],
            "first_mode_header": image_calls[0]["headers"].get("X-Harmonika-Mode") if image_calls else None,
        },
    })

    ok = all(item["ok"] for item in checks)
    summary = {
        "ok": ok,
        "policy": {
            "default_mode": "google",
            "primary_answer_mode": "google",
            "question_analysis_story_mode": "google",
            "answer_mode": "google",
            "question_mode": "google",
            "analysis_mode": "google",
            "conversation_mode": "google",
            "story_companion_mode": "google",
            "file_input_mode": "google",
            "image_input_mode": "google",
            "attachment_understanding_mode": "google",
            "image_creation_task_mode": "codex",
            "image_creation_request_mode": "codex",
            "web_reference_mode": "google",
            "technical_task_mode": "codex",
            "heavy_task_mode": "codex",
            "code_analysis_mode": "codex",
            "codex_policy": "heavy_technical_only",
            "codex_handoff_policy": "only_for_explicit_heavy_technical_symptom_or_private_image_creation",
        },
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
