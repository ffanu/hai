#!/usr/bin/env python3
"""Visual snapshot QA for hai.harmonika.id.

This wrapper captures deterministic desktop/mobile/tablet/landscape screenshots through
``hai_browser_qa.py`` and validates the resulting PNG dimensions. It is not a
pixel-perfect visual diff; it is a release artifact generator plus a smoke gate
that proves the public shell can render at production viewport sizes.

Examples:
  python3 scripts/hai_visual_qa.py --base-url https://hai.harmonika.id --out-dir qa-screenshots/latest
  python3 scripts/hai_visual_qa.py --base-url https://hai.harmonika.id --include-chat --include-composer-states --json-out qa-reports/visual.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
import subprocess
import sys
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]
EXPECTED_VIEWPORTS = {
    "compact": (320, 700),
    "desktop": (1365, 900),
    "mobile": (390, 844),
    "tablet": (820, 1180),
    "landscape": (844, 390),
}


def png_size(path: pathlib.Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"{path} bukan PNG valid")
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def extract_json(stdout: str) -> dict:
    text = stdout.strip()
    start = text.find("{")
    if start < 0:
        return {}
    decoder = json.JSONDecoder()
    try:
        value, _ = decoder.raw_decode(text[start:])
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def extract_component_crops(stdout: str) -> list[dict]:
    payload = extract_json(stdout)
    crops = payload.get("qa", {}).get("component_crops") if isinstance(payload.get("qa"), dict) else None
    if isinstance(crops, list):
        return [item for item in crops if isinstance(item, dict)]
    for line in stdout.splitlines():
        if not line.startswith("component_crops="):
            continue
        try:
            value = json.loads(line.split("=", 1)[1])
            return value if isinstance(value, list) else []
        except json.JSONDecodeError:
            return []
    return []


def flow_supports_component_crops(flow: str) -> bool:
    return flow in {"markdown-rich", "composer-queue-state", "sources-stack"}


def run_snapshot(
    base_url: str,
    viewport: str,
    flow: str,
    out_dir: pathlib.Path,
    timeout: int,
    component_crops: bool = False,
) -> dict:
    screenshot = out_dir / f"{viewport}-{flow}.png"
    crop_dir = out_dir / "components"
    command = [
        sys.executable,
        "scripts/hai_browser_qa.py",
        "--url",
        f"{base_url}/",
        "--viewport",
        viewport,
        "--flow",
        flow,
        "--timeout",
        str(timeout),
        "--screenshot",
        str(screenshot),
    ]
    if component_crops:
        command.extend(["--component-crops-dir", str(crop_dir)])
    if flow == "chat-text":
        command.append("--mock-chat")
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout + 80,
    )
    duration_ms = int((time.time() - started) * 1000)
    metrics = extract_json(proc.stdout)
    crops = extract_component_crops(proc.stdout)
    image_width = image_height = 0
    image_ok = False
    image_error = None
    try:
        image_width, image_height = png_size(screenshot)
        expected_width, expected_height = EXPECTED_VIEWPORTS[viewport]
        image_ok = image_width == expected_width and image_height == expected_height and screenshot.stat().st_size > 10_000
    except Exception as exc:  # pragma: no cover - diagnostic path
        image_error = str(exc)

    crops_ok = True
    if component_crops and flow_supports_component_crops(flow):
        crops_ok = bool(crops) and all(item.get("ok") for item in crops)

    ok = (
        proc.returncode == 0
        and bool(metrics)
        and not metrics.get("horizontalOverflow")
        and image_ok
        and crops_ok
    )
    if flow != "empty":
        ok = ok and bool(metrics.get("ok"))

    return {
        "name": f"{viewport}_{flow}",
        "ok": bool(ok),
        "returncode": proc.returncode,
        "duration_ms": duration_ms,
        "screenshot": str(screenshot),
        "screenshot_bytes": screenshot.stat().st_size if screenshot.exists() else 0,
        "image_width": image_width,
        "image_height": image_height,
        "image_error": image_error,
        "component_crops": crops,
        "metrics": metrics,
        "stdout": proc.stdout[-3000:],
        "stderr": proc.stderr[-3000:],
    }


def is_transient_chat_backend_error(result: dict) -> bool:
    metrics = result.get("metrics") or {}
    sample = str(metrics.get("assistantSample") or "")
    return result.get("name", "").endswith("_chat-text") and (
        "Kode: 502" in sample
        or "network error" in sample.lower()
        or "belum bisa menjawab" in sample.lower()
    )


def is_transient_browser_context_error(result: dict) -> bool:
    stderr = str(result.get("stderr") or "")
    return "Execution context was destroyed" in stderr or "Cannot find context with specified id" in stderr


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://hai.harmonika.id")
    parser.add_argument("--out-dir", default="qa-screenshots/latest")
    parser.add_argument("--json-out", help="Optional path to write full JSON summary.")
    parser.add_argument("--include-chat", action="store_true", help="Also capture chat-text snapshots for each viewport.")
    parser.add_argument("--include-composer-states", action="store_true", help="Also capture composer queue/streaming state snapshots for each viewport.")
    parser.add_argument("--include-rich-content", action="store_true", help="Also capture markdown-rich snapshots with headings, lists, tables, and code blocks.")
    parser.add_argument("--include-source-states", action="store_true", help="Also capture source/reference stack snapshots for desktop and mobile.")
    parser.add_argument("--include-component-crops", action="store_true", help="Also save cropped component screenshots for supported flows.")
    parser.add_argument("--viewports", default="desktop,mobile,tablet,landscape", help="Comma-separated viewport names to capture.")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    selected_viewports = [item.strip() for item in args.viewports.split(",") if item.strip()]
    unknown = [item for item in selected_viewports if item not in EXPECTED_VIEWPORTS]
    if unknown:
        parser.error(f"Viewport tidak dikenal: {', '.join(unknown)}")

    jobs = [(viewport, "empty", 45) for viewport in selected_viewports]
    if args.include_chat:
        jobs.extend((viewport, "chat-text", 75) for viewport in selected_viewports)
    if args.include_rich_content:
        rich_viewports = [viewport for viewport in selected_viewports if viewport in {"desktop", "mobile", "compact"}]
        if "mobile" in selected_viewports and "compact" not in rich_viewports:
            rich_viewports.append("compact")
        jobs.extend((viewport, "markdown-rich", 45) for viewport in rich_viewports)
    if args.include_source_states:
        source_viewports = [viewport for viewport in selected_viewports if viewport in {"desktop", "mobile"}]
        jobs.extend((viewport, "sources-stack", 45) for viewport in source_viewports)
    if args.include_composer_states:
        jobs.extend((viewport, "composer-queue-state", 45) for viewport in selected_viewports)

    results = []
    ok = True
    for viewport, flow, timeout in jobs:
        result = run_snapshot(base_url, viewport, flow, out_dir, timeout, args.include_component_crops)
        attempts = [result]
        while (
            not result["ok"]
            and (is_transient_chat_backend_error(result) or is_transient_browser_context_error(result))
            and len(attempts) < 3
        ):
            time.sleep(2)
            result = run_snapshot(base_url, viewport, flow, out_dir, timeout, args.include_component_crops)
            result["attempt"] = len(attempts) + 1
            attempts.append(result)
        if len(attempts) > 1:
            result["previous_attempts"] = [
                {
                    "attempt": index + 1,
                    "ok": item["ok"],
                    "returncode": item["returncode"],
                    "assistantSample": (item.get("metrics") or {}).get("assistantSample"),
                    "transientBrowserContext": is_transient_browser_context_error(item),
                }
                for index, item in enumerate(attempts[:-1])
            ]
        results.append(result)
        ok = ok and result["ok"]
        print(json.dumps({
            "name": result["name"],
            "ok": result["ok"],
            "duration_ms": result["duration_ms"],
            "screenshot": result["screenshot"],
            "image_width": result["image_width"],
            "image_height": result["image_height"],
            "component_crops": [
                {
                    "name": item.get("name"),
                    "ok": item.get("ok"),
                    "path": item.get("path"),
                    "bytes": item.get("bytes"),
                }
                for item in result.get("component_crops", [])
            ],
        }, ensure_ascii=False), flush=True)
        if not result["ok"]:
            break

    summary = {
        "ok": ok,
        "base_url": base_url,
        "out_dir": str(out_dir),
        "include_chat": args.include_chat,
        "include_rich_content": args.include_rich_content,
        "include_source_states": args.include_source_states,
        "include_composer_states": args.include_composer_states,
        "include_component_crops": args.include_component_crops,
        "passed": sum(1 for item in results if item["ok"]),
        "total_run": len(results),
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
