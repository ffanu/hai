#!/usr/bin/env python3
"""Local QA for Harmonika AI realtime replay foundation.

This intentionally avoids a live model call. It verifies the backend contract
used by future mobile/web resume flows:

- streaming responses can write ordered replay events,
- `/api/realtime/events` returns JSON replay after a sequence,
- the same endpoint can emit SSE replay frames,
- `/api/realtime/ticket` fails safe while WSS is not production-ready,
- missing/expired response ids fail with customer-safe JSON.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as hai_app  # noqa: E402


def add(checks: list[dict], name: str, ok: bool, **extra) -> None:
    item = {"name": name, "ok": bool(ok)}
    item.update(extra)
    checks.append(item)


def main() -> int:
    checks: list[dict] = []
    original_dir = hai_app.REALTIME_EVENT_DIR
    original_ttl = hai_app.REALTIME_EVENT_TTL_SECONDS

    with tempfile.TemporaryDirectory() as tmp_dir:
        hai_app.REALTIME_EVENT_DIR = tmp_dir
        hai_app.REALTIME_EVENT_TTL_SECONDS = 600
        response_id = "resp_realtime_qa"

        chunks = list(
            hai_app._stream_with_heartbeat(
                lambda emit: (emit("Halo"), emit(" realtime")),
                log_name="qa_realtime",
                response_id=response_id,
            )
        )
        record, events = hai_app._realtime_events_after(response_id, 0)
        add(
            checks,
            "stream_records_ordered_events",
            bool(
                record
                and record.get("status") == "completed"
                and chunks
                and events
                and [event.get("sequence") for event in events] == list(range(1, len(events) + 1))
                and events[0].get("type") == "response.created"
                and any(event.get("type") == "response.output_text.delta" and event.get("data", {}).get("text") == "Halo" for event in events)
                and events[-1].get("type") == "response.completed"
            ),
            event_types=[event.get("type") for event in events],
            chunks=chunks,
        )

        client = hai_app.app.test_client()
        json_response = client.get(f"/api/realtime/events?response_id={response_id}&after_sequence=1")
        json_body = json_response.get_json() or {}
        add(
            checks,
            "replay_json_after_sequence",
            bool(
                json_response.status_code == 200
                and json_body.get("ok") is True
                and json_body.get("response_id") == response_id
                and json_body.get("status") == "completed"
                and json_body.get("terminal") is True
                and isinstance(json_body.get("state"), dict)
                and json_body.get("state", {}).get("terminal") is True
                and json_body.get("state", {}).get("last_sequence") == len(events)
                and json_body.get("state", {}).get("last_event_id") == f"{response_id}:{len(events)}"
                and json_body.get("last_event_id") == f"{response_id}:{len(events)}"
                and json_body.get("count") == len(events) - 1
                and all(item.get("sequence", 0) > 1 for item in json_body.get("events", []))
            ),
            status=json_response.status_code,
            payload=json_body,
        )

        sse_response = client.get(
            f"/api/realtime/events?response_id={response_id}&after_sequence=0",
            headers={"Accept": "text/event-stream"},
        )
        sse_text = sse_response.get_data(as_text=True)
        add(
            checks,
            "replay_sse_frames",
            bool(
                sse_response.status_code == 200
                and "event: response.created" in sse_text
                and "event: response.output_text.delta" in sse_text
                and "event: replay.state" in sse_text
                and '"terminal":true' in sse_text
                and '"last_event_id"' in sse_text
                and response_id in sse_text
            ),
            status=sse_response.status_code,
            preview=sse_text[:300],
        )

        missing_response = client.get("/api/realtime/events?response_id=missing_response")
        missing_body = missing_response.get_json() or {}
        add(
            checks,
            "missing_response_safe_error",
            bool(
                missing_response.status_code == 404
                and missing_body.get("ok") is False
                and missing_body.get("error") == "response_not_found"
            ),
            status=missing_response.status_code,
            payload=missing_body,
        )

        ticket_response = client.post("/api/realtime/ticket", headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "hai.harmonika.id"})
        ticket_body = ticket_response.get_json() or {}
        add(
            checks,
            "wss_ticket_fails_safe_until_ready",
            bool(
                ticket_response.status_code == 503
                and ticket_body.get("ok") is False
                and ticket_body.get("error") == "realtime_wss_not_ready"
                and ticket_body.get("realtime_wss") is False
                and ticket_body.get("ticket") is None
                and str(ticket_body.get("ws_url") or "").startswith("wss://hai.harmonika.id/")
                and ticket_body.get("fallback", {}).get("replay") == "/api/realtime/events"
            ),
            status=ticket_response.status_code,
            payload=ticket_body,
        )

    hai_app.REALTIME_EVENT_DIR = original_dir
    hai_app.REALTIME_EVENT_TTL_SECONDS = original_ttl

    ok = all(item["ok"] for item in checks)
    summary = {
        "ok": ok,
        "checks": checks,
        "passed": sum(1 for item in checks if item["ok"]),
        "total_run": len(checks),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
