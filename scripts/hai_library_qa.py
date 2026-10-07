#!/usr/bin/env python3
"""QA for Harmonika AI per-device document library foundation."""

from __future__ import annotations

import io
import json
import os
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    tmp_dir = tempfile.TemporaryDirectory(prefix="hai-library-qa-")
    os.environ["HAI_DATA_DIR"] = tmp_dir.name
    os.environ["HAI_RATE_LIMIT_STORAGE"] = "memory"

    import app as hai_app  # noqa: E402

    hai_app.DATA_DIR = tmp_dir.name
    hai_app.HISTORY_FILE = os.path.join(tmp_dir.name, "history.json")
    hai_app.LIBRARY_FILE = os.path.join(tmp_dir.name, "library.json")
    hai_app.RATE_LIMIT_STORAGE = "memory"

    client = hai_app.app.test_client()
    checks = []

    def add(name: str, ok: bool, **extra) -> None:
        item = {"name": name, "ok": bool(ok)}
        item.update(extra)
        checks.append(item)

    upload = client.post(
        "/api/library/documents",
        data={
            "file": (
                io.BytesIO(b"Dokumen QA library. Kode rahasia RAG-ALFA-255. Topik: instalasi router harmonika."),
                "library-qa.txt",
            )
        },
        content_type="multipart/form-data",
    )
    upload_json = upload.get_json(silent=True) or {}
    doc = upload_json.get("document") if isinstance(upload_json.get("document"), dict) else {}
    doc_id = doc.get("id")
    add(
        "upload_document",
        upload.status_code == 200
        and upload_json.get("ok") is True
        and isinstance(doc_id, str)
        and doc.get("name") == "library-qa.txt"
        and "text_chars" in doc
        and "RAG-ALFA-255" in (doc.get("preview") or ""),
        status=upload.status_code,
        body=upload_json,
    )

    listing = client.get("/api/library/documents")
    listing_json = listing.get_json(silent=True) or {}
    add(
        "list_documents_same_device",
        listing.status_code == 200
        and listing_json.get("ok") is True
        and listing_json.get("count") == 1
        and listing_json.get("documents", [{}])[0].get("id") == doc_id,
        status=listing.status_code,
        body=listing_json,
    )
    with hai_app._library_store_lock():
        private_store = hai_app._load_library_store()
    private_docs = []
    for device_record in (private_store.get("devices", {}) or {}).values():
        if isinstance(device_record, dict):
            private_docs.extend(device_record.get("documents", []) if isinstance(device_record.get("documents"), list) else [])
    private_doc = next((item for item in private_docs if item.get("id") == doc_id), {})
    private_chunks = private_doc.get("chunks") if isinstance(private_doc.get("chunks"), list) else []
    public_doc = (listing_json.get("documents") or [{}])[0]
    add(
        "private_hybrid_vector_chunk_index_stored_not_public",
        bool(private_chunks)
        and private_doc.get("index_mode") == hai_app.LIBRARY_INDEX_MODE
        and private_doc.get("ranking_mode") == hai_app.LIBRARY_RANKING_MODE
        and isinstance(private_chunks[0].get("vector"), dict)
        and isinstance(private_chunks[0].get("embedding"), list)
        and len(private_chunks[0].get("embedding") or []) == hai_app.LIBRARY_VECTOR_DIMS
        and "chunks" not in public_doc
        and "embedding" not in public_doc
        and "text" not in public_doc,
        private_chunk_count=len(private_chunks),
        first_private_chunk={k: private_chunks[0].get(k) for k in ["index", "start", "vector", "embedding"]} if private_chunks else {},
        public_doc=public_doc,
    )

    search = client.post("/api/library/search", json={"query": "kode RAG ALFA router", "limit": 3})
    search_json = search.get_json(silent=True) or {}
    first = (search_json.get("results") or [{}])[0]
    add(
        "search_document",
        search.status_code == 200
        and search_json.get("ok") is True
        and search_json.get("retrieval", {}).get("mode") == hai_app.LIBRARY_RETRIEVAL_MODE
        and search_json.get("retrieval", {}).get("vector_mode") == "private_local_hash_embedding"
        and search_json.get("retrieval", {}).get("semantic_expansion") is True
        and search_json.get("count", 0) >= 1
        and first.get("id") == doc_id
        and first.get("index_mode") == hai_app.LIBRARY_INDEX_MODE
        and first.get("ranking") == hai_app.LIBRARY_RANKING_MODE
        and first.get("semantic_expansion") is True
        and isinstance(first.get("vector_similarity"), (int, float))
        and "embedding" not in first
        and "vector" not in first
        and "RAG-ALFA-255" in (first.get("snippet") or ""),
        status=search.status_code,
        body=search_json,
    )

    deep_marker = "DEEP-RAG-259"
    deep_upload = client.post(
        "/api/library/documents",
        data={
            "file": (
                io.BytesIO(("awal " * 40000 + f" penanda jauh {deep_marker} untuk chunk retrieval.").encode("utf-8")),
                "library-deep-qa.txt",
            )
        },
        content_type="multipart/form-data",
    )
    deep_json = deep_upload.get_json(silent=True) or {}
    deep_doc = deep_json.get("document") if isinstance(deep_json.get("document"), dict) else {}
    deep_search = client.post("/api/library/search", json={"query": deep_marker, "limit": 3})
    deep_search_json = deep_search.get_json(silent=True) or {}
    deep_first = (deep_search_json.get("results") or [{}])[0]
    add(
        "deep_chunk_search_snippet",
        deep_upload.status_code == 200
        and deep_search.status_code == 200
        and deep_search_json.get("ok") is True
        and deep_first.get("id") == deep_doc.get("id")
        and deep_marker in (deep_first.get("snippet") or ""),
        upload_status=deep_upload.status_code,
        search_status=deep_search.status_code,
        body=deep_search_json,
    )

    precise_upload = client.post(
        "/api/library/documents",
        data={
            "file": (
                io.BytesIO(b"Dokumen presisi. Router ALFA unik RAG-BETA-289 untuk prioritas rerank."),
                "library-precise-rerank.txt",
            )
        },
        content_type="multipart/form-data",
    )
    precise_json = precise_upload.get_json(silent=True) or {}
    precise_doc = precise_json.get("document") if isinstance(precise_json.get("document"), dict) else {}
    spam_upload = client.post(
        "/api/library/documents",
        data={
            "file": (
                io.BytesIO(("router " * 900 + " dokumen spam tanpa alfa atau beta.").encode("utf-8")),
                "library-router-spam.txt",
            )
        },
        content_type="multipart/form-data",
    )
    spam_json = spam_upload.get_json(silent=True) or {}
    spam_doc = spam_json.get("document") if isinstance(spam_json.get("document"), dict) else {}
    rerank_search = client.post("/api/library/search", json={"query": "router ALFA RAG-BETA-289", "limit": 3})
    rerank_json = rerank_search.get_json(silent=True) or {}
    rerank_first = (rerank_json.get("results") or [{}])[0]
    add(
        "lexical_chunk_rerank_prefers_term_coverage",
        precise_upload.status_code == 200
        and spam_upload.status_code == 200
        and rerank_search.status_code == 200
        and rerank_json.get("retrieval", {}).get("mode") == hai_app.LIBRARY_RETRIEVAL_MODE
        and rerank_json.get("retrieval", {}).get("rerank") == hai_app.LIBRARY_RANKING_MODE
        and rerank_json.get("retrieval", {}).get("vector_mode") == "private_local_hash_embedding"
        and rerank_first.get("id") == precise_doc.get("id")
        and rerank_first.get("ranking") == hai_app.LIBRARY_RANKING_MODE
        and rerank_first.get("match_coverage", 0) >= 0.66
        and isinstance(rerank_first.get("vector_similarity"), (int, float))
        and isinstance(rerank_first.get("chunk_index"), int)
        and "embedding" not in rerank_first
        and "vector" not in rerank_first
        and "text" not in rerank_first,
        precise_status=precise_upload.status_code,
        spam_status=spam_upload.status_code,
        search_status=rerank_search.status_code,
        body=rerank_json,
    )

    semantic_upload = client.post(
        "/api/library/documents",
        data={
            "file": (
                io.BytesIO(b"Panduan jaringan rumah. Perangkat router utama membagikan koneksi internet ke semua ruangan."),
                "library-semantic-router.txt",
            )
        },
        content_type="multipart/form-data",
    )
    semantic_json = semantic_upload.get_json(silent=True) or {}
    semantic_doc = semantic_json.get("document") if isinstance(semantic_json.get("document"), dict) else {}
    semantic_search = client.post("/api/library/search", json={"query": "gateway wifi rumah", "limit": 3})
    semantic_search_json = semantic_search.get_json(silent=True) or {}
    semantic_first = (semantic_search_json.get("results") or [{}])[0]
    add(
        "semantic_alias_expansion_finds_related_document",
        semantic_upload.status_code == 200
        and semantic_search.status_code == 200
        and semantic_search_json.get("retrieval", {}).get("mode") == hai_app.LIBRARY_RETRIEVAL_MODE
        and semantic_search_json.get("retrieval", {}).get("vector_mode") == "private_local_hash_embedding"
        and semantic_search_json.get("retrieval", {}).get("semantic_expansion") is True
        and semantic_first.get("id") == semantic_doc.get("id")
        and "router" in [str(item).lower() for item in semantic_first.get("semantic_matches", [])],
        upload_status=semantic_upload.status_code,
        search_status=semantic_search.status_code,
        body=semantic_search_json,
    )

    original_limit = hai_app.LIBRARY_MAX_DOCS_PER_DEVICE
    try:
        hai_app.LIBRARY_MAX_DOCS_PER_DEVICE = 1
        capped_client = hai_app.app.test_client()
        cap_first = capped_client.post(
            "/api/library/documents",
            data={"file": (io.BytesIO(b"Dokumen pertama tetap aman."), "cap-one.txt")},
            content_type="multipart/form-data",
        )
        cap_first_json = cap_first.get_json(silent=True) or {}
        cap_first_id = ((cap_first_json.get("document") or {}) if isinstance(cap_first_json.get("document"), dict) else {}).get("id")
        cap_second = capped_client.post(
            "/api/library/documents",
            data={"file": (io.BytesIO(b"Dokumen kedua seharusnya ditolak."), "cap-two.txt")},
            content_type="multipart/form-data",
        )
        cap_second_json = cap_second.get_json(silent=True) or {}
        cap_list = capped_client.get("/api/library/documents")
        cap_list_json = cap_list.get_json(silent=True) or {}
        cap_docs = cap_list_json.get("documents") if isinstance(cap_list_json.get("documents"), list) else []
        add(
            "library_full_no_silent_eviction",
            cap_first.status_code == 200
            and cap_second.status_code == 409
            and cap_second_json.get("error") == "library_full"
            and cap_list_json.get("count") == 1
            and cap_docs
            and cap_docs[0].get("id") == cap_first_id,
            first_status=cap_first.status_code,
            second_status=cap_second.status_code,
            second_body=cap_second_json,
            list_body=cap_list_json,
        )
    finally:
        hai_app.LIBRARY_MAX_DOCS_PER_DEVICE = original_limit

    if deep_doc.get("id"):
        client.delete(f"/api/library/documents/{deep_doc.get('id')}")
    if precise_doc.get("id"):
        client.delete(f"/api/library/documents/{precise_doc.get('id')}")
    if spam_doc.get("id"):
        client.delete(f"/api/library/documents/{spam_doc.get('id')}")
    if semantic_doc.get("id"):
        client.delete(f"/api/library/documents/{semantic_doc.get('id')}")
    delete = client.delete(f"/api/library/documents/{doc_id}")
    delete_json = delete.get_json(silent=True) or {}
    add(
        "delete_document",
        delete.status_code == 200
        and delete_json.get("ok") is True
        and delete_json.get("deleted") is True,
        status=delete.status_code,
        body=delete_json,
    )

    after = client.post("/api/library/search", json={"query": "RAG-ALFA-255"})
    after_json = after.get_json(silent=True) or {}
    add(
        "search_after_delete_empty",
        after.status_code == 200
        and after_json.get("ok") is True
        and after_json.get("count") == 0,
        status=after.status_code,
        body=after_json,
    )

    summary = {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "passed": sum(1 for item in checks if item["ok"]),
        "total_run": len(checks),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    tmp_dir.cleanup()
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
