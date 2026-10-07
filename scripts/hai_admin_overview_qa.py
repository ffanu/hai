#!/usr/bin/env python3
"""QA for aggregate-only admin observability endpoint.

This endpoint is intentionally safe to expose as a read-only production
overview: it must return counts and modes only, never chat content, document
text, device identifiers, or secret-looking strings.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hai-admin-overview-qa-") as data_dir:
        os.environ["HAI_DATA_DIR"] = data_dir
        os.environ["HAI_RATE_LIMIT_FILE"] = str(pathlib.Path(data_dir) / "rate-limits.json")
        os.environ["HAI_REALTIME_EVENT_DIR"] = str(pathlib.Path(data_dir) / "realtime-events")
        os.environ["HAI_RATE_LIMIT_STORAGE"] = "file"

        secret_text = "SECRET_SHOULD_NOT_LEAK_ADMIN_OVERVIEW"
        chat_text = "CHAT_CONTENT_SHOULD_NOT_LEAK_ADMIN_OVERVIEW"
        doc_text = "DOCUMENT_TEXT_SHOULD_NOT_LEAK_ADMIN_OVERVIEW"
        device_id = "device-qa-should-not-leak"

        pathlib.Path(os.environ["HAI_REALTIME_EVENT_DIR"]).mkdir(parents=True, exist_ok=True)
        history_file = pathlib.Path(data_dir) / "chatwebui-history.json"
        library_file = pathlib.Path(data_dir) / "rag-library.json"
        pathlib.Path(history_file).write_text(json.dumps({
            "version": 1,
            "devices": {
                device_id: {
                    "history": {
                        "chats": [
                            {
                                "id": "chat-qa",
                                "title": secret_text,
                                "messages": [
                                    {"role": "user", "content": chat_text, "attachments": [{"name": "secret.pdf"}]},
                                    {"role": "assistant", "content": "jawaban qa", "sources": [{"title": "Sumber", "url": "https://example.com"}], "artifacts": [{"type": "image"}]},
                                ],
                                "updated": 9999999999999,
                            }
                        ]
                    }
                }
            },
        }), encoding="utf-8")
        pathlib.Path(library_file).write_text(json.dumps({
            "version": 1,
            "devices": {
                device_id: {
                    "documents": [
                        {
                            "id": "lib-qa",
                            "name": "dokumen-rahasia.txt",
                            "text": doc_text,
                            "text_chars": len(doc_text),
                            "chunks": [{"text": doc_text, "terms": {"secret": 1}}],
                        }
                    ]
                }
            },
        }), encoding="utf-8")
        pathlib.Path(os.environ["HAI_RATE_LIMIT_FILE"]).write_text(json.dumps({
            "version": 1,
            "buckets": {"chat:qa": [1, 2, 3]},
        }), encoding="utf-8")
        pathlib.Path(os.environ["HAI_REALTIME_EVENT_DIR"], "resp_qa.json").write_text("{}", encoding="utf-8")

        from app import app  # noqa: WPS433 - imported after env setup intentionally

        client = app.test_client()
        admin_response = client.get("/admin")
        admin_html = admin_response.get_data(as_text=True)
        response = client.get("/api/admin/overview")
        payload = response.get_json() or {}
        body = response.get_data(as_text=True)

        checks = []

        def add(name: str, ok: bool, **extra) -> None:
            checks.append({"name": name, "ok": bool(ok), **extra})

        privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
        add(
            "http_json_ok",
            response.status_code == 200 and payload.get("ok") is True and payload.get("service") == "harmonika-chat-webui",
            status=response.status_code,
        )
        add(
            "admin_dashboard_html",
            admin_response.status_code == 200
            and "/api/admin/overview" in admin_html
            and "aggregate-only" in admin_html
            and "Analytics aggregate" in admin_html
            and "admin-overview.js?v=20261007-phase322" in admin_html
            and "<script>" not in admin_html
            and " onclick=" not in admin_html.lower(),
            status=admin_response.status_code,
        )
        add(
            "privacy_flags",
            privacy.get("aggregate_only") is True
            and privacy.get("no_chat_content") is True
            and privacy.get("no_document_text") is True
            and privacy.get("no_device_ids") is True
            and privacy.get("no_secrets") is True,
            privacy=privacy,
        )
        add(
            "aggregate_counts",
            payload.get("history", {}).get("devices") == 1
            and payload.get("history", {}).get("chats") == 1
            and payload.get("history", {}).get("messages") == 2
            and payload.get("library", {}).get("documents") == 1
            and payload.get("library", {}).get("indexed_chunks") == 1
            and payload.get("realtime", {}).get("event_files") == 1
            and payload.get("rate_limit", {}).get("bucket_count") == 1,
            history=payload.get("history"),
            library=payload.get("library"),
            realtime=payload.get("realtime"),
            rate_limit=payload.get("rate_limit"),
        )
        analytics = payload.get("analytics") if isinstance(payload.get("analytics"), dict) else {}
        add(
            "analytics_aggregate_counts",
            analytics.get("mode") == "aggregate_only_no_content"
            and analytics.get("active_chats_24h") == 1
            and analytics.get("active_chats_7d") == 1
            and analytics.get("user_messages") == 1
            and analytics.get("assistant_messages") == 1
            and analytics.get("attachment_messages") == 1
            and analytics.get("image_artifacts") == 1
            and analytics.get("source_references") == 1
            and analytics.get("avg_messages_per_chat") == 2,
            analytics=analytics,
        )
        leaked = [
            needle for needle in [secret_text, chat_text, doc_text, device_id]
            if needle in body or needle in admin_html
        ]
        add("no_sensitive_leak", not leaked, leaked=leaked)

        summary = {
            "ok": all(item["ok"] for item in checks),
            "checks": checks,
            "passed": sum(1 for item in checks if item["ok"]),
            "total_run": len(checks),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
