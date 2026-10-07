#!/usr/bin/env python3
"""Production readiness QA runner for hai.harmonika.id.

This orchestrates the focused QA scripts used by recent phases. It intentionally
defaults to the core suite and leaves image generation opt-in because that flow
can consume production image quota.

Examples:
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --include-image
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --mobile --multi-attachment --json-out /tmp/hai-qa.json
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --web-sources
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --visual-snapshots --visual-out-dir qa-screenshots/latest
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --release-audit
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --a11y-smoke
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --streaming-states
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --stream-stall --quality-cleanup
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --queue-composer
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --layout-metrics
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --targeted-ui-gate
  python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --public-release-gate --json-out qa-reports/public-release-gate.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
from dataclasses import dataclass


ROOT = pathlib.Path(__file__).resolve().parents[1]


@dataclass
class Check:
    name: str
    command: list[str]
    timeout: int = 120
    expensive: bool = False
    retries: int = 0
    retry_delay: float = 2.0


def extract_json(stdout: str) -> dict:
    text = stdout.strip()
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            candidates.append(value)
    if not candidates:
        return {}
    for candidate in reversed(candidates):
        if candidate.get("ok") in {True, False} and "total_run" in candidate:
            return candidate
    for candidate in reversed(candidates):
        if any(key in candidate for key in ("passed", "total_run", "results", "checks")):
            return candidate
    return candidates[-1]


def summarize_child_json(stdout: str) -> dict:
    payload = extract_json(stdout)
    if not payload:
        return {}
    passed = payload.get("passed")
    total_run = payload.get("total_run")
    summary = {
        "ok": payload.get("ok"),
        "passed": passed,
        "total_run": total_run,
    }
    if payload.get("out_dir"):
        summary["out_dir"] = payload.get("out_dir")
    if payload.get("expected_asset_marker"):
        summary["expected_asset_marker"] = payload.get("expected_asset_marker")
    if isinstance(payload.get("results"), list):
        if passed is None:
            summary["passed"] = sum(1 for item in payload["results"] if isinstance(item, dict) and item.get("ok") is True)
        if total_run is None:
            summary["total_run"] = len([item for item in payload["results"] if isinstance(item, dict)])
        summary["children"] = [
            {
                "name": item.get("name"),
                "ok": item.get("ok"),
                "duration_ms": item.get("duration_ms"),
                "screenshot": item.get("screenshot"),
            }
            for item in payload["results"]
            if isinstance(item, dict)
        ]
    if isinstance(payload.get("checks"), list):
        if passed is None:
            summary["passed"] = sum(1 for item in payload["checks"] if isinstance(item, dict) and item.get("ok") is True)
        if total_run is None:
            summary["total_run"] = len([item for item in payload["checks"] if isinstance(item, dict)])
        summary["children"] = [
            {
                "name": item.get("name"),
                "ok": item.get("ok"),
                "status": item.get("status"),
            }
            for item in payload["checks"]
            if isinstance(item, dict)
        ]
    if payload.get("ok") in {True, False} and summary.get("passed") is None and summary.get("total_run") is None:
        summary["passed"] = 1 if payload.get("ok") is True else 0
        summary["total_run"] = 1
    return {key: value for key, value in summary.items() if value is not None}


def detect_local_asset_marker() -> str:
    template = ROOT / "templates" / "index.html"
    html = template.read_text(encoding="utf-8")
    markers = re.findall(r'''(?:styles\.css|scripts\.js).*?\?v=([^"']+)''', html, flags=re.DOTALL)
    unique_markers = sorted(set(markers))
    if len(unique_markers) != 1:
        raise ValueError(f"Asset marker lokal tidak konsisten di {template}: {unique_markers}")
    return unique_markers[0]


def resolve_project_python() -> str:
    """Use the project virtualenv when available.

    Several QA scripts import `app.py`, which depends on packages installed in
    `.venv`. If this runner is launched with the system Python, those child
    checks can fail with missing dependencies even though production and the
    project venv are healthy.
    """
    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def run_check_once(check: Check) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(
            check.command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=check.timeout,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.time() - started) * 1000)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        return {
            "name": check.name,
            "ok": False,
            "returncode": None,
            "duration_ms": duration_ms,
            "command": check.command,
            "child_summary": None,
            "stdout": stdout[-4000:],
            "stderr": (stderr[-4000:] + f"\nTimed out after {check.timeout}s").strip(),
            "timed_out": True,
        }
    duration_ms = int((time.time() - started) * 1000)
    child_summary = summarize_child_json(proc.stdout)
    if proc.returncode == 0 and child_summary:
        stdout = ""
    else:
        stdout_limit = 4000 if proc.returncode != 0 else 1200
        stdout = proc.stdout[-stdout_limit:]
    return {
        "name": check.name,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "duration_ms": duration_ms,
        "command": check.command,
        "child_summary": child_summary or None,
        "stdout": stdout,
        "stderr": proc.stderr[-4000:],
    }


def is_transient_browser_context_error(result: dict) -> bool:
    stderr = str(result.get("stderr") or "")
    return "Execution context was destroyed" in stderr or "Cannot find context with specified id" in stderr


def run_check(check: Check) -> dict:
    attempts = []
    extra_transient_retry_used = False
    attempt_index = 0
    while True:
        result = run_check_once(check)
        result["attempt"] = attempt_index + 1
        attempts.append(result)
        if result["ok"]:
            break
        has_configured_retry_left = attempt_index < check.retries
        should_use_transient_retry = (
            not has_configured_retry_left
            and not extra_transient_retry_used
            and is_transient_browser_context_error(result)
        )
        if should_use_transient_retry:
            extra_transient_retry_used = True
        elif not has_configured_retry_left:
            break
        time.sleep(check.retry_delay)
        attempt_index += 1
    final = attempts[-1]
    if len(attempts) > 1:
        final["attempts"] = [
            {
                "attempt": item["attempt"],
                "ok": item["ok"],
                "returncode": item["returncode"],
                "duration_ms": item["duration_ms"],
                "child_summary": item["child_summary"],
            }
            for item in attempts
        ]
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://hai.harmonika.id")
    parser.add_argument("--public-release-gate", action="store_true", help="Run the standard public release gate: core, mobile, multi-file, web sources, streaming states, stream stall, quality cleanup, queue composer, layout metrics, a11y smoke, visual snapshots, and release audit. Use --include-image separately for image quota smoke.")
    parser.add_argument("--targeted-ui-gate", action="store_true", help="Also run the small Phase 274 targeted UI gate: release audit, streaming states desktop/mobile, markdown-rich desktop/mobile, and mobile chat smoke.")
    parser.add_argument("--include-image", action="store_true", help="Also run image generation artifact QA.")
    parser.add_argument("--mobile", action="store_true", help="Also run selected mobile browser flows.")
    parser.add_argument("--multi-attachment", action="store_true", help="Also run multi-file attachment browser flows.")
    parser.add_argument("--web-sources", action="store_true", help="Also run web/search source chip browser flow.")
    parser.add_argument("--visual-snapshots", action="store_true", help="Also capture desktop/mobile/tablet/landscape visual screenshots.")
    parser.add_argument("--visual-out-dir", default="qa-screenshots/production", help="Directory for --visual-snapshots artifacts.")
    parser.add_argument("--release-audit", action="store_true", help="Also run HTTP release audit for health, assets, and headers.")
    parser.add_argument("--a11y-smoke", action="store_true", help="Also run desktop/mobile browser accessibility smoke checks.")
    parser.add_argument("--streaming-states", action="store_true", help="Also run deterministic browser checks for text-vs-image loading states.")
    parser.add_argument("--stream-stall", action="store_true", help="Also run deterministic browser checks that heartbeat-only stalled streams finalize cleanly.")
    parser.add_argument("--quality-cleanup", action="store_true", help="Also run deterministic browser checks for conservative typo/duplicate cleanup in assistant final text.")
    parser.add_argument("--queue-composer", action="store_true", help="Also run deterministic browser checks for queuing a draft while a response is active.")
    parser.add_argument("--layout-metrics", action="store_true", help="Also run deterministic CSS/layout metrics checks for composer-aware spacing and message action bars.")
    parser.add_argument("--expected-asset-marker", help="Expected CSS/JS cache-bust marker for --release-audit. Defaults to templates/index.html marker.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on the first failed check. By default the runner collects all check results.")
    parser.add_argument("--json-out", help="Optional path to write the full JSON summary for release artifacts.")
    args = parser.parse_args()

    python = resolve_project_python()
    base_url = args.base_url.rstrip("/")
    expected_asset_marker = args.expected_asset_marker or detect_local_asset_marker()
    if args.public_release_gate:
        args.mobile = True
        args.multi_attachment = True
        args.web_sources = True
        args.a11y_smoke = True
        args.streaming_states = True
        args.stream_stall = True
        args.quality_cleanup = True
        args.queue_composer = True
        args.layout_metrics = True
        args.visual_snapshots = True
        args.release_audit = True
        if args.visual_out_dir == "qa-screenshots/production":
            args.visual_out_dir = "qa-screenshots/public-release-gate"
    checks = [
        Check("py_compile", [python, "-m", "py_compile", "app.py", "scripts/hai_browser_qa.py", "scripts/hai_history_qa.py", "scripts/hai_attachment_qa.py", "scripts/hai_library_qa.py", "scripts/hai_library_ui_qa.py", "scripts/hai_backend_contract_qa.py", "scripts/hai_image_contract_qa.py", "scripts/hai_vision_contract_qa.py", "scripts/hai_visual_qa.py", "scripts/hai_release_audit.py", "scripts/hai_readiness_qa.py", "scripts/hai_url_safety_qa.py", "scripts/hai_sources_header_qa.py", "scripts/hai_stream_open_qa.py", "scripts/hai_routing_qa.py", "scripts/hai_rate_limit_qa.py", "scripts/hai_realtime_qa.py", "scripts/hai_admin_overview_qa.py", "scripts/hai_gemini_report_qa.py", "scripts/hai_agent_audit.py", "scripts/hai_targeted_ui_gate.py", "scripts/hai_production_qa.py"], 60),
        Check("gemini_report_local", [python, "scripts/hai_gemini_report_qa.py"], 60),
        Check("js_syntax", ["node", "--check", "static/js/scripts.js"], 60),
        Check("url_safety_local", [python, "scripts/hai_url_safety_qa.py"], 60),
        Check("sources_header_local", [python, "scripts/hai_sources_header_qa.py"], 60),
        Check("stream_open_local", [python, "scripts/hai_stream_open_qa.py"], 60),
        Check("routing_policy_local", [python, "scripts/hai_routing_qa.py"], 60),
        Check("rate_limit_storage_local", [python, "scripts/hai_rate_limit_qa.py"], 60),
        Check("realtime_replay_local", [python, "scripts/hai_realtime_qa.py"], 60),
        Check("admin_dashboard_local", [python, "scripts/hai_admin_overview_qa.py"], 60),
        Check("library_api_local", [python, "scripts/hai_library_qa.py"], 60),
        Check("library_ui_local", [python, "scripts/hai_library_ui_qa.py"], 60),
        Check("backend_contract_api", [python, "scripts/hai_backend_contract_qa.py", "--base-url", base_url], 60),
        Check("readiness_api", [python, "scripts/hai_readiness_qa.py", "--base-url", base_url], 60),
        Check("image_contract_api", [python, "scripts/hai_image_contract_qa.py", "--base-url", base_url], 240, retries=1, retry_delay=3.0),
        Check("vision_contract_api", [python, "scripts/hai_vision_contract_qa.py", "--base-url", base_url], 140),
        Check("history_api", [python, "scripts/hai_history_qa.py", "--base-url", base_url], 60),
        Check("attachment_api", [python, "scripts/hai_attachment_qa.py", "--base-url", base_url], 90),
        Check("browser_empty_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "empty", "--timeout", "45"], 90),
        Check("browser_sidebar_collapse_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "sidebar-collapse", "--timeout", "45"], 90),
        Check("browser_chat_text_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "chat-text", "--timeout", "70"], 120, retries=1, retry_delay=2.0),
        Check("browser_history_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "history-controls", "--timeout", "60"], 120),
        Check("browser_library_panel_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "library-panel", "--timeout", "45"], 90),
        Check("browser_stop_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "stop-stream", "--timeout", "80"], 120, retries=1, retry_delay=2.0),
        Check("browser_regenerate_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "regenerate", "--timeout", "90"], 140, retries=2, retry_delay=12.0),
        Check("browser_error_retry_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "error-retry", "--timeout", "60"], 100),
        Check("browser_error_history_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "error-history-hygiene", "--timeout", "70"], 110),
        Check("browser_edit_error_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "edit-error", "--timeout", "70"], 110),
        Check("browser_continue_error_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "continue-error", "--timeout", "70"], 110),
        Check("browser_attachment_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "attachment-chat", "--timeout", "100"], 140, retries=2, retry_delay=12.0),
        Check("browser_attachment_image_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "attachment-image-chat", "--timeout", "120"], 170, retries=2, retry_delay=12.0),
    ]
    if args.mobile:
        checks.extend([
            Check("browser_empty_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "empty", "--timeout", "45"], 90),
            Check("browser_history_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "history-controls", "--timeout", "60"], 120),
            Check("browser_library_panel_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "library-panel", "--timeout", "45"], 90),
            Check("browser_stop_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "stop-stream", "--timeout", "80"], 120, retries=1, retry_delay=2.0),
            Check("browser_regenerate_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "regenerate", "--timeout", "90"], 140, retries=2, retry_delay=8.0),
            Check("browser_error_retry_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "error-retry", "--timeout", "60"], 100, retries=1, retry_delay=2.0),
            Check("browser_error_history_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "error-history-hygiene", "--timeout", "70"], 110),
            Check("browser_edit_error_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "edit-error", "--timeout", "70"], 110),
            Check("browser_continue_error_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "continue-error", "--timeout", "70"], 110),
            Check("browser_attachment_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "attachment-chat", "--timeout", "100"], 140, retries=2, retry_delay=2.0),
            Check("browser_attachment_image_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "attachment-image-chat", "--timeout", "120"], 170, retries=2, retry_delay=8.0),
        ])
    if args.multi_attachment:
        checks.append(Check("browser_attachment_multi_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "attachment-multi-chat", "--timeout", "120"], 170, retries=2, retry_delay=8.0))
        if args.mobile:
            checks.append(Check("browser_attachment_multi_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "attachment-multi-chat", "--timeout", "120"], 170, retries=2, retry_delay=2.0))
    if args.web_sources:
        checks.append(Check("browser_sources_web_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "sources-web", "--timeout", "120"], 170, retries=2, retry_delay=3.0))
        checks.append(Check("browser_sources_stack_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "sources-stack", "--timeout", "45"], 90))
        if args.mobile:
            checks.append(Check("browser_sources_web_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "sources-web", "--timeout", "120"], 170, retries=2, retry_delay=3.0))
            checks.append(Check("browser_sources_stack_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "sources-stack", "--timeout", "45"], 90))
    if args.a11y_smoke:
        checks.append(Check("browser_a11y_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "a11y-smoke", "--timeout", "45"], 90))
        if args.mobile:
            checks.append(Check("browser_a11y_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "a11y-smoke", "--timeout", "45"], 90))
    if args.streaming_states:
        checks.append(Check("browser_streaming_states_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "streaming-states", "--timeout", "45"], 90))
        if args.mobile:
            checks.append(Check("browser_streaming_states_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "streaming-states", "--timeout", "45"], 90))
    if args.stream_stall:
        checks.append(Check("browser_stream_stall_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "stream-stall", "--timeout", "60"], 100))
        checks.append(Check("browser_empty_stream_fallback_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "empty-stream-fallback", "--timeout", "45"], 90))
        checks.append(Check("browser_realtime_resume_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "realtime-resume", "--timeout", "60"], 100))
        if args.mobile:
            checks.append(Check("browser_stream_stall_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "stream-stall", "--timeout", "60"], 100))
            checks.append(Check("browser_empty_stream_fallback_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "empty-stream-fallback", "--timeout", "45"], 90))
            checks.append(Check("browser_realtime_resume_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "realtime-resume", "--timeout", "60"], 100))
    if args.quality_cleanup:
        checks.append(Check("browser_quality_cleanup_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "quality-cleanup", "--timeout", "45"], 90))
        if args.mobile:
            checks.append(Check("browser_quality_cleanup_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "quality-cleanup", "--timeout", "45"], 90))
    if args.queue_composer:
        checks.append(Check("browser_queue_composer_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "queue-composer", "--timeout", "45"], 90))
        if args.mobile:
            checks.append(Check("browser_queue_composer_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "queue-composer", "--timeout", "45"], 90))
    if args.layout_metrics:
        checks.append(Check("browser_layout_metrics_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "layout-metrics", "--timeout", "45"], 90))
        checks.append(Check("browser_composer_keyboard_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "composer-keyboard", "--timeout", "45"], 90))
        if args.mobile:
            checks.append(Check("browser_layout_metrics_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "layout-metrics", "--timeout", "45"], 90))
            checks.append(Check("browser_composer_keyboard_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "composer-keyboard", "--timeout", "45"], 90))
    if args.public_release_gate:
        checks.append(Check("browser_image_modal_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "image-modal", "--timeout", "45"], 90))
        if args.mobile:
            checks.append(Check("browser_image_modal_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "image-modal", "--timeout", "45"], 90))
        checks.append(Check("browser_export_localization_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "export-localization", "--timeout", "45"], 90))
        checks.append(Check("browser_attachment_preview_a11y_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "attachment-preview-a11y", "--timeout", "45"], 90))
        checks.append(Check("browser_markdown_rich_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "markdown-rich", "--timeout", "45"], 90))
        if args.mobile:
            checks.append(Check("browser_markdown_rich_mobile", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "mobile", "--flow", "markdown-rich", "--timeout", "45"], 90))
    if args.include_image:
        checks.append(Check("browser_image_artifact_desktop", [python, "scripts/hai_browser_qa.py", "--url", f"{base_url}/", "--viewport", "desktop", "--flow", "image-artifact", "--timeout", "110"], 180, expensive=True))
    if args.visual_snapshots:
        checks.append(Check("visual_snapshots", [python, "scripts/hai_visual_qa.py", "--base-url", base_url, "--out-dir", args.visual_out_dir, "--include-chat", "--include-rich-content", "--include-source-states", "--include-composer-states", "--include-component-crops"], 540, retries=1, retry_delay=3.0))
    if args.release_audit:
        checks.append(Check("release_audit", [python, "scripts/hai_release_audit.py", "--base-url", base_url, "--expected-asset-marker", expected_asset_marker], 80))
    if args.targeted_ui_gate:
        checks.append(Check("targeted_ui_gate", [python, "scripts/hai_targeted_ui_gate.py", "--base-url", base_url, "--expected-asset-marker", expected_asset_marker], 560))

    results = []
    ok = True
    for check in checks:
        result = run_check(check)
        results.append(result)
        ok = ok and result["ok"]
        print(json.dumps({
            "name": result["name"],
            "ok": result["ok"],
            "returncode": result["returncode"],
            "duration_ms": result["duration_ms"],
        }, ensure_ascii=False), flush=True)
        if args.fail_fast and not result["ok"]:
            break

    failed = [item["name"] for item in results if not item["ok"]]
    summary = {
        "ok": ok,
        "base_url": base_url,
        "public_release_gate": args.public_release_gate,
        "targeted_ui_gate": args.targeted_ui_gate,
        "include_image": args.include_image,
        "mobile": args.mobile,
        "multi_attachment": args.multi_attachment,
        "web_sources": args.web_sources,
        "visual_snapshots": args.visual_snapshots,
        "visual_out_dir": args.visual_out_dir if args.visual_snapshots else None,
        "release_audit": args.release_audit,
        "a11y_smoke": args.a11y_smoke,
        "streaming_states": args.streaming_states,
        "stream_stall": args.stream_stall,
        "quality_cleanup": args.quality_cleanup,
        "queue_composer": args.queue_composer,
        "layout_metrics": args.layout_metrics,
        "expected_asset_marker": expected_asset_marker if (args.release_audit or args.targeted_ui_gate) else None,
        "passed": sum(1 for item in results if item["ok"]),
        "total_run": len(results),
        "total_planned": len(checks),
        "failed": failed,
        "fail_fast": args.fail_fast,
        "results": results,
    }
    if args.json_out:
        out = pathlib.Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
