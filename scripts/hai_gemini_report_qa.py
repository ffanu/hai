#!/usr/bin/env python3
"""Validate the owner/Gemini consultation report stays in sync.

This is intentionally local/docs-focused: the report is used as a handoff
artifact, so stale gate numbers or release paths are treated as QA failures.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "phase219-gemini-current-report.md"
README = ROOT / "README.md"


def active_release_from_server() -> str:
    try:
        proc = subprocess.run(
            ["ssh", "-p", "22023", "root@103.157.24.189", "readlink -f /srv/harmonika-chat-webui"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--active-release", help="Expected active production release path. If omitted, SSH is used when available.")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    report = REPORT.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    active_release = args.active_release or active_release_from_server()
    checks = []

    def add(name: str, ok: bool, **extra) -> None:
        item = {"name": name, "ok": bool(ok)}
        item.update(extra)
        checks.append(item)

    add("report_exists", REPORT.exists(), path=str(REPORT.relative_to(ROOT)))
    add("readme_phase222", "Gemini Current Report Refresh Phase 222" in readme)
    add(
        "release_audit_current",
        "Release audit terbaru: `6/6 OK`" in report
        or "Release audit terbaru: `5/5 OK`" in report,
    )
    add("readiness_7_of_7", "Readiness QA terbaru: `7/7 OK`" in report)
    add(
        "gate_current",
        "Gate terbaru: `phase319-public-release-gate`" in report
        and "Gate result: `72/72 OK`" in report
        and "production.gate_result.total=72" in report,
    )
    add("previous_full_gate_recorded", "previous_full_public_gate_total=72" in report or "previous_full_public_gate_total=71" in report)
    add("visual_17_of_17", "Visual snapshots: `17/17 OK`" in report and "production.gate_result.visual_snapshots_total=17" in report)
    add("phase220_221_notes", "Phase 220" in report and "Phase 221" in report and "/api/readiness" in report)
    add("roadmap_not_overclaimed", "Full platform complete: `false`" in report and "full_platform_complete=false" in report)
    add(
        "raster_image_ready_reported",
        "Raster image generation provider | Selesai production" in report
        and "member_ai_bridge" in report
        and "PNG private `file_id`" in report
        and "raster image provider sudah ready" in report,
    )
    add(
        "no_stale_svg_question",
        "Untuk fitur gambar, apakah SVG private artifact cukup sebagai MVP atau wajib PNG/WebP raster?" not in report
        and "Raster image generation provider penuh | In progress" not in report
        and "Raster image generation provider penuh | Pending" not in report,
    )
    add(
        "readme_phase236",
        "Release Audit Raster Lock Phase 236" in readme
        and "Production QA Image Timeout Phase 235" in readme,
    )
    add(
        "readme_phase247",
        "Google-Primary Routing Phase 247" in readme
        and "Public Gate Repair Phase 246" in readme,
    )
    add(
        "readme_phase249",
        "Routing Policy QA Phase 248" in readme
        and "Public Gate Sync Phase 249" in readme,
    )
    add(
        "readme_phase250_251",
        "Shared Rate Limit Phase 250" in readme
        and "Member AI Session Isolation Phase 251" in readme
        and "Q&A / Checkpoint Phase 251" in readme,
    )
    add(
        "readme_phase253",
        "Public Gate Sync Phase 253" in readme
        and "phase253-public-release-gate" in readme,
    )
    add(
        "report_phase250_shared_rate_limit",
        "Phase 250 aktif" in report
        and "shared_across_workers=true" in report
        and "HAI_RATE_LIMIT_STORAGE=file" in report
        and "scripts/hai_rate_limit_qa.py" in report,
    )
    add(
        "report_phase251_member_ai_isolation",
        "Phase 251 aktif" in report
        and "Focused production QA pasca deploy lulus `27/27 OK`" in report
        and "mengabaikan konteks session internal lama" in report
        and "[Document: ...]" in report,
    )
    add(
        "report_phase254_next_priorities",
        "Phase 254" in report
        and 'next_priorities[0].id="rag_library"' in report
        and 'next_priorities[1].id="realtime_resume_wss"' in report
        and "admin analytics/observability" in report,
    )
    add(
        "report_phase255_library_foundation",
        "Phase 255" in report
        and "RAG/library backend foundation" in report
        and "/api/library/documents" in report
        and "/api/library/search" in report
        and "scripts/hai_library_qa.py" in report,
    )
    add(
        "report_phase256_google_primary_refresh",
        "Phase 256" in report
        and "Google Mode tetap menjadi primary answer engine" in report
        and "kode promo" in report
        and "Codex hanya untuk coding/debug/deploy/stacktrace" in report,
    )
    add(
        "report_phase257_library_ui_grounding",
        "Phase 257" in report
        and "RAG/library UI + snippet grounding" in report
        and "Sidebar Library" in report
        and "tanpa mengekspos full text/ID internal" in report,
    )
    add(
        "report_phase258_server_side_library_grounding",
        "Phase 258" in report
        and "backend `/chat`" in report
        and "source Library tanpa URL publik" in report
        and "Konteks Library" in report,
    )
    add(
        "report_phase259_library_retrieval_hardening",
        "Phase 259" in report
        and "Chunk scoring" in report
        and "409 library_full" in report
        and "bucket rate-limit `library`" in report
        and "Codex hanya handoff teknis berat" in report,
    )
    add(
        "readme_phase259",
        "Library Retrieval Hardening Phase 259" in readme
        and "409 library_full" in readme
        and "Google Mode tetap primary" in readme,
    )
    add(
        "report_phase289_library_lexical_rerank",
        "Phase 289" in report
        and "match_coverage" in report
        and "chunk_index" in report,
    )
    add(
        "report_phase294_library_semantic_expansion",
        "Phase 294" in report
        and "lexical_semantic_bm25_sparse_rerank" in report
        and "semantic alias expansion" in report,
    )
    add(
        "readme_phase289",
        "Library Lexical Rerank Phase 289" in readme
        and "lexical_chunk_rerank_prefers_term_coverage" in readme
        and "rag_library_lexical_rerank=true" in readme,
    )
    add(
        "readme_phase294_library_semantic_expansion",
        "Library Semantic Expansion Phase 294" in readme
        and "lexical_semantic_bm25_sparse_rerank" in readme
        and "semantic_alias_expansion_finds_related_document" in readme
        and "rag_library_semantic_expansion=true" in readme,
    )
    add(
        "readme_phase295_library_full_context",
        "Library Full Context Phase 295" in readme
        and "libraryContextMode=full" in readme
        and "chat_library_full_context_mode" in readme
        and "rag_library_full_context=true" in readme,
    )
    add(
        "report_phase295_library_full_context",
        "Phase 295" in report
        and "Cuplikan/Penuh" in report
        and "context_mode" in report,
    )
    add(
        "readme_phase296_library_sparse_index",
        "Library Sparse Index Phase 296" in readme
        and "private_sparse_chunk_index" in readme
        and "private_sparse_chunk_index_stored_not_public" in readme
        and "rag_library_sparse_index=true" in readme,
    )
    add(
        "report_phase296_library_sparse_index",
        "Phase 296" in report
        and "private sparse chunk index" in report
        and "term-vector" in report,
    )
    add(
        "readme_phase299_library_bm25_sparse_rerank",
        "Library BM25 Sparse Rerank Phase 299" in readme
        and "lexical_semantic_bm25_sparse_rerank" in readme
        and "bm25_sparse_coverage_rerank" in readme,
    )
    add(
        "report_phase299_library_bm25_sparse_rerank",
        "Phase 299" in report
        and "BM25-lite sparse rerank" in report
        and "bm25_sparse_coverage_rerank" in report,
    )
    add(
        "report_phase260_public_gate_sync",
        "Phase 260" in report
        and "full public release gate production setelah Phase 259" in report
        and "phase260-public-release-gate" in report,
    )

    add(
        "report_phase261_library_browser_gate",
        "Phase 261" in report
        and "browser QA nyata untuk panel Library" in report
        and "68/68 OK" in report
        and "20261007-phase261" in report,
    )
    add(
        "readme_phase261",
        "Library Browser Gate Phase 261" in readme
        and "browser_library_panel" in readme
        and "20261007-phase261" in readme
        and "68/68" in readme,
    )
    add(
        "readme_phase260",
        "Public Gate Sync Phase 260" in readme
        and "66/66 OK" in readme
        and "visual snapshots `17/17`" in readme,
    )
    add(
        "report_phase264_realtime_replay",
        "Phase 264" in report
        and "X-HAI-Response-ID" in report
        and "/api/realtime/events" in report
        and "WSS tetap belum diklaim production" in report,
    )
    add(
        "report_phase292_realtime_wss_ticket",
        "Phase 292" in report
        and "/api/realtime/ticket" in report
        and "realtime_wss_not_ready" in report
        and "realtime_wss=false" in report,
    )
    add(
        "readme_phase300_realtime_replay_state",
        "Realtime Replay State Phase 300" in readme
        and "last_event_id" in readme
        and "realtime_wss=false" in readme,
    )
    add(
        "report_phase300_realtime_replay_state",
        "Phase 300" in report
        and "replay state eksplisit" in report
        and "last_event_id" in report,
    )
    add(
        "readme_phase264",
        "Realtime Replay Foundation Phase 264" in readme
        and "realtime_replay_api=true" in readme
        and "realtime_wss=false" in readme
        and "scripts/hai_realtime_qa.py" in readme,
    )
    add(
        "report_phase287_realtime_typing_ux",
        "Phase 287" in report
        and "Jawaban sedang disiapkan" in report
        and "Jawaban sedang diketik realtime" in report
        and "phase287-public-release-gate" in report
        and "20261007-phase297" in report
        and "71/71 OK" in report,
    )
    add(
        "report_phase290_connection_pill",
        "Phase 290" in report
        and "connection pill" in report
        and "Menyambung ulang" in report
        and "Dipulihkan" in report
        and "WSS tetap belum diklaim production" in report,
    )
    add(
        "report_phase281_member_ai_session_isolation",
        "Phase 281" in report
        and "reset session upstream" in report
        and "member_ai_chat_session_isolation=true" in report,
    )
    add(
        "readme_phase281",
        "Member AI Session Isolation Phase 281" in readme
        and "locked_reset_per_request" in readme
        and "member_ai_chat_session_isolation=true" in readme,
    )
    add(
        "readme_phase284",
        "Loading Simplify Phase 284" in readme
        and "20261007-phase284" in readme
        and "streaming-states" in readme,
    )
    add(
        "readme_phase283_deploy_venv_guard",
        "Deploy Venv Guard Phase 283" in readme
        and "hai_finalize_remote_release.sh" in readme
        and "status=203/EXEC" in readme,
    )
    add(
        "report_phase283_deploy_venv_guard",
        "Phase 283" in report
        and "venv real" in report
        and "gunicorn" in report
        and "healthz" in report,
    )
    add(
        "readme_phase285_deploy_health_retry",
        "Deploy Health Retry Phase 285" in readme
        and "20 kali" in readme
        and "0.5 detik" in readme,
    )
    add(
        "report_phase285_deploy_health_retry",
        "Phase 285" in report
        and "retry" in report
        and "healthz" in report,
    )
    add(
        "report_phase277_targeted_ui_gate",
        "Phase 277" in report
        and "scripts/hai_targeted_ui_gate.py" in report
        and "--targeted-ui-gate" in report,
    )
    add(
        "readme_phase277",
        "Targeted UI Gate Script Phase 277" in readme
        and "scripts/hai_targeted_ui_gate.py" in readme
        and "phase287-realtime-loading-gate" in readme,
    )
    add(
        "readme_phase287",
        "Realtime Typing UX Phase 287" in readme
        and "Jawaban sedang disiapkan" in readme
        and "20261007-phase287" in readme
        and "phase287-public-release-gate" in readme,
    )
    add(
        "readme_phase290",
        "Realtime Connection Pill Phase 290" in readme
        and "Siap / Realtime / Menyambung ulang / Dipulihkan" in readme
        and "20261007-phase297" in readme
        and "realtime-resume" in readme,
    )
    add(
        "report_phase291_library_grounding_toggle",
        "Phase 291" in report
        and "Otomatis/Selalu/Mati" in report
        and "X-HAI-Library-Grounding" in report,
    )
    add(
        "readme_phase291",
        "Library Grounding Toggle Phase 291" in readme
        and "rag_library_grounding_toggle=true" in readme
        and "auto→force→off→auto" in readme,
    )
    add(
        "readme_phase292",
        "Realtime WSS Ticket Contract Phase 292" in readme
        and "wss_ticket_fails_safe_until_ready" in readme
        and "realtime_wss_ticket_endpoint=true" in readme,
    )
    add(
        "readme_phase293_realtime_visual",
        "Realtime Typing Visual Phase 293" in readme
        and "robot mini animasi CSS" in readme
        and "menulis kode" in readme
        and "20261007-phase293" in readme,
    )
    add(
        "report_phase293_realtime_visual",
        (
            "Phase 297 aktif" in report
            and "ikon robot animasi" in report
            and "code block editor-style" in report
            and "20261007-phase297" in report
        )
        or (
            "Phase 302 aktif" in report
            and "ikon robot SVG" in report
            and "editor-style" in report
            and "20261007-phase302" in report
        )
        or (
            "Phase 304 aktif" in report
            and "robot SVG animasi" in report
            and "editor modern" in report
            and "20261007-phase304" in report
        )
        or (
            "Phase 305 aktif" in report
            and "ikon robot/gambar" in report
            and "editor modern" in report
            and "20261007-phase305" in report
        )
        or (
            "Phase 306 aktif" in report
            and "ikon robot/gambar" in report
            and "editor modern" in report
            and "20261007-phase306" in report
        )
        or (
            "Phase 307 aktif" in report
            and "ikon robot kecil" in report
            and "editor modern" in report
            and "20261007-phase307" in report
        ),
    )
    add(
        "readme_phase297_robot_typing_icon",
        "Robot Typing Icon Phase 297" in readme
        and "ikon robot animasi SVG" in readme
        and "20261007-phase297" in readme,
    )
    add(
        "readme_phase298_public_gate_sync",
        "Public Gate Sync Phase 298" in readme
        and "phase297-public-release-gate" in readme
        and "71/71 OK" in readme
        and "20261007-phase297" in readme,
    )
    add(
        "report_phase298_public_gate_sync",
        "Phase 298" in report
        and "phase297-public-release-gate" in report
        and "20261007-phase297" in report
        and "71/71 OK" in report,
    )
    add(
        "readme_phase302_realtime_loading_chunking",
        "Realtime Loading Chunking Phase 302" in readme
        and "20261007-phase302" in readme
        and "71/71 OK" in readme
        and "Admin Overview Phase 302" in readme,
    )
    add(
        "report_phase302_public_gate_sync",
        "Phase 302" in report
        and "20261007-phase302" in report
        and "71/71 OK" in report
        and "/api/admin/overview" in report,
    )
    add(
        "readme_phase306_public_gate_sync",
        "Public Gate Sync Phase 306" in readme
        and "phase306-public-release-gate" in readme
        and "72/72 OK" in readme
        and "20261007-phase306" in readme,
    )
    add(
        "report_phase306_public_gate_sync",
        ("Phase 306 aktif" in report or "Phase 306 memperbaiki" in report)
        and "20261007-phase306" in report
        and "72/72 OK" in report,
    )
    add(
        "readme_phase307_loading_clarity",
        "Realtime Loading Clarity Phase 307" in readme
        and "20261007-phase307" in readme
        and "72/72 OK" in readme
        and "17/17 OK" in readme,
    )
    add(
        "report_phase307_public_gate_sync",
        "Phase 307 aktif" in report
        and "phase307-public-release-gate" in report
        and "20261007-phase307" in report
        and "72/72 OK" in report,
    )
    add(
        "readme_phase309_answer_loading_polish",
        "Answer Loading Polish Phase 309" in readme
        and "20261007-phase309" in readme
        and "72/72 OK" in readme
        and "17/17 OK" in readme,
    )
    add(
        "readme_phase310_mobile_image_loading_fit",
        "Mobile Image Loading Fit Phase 310" in readme
        and "20261007-phase310" in readme
        and "screenshot loading aktif" in readme
        and "bubble assistant kosong" in readme,
    )
    add(
        "report_phase310_public_gate_sync",
        "Phase 310 memperbaiki visual loading gambar mobile" in report
        and "full gate rerun production lulus `72/72 OK`" in report
        and "20261007-phase310" in report
        and "17/17" in report,
    )
    add(
        "readme_phase311_image_contract_stability",
        "Image Contract Stability Phase 311" in readme
        and "400 invalid_prompt" in readme
        and "phase310-public-release-gate-rerun" in readme
        and "72/72 OK" in readme,
    )
    add(
        "report_phase311_image_contract_stability",
        "Phase 311" in report
        and "400 invalid_prompt" in report
        and "Kontrak production image lulus `6/6 OK`" in report
        and "full public release gate rerun lulus `72/72 OK`" in report,
    )
    add(
        "readme_phase312_desktop_image_loading_compact",
        "Desktop Image Loading Compact Phase 312" in readme
        and "20261007-phase312" in readme
        and "max-width" in readme
        and "700px" in readme
        and "phase312-public-release-gate" in readme
        and "72/72 OK" in readme,
    )
    add(
        "report_phase312_desktop_image_loading_compact",
        "Phase 312" in report
        and "20261007-phase312" in report
        and "kartu loading pembuatan gambar desktop/tablet" in report
        and "lebar chat response" in report,
    )
    add(
        "report_phase312_public_gate_sync",
        "phase312-public-release-gate" in report
        and "72/72 OK" in report
        and "visual snapshots `17/17 OK`" in report,
    )
    add(
        "readme_phase313_mobile_rich_answer_containment",
        "Mobile Rich Answer Containment Phase 313" in readme
        and "20261007-phase313" in readme
        and "Markdown, tabel, dan code block" in readme
        and "scroll di dalam bubble" in readme,
    )
    add(
        "report_phase313_mobile_rich_answer_containment",
        "Phase 313" in report
        and "20261007-phase313" in report
        and "containment jawaban mobile" in report
        and "terpotong ke kanan" in report,
    )
    add(
        "readme_phase314_mobile_table_readability",
        "Mobile Table Readability Phase 314" in readme
        and "20261007-phase314" in readme
        and "perlu koreksi" in readme
        and "bubble" in readme,
    )
    add(
        "report_phase314_mobile_table_readability",
        "Phase 314" in report
        and "readability tabel mobile" in report
        and "tidak melebihi bubble" in report,
    )
    add(
        "readme_phase315_realtime_loading_table_fix",
        "Realtime Loading & Mobile Table Fix Phase 315" in readme
        and "20261007-phase315" in readme
        and "robot kecil" in readme
        and "tabel mobile" in readme,
    )
    add(
        "report_phase315_realtime_loading_table_fix",
        "Phase 315" in report
        and "20261007-phase315" in report
        and "robot/loading teks" in report
        and "tabel mobile" in report,
    )
    add(
        "readme_phase315_public_gate_sync",
        "Public Gate Sync Phase 315" in readme
        and "phase315-public-release-gate" in readme
        and "20261007-phase315" in readme
        and "72/72 OK" in readme,
    )
    add(
        "report_phase315_public_gate_sync",
        "phase315-public-release-gate" in report
        and "20261007-phase315" in report
        and "72/72 OK" in report
        and "visual snapshots `17/17 OK`" in report,
    )
    add(
        "readme_phase316_admin_analytics_aggregate",
        "Admin Analytics Aggregate Phase 316" in readme
        and "20261007-phase316" in readme
        and "analytics aggregate" in readme.lower()
        and "tanpa isi chat" in readme.lower(),
    )
    add(
        "report_phase316_admin_analytics_aggregate",
        "Phase 316" in report
        and "20261007-phase316" in report
        and "analytics aggregate" in report.lower()
        and "tanpa isi chat" in report.lower(),
    )
    add(
        "readme_phase317_realtime_typewriter_polish",
        "Realtime Typewriter Polish Phase 317" in readme
        and "20261007-phase317" in readme
        and "typewriter" in readme.lower()
        and "loader robot" in readme.lower(),
    )
    add(
        "readme_phase317_public_gate_sync",
        "Public Gate Sync Phase 317" in readme
        and "phase317-public-release-gate" in readme
        and "20261007-phase317" in readme
        and "72/72 OK" in readme,
    )
    add(
        "report_phase317_public_gate_sync",
        "phase317-public-release-gate" in report
        and "20261007-phase317" in report
        and "72/72 OK" in report
        and "visual snapshots `17/17 OK`" in report,
    )
    add(
        "readme_phase318_library_hybrid_vector_index",
        "Library Hybrid Vector Index Phase 318" in readme
        and "private_hybrid_sparse_vector_chunk_index" in readme
        and "hybrid_vector_bm25_coverage_rerank" in readme
        and "private_local_hash_embedding" in readme,
    )
    add(
        "report_phase318_library_hybrid_vector_index",
        "Phase 318" in report
        and "hybrid_vector_lexical_semantic_rerank" in report
        and "private hybrid sparse+hash-vector" in report
        and "external managed vector DB" in report,
    )
    add(
        "readme_phase319_realtime_loader_ui_stable_gate",
        "Realtime Loader UI Stable Gate Phase 319" in readme
        and "20261007-phase319" in readme
        and "phase319" in readme
        and "LIVE" in readme
        and "DESIGN" in readme
        and "72/72 OK" in readme,
    )
    add(
        "report_phase319_realtime_loader_ui_stable_gate",
        "phase319-public-release-gate" in report
        and "20261007-phase319" in report
        and "loader robot" in report.lower()
        and "badge `LIVE`" in report
        and "kartu `DESIGN`" in report
        and "72/72 OK" in report,
    )
    add(
        "readme_phase331_empty_writing_bubble_cleanup",
        "Empty Writing Bubble Cleanup Phase 331" in readme
        and "20261007-phase331" in readme
        and 'data-loading="writing"' in readme
        and "Markdown baru dirender" in readme
        and "`hai-connection-pill`" in readme
        and "card Library" in readme,
    )
    add(
        "report_phase331_empty_writing_bubble_cleanup",
        "Phase 331" in report
        and "20261007-phase331" in report
        and 'data-loading="writing"' in report
        and "hai-connection-pill" in report
        and ".assistant-message" in report
        and "export-buttons" in report
        and "timeline chat" in report
        and "bubble assistant" in report,
    )

    release_match = re.search(r"Release aktif: `([^`]+)`", report)
    report_release = release_match.group(1) if release_match else ""
    add(
        "active_release_current",
        report_release == "/srv/harmonika-chat-webui" or (bool(active_release) and report_release == active_release),
        report_release=report_release,
        active_release=active_release,
    )

    ok = all(item["ok"] for item in checks)
    summary = {
        "ok": ok,
        "report": str(REPORT.relative_to(ROOT)),
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
