#!/usr/bin/env python3
"""HTTP release audit for hai.harmonika.id production.

This checks the externally visible production state, not local files:

- `/healthz` reports ok and safe security booleans.
- `/api/capabilities` exposes expected public features.
- `/api/readiness` exposes the latest public MVP gate evidence.
- HTML points to the expected asset marker.
- CSS/JS assets load with 200 status.
- Basic security headers are present.
- Old cache-bust markers are not present in the HTML.

Examples:
  python3 scripts/hai_release_audit.py --base-url https://hai.harmonika.id
  python3 scripts/hai_release_audit.py --base-url https://hai.harmonika.id --expected-asset-marker 20261006-phase94
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request


SECURITY_HEADERS = [
    "x-content-type-options",
    "x-frame-options",
    "content-security-policy",
    "referrer-policy",
    "permissions-policy",
    "strict-transport-security",
]
ROOT = pathlib.Path(__file__).resolve().parents[1]


def fetch(url: str, accept: str = "*/*", timeout: int = 25) -> dict:
    started = time.time()
    request = urllib.request.Request(url, headers={
        "Accept": accept,
        "User-Agent": "hai-release-audit/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            status = int(response.status)
            headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = int(exc.code)
        headers = {key.lower(): value for key, value in exc.headers.items()}
    except urllib.error.URLError as exc:
        body = json.dumps({"error": "request_failed", "detail": str(exc.reason)}, ensure_ascii=False).encode("utf-8")
        status = 0
        headers = {}
    duration_ms = int((time.time() - started) * 1000)
    return {
        "url": url,
        "status": status,
        "headers": headers,
        "body": body,
        "duration_ms": duration_ms,
    }


def json_body(result: dict) -> dict:
    try:
        return json.loads(result["body"].decode("utf-8"))
    except Exception:
        return {}


def asset_urls(base_url: str, html: str, marker: str) -> list[str]:
    urls = []
    for match in re.finditer(r'''(?:href|src)=["']([^"']+\?v=%s)["']''' % re.escape(marker), html):
        url = match.group(1)
        urls.append(urllib.parse.urljoin(f"{base_url}/", url))
    return urls


def detect_local_asset_marker() -> str:
    template = ROOT / "templates" / "index.html"
    html = template.read_text(encoding="utf-8")
    markers = re.findall(r'''(?:styles\.css|scripts\.js).*?\?v=([^"']+)''', html, flags=re.DOTALL)
    unique_markers = sorted(set(markers))
    if len(unique_markers) != 1:
        raise ValueError(f"Asset marker lokal tidak konsisten di {template}: {unique_markers}")
    return unique_markers[0]


def css_block_has(css: str, selector: str, required_fragment: str) -> bool:
    """Return true only when a CSS block containing selector also has fragment.

    The release audit intentionally checks the selector block, not a loose global
    substring, so a future unrelated `filter: none` does not make the guard pass.
    """
    for match in re.finditer(r"(?P<selectors>[^{}]+)\{(?P<body>[^{}]*)\}", css, flags=re.DOTALL):
        selectors = " ".join(match.group("selectors").split())
        body = " ".join(match.group("body").split())
        if selector in selectors and required_fragment in body:
            return True
    return False


def js_icon_version_matches(script: str, expected_asset_marker: str) -> bool:
    match = re.search(r"""HAI_ICON_VERSION\s*=\s*['"]([^'"]+)['"]""", script)
    return bool(match and match.group(1) == expected_asset_marker)


def html_attr_value(html: str, tag_pattern: str, attr: str = "content") -> str:
    match = re.search(tag_pattern, html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    tag = match.group(0)
    attr_match = re.search(r"""\b%s=["']([^"']+)["']""" % re.escape(attr), tag, flags=re.IGNORECASE)
    return attr_match.group(1).strip() if attr_match else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://hai.harmonika.id")
    parser.add_argument("--expected-asset-marker", help="Expected CSS/JS cache-bust marker. Defaults to the marker detected from templates/index.html.")
    parser.add_argument("--forbidden-asset-marker", default="20261006-phase89,20261006-phase94,20261006-phase100,20261006-phase104,20261006-phase105,20261006-phase110,20261006-phase111,20261006-phase112,20261006-phase113,20261006-phase114,20261006-phase115,20261006-phase116,20261006-phase117,20261006-phase118,20261006-phase119,20261006-phase120,20261006-phase121,20261006-phase122,20261006-phase123,20261006-phase124,20261006-phase125,20261006-phase126,20261006-phase127,20261006-phase129,20261006-phase130,20261006-phase131,20261006-phase132,20261006-phase133,20261006-phase134,20261006-phase135,20261006-phase136,20261006-phase137,20261006-phase138,20261006-phase139,20261006-phase140,20261006-phase141,20261006-phase143,20261006-phase144,20261006-phase145,20261006-phase148,20261006-phase150,20261006-phase152,20261006-phase204,20261006-phase238,20261006-phase240,20261006-phase241,20261006-phase242,20261006-phase243", help="Comma-separated old cache-bust markers that must not appear in production HTML.")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    try:
        expected_asset_marker = args.expected_asset_marker or detect_local_asset_marker()
    except Exception as exc:
        parser.error(str(exc))
    forbidden_asset_markers = [item.strip() for item in str(args.forbidden_asset_marker or "").split(",") if item.strip()]
    checks = []

    index = fetch(f"{base_url}/", "text/html")
    html = index["body"].decode("utf-8", errors="replace")
    index_headers_present = {name: bool(index["headers"].get(name)) for name in SECURITY_HEADERS}
    csp_header = index["headers"].get("content-security-policy", "")
    csp_ok = (
        "default-src 'self'" in csp_header
        and "script-src 'self'" in csp_header
        and "'unsafe-inline'" not in (re.search(r"script-src\s+([^;]+)", csp_header) or ["", ""])[1]
        and "object-src 'none'" in csp_header
        and "frame-ancestors 'self'" in csp_header
    )
    index_set_cookie = index["headers"].get("set-cookie", "")
    device_cookie_ok = (
        "__Host-hai_device=" in index_set_cookie
        and "Secure" in index_set_cookie
        and "HttpOnly" in index_set_cookie
        and "SameSite=Lax" in index_set_cookie
        and "Path=/" in index_set_cookie
    )
    description = html_attr_value(html, r"""<meta\s+[^>]*name=["']description["'][^>]*>""")
    inline_script_blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html, flags=re.I)
    inline_event_handlers = re.findall(r"\s+on[a-z]+\s*=", html, flags=re.I)
    no_inline_script_surface = not inline_script_blocks and not inline_event_handlers
    theme_color = html_attr_value(html, r"""<meta\s+[^>]*name=["']theme-color["'][^>]*>""")
    robots = html_attr_value(html, r"""<meta\s+[^>]*name=["']robots["'][^>]*>""")
    canonical = html_attr_value(html, r"""<link\s+[^>]*rel=["']canonical["'][^>]*>""", "href")
    og_title = html_attr_value(html, r"""<meta\s+[^>]*property=["']og:title["'][^>]*>""")
    og_description = html_attr_value(html, r"""<meta\s+[^>]*property=["']og:description["'][^>]*>""")
    og_url = html_attr_value(html, r"""<meta\s+[^>]*property=["']og:url["'][^>]*>""")
    og_image = html_attr_value(html, r"""<meta\s+[^>]*property=["']og:image["'][^>]*>""")
    twitter_card = html_attr_value(html, r"""<meta\s+[^>]*name=["']twitter:card["'][^>]*>""")
    metadata_ok = (
        40 <= len(description) <= 160
        and theme_color.lower() == "#343a40"
        and "noindex" not in robots.lower()
        and canonical == f"{base_url}/"
        and og_title == "Harmonika AI"
        and 20 <= len(og_description) <= 140
        and og_url == f"{base_url}/"
        and og_image.startswith(f"{base_url}/static/images/")
        and twitter_card == "summary"
    )
    checks.append({
        "name": "index_html",
        "ok": (
            index["status"] == 200
            and expected_asset_marker in html
            and all(marker not in html for marker in forbidden_asset_markers)
            and all(index_headers_present.values())
            and csp_ok
            and no_inline_script_surface
            and metadata_ok
            and device_cookie_ok
        ),
        "status": index["status"],
        "duration_ms": index["duration_ms"],
        "expected_asset_marker": expected_asset_marker in html,
        "expected_asset_marker_value": expected_asset_marker,
        "forbidden_asset_markers_absent": {marker: marker not in html for marker in forbidden_asset_markers},
        "security_headers": index_headers_present,
        "content_security_policy_ok": csp_ok,
        "content_security_policy": csp_header,
        "no_inline_script_surface": no_inline_script_surface,
        "inline_script_blocks": inline_script_blocks,
        "inline_event_handler_count": len(inline_event_handlers),
        "device_cookie_ok": device_cookie_ok,
        "metadata": {
            "description": description,
            "description_length": len(description),
            "theme_color": theme_color,
            "robots": robots,
            "canonical": canonical,
            "og_title": og_title,
            "og_description": og_description,
            "og_description_length": len(og_description),
            "og_url": og_url,
            "og_image": og_image,
            "twitter_card": twitter_card,
            "ok": metadata_ok,
        },
    })

    admin = fetch(f"{base_url}/admin", "text/html")
    admin_html = admin["body"].decode("utf-8", errors="replace")
    admin_inline_script_blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", admin_html, flags=re.I)
    admin_inline_event_handlers = re.findall(r"\s+on[a-z]+\s*=", admin_html, flags=re.I)
    checks.append({
        "name": "admin_dashboard",
        "ok": (
            admin["status"] == 200
            and expected_asset_marker in admin_html
            and "/api/admin/overview" in admin_html
            and "aggregate-only" in admin_html
            and not admin_inline_script_blocks
            and not admin_inline_event_handlers
        ),
        "status": admin["status"],
        "duration_ms": admin["duration_ms"],
        "expected_asset_marker": expected_asset_marker in admin_html,
        "has_overview_endpoint_copy": "/api/admin/overview" in admin_html,
        "no_inline_script_surface": not admin_inline_script_blocks and not admin_inline_event_handlers,
    })

    assets = asset_urls(base_url, html, expected_asset_marker)
    asset_results = []
    script_icon_url_leaks: list[str] = []
    script_icon_version_ok = False
    css_required_guards = {
        "adminlte_sidebar_icon_filter": False,
        "adminlte_attachment_icon_filter": False,
        "adminlte_user_attachment_icon_filter": False,
        "adminlte_code_copy_icon_filter": False,
        "adminlte_code_copy_success_filter": False,
    }
    for url in assets:
        result = fetch(url, "*/*")
        content_type = result["headers"].get("content-type", "")
        content_type_base = content_type.split(";", 1)[0].strip().lower()
        is_svg = content_type_base == "image/svg+xml" or url.endswith(".svg")
        min_bytes = 100 if is_svg else 1000
        body_text = result["body"].decode("utf-8", errors="replace")
        if url.endswith(".js") or ".js?" in url:
            script_icon_url_leaks.extend(sorted(set(re.findall(r"/static/images/icons/[A-Za-z0-9_-]+\.svg(?!\?v=)", body_text))))
            script_icon_version_ok = script_icon_version_ok or js_icon_version_matches(body_text, expected_asset_marker)
        if url.endswith(".css") or ".css?" in url:
            css_required_guards["adminlte_sidebar_icon_filter"] = css_block_has(body_text, "body.hai-theme-adminlte-classic .sidebar-buttons .icon-svg", "filter: none !important")
            css_required_guards["adminlte_attachment_icon_filter"] = css_block_has(body_text, "body.hai-theme-adminlte-classic .hai-attachment-icon .icon-svg", "filter: none !important")
            css_required_guards["adminlte_user_attachment_icon_filter"] = css_block_has(body_text, "body.hai-theme-adminlte-classic .hai-user-attachment-chip .icon-svg", "filter: none !important")
            css_required_guards["adminlte_code_copy_icon_filter"] = css_block_has(body_text, "body.hai-theme-adminlte-classic .code-block .code-title .copy-button .icon-svg", "filter: brightness(0) invert(1) !important")
            css_required_guards["adminlte_code_copy_success_filter"] = css_block_has(body_text, "body.hai-theme-adminlte-classic .code-block .code-title .copy-button.is-copied .icon-svg", "filter: none !important")
        asset_results.append({
            "url": url,
            "status": result["status"],
            "duration_ms": result["duration_ms"],
            "content_type": content_type,
            "bytes": len(result["body"]),
            "ok": result["status"] == 200 and len(result["body"]) > min_bytes,
        })
    checks.append({
        "name": "assets",
        "ok": len(asset_results) >= 2 and all(item["ok"] for item in asset_results) and not script_icon_url_leaks and script_icon_version_ok and all(css_required_guards.values()),
        "assets": asset_results,
        "script_icon_url_leaks": script_icon_url_leaks,
        "script_icon_version_ok": script_icon_version_ok,
        "css_required_guards": css_required_guards,
    })

    health = fetch(f"{base_url}/healthz", "application/json")
    health_json = json_body(health)
    checks.append({
        "name": "healthz",
        "ok": (
            health["status"] == 200
            and health_json.get("ok") is True
            and health_json.get("service") == "harmonika-chat-webui"
            and health_json.get("security", {}).get("flask_secret_configured") is True
            and health_json.get("security", {}).get("device_secret_configured") is True
        ),
        "status": health["status"],
        "duration_ms": health["duration_ms"],
        "json": health_json,
    })

    capabilities = fetch(f"{base_url}/api/capabilities", "application/json")
    capabilities_json = json_body(capabilities)
    features = capabilities_json.get("features", {})
    limits = capabilities_json.get("limits", {})
    image_generation = capabilities_json.get("image_generation", {}) if isinstance(capabilities_json.get("image_generation"), dict) else {}
    chat_routing = capabilities_json.get("chat_routing", {}) if isinstance(capabilities_json.get("chat_routing"), dict) else {}
    rate_limit = capabilities_json.get("rate_limit", {}) if isinstance(capabilities_json.get("rate_limit"), dict) else {}
    expected_features = [
        "chat",
        "streaming",
        "realtime_replay_api",
        "realtime_replay_state",
        "realtime_resume",
        "realtime_wss_ticket_endpoint",
        "admin_overview",
        "admin_dashboard",
        "observability_aggregate",
        "google_mode",
        "member_ai_chat_bridge",
        "member_ai_chat_session_isolation",
        "codex_task_routing",
        "web_search",
        "sources",
        "file_upload",
        "rag_library_api",
        "rag_library_ui",
        "rag_library_grounding",
        "rag_library_server_grounding",
        "rag_library_chunked_retrieval",
        "rag_library_lexical_rerank",
        "rag_library_bm25_sparse_rerank",
        "rag_library_vector_index",
        "rag_library_hybrid_retrieval",
        "rag_library_semantic_expansion",
        "rag_library_full_context",
        "rag_library_sparse_index",
        "rag_library_grounding_toggle",
        "pdf_input",
        "memory",
        "message_queue",
        "artifact_canvas",
    ]
    expected_image_features = [
        "image_generation",
        "image_generation_sse",
        "image_preview",
        "image_download",
        "raster_image_generation",
        "member_ai_image_bridge",
    ]
    checks.append({
        "name": "capabilities",
        "ok": (
            capabilities["status"] == 200
            and capabilities_json.get("ok") is True
            and all(features.get(name) is True for name in expected_features)
            and features.get("realtime_wss") is False
            and all(features.get(name) is True for name in expected_image_features)
            and chat_routing.get("default_mode") == "google"
            and chat_routing.get("codex_mode") == "codex"
            and chat_routing.get("text_backend") == "chat.harmonika.id/member-ai"
            and chat_routing.get("answer_mode") == "google"
            and chat_routing.get("question_mode") == "google"
            and chat_routing.get("analysis_mode") == "google"
            and chat_routing.get("conversation_mode") == "google"
            and chat_routing.get("story_companion_mode") == "google"
            and chat_routing.get("general_chat_mode") == "google"
            and chat_routing.get("file_and_image_input_mode") == "google"
            and chat_routing.get("attachment_understanding_mode") == "google"
            and chat_routing.get("file_input_mode") == "google"
            and chat_routing.get("image_input_mode") == "google"
            and chat_routing.get("question_analysis_story_mode") == "google"
            and chat_routing.get("image_creation_task_mode") == "codex"
            and chat_routing.get("image_creation_request_mode") == "codex"
            and chat_routing.get("technical_task_mode") == "codex"
            and chat_routing.get("heavy_task_mode") == "codex"
            and chat_routing.get("code_analysis_mode") == "codex"
            and chat_routing.get("codex_policy") == "heavy_technical_only"
            and chat_routing.get("google_mode_policy") == "primary_for_answers_questions_analysis_story_web_files_images"
            and chat_routing.get("chat_bridge_session_policy") == "locked_reset_per_request"
            and chat_routing.get("codex_handoff_policy") == "only_for_explicit_heavy_technical_symptom_or_private_image_creation"
            and chat_routing.get("routing_summary") == "google_default_codex_for_heavy_technical_and_image_creation"
            and chat_routing.get("public_urls") is False
            and rate_limit.get("storage") == "file"
            and rate_limit.get("shared_across_workers") is True
            and rate_limit.get("library_bucket") == "library"
            and limits.get("library_retrieval_mode") == "hybrid_vector_lexical_semantic_rerank"
            and limits.get("library_ranking_mode") == "hybrid_vector_bm25_coverage_rerank"
            and limits.get("library_vector_mode") == "private_local_hash_embedding"
            and int(limits.get("library_vector_dimensions") or 0) >= 16
            and limits.get("library_semantic_expansion") is True
            and limits.get("library_index_mode") == "private_hybrid_sparse_vector_chunk_index"
            and limits.get("library_context_mode") == "snippet_or_full_context_server_side"
            and limits.get("library_context_modes") == ["snippet", "full"]
            and limits.get("library_grounding_mode") == "auto_toggle_server_side"
            and limits.get("library_grounding_modes") == ["auto", "force", "off"]
            and limits.get("realtime_wss_ready") is False
            and isinstance(limits.get("realtime_replay_state_fields"), list)
            and "last_event_id" in limits.get("realtime_replay_state_fields", [])
            and limits.get("realtime_wss_ticket_endpoint") == "/api/realtime/ticket"
            and limits.get("admin_overview_endpoint") == "/api/admin/overview"
            and limits.get("admin_dashboard_path") == "/admin"
            and image_generation.get("mode") == "member_ai_bridge"
            and image_generation.get("result_format") == "private_file_artifact"
            and image_generation.get("public_urls") is False
            and image_generation.get("raster_public") is True
            and image_generation.get("backend") == "chat.harmonika.id"
            and int(limits.get("attachments_per_message", 0)) >= 3
            and int(limits.get("max_upload_bytes", 0)) >= 10 * 1024 * 1024
            and int(limits.get("image_generations_per_day", 0)) > 0
            and len(limits.get("image_sizes", []) or []) > 0
        ),
        "status": capabilities["status"],
        "duration_ms": capabilities["duration_ms"],
        "features": {name: features.get(name) for name in expected_features},
        "image_features": {name: features.get(name) for name in expected_image_features},
        "image_generation": image_generation,
        "chat_routing": chat_routing,
        "rate_limit": rate_limit,
        "limits": {
            "attachments_per_message": limits.get("attachments_per_message"),
            "max_upload_bytes": limits.get("max_upload_bytes"),
            "image_generations_per_day": limits.get("image_generations_per_day"),
            "image_sizes": limits.get("image_sizes"),
        },
    })

    readiness = fetch(f"{base_url}/api/readiness", "application/json")
    readiness_json = json_body(readiness)
    production = readiness_json.get("production", {}) if isinstance(readiness_json.get("production"), dict) else {}
    gate_result = production.get("gate_result", {}) if isinstance(production.get("gate_result"), dict) else {}
    core = readiness_json.get("core", {}) if isinstance(readiness_json.get("core"), dict) else {}
    roadmap = readiness_json.get("roadmap", {}) if isinstance(readiness_json.get("roadmap"), dict) else {}
    contracts = readiness_json.get("contracts", {}) if isinstance(readiness_json.get("contracts"), dict) else {}
    next_priorities = readiness_json.get("next_priorities") if isinstance(readiness_json.get("next_priorities"), list) else []
    priority_ids = [
        item.get("id")
        for item in next_priorities
        if isinstance(item, dict)
    ]
    required_core = [
        "chat",
        "streaming",
        "history",
        "responsive_ui",
        "google_mode_backend",
        "file_upload",
        "pdf_input",
        "image_input",
        "image_artifact_preview",
        "message_queue",
        "artifact_canvas_basic",
        "realtime_replay_api",
        "admin_analytics",
        "release_gate",
    ]
    required_roadmap = [
        "raster_image_generation",
        "rag_library",
        "realtime_resume_wss",
        "voice_video",
        "calendar_automation_admin",
        "admin_analytics",
    ]
    checks.append({
        "name": "readiness",
        "ok": (
            readiness["status"] == 200
            and readiness_json.get("ok") is True
            and readiness_json.get("service") == "harmonika-chat-webui"
            and production.get("public_mvp_ready") is True
            and production.get("full_platform_complete") is False
            and production.get("gate") == "phase319-public-release-gate"
            and gate_result.get("passed") == gate_result.get("total") == 72
            and gate_result.get("visual_snapshots_passed") == gate_result.get("visual_snapshots_total") == 17
            and all(core.get(name) is True for name in required_core)
            and all(isinstance(roadmap.get(name), dict) for name in required_roadmap)
            and priority_ids[:2] == ["rag_library", "realtime_resume_wss"]
            and contracts.get("admin_overview") is True
            and contracts.get("observability_aggregate") is True
            and contracts.get("admin_analytics") is True
            and contracts.get("admin_overview_endpoint") == "/api/admin/overview"
        ),
        "status": readiness["status"],
        "duration_ms": readiness["duration_ms"],
        "production": production,
        "core": {name: core.get(name) for name in required_core},
        "roadmap_status": {name: roadmap.get(name, {}).get("status") if isinstance(roadmap.get(name), dict) else None for name in required_roadmap},
        "next_priority_ids": priority_ids,
    })

    ok = all(check["ok"] for check in checks)
    summary = {
        "ok": ok,
        "base_url": base_url,
        "expected_asset_marker": expected_asset_marker,
        "checks": checks,
        "passed": sum(1 for check in checks if check["ok"]),
        "total_run": len(checks),
    }
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
