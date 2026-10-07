#!/usr/bin/env python3
"""Readiness contract QA for Harmonika AI WebUI."""

from __future__ import annotations

import argparse
import json
import pathlib
import time
import urllib.error
import urllib.request


SECRET_STRINGS = [
    "HAI_MEMBER_AI_TOKEN",
    "Authorization",
    "Bearer",
    "password",
    "api_key",
]


def fetch_json(url: str, timeout: int = 25) -> tuple[int, dict, str, int]:
    started = time.time()
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "hai-readiness-qa/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = int(exc.code)
    except urllib.error.URLError as exc:
        body = json.dumps({"error": "request_failed", "detail": str(exc.reason)}, ensure_ascii=False)
        status = 0
    duration_ms = int((time.time() - started) * 1000)
    try:
        payload = json.loads(body)
    except Exception:
        payload = {}
    return status, payload, body, duration_ms


def add_check(checks: list[dict], name: str, ok: bool, **extra) -> None:
    item = {"name": name, "ok": bool(ok)}
    item.update(extra)
    checks.append(item)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://hai.harmonika.id")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    readiness_status, readiness, readiness_body, readiness_ms = fetch_json(f"{base_url}/api/readiness")
    capabilities_status, capabilities, _capabilities_body, capabilities_ms = fetch_json(f"{base_url}/api/capabilities")
    checks: list[dict] = []

    add_check(
        checks,
        "readiness_http_json",
        readiness_status == 200 and readiness.get("ok") is True and readiness.get("service") == "harmonika-chat-webui",
        status=readiness_status,
        duration_ms=readiness_ms,
        profile=readiness.get("profile"),
    )
    production = readiness.get("production") if isinstance(readiness.get("production"), dict) else {}
    add_check(
        checks,
        "production_claims",
        production.get("public_mvp_ready") is True
        and production.get("full_platform_complete") is False
        and production.get("gate") == "phase319-public-release-gate"
        and isinstance(production.get("gate_result"), dict)
        and production["gate_result"].get("passed") == production["gate_result"].get("total") == 72
        and production["gate_result"].get("visual_snapshots_passed") == production["gate_result"].get("visual_snapshots_total") == 17,
        production=production,
    )

    core = readiness.get("core") if isinstance(readiness.get("core"), dict) else {}
    required_core_true = [
        "chat",
        "streaming",
        "history",
        "responsive_ui",
        "file_upload",
        "pdf_input",
        "image_input",
        "image_artifact_preview",
        "message_queue",
        "artifact_canvas_basic",
        "realtime_replay_api",
        "realtime_replay_state",
        "admin_overview",
        "admin_dashboard",
        "observability_aggregate",
        "admin_analytics",
        "release_gate",
    ]
    add_check(
        checks,
        "core_mvp_flags",
        all(core.get(name) is True for name in required_core_true),
        core={name: core.get(name) for name in required_core_true},
    )

    roadmap = readiness.get("roadmap") if isinstance(readiness.get("roadmap"), dict) else {}
    required_roadmap = [
        "raster_image_generation",
        "rag_library",
        "realtime_resume_wss",
        "voice_video",
        "calendar_automation_admin",
        "admin_analytics",
    ]
    roadmap_status_ok = all(
        isinstance(roadmap.get(name), dict) and roadmap[name].get("status") in {"ready", "pending", "planned", "foundation"}
        for name in required_roadmap
    )
    add_check(
        checks,
        "roadmap_flags",
        roadmap_status_ok,
        roadmap={name: roadmap.get(name) for name in required_roadmap},
    )
    next_priorities = readiness.get("next_priorities") if isinstance(readiness.get("next_priorities"), list) else []
    priority_ids = [
        item.get("id")
        for item in next_priorities
        if isinstance(item, dict)
    ]
    add_check(
        checks,
        "next_priorities",
        len(next_priorities) >= 3
        and priority_ids[:2] == ["rag_library", "realtime_resume_wss"]
        and all(isinstance(item, dict) and item.get("title") and item.get("why") and item.get("status") for item in next_priorities[:3]),
        priority_ids=priority_ids,
    )

    contracts = readiness.get("contracts") if isinstance(readiness.get("contracts"), dict) else {}
    features = capabilities.get("features") if isinstance(capabilities.get("features"), dict) else {}
    add_check(
        checks,
        "capability_alignment",
        capabilities_status == 200
        and capabilities.get("ok") is True
        and contracts.get("raster_public") is features.get("raster_image_generation")
        and contracts.get("no_public_media_urls") is True
        and contracts.get("sources_without_full_url_in_bubble") is True
        and contracts.get("member_ai_chat_session_isolation") is True
        and contracts.get("member_ai_chat_session_policy") == "locked_reset_per_request"
        and contracts.get("library_grounding_mode") == "auto_toggle_server_side"
        and features.get("rag_library_grounding_toggle") is True
        and features.get("rag_library_semantic_expansion") is True
        and features.get("rag_library_full_context") is True
        and features.get("rag_library_sparse_index") is True
        and features.get("rag_library_bm25_sparse_rerank") is True
        and features.get("rag_library_vector_index") is True
        and features.get("rag_library_hybrid_retrieval") is True
        and contracts.get("library_index_mode") == "private_hybrid_sparse_vector_chunk_index"
        and contracts.get("library_ranking_mode") == "hybrid_vector_bm25_coverage_rerank"
        and contracts.get("library_vector_mode") == "private_local_hash_embedding"
        and int(contracts.get("library_vector_dimensions") or 0) >= 16
        and contracts.get("library_context_modes") == ["snippet", "full"]
        and contracts.get("realtime_wss") is False
        and contracts.get("realtime_replay_state") is True
        and isinstance(contracts.get("realtime_replay_state_fields"), list)
        and "last_event_id" in contracts.get("realtime_replay_state_fields", [])
        and contracts.get("realtime_wss_ticket_endpoint") == "/api/realtime/ticket"
        and features.get("realtime_wss_ticket_endpoint") is True
        and contracts.get("admin_overview") is True
        and contracts.get("admin_dashboard") is True
        and contracts.get("observability_aggregate") is True
        and contracts.get("admin_analytics") is True
        and contracts.get("admin_overview_endpoint") == "/api/admin/overview"
        and contracts.get("admin_dashboard_path") == "/admin"
        and features.get("admin_overview") is True
        and features.get("admin_dashboard") is True
        and features.get("observability_aggregate") is True
        and features.get("admin_analytics") is True,
        capabilities_status=capabilities_status,
        capabilities_duration_ms=capabilities_ms,
        raster_public=contracts.get("raster_public"),
        feature_raster_image_generation=features.get("raster_image_generation"),
        image_result_format=contracts.get("image_result_format"),
        member_ai_chat_session_isolation=contracts.get("member_ai_chat_session_isolation"),
        member_ai_chat_session_policy=contracts.get("member_ai_chat_session_policy"),
        library_grounding_mode=contracts.get("library_grounding_mode"),
        rag_library_grounding_toggle=features.get("rag_library_grounding_toggle"),
        rag_library_semantic_expansion=features.get("rag_library_semantic_expansion"),
        rag_library_full_context=features.get("rag_library_full_context"),
        rag_library_sparse_index=features.get("rag_library_sparse_index"),
        rag_library_bm25_sparse_rerank=features.get("rag_library_bm25_sparse_rerank"),
        rag_library_vector_index=features.get("rag_library_vector_index"),
        rag_library_hybrid_retrieval=features.get("rag_library_hybrid_retrieval"),
        library_index_mode=contracts.get("library_index_mode"),
        library_ranking_mode=contracts.get("library_ranking_mode"),
        library_vector_mode=contracts.get("library_vector_mode"),
        library_vector_dimensions=contracts.get("library_vector_dimensions"),
        library_context_modes=contracts.get("library_context_modes"),
        realtime_wss=contracts.get("realtime_wss"),
        realtime_replay_state=contracts.get("realtime_replay_state"),
        realtime_wss_ticket_endpoint=contracts.get("realtime_wss_ticket_endpoint"),
        admin_overview_endpoint=contracts.get("admin_overview_endpoint"),
        admin_dashboard_path=contracts.get("admin_dashboard_path"),
        admin_overview=features.get("admin_overview"),
        admin_dashboard=features.get("admin_dashboard"),
        observability_aggregate=features.get("observability_aggregate"),
        admin_analytics=features.get("admin_analytics"),
    )

    leaked = [needle for needle in SECRET_STRINGS if needle.lower() in readiness_body.lower()]
    add_check(checks, "no_secret_words", not leaked, leaked=leaked)

    ok = all(check["ok"] for check in checks)
    summary = {
        "ok": ok,
        "base_url": base_url,
        "checks": checks,
        "passed": sum(1 for check in checks if check["ok"]),
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
