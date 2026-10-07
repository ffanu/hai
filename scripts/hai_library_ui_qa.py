#!/usr/bin/env python3
"""QA for Harmonika AI Library/RAG UI and server-side grounding.

This locks the next-step product behavior without spending model quota:

- Sidebar exposes Library upload/search/list controls.
- Frontend can call `/api/library/*` for sidebar management.
- Backend `/chat` attaches relevant Library snippets as private per-device
  grounding context and emits URL-less `source:"library"` source metadata.
- Backend library endpoints still isolate documents by device cookie and do
  not expose full stored text in list/search metadata.
"""

from __future__ import annotations

import io
import json
import os
import pathlib
import sys
import tempfile
import base64


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def add(checks: list[dict], name: str, ok: bool, **extra) -> None:
    item = {"name": name, "ok": bool(ok)}
    item.update(extra)
    checks.append(item)


def main() -> int:
    tmp_dir = tempfile.TemporaryDirectory(prefix="hai-library-ui-qa-")
    os.environ["HAI_DATA_DIR"] = tmp_dir.name
    os.environ["HAI_RATE_LIMIT_STORAGE"] = "memory"

    import app as hai_app  # noqa: E402

    hai_app.DATA_DIR = tmp_dir.name
    hai_app.HISTORY_FILE = os.path.join(tmp_dir.name, "history.json")
    hai_app.LIBRARY_FILE = os.path.join(tmp_dir.name, "library.json")
    hai_app.RATE_LIMIT_STORAGE = "memory"

    checks: list[dict] = []
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "scripts.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "styles.css").read_text(encoding="utf-8")

    add(
        checks,
        "template_library_panel",
        all(token in template for token in [
            'id="hai-library-panel"',
            'id="hai-library-search"',
            'id="hai-library-upload"',
            'id="hai-library-grounding-toggle"',
            'id="hai-library-context-toggle"',
            'id="hai-library-list"',
            '?v=20261007-phase325',
        ]),
    )
    add(
        checks,
        "js_library_integration",
        all(token in script for token in [
            "const HAI_LIBRARY_GROUNDING_LIMIT",
            "loadLibraryDocuments",
            "uploadLibraryDocument",
            "deleteLibraryDocument",
            "searchLibraryPanel",
            "scheduleLibraryPanelSearch",
            "haiLibrarySearchResults",
            "searchLibraryForContext",
            "appendLibraryContextToMessageContent",
            "libraryGrounding: haiLibraryGroundingMode",
            "libraryContextMode: haiLibraryContextMode",
            "parseHaiLibraryGroundingHeader",
            "grounding moved server-side",
            "await loadLibraryDocuments()",
            "?v=${HAI_ICON_VERSION}",
            "20261007-phase325",
        ]),
    )
    add(
        checks,
        "css_library_panel",
        all(token in css for token in [
            "Phase 257: Library/RAG sidebar foundation UI",
            ".hai-library-panel",
            ".hai-library-grounding",
            ".hai-library-context",
            ".hai-library-item",
            ".hai-library-delete",
        ]),
    )

    client = hai_app.app.test_client()
    upload = client.post(
        "/api/library/documents",
        data={
            "file": (
                io.BytesIO(b"Dokumen library UI QA. Kode verifikasi: HAI-LIB-UI-257."),
                "hai-library-ui-qa.txt",
            )
        },
        content_type="multipart/form-data",
    )
    upload_json = upload.get_json() or {}
    doc_id = (upload_json.get("document") or {}).get("id")
    add(
        checks,
        "backend_upload_document",
        upload.status_code == 200
        and upload_json.get("ok") is True
        and bool(doc_id)
        and "text" not in (upload_json.get("document") or {}),
        status=upload.status_code,
        payload=upload_json,
    )

    list_response = client.get("/api/library/documents")
    list_json = list_response.get_json() or {}
    first_doc = (list_json.get("documents") or [{}])[0]
    add(
        checks,
        "backend_list_no_full_text",
        list_response.status_code == 200
        and list_json.get("ok") is True
        and list_json.get("count", 0) >= 1
        and "preview" in first_doc
        and "text" not in first_doc,
        status=list_response.status_code,
        payload=list_json,
    )

    search_response = client.post(
        "/api/library/search",
        data=json.dumps({"query": "HAI-LIB-UI-257", "limit": 3}),
        content_type="application/json",
    )
    search_json = search_response.get_json() or {}
    search_results = search_json.get("results") or []
    add(
        checks,
        "backend_search_snippet",
        search_response.status_code == 200
        and search_json.get("ok") is True
        and search_json.get("retrieval", {}).get("mode") == hai_app.LIBRARY_RETRIEVAL_MODE
        and search_json.get("retrieval", {}).get("rerank") == hai_app.LIBRARY_RANKING_MODE
        and search_json.get("retrieval", {}).get("vector_mode") == "private_local_hash_embedding"
        and search_json.get("retrieval", {}).get("semantic_expansion") is True
        and any("HAI-LIB-UI-257" in (item.get("snippet") or "") for item in search_results)
        and all(item.get("retrieval_mode") == hai_app.LIBRARY_RETRIEVAL_MODE for item in search_results)
        and all(item.get("ranking") == hai_app.LIBRARY_RANKING_MODE for item in search_results)
        and all(item.get("semantic_expansion") is True for item in search_results)
        and all(isinstance(item.get("vector_similarity"), (int, float)) for item in search_results)
        and all(isinstance(item.get("chunk_index"), int) for item in search_results)
        and all("embedding" not in item and "vector" not in item for item in search_results)
        and all("text" not in item for item in search_results),
        status=search_response.status_code,
        payload=search_json,
    )

    chat_response = client.post(
        "/chat",
        data=json.dumps({"message": "Apa kode verifikasi HAI-LIB-UI-257 dari Library?", "conversation": []}),
        content_type="application/json",
        headers={"Accept": "text/event-stream"},
    )
    library_header = chat_response.headers.get("X-HAI-Library-Grounding", "")
    try:
        decoded_library_header = json.loads(base64.urlsafe_b64decode(library_header.encode("ascii")).decode("utf-8")) if library_header else {}
    except Exception:
        decoded_library_header = {}
    encoded_sources = chat_response.headers.get("X-HAI-Sources", "")
    try:
        decoded_sources = json.loads(base64.urlsafe_b64decode(encoded_sources.encode("ascii")).decode("utf-8")) if encoded_sources else []
    except Exception:
        decoded_sources = []
    add(
        checks,
        "chat_server_side_library_sources",
        chat_response.status_code == 200
        and decoded_library_header.get("mode") == "auto"
        and decoded_library_header.get("context_mode") == "snippet"
        and decoded_library_header.get("used") is True
        and decoded_library_header.get("count", 0) >= 1
        and any(
            item.get("source") == "library"
            and item.get("url") == ""
            and "HAI-LIB-UI-257" in (item.get("snippet") or "")
            for item in decoded_sources
        ),
        status=chat_response.status_code,
        decoded_library_header=decoded_library_header,
        decoded_sources=decoded_sources,
    )

    chat_full_response = client.post(
        "/chat",
        data=json.dumps({
            "message": "Apa kode verifikasi HAI-LIB-UI-257 dari Library?",
            "conversation": [],
            "libraryContextMode": "full",
        }),
        content_type="application/json",
        headers={"Accept": "text/event-stream"},
    )
    full_header = chat_full_response.headers.get("X-HAI-Library-Grounding", "")
    try:
        decoded_full_header = json.loads(base64.urlsafe_b64decode(full_header.encode("ascii")).decode("utf-8")) if full_header else {}
    except Exception:
        decoded_full_header = {}
    add(
        checks,
        "chat_library_full_context_mode",
        chat_full_response.status_code == 200
        and decoded_full_header.get("context_mode") == "full"
        and decoded_full_header.get("used") is True
        and decoded_full_header.get("context_chars", 0) >= decoded_library_header.get("context_chars", 0),
        status=chat_full_response.status_code,
        decoded_full_header=decoded_full_header,
    )

    chat_off_response = client.post(
        "/chat",
        data=json.dumps({
            "message": "Apa kode verifikasi HAI-LIB-UI-257 dari Library?",
            "conversation": [],
            "libraryGrounding": "off",
        }),
        content_type="application/json",
        headers={"Accept": "text/event-stream"},
    )
    off_header = chat_off_response.headers.get("X-HAI-Library-Grounding", "")
    try:
        decoded_off_header = json.loads(base64.urlsafe_b64decode(off_header.encode("ascii")).decode("utf-8")) if off_header else {}
    except Exception:
        decoded_off_header = {}
    off_sources_header = chat_off_response.headers.get("X-HAI-Sources", "")
    add(
        checks,
        "chat_library_grounding_toggle_off",
        chat_off_response.status_code == 200
        and decoded_off_header.get("mode") == "off"
        and decoded_off_header.get("used") is False
        and not off_sources_header,
        status=chat_off_response.status_code,
        decoded_library_header=decoded_off_header,
        sources_header_present=bool(off_sources_header),
    )

    if doc_id:
        delete_response = client.delete(f"/api/library/documents/{doc_id}")
        delete_json = delete_response.get_json() or {}
        add(
            checks,
            "backend_delete_document",
            delete_response.status_code == 200 and delete_json.get("deleted") is True,
            status=delete_response.status_code,
            payload=delete_json,
        )

    ok = all(item["ok"] for item in checks)
    summary = {
        "ok": ok,
        "checks": checks,
        "passed": sum(1 for item in checks if item["ok"]),
        "total_run": len(checks),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
