#!/usr/bin/env python3
"""History API QA for Harmonika AI WebUI.

Uses an isolated in-memory cookie jar, so it validates one fresh device session
without touching a real browser profile. It creates a temporary chat, verifies
reload, then deletes that temporary chat with a tombstone.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import time
import urllib.request
from urllib.error import HTTPError


def request_json(opener: urllib.request.OpenerDirector, url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"User-Agent": "HAI-history-qa/1.0"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        response = opener.open(request, timeout=20)
        return response.status, json.loads(response.read().decode("utf-8", "replace"))
    except HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {"ok": False, "error": "non_json_error", "body": body[:500]}
        return error.code, parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://hai.harmonika.id")
    parser.add_argument("--chat-id-prefix", default="qa-history")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    status, initial = request_json(opener, f"{base_url}/api/history")
    if status != 200 or not initial.get("ok"):
        raise SystemExit(f"GET awal gagal: status={status} body={initial}")

    now = int(time.time() * 1000)
    chat_id = f"{args.chat_id_prefix}-{now}"
    payload = {
        "chats": [
            {
                "id": chat_id,
                "title": "QA History Temporary Chat",
                "createdAt": now,
                "updated": now,
                "messages": [
                    {"role": "user", "content": "HAI_HISTORY_QA_USER"},
                    {"role": "assistant", "content": "HAI_HISTORY_QA_ASSISTANT"},
                ],
            }
        ],
        "active": chat_id,
        "deleted": [],
    }

    status, saved = request_json(opener, f"{base_url}/api/history", method="PUT", payload=payload)
    if status != 200 or not saved.get("ok") or saved.get("active") != chat_id:
        raise SystemExit(f"PUT save gagal: status={status} body={saved}")

    status, reloaded = request_json(opener, f"{base_url}/api/history")
    if status != 200 or not reloaded.get("ok"):
        raise SystemExit(f"GET reload gagal: status={status} body={reloaded}")
    chat = next((item for item in reloaded.get("chats", []) if item.get("id") == chat_id), None)
    if not chat:
        raise SystemExit(f"Chat test tidak ditemukan setelah reload: {reloaded}")
    if chat.get("title") != "QA History Temporary Chat" or len(chat.get("messages", [])) != 2:
        raise SystemExit(f"Chat test tidak tersimpan lengkap: {chat}")

    delete_time = int(time.time() * 1000)
    status, deleted = request_json(
        opener,
        f"{base_url}/api/history",
        method="PUT",
        payload={"chats": [], "active": "", "deleted": [{"id": chat_id, "updated": delete_time}]},
    )
    if status != 200 or not deleted.get("ok"):
        raise SystemExit(f"PUT delete tombstone gagal: status={status} body={deleted}")

    status, after_delete = request_json(opener, f"{base_url}/api/history")
    if status != 200 or not after_delete.get("ok"):
        raise SystemExit(f"GET after delete gagal: status={status} body={after_delete}")
    if any(item.get("id") == chat_id for item in after_delete.get("chats", [])):
        raise SystemExit(f"Chat test masih muncul setelah delete: {after_delete}")
    if not any(item.get("id") == chat_id for item in after_delete.get("deleted", [])):
        raise SystemExit(f"Tombstone test tidak tersimpan: {after_delete}")

    print(json.dumps({
        "ok": True,
        "base_url": base_url,
        "device": after_delete.get("device"),
        "chat_id": chat_id,
        "initial_chats": len(initial.get("chats", [])),
        "saved_count": saved.get("saved"),
        "after_delete_chats": len(after_delete.get("chats", [])),
        "tombstone_saved": True,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
