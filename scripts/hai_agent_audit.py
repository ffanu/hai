#!/usr/bin/env python3
"""Run bounded non-edit audits with local Claude/opencode agents.

The script is intentionally conservative:
- It never edits project files.
- It uses subprocess timeouts so an agent cannot hang the release workflow.
- It writes a JSON artifact that can be attached to phase reports.

Examples:
  python3 scripts/hai_agent_audit.py --agent claude --timeout 120 --json-out qa-reports/agent-claude.json
  python3 scripts/hai_agent_audit.py --agent opencode --timeout 120 --json-out qa-reports/agent-opencode.json
  python3 scripts/hai_agent_audit.py --agent both --timeout 120 --json-out qa-reports/agent-audit.json
  python3 scripts/hai_agent_audit.py --agent both --timeout 90 --accept-partial --json-out qa-reports/agent-audit.json
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]

DEFAULT_PROMPT = (
    "Audit non-edit repo hai.harmonika.id. Fokus cari 3 gap kecil berikutnya "
    "agar web chat AI classic lebih production-ready. Periksa README, docs phase terbaru, "
    "scripts QA, readiness/capabilities, dan UX/production reporting. Jangan edit file. "
    "Jawab ringkas dengan prioritas, alasan, dan file/test command yang relevan."
)

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def clean_output(text: str) -> str:
    return ANSI_RE.sub("", text or "")


def agent_command(agent: str, prompt: str) -> list[str]:
    if agent == "claude":
        return ["claude", "-p", "--output-format", "text", "--dangerously-skip-permissions", prompt]
    if agent == "opencode":
        return ["opencode", "run", prompt]
    raise ValueError(f"Unknown agent: {agent}")


def run_agent(agent: str, prompt: str, timeout: int) -> dict:
    binary = "claude" if agent == "claude" else "opencode"
    if not shutil.which(binary):
        return {
            "agent": agent,
            "ok": False,
            "skipped": True,
            "error": f"{binary} not found in PATH",
            "stdout": "",
            "duration_ms": 0,
        }

    started = time.time()
    env = os.environ.copy()
    env.pop("FORCE_COLOR", None)
    env["NO_COLOR"] = "1"
    try:
        proc = subprocess.run(
            agent_command(agent, prompt),
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        duration_ms = int((time.time() - started) * 1000)
        stdout = clean_output(proc.stdout or "")
        stdout_chars = len(stdout.strip())
        return {
            "agent": agent,
            "ok": proc.returncode == 0 and bool(stdout.strip()),
            "useful": proc.returncode == 0 and stdout_chars >= 80,
            "partial": False,
            "returncode": proc.returncode,
            "timed_out": False,
            "duration_ms": duration_ms,
            "stdout_chars": stdout_chars,
            "stdout": stdout[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.time() - started) * 1000)
        stdout = exc.stdout or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        stdout = clean_output(stdout)
        stdout_chars = len(stdout.strip())
        return {
            "agent": agent,
            "ok": False,
            "useful": stdout_chars >= 300,
            "partial": stdout_chars >= 300,
            "returncode": None,
            "timed_out": True,
            "duration_ms": duration_ms,
            "stdout_chars": stdout_chars,
            "stdout": stdout[-12000:],
            "error": f"Timed out after {timeout}s",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=["claude", "opencode", "both"], default="both")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--accept-partial", action="store_true", help="Exit 0 when every agent either completes successfully or produces useful partial output before timeout.")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    agents = ["claude", "opencode"] if args.agent == "both" else [args.agent]
    results = [run_agent(agent, args.prompt, args.timeout) for agent in agents]
    strict_ok = all(item.get("ok") for item in results)
    useful_ok = all(item.get("ok") or item.get("useful") for item in results)
    summary = {
        "ok": strict_ok or (args.accept_partial and useful_ok),
        "strict_ok": strict_ok,
        "useful_ok": useful_ok,
        "accept_partial": args.accept_partial,
        "agents": agents,
        "timeout": args.timeout,
        "results": results,
        "passed": sum(1 for item in results if item.get("ok")),
        "useful": sum(1 for item in results if item.get("ok") or item.get("useful")),
        "partial": sum(1 for item in results if item.get("partial")),
        "total_run": len(results),
    }
    if args.json_out:
        out = pathlib.Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
