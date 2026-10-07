#!/usr/bin/env python3
"""Browser QA smoke for hai.harmonika.id.

No third-party dependency. It launches a temporary Chrome profile, talks to the
Chrome DevTools Protocol with a tiny built-in WebSocket client, and reports
layout metrics that catch mobile/desktop horizontal overflow more reliably than
plain --screenshot.

Examples:
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport mobile --screenshot /tmp/hai-mobile.png
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport tablet --flow chat-text
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport landscape --flow empty
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow new-chat
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow chat-text
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow image-artifact
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow history-controls
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow stop-stream
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow regenerate
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow attachment-chat
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow attachment-multi-chat
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow sources-web
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport mobile --flow layout-metrics
  python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport mobile --flow chat-text --screenshot /tmp/hai.png --json-out /tmp/hai.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request


VIEWPORTS = {
    "compact": (320, 700, True),
    "mobile": (390, 844, True),
    "landscape": (844, 390, True),
    "tablet": (820, 1180, True),
    "desktop": (1365, 900, False),
}


def find_chrome() -> str:
    candidates = [
        os.environ.get("CHROME_BIN"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).exists():
            return candidate
    raise SystemExit("Chrome/Chromium tidak ditemukan. Set CHROME_BIN jika path berbeda.")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def ws_send(sock: socket.socket, obj: dict) -> None:
    data = json.dumps(obj).encode("utf-8")
    header = bytearray([0x81])
    length = len(data)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    mask = os.urandom(4)
    header.extend(mask)
    sock.sendall(header + bytes(byte ^ mask[index % 4] for index, byte in enumerate(data)))


def ws_recv(sock: socket.socket) -> dict:
    header = sock.recv(2)
    if not header:
        raise EOFError("WebSocket closed")
    _, second = header
    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", sock.recv(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", sock.recv(8))[0]
    mask = sock.recv(4) if second & 0x80 else None
    payload = b""
    while len(payload) < length:
        payload += sock.recv(length - len(payload))
    if mask:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return json.loads(payload.decode("utf-8"))


def cdp_call(sock: socket.socket, call_id: int, method: str, params: dict | None = None) -> dict:
    ws_send(sock, {"id": call_id, "method": method, "params": params or {}})
    while True:
        message = ws_recv(sock)
        if message.get("id") == call_id:
            if "error" in message:
                raise RuntimeError(f"{method} failed: {message['error']}")
            return message


def cdp_eval(sock: socket.socket, call_id: int, expression: str) -> dict:
    result = cdp_call(sock, call_id, "Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": True,
    })
    value = result.get("result", {}).get("result", {})
    if "exceptionDetails" in result.get("result", {}):
        raise RuntimeError(f"Runtime.evaluate exception: {result['result']['exceptionDetails']}")
    if value.get("type") == "undefined":
        return {}
    return value.get("value", {})


def with_mock_chat_stream(expression: str) -> str:
    """Patch /chat in the browser context for visual-only snapshots.

    The production gate has separate live `/chat` browser flows. Visual
    snapshots should be deterministic UI captures, not provider latency tests.
    """
    prefix = """
window.__haiOriginalFetchForMockChat = window.__haiOriginalFetchForMockChat || window.fetch.bind(window);
window.fetch = (input, init = {}) => {
  const url = String(typeof input === 'string' ? input : (input?.url || ''));
  if (url === '/chat' || url.endsWith('/chat')) {
    const encoder = new TextEncoder();
    const text = 'Router adalah perangkat jaringan yang menghubungkan beberapa perangkat dan mengarahkan lalu lintas data agar koneksi internet berjalan ke tujuan yang tepat.';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(text));
        controller.close();
      }
    });
    return Promise.resolve(new Response(stream, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'X-HAI-Intent': 'text'
      }
    }));
  }
  return window.__haiOriginalFetchForMockChat(input, init);
};
"""
    return f"{prefix}\n{expression}"


def is_cdp_context_destroyed_error(error: Exception) -> bool:
    text = str(error)
    return "Execution context was destroyed" in text or "Cannot find context with specified id" in text


def cdp_eval_readiness(sock: socket.socket, call_id: int, expression: str, attempts: int = 5) -> dict:
    last_error: Exception | None = None
    for offset in range(attempts):
        try:
            return cdp_eval(sock, call_id + offset, expression)
        except RuntimeError as exc:
            if not is_cdp_context_destroyed_error(exc) or offset >= attempts - 1:
                raise
            last_error = exc
            time.sleep(0.6 + (offset * 0.2))
    if last_error:
        raise last_error
    return {}


def component_crop_selectors(flow: str) -> list[tuple[str, str]]:
    """Small visual QA crops for components that are easy to miss in full-page shots."""
    if flow == "markdown-rich":
        return [
            ("markdown-table", ".assistant-message table"),
            ("code-block", ".assistant-message .code-block"),
        ]
    if flow == "composer-queue-state":
        return [
            ("queue-pill", "#hai-queue-status.is-visible"),
            ("composer", ".bottom-panel form"),
        ]
    if flow == "sources-stack":
        return [
            ("source-stack", ".hai-source-chips"),
            ("source-details", ".hai-source-details:not([hidden])"),
        ]
    if flow == "library-panel":
        return [
            ("library-panel", "#hai-library-panel"),
        ]
    return []


def capture_component_crops(
    sock: socket.socket,
    viewport: str,
    flow: str,
    crop_dir: pathlib.Path,
    call_id_start: int = 40,
) -> list[dict]:
    selectors = component_crop_selectors(flow)
    if viewport == "compact" and flow == "markdown-rich":
        selectors = [(name, selector) for name, selector in selectors if name == "markdown-table"]
    if not selectors:
        return []
    crop_dir.mkdir(parents=True, exist_ok=True)
    selector_payload = json.dumps([{"name": name, "selector": selector} for name, selector in selectors])
    rects = cdp_eval(sock, call_id_start, f"""
(() => {{
  const configs = {selector_payload};
  const pad = 8;
  const bottomPanel = document.querySelector('.bottom-panel')?.getBoundingClientRect();
  return configs.map((config) => {{
    const element = document.querySelector(config.selector);
    if (!element) return {{ name: config.name, selector: config.selector, found: false }};
    const rect = element.getBoundingClientRect();
    const isBottomUi = config.selector.includes('.bottom-panel') || config.selector.includes('hai-queue-status');
    const safeBottom = (!isBottomUi && bottomPanel)
      ? Math.max(0, Math.min(window.innerHeight, Math.floor(bottomPanel.top - pad)))
      : window.innerHeight;
    const x = Math.max(0, Math.floor(rect.left - pad));
    const y = Math.max(0, Math.floor(rect.top - pad));
    const right = Math.min(window.innerWidth, Math.ceil(rect.right + pad));
    const bottom = Math.min(safeBottom, Math.ceil(rect.bottom + pad));
    return {{
      name: config.name,
      selector: config.selector,
      found: rect.width > 0 && rect.height > 0 && right > x && bottom > y,
      x,
      y,
      width: Math.max(1, right - x),
      height: Math.max(1, bottom - y)
    }};
  }});
}})()
""")
    if not isinstance(rects, list):
        return [{"name": name, "selector": selector, "ok": False, "error": "rect_eval_failed"} for name, selector in selectors]

    results: list[dict] = []
    call_id = call_id_start + 1
    for rect in rects:
        name = str(rect.get("name") or "component")
        path = crop_dir / f"{viewport}-{flow}-{name}.png"
        result = {
            "name": name,
            "selector": rect.get("selector"),
            "path": str(path),
            "found": bool(rect.get("found")),
            "ok": False,
            "bytes": 0,
            "width": int(rect.get("width") or 0),
            "height": int(rect.get("height") or 0),
        }
        if not rect.get("found"):
            results.append(result)
            continue
        shot = cdp_call(sock, call_id, "Page.captureScreenshot", {
            "format": "png",
            "fromSurface": True,
            "captureBeyondViewport": False,
            "clip": {
                "x": float(rect.get("x") or 0),
                "y": float(rect.get("y") or 0),
                "width": float(rect.get("width") or 1),
                "height": float(rect.get("height") or 1),
                "scale": 1,
            },
        })
        call_id += 1
        path.write_bytes(base64.b64decode(shot["result"]["data"]))
        result["bytes"] = path.stat().st_size
        result["ok"] = result["bytes"] > 800 and result["width"] >= 24 and result["height"] >= 18
        results.append(result)
    return results


def wait_for_page(port: int, timeout: float) -> dict:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1).read())
            page = next((item for item in pages if item.get("type") == "page" and item.get("webSocketDebuggerUrl")), None)
            if page:
                return page
        except Exception as exc:  # pragma: no cover - diagnostic only
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"Chrome page not ready: {last_error}")


def connect_ws(ws_url: str) -> socket.socket:
    hostport = ws_url.split("/")[2]
    path = "/" + "/".join(ws_url.split("/")[3:])
    host, port = hostport.split(":")
    sock = socket.create_connection((host, int(port)), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {hostport}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(request.encode("ascii"))
    response = sock.recv(4096)
    if b" 101 " not in response:
        raise RuntimeError(f"WebSocket handshake failed: {response[:120]!r}")
    return sock


APP_READY_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const started = Date.now();
  while (Date.now() - started < 15000) {
    const readyState = document.readyState;
    const hasCoreDom = Boolean(
      document.body &&
      document.querySelector('#user-input') &&
      document.querySelector('#submit-button') &&
      document.querySelector('#chat-messages') &&
      document.querySelector('.bottom-panel form')
    );
    const hasCoreFunctions = typeof renderMessage === 'function' && typeof sendMessage === 'function';
    const hasChatModeClass = document.body?.classList.contains('hai-chat-empty') || document.body?.classList.contains('hai-chat-active');
    if (readyState !== 'loading' && hasCoreDom && hasCoreFunctions && hasChatModeClass) {
      return { ok: true, waitedMs: Date.now() - started, readyState };
    }
    await wait(150);
  }
  return {
    ok: false,
    waitedMs: Date.now() - started,
    readyState: document.readyState,
    hasBody: Boolean(document.body),
    hasInput: Boolean(document.querySelector('#user-input')),
    hasSubmit: Boolean(document.querySelector('#submit-button')),
    hasChat: Boolean(document.querySelector('#chat-messages')),
    hasForm: Boolean(document.querySelector('.bottom-panel form')),
    hasRenderMessage: typeof renderMessage === 'function',
    hasSendMessage: typeof sendMessage === 'function',
    hasChatEmpty: Boolean(document.body?.classList.contains('hai-chat-empty')),
    hasChatActive: Boolean(document.body?.classList.contains('hai-chat-active')),
    bodyClass: document.body?.className || ''
  };
})()
"""


BASELINE_METRICS_JS = """
(() => {
  const empty = document.querySelector('.hai-empty-state');
  const composer = document.querySelector('.bottom-panel form');
  const source = document.querySelector('link[href*="styles"]');
  const assetMarker = source ? new URL(source.href, location.href).searchParams.get('v') : '';
  const emptyRect = empty ? empty.getBoundingClientRect() : null;
  const composerRect = composer ? composer.getBoundingClientRect() : null;
  const heading = empty?.querySelector('h1')?.textContent?.trim() || '';
  const description = empty?.querySelector('p')?.textContent?.trim() || '';
  const capabilityLabels = [...(empty?.querySelectorAll('.hai-capabilities span') || [])].map((node) => node.textContent.trim());
  const suggestionTitles = [...(empty?.querySelectorAll('.hai-suggestions strong') || [])].map((node) => node.textContent.trim());
  const expectedSuggestions = ['Jelaskan sesuatu', 'Buat ide', 'Bantu coding', 'Buat gambar'];
  const suggestionButtons = [...(empty?.querySelectorAll('.hai-suggestions button') || [])].map((node) => {
    const box = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    return {
      width: box.width,
      height: box.height,
      borderRadius: style.borderRadius,
      text: node.textContent.trim(),
      hasLongDescription: Boolean(node.querySelector('span')?.textContent?.trim())
    };
  });
  const logo = empty?.querySelector('img');
  const logoRect = logo ? logo.getBoundingClientRect() : null;
  const emptyStyle = empty ? getComputedStyle(empty) : null;
  const topActionLabels = [...document.querySelectorAll('.hai-top-actions span')].map((node) => node.textContent.trim());
  const topActionsStyle = document.querySelector('.hai-top-actions') ? getComputedStyle(document.querySelector('.hai-top-actions')) : null;
  const topActionsHiddenOnEmpty = Boolean(
    document.body.classList.contains('hai-chat-empty') &&
    topActionsStyle &&
    (topActionsStyle.display === 'none' || topActionsStyle.visibility === 'hidden' || Number(topActionsStyle.opacity) === 0)
  );
  const exportLabels = [...document.querySelectorAll('.export-button span')].map((node) => node.textContent.trim());
  const exportButtonsHidden = exportLabels.length === 0;
  const quickRowStyle = document.querySelector('.hai-quick-row') ? getComputedStyle(document.querySelector('.hai-quick-row')) : null;
  const quickRowHiddenOnEmpty = Boolean(
    document.body.classList.contains('hai-chat-empty') &&
    quickRowStyle &&
    (quickRowStyle.display === 'none' || quickRowStyle.visibility === 'hidden' || Number(quickRowStyle.opacity) === 0)
  );
  const chromeIconNodes = [...document.querySelectorAll('#close-sidebar img.icon-svg, #new-chat img.icon-svg, .sidebar-buttons img.icon-svg')]
    .filter((icon) => {
      const style = getComputedStyle(icon);
      const box = icon.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
    });
  const chromeIcons = chromeIconNodes.map((icon) => {
    const box = icon.getBoundingClientRect();
    return {
      src: icon.getAttribute('src') || '',
      complete: Boolean(icon.complete),
      naturalWidth: icon.naturalWidth || 0,
      naturalHeight: icon.naturalHeight || 0,
      width: box.width || 0,
      height: box.height || 0,
      paints: Boolean(icon.complete && icon.naturalWidth > 0 && icon.naturalHeight > 0 && box.width >= 16 && box.height >= 16)
    };
  });
  const chromeIconsPaint = Boolean(assetMarker) && chromeIcons.length >= 2 && chromeIcons.every((item) => item.paints && item.src.includes(`?v=${assetMarker}`));
  const composerHint = document.querySelector('.hai-composer-hint')?.textContent?.trim() || '';
  const settingsText = [
    document.querySelector('#settings-popup-title')?.textContent?.trim() || '',
    document.querySelector('label[for="base-url"]')?.textContent?.trim() || '',
    document.querySelector('label[for="api-key"]')?.textContent?.trim() || '',
    document.querySelector('#settings-save')?.textContent?.trim() || '',
    document.querySelector('#additional-settings-popup-title')?.textContent?.trim() || '',
    document.querySelector('label[for="system-content"]')?.textContent?.trim() || '',
    document.querySelector('label[for="start-tag"]')?.textContent?.trim() || '',
    document.querySelector('label[for="end-tag"]')?.textContent?.trim() || '',
    document.querySelector('#additional-settings-save')?.textContent?.trim() || ''
  ].filter(Boolean).join(' ');
  const settingsPlaceholders = [
    document.querySelector('#model-search')?.getAttribute('placeholder') || '',
    document.querySelector('#base-url')?.getAttribute('placeholder') || '',
    document.querySelector('#api-key')?.getAttribute('placeholder') || '',
    document.querySelector('#system-content')?.getAttribute('placeholder') || '',
    document.querySelector('#start-tag')?.getAttribute('placeholder') || '',
    document.querySelector('#end-tag')?.getAttribute('placeholder') || ''
  ].filter(Boolean).join(' ');
  const parameterLabels = [...document.querySelectorAll('.parameter-button')].map((node) => node.textContent.trim());
  const artifactLabels = [
    document.querySelector('#hai-artifact-panel')?.getAttribute('aria-label') || '',
    document.querySelector('.hai-artifact-kicker')?.textContent?.trim() || '',
    document.querySelector('#hai-artifact-title')?.textContent?.trim() || '',
    document.querySelector('#hai-artifact-copy')?.getAttribute('title') || '',
    document.querySelector('#hai-artifact-close')?.getAttribute('title') || ''
  ].filter(Boolean).join(' ');
  const artifactLocalizedOk = Boolean(
    /Kanvas/.test(artifactLabels) &&
    /artefak/i.test(artifactLabels) &&
    /Tutup kanvas/.test(artifactLabels) &&
    !/(Canvas artifact|Kanvas artifact|\\bCanvas\\b|Tutup canvas|Salin artifact|\\bArtifact\\b)/i.test(artifactLabels)
  );
  const settingsLocalizedOk = Boolean(
    /Pengaturan/.test(settingsText) &&
    /URL Dasar/.test(settingsText) &&
    /Kunci API/.test(settingsText) &&
    /Prompt sistem/.test(settingsText) &&
    /Tag mulai/.test(settingsText) &&
    /Tag akhir/.test(settingsText) &&
    parameterLabels.join('|') === 'Presisi|Seimbang|Kreatif|Kustom' &&
    /Cari model/.test(settingsPlaceholders) &&
    /Masukkan kunci API/.test(settingsPlaceholders) &&
    /Masukkan instruksi sistem/.test(settingsPlaceholders) &&
    !/(\\bSettings\\b|Save Settings|Additional Settings|Search a model|Search models|Enter your API Key|Enter system|Model Parameters|Precise|Balanced|Creative|Custom|Deep Query Tags|Start Tag|End Tag)/i.test(`${settingsText} ${settingsPlaceholders} ${parameterLabels.join(' ')}`)
  );
  const visibleChromeText = [
    ...topActionLabels,
    ...exportLabels,
    composerHint,
    document.querySelector('#chat-history .conversation-text span')?.textContent?.trim() || ''
  ].filter(Boolean).join(' ');
  const localizedChromeOk = Boolean(
    topActionLabels.includes('Ubah nama') &&
    topActionLabels.includes('Salin link') &&
    exportButtonsHidden &&
    /^Tekan Enter untuk kirim/.test(composerHint) &&
    settingsLocalizedOk &&
    artifactLocalizedOk &&
    !/(\\bRename\\b|\\bNew Chat\\b|Export as)/i.test(visibleChromeText)
  );
  const emptyStateOk = Boolean(
    heading === 'Selamat datang di Harmonika AI' &&
    /bertanya/i.test(description) &&
    /membaca dokumen/i.test(description) &&
    logoRect &&
    logoRect.width >= (innerWidth <= 820 ? 56 : 70) &&
    capabilityLabels.join('|') === 'Chat umum|Web|File|Gambar' &&
    emptyStyle &&
    emptyStyle.backgroundColor === 'rgba(0, 0, 0, 0)' &&
    expectedSuggestions.every((title, index) => suggestionTitles[index] === title) &&
    suggestionButtons.length === 4 &&
    suggestionButtons.every((item) => item.height <= 48 && !item.hasLongDescription) &&
    localizedChromeOk &&
    topActionsHiddenOnEmpty &&
    quickRowHiddenOnEmpty &&
    chromeIconsPaint
  );
  return {
    ok: Boolean(emptyStateOk),
    url: location.href,
    css: source ? source.href : '',
    assetMarker,
    bodyClass: document.body.className,
    innerWidth,
    innerHeight,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth,
    emptyState: emptyRect ? { left: emptyRect.left, right: emptyRect.right, width: emptyRect.width } : null,
    emptyHeading: heading,
    emptyDescription: description,
    capabilityLabels,
    suggestionTitles,
    suggestionButtons,
    welcomeLogo: logoRect ? { width: logoRect.width, height: logoRect.height } : null,
    emptyBackground: emptyStyle?.backgroundColor || '',
    topActionLabels,
    topActionsHiddenOnEmpty,
    quickRowHiddenOnEmpty,
    chromeIcons,
    chromeIconsPaint,
    exportLabels,
    exportButtonsHidden,
    composerHint,
    settingsText,
    settingsPlaceholders,
    parameterLabels,
    settingsLocalizedOk,
    artifactLabels,
    artifactLocalizedOk,
    localizedChromeOk,
    emptyStateOk,
    composer: composerRect ? { left: composerRect.left, right: composerRect.right, width: composerRect.width } : null,
    ariaBusy: document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null
  };
})()
"""

IMAGE_MODAL_FLOW_JS = """
(async () => {
  if (typeof window.openHaiImageModal !== 'function') {
    return { ok: false, reason: 'missing_openHaiImageModal' };
  }
  window.openHaiImageModal('/static/images/hai-logo.png', 'Pratinjau Harmonika AI', '/static/images/hai-logo.png');
  const modal = document.querySelector('.hai-image-modal');
  const card = document.querySelector('.hai-image-modal-card');
  const img = card?.querySelector('img');
  const actions = card?.querySelector('.hai-image-modal-actions');
  const modalStyle = modal ? getComputedStyle(modal) : null;
  const cardStyle = card ? getComputedStyle(card) : null;
  const actionsStyle = actions ? getComputedStyle(actions) : null;
  const modalBackground = modalStyle?.backgroundColor || '';
  const modalBackdropFilter = modalStyle?.backdropFilter || '';
  const cardBackground = cardStyle?.backgroundColor || '';
  const cardDisplay = cardStyle?.display || '';
  const actionsBackground = actionsStyle?.backgroundColor || '';
  const actionsBorderTop = actionsStyle?.borderTopStyle || '';
  const actionButtons = [...(actions?.querySelectorAll('a,button') || [])].map((node) => {
    const style = getComputedStyle(node);
    return {
      text: node.textContent.trim(),
      background: style.backgroundColor,
      color: style.color,
      borderColor: style.borderColor
    };
  });
  const rect = card ? card.getBoundingClientRect() : null;
  const imageRect = img ? img.getBoundingClientRect() : null;
  const interaction = await (async () => {
    img?.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 20, clientY: 20 }));
    await new Promise((resolve) => setTimeout(resolve, 150));
    const staysOpenOnInnerClick = Boolean(document.querySelector('.hai-image-modal'));
    document.querySelector('.hai-image-modal')?.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 4, clientY: 4 }));
    await new Promise((resolve) => setTimeout(resolve, 150));
    const closesOnBackdrop = !document.querySelector('.hai-image-modal');
    window.openHaiImageModal('/static/images/hai-logo.png', 'Pratinjau Harmonika AI', '/static/images/hai-logo.png');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    await new Promise((resolve) => setTimeout(resolve, 150));
    const closesOnEscape = !document.querySelector('.hai-image-modal');
    return {
      ok: Boolean(staysOpenOnInnerClick && closesOnBackdrop && closesOnEscape),
      staysOpenOnInnerClick,
      closesOnBackdrop,
      closesOnEscape
    };
  })();
  return {
    ok: Boolean(
      modal &&
      card &&
      img &&
      img.complete &&
      rect &&
      rect.width > 0 &&
      rect.width <= window.innerWidth &&
      rect.height <= window.innerHeight &&
      cardBackground === 'rgb(255, 255, 255)' &&
      cardDisplay === 'flex' &&
      actionsBackground === 'rgb(255, 255, 255)' &&
      actionsBorderTop !== 'none' &&
      !/blur/i.test(modalBackdropFilter) &&
      /Pratinjau Harmonika AI/.test(actions?.innerText || '') &&
      !/Preview Harmonika AI|Tutup preview/i.test(actions?.innerText || '') &&
      document.documentElement.scrollWidth <= window.innerWidth &&
      interaction.ok
    ),
    modalBackground,
    modalBackdropFilter,
    cardBackground,
    cardDisplay,
    actionsBackground,
    actionsBorderTop,
    cardWidth: rect?.width || 0,
    cardHeight: rect?.height || 0,
    imageWidth: imageRect?.width || 0,
    imageHeight: imageRect?.height || 0,
    actionText: actions?.innerText.trim() || '',
    actionButtons,
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
    interaction
  };
})()
"""

EXPORT_LOCALIZATION_FLOW_JS = """
(async () => {
  const downloads = [];
  const originalCreateObjectURL = URL.createObjectURL.bind(URL);
  const originalRevokeObjectURL = URL.revokeObjectURL.bind(URL);
  const originalClick = HTMLAnchorElement.prototype.click;
  URL.createObjectURL = (blob) => {
    downloads.push({ blob, href: `blob:hai-qa-${downloads.length + 1}` });
    return downloads.at(-1).href;
  };
  URL.revokeObjectURL = () => {};
  HTMLAnchorElement.prototype.click = function () {
    const item = downloads.at(-1);
    if (item) item.download = this.getAttribute('download') || '';
  };
  try {
    currentConversationId = `qa-export-${Date.now()}`;
    isPrivateChat = false;
    selectedModel = 'harmonika-ai';
    SYSTEM_CONTENT = '';
    MODEL_PARAMETERS = { temperature: 0.5 };
    conversationHistory = [
      { role: 'user', content: 'Halo export QA' },
      { role: 'assistant', content: 'Ini jawaban Harmonika AI.' }
    ];
    if (typeof exportMarkdown !== 'function' || typeof exportJSON !== 'function') {
      return { ok: false, reason: 'missing_export_functions' };
    }
    exportMarkdown();
    exportJSON();
    const markdown = downloads[0] ? await downloads[0].blob.text() : '';
    const jsonText = downloads[1] ? await downloads[1].blob.text() : '';
    let jsonData = null;
    try {
      jsonData = JSON.parse(jsonText);
    } catch (error) {
      jsonData = { parse_error: String(error?.message || error) };
    }
    const markdownOk = Boolean(
      downloads[0]?.download?.startsWith('ekspor-chat-') &&
      downloads[0]?.download?.endsWith('.md') &&
      /^# Ekspor Chat/m.test(markdown) &&
      /## Pesan/.test(markdown) &&
      /### Pengguna/.test(markdown) &&
      /### Harmonika AI/.test(markdown) &&
      /Prompt sistem: Tidak ada/.test(markdown) &&
      !/(# Chat Export|## Messages|### User|### Assistant|System Prompt|None)/.test(markdown)
    );
    const jsonOk = Boolean(
      downloads[1]?.download?.startsWith('ekspor-chat-') &&
      downloads[1]?.download?.endsWith('.json') &&
      jsonData &&
      jsonData.metadata &&
      jsonData.metadata.tanggal &&
      jsonData.metadata.model === 'harmonika-ai' &&
      jsonData.metadata.prompt_sistem === 'Tidak ada' &&
      Array.isArray(jsonData.pesan) &&
      jsonData.pesan.length === 2 &&
      !('messages' in jsonData) &&
      !('system prompt' in (jsonData.metadata || {})) &&
      !('parameters' in (jsonData.metadata || {}))
    );
    return {
      ok: Boolean(markdownOk && jsonOk),
      markdownFile: downloads[0]?.download || '',
      jsonFile: downloads[1]?.download || '',
      markdownOk,
      jsonOk,
      markdownPreview: markdown.slice(0, 240),
      jsonKeys: Object.keys(jsonData || {}),
      jsonMetadataKeys: Object.keys(jsonData?.metadata || {}),
      pesanCount: Array.isArray(jsonData?.pesan) ? jsonData.pesan.length : null
    };
  } finally {
    URL.createObjectURL = originalCreateObjectURL;
    URL.revokeObjectURL = originalRevokeObjectURL;
    HTMLAnchorElement.prototype.click = originalClick;
  }
})()
"""

MARKDOWN_RICH_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const chat = document.querySelector('#chat-messages');
  if (!chat || typeof ReactDOM === 'undefined' || typeof React === 'undefined' || typeof renderMessage !== 'function') {
    return { ok: false, reason: 'missing_markdown_runtime' };
  }
  chat.querySelector('.hai-empty-state')?.remove();
  document.body.classList.remove('hai-chat-empty');
  document.body.classList.add('hai-chat-active');
  const rich = [
    '## Ringkasan markdown panjang',
    '',
    'Jawaban ini menguji **teks tebal**, paragraf, daftar, tabel, dan kode agar terlihat seperti chat modern.',
    '',
    '- Poin pertama punya kalimat cukup panjang untuk menguji wrapping.',
    '- Poin kedua memakai `inline code` dan tautan aman.',
    '- Poin ketiga memastikan spasi antar item rapi.',
    '',
    '| Fitur | Status | Catatan panjang |',
    '| --- | --- | --- |',
    '| Markdown | Siap | Heading, paragraf, list, dan emphasis terbaca nyaman |',
    '| Tabel | Scroll aman | Kolom panjang tidak boleh membuat halaman overflow horizontal |',
    '| Kode | Siap | Header, tombol copy, dan scroll horizontal tetap di dalam block |',
    '',
    '```js',
    'function harmonikaPreview(items) {',
    '  return items.map((item) => `${item.name}: ${item.status}`).join("\\\\n");',
    '}',
    '```',
    '',
    '> Catatan: blockquote harus halus dan tidak mendominasi jawaban.'
  ].join('\\n');
  const container = document.createElement('div');
  container.className = 'assistant-message-container';
  const message = document.createElement('div');
  message.className = 'assistant-message';
  container.appendChild(message);
  chat.innerHTML = '';
  chat.appendChild(container);
  if (typeof updateQuickPromptVisibility === 'function') updateQuickPromptVisibility();
  const root = ReactDOM.createRoot(message);
  root.render(renderMessage({ content: rich, endTag: '' }));
  let tableReady = false;
  for (let i = 0; i < 30; i += 1) {
    await wait(150);
    const probe = message.querySelector('table');
    if (probe && probe.getBoundingClientRect().width > 0) {
      tableReady = true;
      break;
    }
  }
  const heading = message.querySelector('h2');
  const list = message.querySelector('ul');
  const table = message.querySelector('table');
  const codeBlock = message.querySelector('.code-block');
  const codePre = message.querySelector('.code-block .code-pre, .code-block pre, pre');
  const quote = message.querySelector('blockquote');
  const latexConverted = typeof replaceLatexSyntax === 'function'
    ? replaceLatexSyntax('Rumus \\\\(E=mc^2\\\\) dan \\\\[ x \\\\]')
    : '';
  const latexSyntaxOk = latexConverted === 'Rumus $E=mc^2$ dan $$x$$';
  const sanitizedImageHistory = typeof cleanMessageForAPI === 'function'
    ? cleanMessageForAPI({
        role: 'user',
        content: [
          { type: 'text', text: 'Jelaskan gambar sebelumnya' },
          { type: 'image_url', image_url: { url: '[image omitted from history]' } }
        ]
      })
    : null;
  const apiSanitizeOk = Boolean(
    sanitizedImageHistory &&
    sanitizedImageHistory.role === 'user' &&
    sanitizedImageHistory.content === 'Jelaskan gambar sebelumnya'
  );
  const tableRect = table?.getBoundingClientRect();
  const codeRect = codeBlock?.getBoundingClientRect();
  const messageRect = message.getBoundingClientRect();
  const tableStyle = table ? getComputedStyle(table) : null;
  const headingStyle = heading ? getComputedStyle(heading) : null;
  const firstCell = table?.querySelector('td, th') || null;
  const firstCellStyle = firstCell ? getComputedStyle(firstCell) : null;
  const inlineCode = message.querySelector('p code, li code');
  const inlineCodeStyle = inlineCode ? getComputedStyle(inlineCode) : null;
  const tableCells = [...(table?.querySelectorAll('th, td') || [])];
  const verticalCellBorders = tableCells.filter((cell) => {
    const style = getComputedStyle(cell);
    return (parseFloat(style.borderLeftWidth || '0') > 0.5 || parseFloat(style.borderRightWidth || '0') > 0.5);
  }).length;
  const codePreStyle = codePre ? getComputedStyle(codePre) : null;
  const codeBlockStyle = codeBlock ? getComputedStyle(codeBlock) : null;
  const codeTitleStyle = codeBlock?.querySelector('.code-title') ? getComputedStyle(codeBlock.querySelector('.code-title')) : null;
  const codeHintStyle = codeBlock ? getComputedStyle(codeBlock, '::after') : null;
  const quoteStyle = quote ? getComputedStyle(quote) : null;
  const tableHeader = table?.querySelector('th') || null;
  const tableHeaderStyle = tableHeader ? getComputedStyle(tableHeader) : null;
  const copyButton = codeBlock?.querySelector('.copy-button, button');
  const codeCopyLabel = copyButton?.getAttribute('aria-label') || copyButton?.getAttribute('title') || '';
  const codeCopyTitle = copyButton?.getAttribute('title') || '';
  const codeCopyIconAlt = copyButton?.querySelector('img')?.getAttribute('alt') ?? null;
  const codeCopyLocalized = Boolean(
    copyButton &&
    codeCopyLabel === 'Salin kode' &&
    codeCopyTitle === 'Salin kode' &&
    (codeCopyIconAlt === '' || codeCopyIconAlt === null)
  );
  const pageOverflow = document.documentElement.scrollWidth > window.innerWidth;
  const isCompact = window.innerWidth <= 420;
  const shortTableLabels = ['Markdown', 'Tabel', 'Kode'];
  const rectCountForCell = (cell) => {
    if (!cell) return 99;
    const range = document.createRange();
    range.selectNodeContents(cell);
    const count = [...range.getClientRects()].filter((rect) => rect.width > 1 && rect.height > 1).length;
    range.detach();
    return count;
  };
  const shortTableLabelRects = shortTableLabels.map((label) => {
    const cell = [...(table?.querySelectorAll('td') || [])].find((item) => item.textContent.trim() === label);
    return { label, rects: rectCountForCell(cell), width: cell?.getBoundingClientRect().width || 0 };
  });
  const shortTableLabelsReadable = !isCompact || shortTableLabelRects.every((item) => item.rects <= 1 && item.width >= 58);
  const compactTableHeightLimit = window.innerWidth <= 340 ? 0.70 : 0.40;
  const mobileTableCompact = !isCompact || (tableRect && tableRect.height <= window.innerHeight * compactTableHeightLimit);
  const codeBlockModern = Boolean(
    codeBlockStyle &&
    (
      codeBlockStyle.boxShadow === 'none' ||
      codeBlockStyle.boxShadow.includes('rgba(15, 23, 42') ||
      codeBlockStyle.boxShadow.includes('rgba(0, 0, 0')
    ) &&
    codeBlockStyle.borderTopColor !== 'rgb(52, 58, 64)' &&
    (!codeTitleStyle || (
      codeTitleStyle.backgroundColor !== 'rgb(52, 58, 64)' &&
      !String(codeTitleStyle.backgroundImage || '').includes('rgb(52, 58, 64)')
    ))
  );
  const transcriptVisualPolished = Boolean(
    codeBlockModern &&
    tableCells.length > 0 &&
    verticalCellBorders <= Math.max(2, Math.ceil(tableCells.length * 0.25))
  );
  const richTypographyPolished = Boolean(
    headingStyle &&
    quoteStyle &&
    inlineCodeStyle &&
    tableHeaderStyle &&
    parseFloat(headingStyle.borderBottomWidth || '0') >= 0.5 &&
    headingStyle.borderBottomColor !== 'rgba(0, 0, 0, 0)' &&
    quoteStyle.borderLeftColor !== 'rgba(0, 0, 0, 0)' &&
    parseFloat(quoteStyle.borderLeftWidth || '0') >= 3 &&
    (quoteStyle.backgroundColor !== 'rgba(0, 0, 0, 0)' || quoteStyle.backgroundImage !== 'none') &&
    inlineCodeStyle.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
    tableHeaderStyle.backgroundColor !== 'rgba(0, 0, 0, 0)'
  );
  const mobileTableReadable = !isCompact || (
    table.scrollWidth <= table.clientWidth + 4 &&
    firstCellStyle?.whiteSpace !== 'nowrap' &&
    ['break-word', 'anywhere'].includes(firstCellStyle?.overflowWrap || '') &&
    firstCellStyle?.wordBreak === 'normal' &&
    shortTableLabelsReadable
  );
  const codeScrollHint = !isCompact || (
    codePre.scrollWidth <= codePre.clientWidth + 4 ||
    (codeHintStyle?.content && codeHintStyle.content !== 'none' && codeHintStyle.content !== 'normal' && codeHintStyle?.backgroundImage !== 'none')
  );
  return {
    ok: Boolean(
      heading &&
      list &&
      table &&
      codeBlock &&
      codePre &&
      quote &&
      tableRect &&
      codeRect &&
      messageRect &&
      tableRect.width <= messageRect.width + 1 &&
      codeRect.width <= messageRect.width + 1 &&
      tableStyle?.overflowX === 'auto' &&
      ['auto', 'scroll'].includes(codePreStyle?.overflowX || '') &&
      copyButton &&
      codeCopyLocalized &&
      mobileTableReadable &&
      mobileTableCompact &&
      transcriptVisualPolished &&
      richTypographyPolished &&
      latexSyntaxOk &&
      apiSanitizeOk &&
      codeScrollHint &&
      !pageOverflow
    ),
    latexConverted,
    latexSyntaxOk,
    sanitizedImageHistory,
    apiSanitizeOk,
    headingText: heading?.textContent?.trim() || '',
    listItems: list ? list.querySelectorAll('li').length : 0,
    table: tableRect ? {
      width: tableRect.width,
      scrollWidth: table.scrollWidth,
      clientWidth: table.clientWidth,
      overflowX: tableStyle?.overflowX || '',
      firstCellWhiteSpace: firstCellStyle?.whiteSpace || '',
      firstCellOverflowWrap: firstCellStyle?.overflowWrap || '',
      firstCellWordBreak: firstCellStyle?.wordBreak || '',
      cellCount: tableCells.length,
      verticalCellBorders,
      shortTableLabelRects,
      shortTableLabelsReadable,
      mobileReadable: mobileTableReadable,
      mobileCompact: mobileTableCompact,
      compactTableHeightLimit,
      heightRatio: tableRect.height / window.innerHeight
    } : null,
    code: codeRect ? {
      width: codeRect.width,
      preScrollWidth: codePre?.scrollWidth || 0,
      preClientWidth: codePre?.clientWidth || 0,
      overflowX: codePreStyle?.overflowX || '',
      hasCopy: Boolean(copyButton),
      copyLabel: codeCopyLabel,
      copyTitle: codeCopyTitle,
      copyIconAlt: codeCopyIconAlt,
      copyLocalized: codeCopyLocalized,
      scrollHint: codeScrollHint,
      hintBackground: codeHintStyle?.backgroundImage || ''
    } : null,
    transcriptVisualPolished,
    richTypographyPolished,
    headingStyle: headingStyle ? {
      borderBottomWidth: headingStyle.borderBottomWidth || '',
      borderBottomColor: headingStyle.borderBottomColor || '',
      lineHeight: headingStyle.lineHeight || ''
    } : null,
    quoteStyle: quoteStyle ? {
      borderLeftWidth: quoteStyle.borderLeftWidth || '',
      borderLeftColor: quoteStyle.borderLeftColor || '',
      background: quoteStyle.backgroundColor || '',
      backgroundImage: quoteStyle.backgroundImage || '',
      borderRadius: quoteStyle.borderRadius || ''
    } : null,
    inlineCodeStyle: inlineCodeStyle ? {
      background: inlineCodeStyle.backgroundColor || '',
      borderColor: inlineCodeStyle.borderTopColor || '',
      borderRadius: inlineCodeStyle.borderRadius || ''
    } : null,
    tableHeaderStyle: tableHeaderStyle ? {
      background: tableHeaderStyle.backgroundColor || '',
      color: tableHeaderStyle.color || '',
      fontWeight: tableHeaderStyle.fontWeight || ''
    } : null,
    codeBlockModern,
    codeBlockStyle: codeBlockStyle ? {
      boxShadow: codeBlockStyle.boxShadow || '',
      borderColor: codeBlockStyle.borderTopColor || '',
      background: codeBlockStyle.backgroundColor || ''
    } : null,
    codeTitleBackground: codeTitleStyle?.backgroundColor || '',
    codeTitleBackgroundImage: codeTitleStyle?.backgroundImage || '',
    quoteText: quote?.textContent?.trim() || '',
    messageWidth: messageRect.width,
    tableReady,
    horizontalOverflow: pageOverflow
  };
})()
"""


LAYOUT_METRICS_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('Layout metrics QA response untuk mengunci spacing composer dan action bar.'));
          controller.close();
        }
      });
      return Promise.resolve(new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/plain; charset=utf-8' }
      }));
    }
    return originalFetch(input, init);
  };

  try {
    document.querySelector('#new-chat')?.click();
    let input = null;
    let submit = null;
    for (let i = 0; i < 24; i += 1) {
      await wait(250);
      input = document.querySelector('#user-input');
      submit = document.querySelector('#submit-button');
      if (input && submit) break;
    }
    if (!input || !submit) {
      return {
        ok: false,
        reason: 'missing_composer',
        hasInput: Boolean(input),
        hasSubmit: Boolean(submit),
        bodyClass: document.body?.className || '',
        bodyText: document.body?.innerText?.slice(0, 240) || '',
        url: location.href
      };
    }

    input.value = 'layout metrics qa';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    submit.click();

    const startedAt = Date.now();
    while (Date.now() - startedAt < 8000) {
      await wait(200);
      const assistant = [...document.querySelectorAll('.assistant-message-container')].at(-1);
      const ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '';
      if (assistant?.innerText?.includes('Layout metrics QA response') && ariaBusy === 'false') break;
    }

    const rootStyle = getComputedStyle(document.documentElement);
    const composerHeightVar = parseFloat(rootStyle.getPropertyValue('--hai-composer-height')) || 0;
    const composer = document.querySelector('.bottom-panel');
    const messageContainer = document.querySelector('#chat-messages');
    const toast = document.querySelector('.toast') || (() => {
      window.showToast?.('Layout metrics QA toast', 'success');
      return document.querySelector('.toast');
    })();
    await wait(120);
    const scrollButton = document.querySelector('.scroll-bottom-button') || (() => {
      const node = document.createElement('button');
      node.type = 'button';
      node.className = 'scroll-bottom-button';
      node.style.display = 'block';
      document.body.appendChild(node);
      return node;
    })();

    const composerRect = composer?.getBoundingClientRect();
    const toastRect = toast?.getBoundingClientRect();
    const messageStyle = messageContainer ? getComputedStyle(messageContainer) : null;
    const toastStyle = toast ? getComputedStyle(toast) : null;
    const scrollButtonStyle = scrollButton ? getComputedStyle(scrollButton) : null;
    const topPanel = document.querySelector('.top-panel');
    const firstUser = document.querySelector('.user-message-container');
    const firstAssistant = document.querySelector('.assistant-message-container');
    const topPanelRect = topPanel?.getBoundingClientRect();
    const firstUserRect = firstUser?.getBoundingClientRect();
    const firstAssistantRect = firstAssistant?.getBoundingClientRect();
    const transcriptFirstGap = topPanelRect && firstUserRect ? firstUserRect.top - topPanelRect.bottom : null;
    const transcriptTurnGap = firstUserRect && firstAssistantRect ? firstAssistantRect.top - firstUserRect.bottom : null;
    const bodyStyle = getComputedStyle(document.body);
    const middlePanel = document.querySelector('.middle-panel');
    const middlePanelStyle = middlePanel ? getComputedStyle(middlePanel) : null;
    const bodyScrollbarStyle = getComputedStyle(document.body, '::-webkit-scrollbar');
    const middleScrollbarStyle = middlePanel ? getComputedStyle(middlePanel, '::-webkit-scrollbar') : null;
    const bodyScrollbarThumbStyle = getComputedStyle(document.body, '::-webkit-scrollbar-thumb');
    const scrollbarWidthValue = parseFloat(bodyScrollbarStyle?.width || '0') || 0;
    const middleScrollbarWidthValue = parseFloat(middleScrollbarStyle?.width || '0') || 0;
    const isMobile = innerWidth <= 820;
    const isCompactViewport = isMobile || (innerHeight <= 520 && matchMedia('(orientation: landscape)').matches);
    const scrollbarColorValue = bodyStyle.scrollbarColor || '';
    const classicScrollbarOk = Boolean(
      document.body.classList.contains('hai-theme-adminlte-classic') &&
      (
        (
          (scrollbarColorValue.includes('108, 117, 125') || scrollbarColorValue.includes('#6c757d')) &&
          bodyScrollbarStyle?.display !== 'none' &&
          bodyScrollbarThumbStyle?.backgroundColor !== 'rgb(0, 0, 0)'
        ) ||
        (
          isCompactViewport &&
          (bodyStyle.scrollbarWidth === 'none' || scrollbarWidthValue <= 1.5) &&
          (middlePanelStyle?.scrollbarWidth === 'none' || middleScrollbarWidthValue <= 1.5)
        )
      ) &&
      (!isMobile || scrollbarWidthValue <= 4.5) &&
      (!isMobile || middleScrollbarWidthValue <= 4.5) &&
      (isMobile || scrollbarWidthValue <= 6.5)
    );
    const actionBars = [...document.querySelectorAll('.assistant-message-container .message-buttons, .user-message-container .message-buttons')]
      .filter((bar) => getComputedStyle(bar).display !== 'none' && getComputedStyle(bar).visibility !== 'hidden')
      .map((bar) => {
        const style = getComputedStyle(bar);
        const buttons = [...bar.querySelectorAll('button')]
          .map((button) => {
            const style = getComputedStyle(button);
            const rect = button.getBoundingClientRect();
            return { width: rect.width, height: rect.height, visible: style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 };
          })
          .filter((button) => button.visible);
        return {
          opacity: Number(style.opacity || 1),
          pointerEvents: style.pointerEvents || '',
          background: style.backgroundColor || '',
          marginTop: parseFloat(style.marginTop || '0') || 0,
          buttonCount: buttons.length,
          buttonMin: buttons.reduce((min, item) => Math.min(min, item.width, item.height), buttons.length ? Infinity : 0)
        };
      });
    const actionableBars = actionBars.filter((bar) => bar.buttonCount > 0);
    const visibleUserIdleBars = [...document.querySelectorAll('.user-message-container:not(.is-actions-active) .message-buttons')]
      .filter((bar) => {
        const style = getComputedStyle(bar);
        const rect = bar.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
      });
    const mobileActionsQuiet = !isMobile || actionableBars.every((bar) => bar.opacity >= 0.18 && bar.opacity <= 0.45 && bar.pointerEvents === 'auto' && bar.buttonMin >= 34 && bar.marginTop <= 4);
    const mobileActionsMinimal = !isMobile || actionableBars.every((bar) => bar.buttonCount <= 2);
    const mobileUserActionsHidden = !isMobile || visibleUserIdleBars.length === 0;
    if (isMobile && firstAssistant) {
      firstAssistant.click();
      await wait(140);
    }
    const activeActionBars = [...document.querySelectorAll('.assistant-message-container.is-actions-active .message-buttons, .user-message-container.is-actions-active .message-buttons')]
      .filter((bar) => getComputedStyle(bar).display !== 'none' && getComputedStyle(bar).visibility !== 'hidden')
      .map((bar) => {
        const style = getComputedStyle(bar);
        const buttons = [...bar.querySelectorAll('button')]
          .map((button) => {
            const rect = button.getBoundingClientRect();
            return { width: rect.width, height: rect.height, visible: rect.width > 0 && rect.height > 0 };
          })
          .filter((button) => button.visible);
        return {
          opacity: Number(style.opacity || 1),
          pointerEvents: style.pointerEvents || '',
          buttonCount: buttons.length,
          buttonMin: buttons.reduce((min, item) => Math.min(min, item.width, item.height), buttons.length ? Infinity : 0)
        };
      });
    const mobileActionsActivate = !isMobile || activeActionBars.some((bar) => bar.opacity >= 0.9 && bar.pointerEvents === 'auto' && bar.buttonMin >= 34);
    const mobileActionOk = mobileActionsQuiet && mobileActionsMinimal && mobileUserActionsHidden && mobileActionsActivate;
    const desktopActionQuiet = isMobile || actionBars.every((bar) => bar.opacity <= 0.2 || bar.pointerEvents === 'none');
    const transcriptDensityOk = Boolean(
      transcriptFirstGap !== null &&
      transcriptTurnGap !== null &&
      transcriptFirstGap >= 8 &&
      transcriptFirstGap <= (isMobile ? 58 : 64) &&
      transcriptTurnGap >= 0 &&
      transcriptTurnGap <= (isMobile ? 64 : 72)
    );
    const messagePaddingBottom = parseFloat(messageStyle?.paddingBottom || '0') || 0;
    const toastBottom = parseFloat(toastStyle?.bottom || '0') || 0;
    const toastWithinViewport = Boolean(!toastRect || (toastRect.left >= 8 && toastRect.right <= innerWidth - 8));
    const scrollBottom = parseFloat(scrollButtonStyle?.bottom || '0') || 0;
    const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

    return {
      ok: Boolean(
        composerRect &&
        composerHeightVar >= 72 &&
        Math.abs(composerHeightVar - composerRect.height) <= 6 &&
        messagePaddingBottom >= Math.min(132, composerHeightVar + 20) &&
        toastBottom >= composerHeightVar + 8 &&
        toastWithinViewport &&
        scrollBottom >= composerHeightVar + 8 &&
        mobileActionOk &&
        desktopActionQuiet &&
        classicScrollbarOk &&
        transcriptDensityOk &&
        scrollWidth <= innerWidth
      ),
      composerHeightVar,
      composerHeightRect: composerRect?.height || 0,
      messagePaddingBottom,
      toastBottom,
      toastRect: toastRect ? { left: toastRect.left, right: toastRect.right, width: toastRect.width } : null,
      toastWithinViewport,
      scrollBottom,
      actionBars,
      activeActionBars,
      actionableBarCount: actionableBars.length,
      mobileActionsQuiet,
      mobileActionsMinimal,
      mobileUserActionsHidden,
      mobileActionsActivate,
      mobileActionOk,
      desktopActionQuiet,
      transcriptFirstGap,
      transcriptTurnGap,
      transcriptDensityOk,
      classicScrollbarOk,
      scrollbarColor: scrollbarColorValue,
      middleScrollbarColor: middlePanelStyle?.scrollbarColor || '',
      webkitScrollbarDisplay: bodyScrollbarStyle?.display || '',
      webkitScrollbarWidth: bodyScrollbarStyle?.width || '',
      webkitMiddleScrollbarWidth: middleScrollbarStyle?.width || '',
      webkitScrollbarThumbColor: bodyScrollbarThumbStyle?.backgroundColor || '',
      ariaBusy: document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '',
      innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      horizontalOverflow: scrollWidth > innerWidth
    };
  } finally {
    window.fetch = originalFetch;
  }
})()
"""


COMPOSER_KEYBOARD_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  document.querySelector('#new-chat')?.click();
  await wait(450);
  const form = document.querySelector('.bottom-panel form');
  const upload = document.querySelector('#upload-files');
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  if (!form || !upload || !input || !submit) {
    return {
      ok: false,
      reason: 'missing_composer_nodes',
      hasForm: Boolean(form),
      hasUpload: Boolean(upload),
      hasInput: Boolean(input),
      hasSubmit: Boolean(submit)
    };
  }

  const domOrderOk = Boolean(
    upload.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING &&
    input.compareDocumentPosition(submit) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const attrsOk = input.getAttribute('enterkeyhint') === 'send' &&
    input.getAttribute('autocomplete') === 'off' &&
    input.getAttribute('autocapitalize') === 'sentences' &&
    input.getAttribute('spellcheck') === 'true';

  input.focus();
  await wait(120);
  const inputStyle = getComputedStyle(input);
  const formFocusStyle = getComputedStyle(form);
  const inputFontSize = parseFloat(inputStyle.fontSize || '0') || 0;
  const formFocusVisible = formFocusStyle.borderColor !== 'rgb(206, 212, 218)' ||
    formFocusStyle.boxShadow !== 'none';
  const formRect = form.getBoundingClientRect();

  upload.focus();
  await wait(80);
  const uploadFocusStyle = getComputedStyle(upload);
  const uploadOutlineWidth = uploadFocusStyle.outlineWidth || '';
  const uploadOutlineStyle = uploadFocusStyle.outlineStyle || '';
  const uploadFocusVisible = uploadOutlineStyle !== 'none' &&
    parseFloat(uploadOutlineWidth || '0') >= 1;

  submit.focus();
  await wait(80);
  const submitFocusStyle = getComputedStyle(submit);
  const submitOutlineWidth = submitFocusStyle.outlineWidth || '';
  const submitOutlineStyle = submitFocusStyle.outlineStyle || '';
  const submitFocusVisible = submitOutlineStyle !== 'none' &&
    parseFloat(submitOutlineWidth || '0') >= 1;
  const uploadRect = upload.getBoundingClientRect();
  const submitRect = submit.getBoundingClientRect();
  const radiusValue = (value) => parseFloat(String(value || '0')) || 0;
  const formRadius = radiusValue(formFocusStyle.borderTopLeftRadius);
  const uploadRadius = radiusValue(uploadFocusStyle.borderTopLeftRadius);
  const submitRadius = radiusValue(submitFocusStyle.borderTopLeftRadius);
  const composerVisualClean = Boolean(
    formRect.height >= 54 &&
    formRadius >= 10 &&
    uploadRadius >= 10 &&
    submitRadius >= 10 &&
    Math.abs(uploadRect.height - submitRect.height) <= 2 &&
    Math.abs(uploadRect.width - uploadRect.height) <= 2 &&
    Math.abs(submitRect.width - submitRect.height) <= 2 &&
    !/rgba\\(0, 0, 0, 0\\.1\\).*rgba\\(0, 0, 0, 0\\.125\\)/.test(formFocusStyle.boxShadow)
  );

  input.value = 'baris satu';
  input.selectionStart = input.selectionEnd = input.value.length;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  const beforeShiftEnter = input.value;
  const shiftEnter = new KeyboardEvent('keydown', { key: 'Enter', shiftKey: true, bubbles: true, cancelable: true });
  input.dispatchEvent(shiftEnter);
  await wait(120);
  const shiftEnterInsertedNewline = input.value === 'baris satu\\n';
  const shiftEnterPreventedDefault = shiftEnter.defaultPrevented;

  input.value = 'sedang komposisi';
  input.selectionStart = input.selectionEnd = input.value.length;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  const beforeImeEnter = input.value;
  const imeEnter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
  Object.defineProperty(imeEnter, 'isComposing', { value: true });
  input.dispatchEvent(imeEnter);
  await wait(160);
  const imeEnterIgnored = input.value === beforeImeEnter && !imeEnter.defaultPrevented &&
    (document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '') === 'false';

  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  return {
    ok: Boolean(
      attrsOk &&
      domOrderOk &&
      inputFontSize >= 16 &&
      formFocusVisible &&
      uploadFocusVisible &&
      submitFocusVisible &&
      composerVisualClean &&
      shiftEnterInsertedNewline &&
      shiftEnterPreventedDefault &&
      imeEnterIgnored &&
      scrollWidth <= innerWidth
    ),
    attrs: {
      enterkeyhint: input.getAttribute('enterkeyhint') || '',
      autocomplete: input.getAttribute('autocomplete') || '',
      autocapitalize: input.getAttribute('autocapitalize') || '',
      spellcheck: input.getAttribute('spellcheck') || ''
    },
    attrsOk,
    domOrderOk,
    beforeShiftEnter,
    shiftEnterValue: input.value,
    shiftEnterInsertedNewline,
    shiftEnterPreventedDefault,
    beforeImeEnter,
    imeEnterValue: input.value,
    imeEnterIgnored,
    inputFontSize,
    formFocusVisible,
    composerVisualClean,
    formRadius,
    uploadRadius,
    submitRadius,
    formRect: { width: formRect.width, height: formRect.height },
    uploadRect: { width: uploadRect.width, height: uploadRect.height },
    submitRect: { width: submitRect.width, height: submitRect.height },
    formBorderColor: formFocusStyle.borderColor,
    formBoxShadow: formFocusStyle.boxShadow,
    uploadFocusVisible,
    uploadOutline: `${uploadOutlineWidth} ${uploadOutlineStyle}`,
    submitFocusVisible,
    submitOutline: `${submitOutlineWidth} ${submitOutlineStyle}`,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


NEW_CHAT_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const beforePath = location.pathname;
  const button = document.querySelector('#new-chat');
  if (!button) {
    return { ok: false, reason: 'missing_new_chat_button', beforePath };
  }
  button.click();
  await wait(450);
  const historyItems = [...document.querySelectorAll('#chat-history .conversation-item')];
  const activeItem = document.querySelector('#chat-history .conversation-item.active');
  const idFromPath = (location.pathname.match(/^\\/c\\/([^/?#]+)/) || [])[1] || '';
  const activeId = activeItem?.id?.replace(/^conversation-/, '') || '';
  const title = activeItem?.querySelector('.conversation-text span')?.textContent?.trim() || '';
  const meta = activeItem?.querySelector('.conversation-text small')?.textContent?.trim() || '';
  const empty = document.querySelector('.hai-empty-state');
  const composer = document.querySelector('.bottom-panel form');
  const emptyRect = empty ? empty.getBoundingClientRect() : null;
  const composerRect = composer ? composer.getBoundingClientRect() : null;
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  return {
    ok: Boolean(idFromPath && activeId && idFromPath === activeId && historyItems.length >= 1),
    beforePath,
    afterPath: location.pathname,
    idFromPath,
    activeId,
    historyCount: historyItems.length,
    activeTitle: title,
    activeMeta: meta,
    url: location.href,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth,
    emptyState: emptyRect ? { left: emptyRect.left, right: emptyRect.right, width: emptyRect.width } : null,
    composer: composerRect ? { left: composerRect.left, right: composerRect.right, width: composerRect.width } : null,
    ariaBusy: document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null
  };
})()
"""


CHAT_TEXT_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const beforePath = location.pathname;
  document.querySelector('#new-chat')?.click();
  await wait(450);
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  if (!input || !submit) {
    return { ok: false, reason: 'missing_composer', beforePath };
  }
  input.value = 'browser qa jawab satu kalimat: apa itu router?';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const startedAt = Date.now();
  let assistantText = '';
  let assistantCount = 0;
  let userCount = 0;
  let ariaBusy = null;
  let lastAssistant = null;
  while (Date.now() - startedAt < 70000) {
    await wait(300);
    const assistants = [...document.querySelectorAll('.assistant-message-container')];
    const users = [...document.querySelectorAll('.user-message-container')];
    assistantCount = assistants.length;
    userCount = users.length;
    lastAssistant = assistants.at(-1) || null;
    assistantText = lastAssistant?.innerText?.trim() || '';
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null;
    const stillStreaming = Boolean(document.querySelector('.assistant-message-container.is-streaming'));
    if (assistantText && assistantText.length > 8 && ariaBusy === 'false' && !stillStreaming) break;
  }

  const idFromPath = (location.pathname.match(/^\\/c\\/([^/?#]+)/) || [])[1] || '';
  const activeId = document.querySelector('#chat-history .conversation-item.active')?.id?.replace(/^conversation-/, '') || '';
  const hasThinkLeak = /<\\/?think>|Sedang menyusun jawaban/i.test(assistantText);
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  const isCompactChromeViewport = innerWidth <= 820 || (innerHeight <= 520 && matchMedia('(orientation: landscape)').matches);
  const expectedAssistantActions = ['Edit pesan', 'Salin pesan', 'Hapus pesan', 'Buat ulang jawaban'];
  const collectVisibleAssistantActionIcons = () => [...document.querySelectorAll('.assistant-message-container .message-buttons button')]
    .filter((button) => getComputedStyle(button).display !== 'none' && getComputedStyle(button).visibility !== 'hidden')
    .map((button) => {
      const icon = button.querySelector('img.icon-svg');
      const box = icon?.getBoundingClientRect?.() || { width: 0, height: 0 };
      const buttonBox = button.getBoundingClientRect?.() || { width: 0, height: 0 };
      const buttonStyle = getComputedStyle(button);
      return {
        label: button.getAttribute('aria-label') || button.title || button.className,
        src: icon?.getAttribute('src') || '',
        complete: Boolean(icon?.complete),
        naturalWidth: icon?.naturalWidth || 0,
        naturalHeight: icon?.naturalHeight || 0,
        width: box.width || 0,
        height: box.height || 0,
        buttonWidth: buttonBox.width || 0,
        buttonHeight: buttonBox.height || 0,
        buttonBackground: buttonStyle.backgroundColor || '',
        buttonBorderColor: buttonStyle.borderColor || '',
        buttonOpacity: Number(buttonStyle.opacity || 1),
        paints: Boolean(icon && icon.complete && icon.naturalWidth > 0 && icon.naturalHeight > 0 && box.width >= 12 && box.height >= 12)
      };
    });
  const idleAssistantActionIcons = collectVisibleAssistantActionIcons();
  const compactIdleActionsMinimal = !isCompactChromeViewport || idleAssistantActionIcons.length <= 2;
  if (isCompactChromeViewport && lastAssistant) {
    lastAssistant.click();
    await wait(180);
  }
  let visibleAssistantActionIcons = collectVisibleAssistantActionIcons();
  const iconWaitStartedAt = Date.now();
  const actionsMatchExpected = () => expectedAssistantActions.every((label) => visibleAssistantActionIcons.some((item) => item.label === label)) && visibleAssistantActionIcons.length === expectedAssistantActions.length;
  while (!(actionsMatchExpected() && visibleAssistantActionIcons.every((item) => item.paints)) && Date.now() - iconWaitStartedAt < 3000) {
    await wait(100);
    visibleAssistantActionIcons = collectVisibleAssistantActionIcons();
  }
  const visibleAssistantActions = visibleAssistantActionIcons.map((item) => item.label);
  const visibleAssistantActionIconsPaint = visibleAssistantActionIcons.every((item) => item.paints);
  const visibleAssistantActionPillsReadable = !isCompactChromeViewport || visibleAssistantActionIcons.every((item) =>
    item.buttonWidth >= 32 &&
    item.buttonHeight >= 32 &&
    !/rgba\\(0, 0, 0, 0\\)|transparent/i.test(`${item.buttonBackground} ${item.buttonBorderColor}`) &&
    item.buttonOpacity >= .8
  );
  const visibleAssistantActionsExact = actionsMatchExpected();
  const regenerateIcon = document.querySelector('.assistant-message-container .message-regenerate-button img.icon-svg');
  const regenerateIconSrc = regenerateIcon?.getAttribute('src') || '';
  const regenerateIconBox = regenerateIcon?.getBoundingClientRect?.() || { width: 0, height: 0 };
  const regenerateUsesStableIcon = regenerateIconSrc.includes('/static/images/icons/regenerate.svg');
  const regenerateIconPaints = Boolean(regenerateIcon && regenerateIcon.complete && regenerateIcon.naturalWidth > 0 && regenerateIcon.naturalHeight > 0 && regenerateIconBox.width >= 12 && regenerateIconBox.height >= 12);
  const actionBars = [...document.querySelectorAll('.assistant-message-container .message-buttons, .user-message-container .message-buttons')]
    .filter((bar) => getComputedStyle(bar).display !== 'none' && getComputedStyle(bar).visibility !== 'hidden')
    .map((bar) => {
      const style = getComputedStyle(bar);
      return {
        opacity: Number(style.opacity || 1),
        pointerEvents: style.pointerEvents || '',
        className: String(bar.className || '')
      };
    });
  const desktopActionBarsQuiet = isCompactChromeViewport || actionBars.every((bar) => bar.opacity <= 0.2 || bar.pointerEvents === 'none');
  const quickRow = document.querySelector('.hai-quick-row');
  const quickStyle = quickRow ? getComputedStyle(quickRow) : null;
  const quickPromptsHiddenAfterChat = Boolean(quickRow && (quickStyle.display === 'none' || quickRow.getAttribute('aria-hidden') === 'true') && document.body.classList.contains('hai-chat-active'));
  const topbarTitle = document.querySelector('#hai-top-heading')?.textContent?.trim() || '';
  const topbarSubtitle = document.querySelector('#hai-top-subtitle')?.textContent?.trim() || '';
  const topbarUsesChatTitle = Boolean(document.body.classList.contains('hai-chat-active') && topbarTitle && topbarTitle !== 'Harmonika AI' && topbarTitle !== 'Percakapan baru' && topbarSubtitle === 'Percakapan aktif');
  const topTitleNode = document.querySelector('.hai-top-title');
  const topActionsNode = document.querySelector('.hai-top-actions');
  const topActionButtons = [...document.querySelectorAll('.hai-top-actions button')];
  const topTitleRect = topTitleNode?.getBoundingClientRect?.() || null;
  const topActionsRect = topActionsNode?.getBoundingClientRect?.() || null;
  const topActionsStyle = topActionsNode ? getComputedStyle(topActionsNode) : null;
  const sidebarButtonsRect = document.querySelector('.sidebar-buttons')?.getBoundingClientRect?.() || null;
  const topbarLeadingGap = sidebarButtonsRect && topTitleRect ? topTitleRect.left - sidebarButtonsRect.right : null;
  const topActionMetrics = {
    titleWidth: topTitleRect?.width || 0,
    actionsWidth: topActionsRect?.width || 0,
    opacity: Number(topActionsStyle?.opacity || 1),
    buttonWidths: topActionButtons.map((button) => button.getBoundingClientRect().width || 0),
    leadingGap: topbarLeadingGap
  };
  const mobileTopbarCompact = !isCompactChromeViewport || Boolean(
    topActionMetrics.titleWidth >= 120 &&
    (topbarLeadingGap === null || (topbarLeadingGap >= 8 && topbarLeadingGap <= 24)) &&
    topActionMetrics.actionsWidth <= 74 &&
    topActionMetrics.opacity <= 0.82 &&
    topActionMetrics.buttonWidths.length === 2 &&
    topActionMetrics.buttonWidths.every((width) => width <= 34)
  );
  if (isCompactChromeViewport) {
    document.activeElement?.blur?.();
    document.querySelectorAll('.assistant-message-container.is-actions-active, .user-message-container.is-actions-active')
      .forEach((node) => node.classList.remove('is-actions-active'));
    await wait(120);
  }
  const postResetAssistantActions = collectVisibleAssistantActionIcons().map((item) => item.label);
  const postResetUserActions = [...document.querySelectorAll('.user-message-container .message-buttons button')]
    .filter((button) => getComputedStyle(button).display !== 'none' && getComputedStyle(button).visibility !== 'hidden')
    .map((button) => button.getAttribute('aria-label') || button.title || button.className);
  const compactScreenshotActionsIdle = !isCompactChromeViewport || (postResetAssistantActions.length <= 2 && postResetUserActions.length === 0);
  return {
    ok: Boolean(idFromPath && activeId === idFromPath && userCount >= 1 && assistantCount >= 1 && assistantText.length > 8 && !hasThinkLeak && ariaBusy === 'false' && scrollWidth <= innerWidth && compactIdleActionsMinimal && compactScreenshotActionsIdle && visibleAssistantActionsExact && !visibleAssistantActions.includes('Lanjutkan jawaban') && desktopActionBarsQuiet && quickPromptsHiddenAfterChat && topbarUsesChatTitle && mobileTopbarCompact && regenerateUsesStableIcon && regenerateIconPaints && visibleAssistantActionIconsPaint && visibleAssistantActionPillsReadable),
    beforePath,
    afterPath: location.pathname,
    idFromPath,
    activeId,
    userCount,
    assistantCount,
    assistantSample: assistantText.slice(0, 240),
    visibleAssistantActions,
    idleAssistantActions: idleAssistantActionIcons.map((item) => item.label),
    postResetAssistantActions,
    postResetUserActions,
    compactIdleActionsMinimal,
    compactScreenshotActionsIdle,
    regenerateIconSrc,
    regenerateUsesStableIcon,
    regenerateIconPaints,
    regenerateIconNaturalWidth: regenerateIcon?.naturalWidth || 0,
    regenerateIconNaturalHeight: regenerateIcon?.naturalHeight || 0,
    regenerateIconBox: {
      width: regenerateIconBox.width || 0,
      height: regenerateIconBox.height || 0
    },
    visibleAssistantActionIcons,
    visibleAssistantActionIconsPaint,
    visibleAssistantActionPillsReadable,
    visibleAssistantActionsExact,
    actionBars,
    desktopActionBarsQuiet,
    quickPromptsHiddenAfterChat,
    topbarTitle,
    topbarSubtitle,
    topbarUsesChatTitle,
    topActionMetrics,
    mobileTopbarCompact,
    quickRowDisplay: quickStyle?.display || '',
    bodyIsChatActive: document.body.classList.contains('hai-chat-active'),
    hasThinkLeak,
    ariaBusy,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


IMAGE_ARTIFACT_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  document.querySelector('#new-chat')?.click();
  await wait(450);
  let input = null;
  let submit = null;
  for (let i = 0; i < 20; i += 1) {
    input = document.querySelector('#user-input');
    submit = document.querySelector('#submit-button');
    if (input && submit) break;
    await wait(250);
  }
  if (!input || !submit) {
    return { ok: false, reason: 'missing_composer', url: location.href, bodyText: document.body?.innerText?.slice(0, 240) || '' };
  }
  input.value = 'Buatkan gambar ikon robot lucu sederhana';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const startedAt = Date.now();
  let state = {};
  while (Date.now() - startedAt < 70000) {
    await wait(600);
    const assistant = [...document.querySelectorAll('.assistant-message-container')].at(-1);
    const text = assistant?.innerText?.trim() || '';
    const image = assistant?.querySelector('img[src^="/api/files/"]') || null;
    const artifact = assistant?.querySelector('.hai-member-image-artifact, .hai-legacy-image, .hai-image-artifact, figure') || null;
    const ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null;
    state = {
      text: text.slice(0, 320),
      hasPrivatePreview: Boolean(image),
      previewSrc: image?.getAttribute('src') || '',
      hasArtifact: Boolean(artifact),
      hasPublicUrlText: /https?:\\/\\//i.test(text),
      hasRawSvgCode: /<svg|```svg/i.test(text),
      ariaBusy
    };
    if (image && artifact && ariaBusy === 'false') break;
  }

  const previewImage = document.querySelector('.assistant-message-container img[src^="/api/files/"]');
  previewImage?.click();
  await wait(700);
  const modal = document.querySelector('.hai-image-modal');
  const card = document.querySelector('.hai-image-modal-card');
  const modalRect = modal?.getBoundingClientRect?.();
  const cardRect = card?.getBoundingClientRect?.();
  const modalOpen = Boolean(modal && card && modalRect.width >= innerWidth * 0.95 && modalRect.height >= innerHeight * 0.95);
  const cardLooksCentered = Boolean(cardRect && cardRect.width >= innerWidth * 0.35 && cardRect.width <= innerWidth * 0.72 && cardRect.height >= innerHeight * 0.35);
  modal?.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 8, clientY: 8 }));
  await wait(400);
  const closedByBackdrop = !document.querySelector('.hai-image-modal');
  const activeId = document.querySelector('#chat-history .conversation-item.active')?.id?.replace(/^conversation-/, '') || '';
  if (activeId && typeof loadConversation === 'function') {
    await loadConversation(activeId, false);
    await wait(900);
  }
  const reloadedAssistant = [...document.querySelectorAll('.assistant-message-container')].at(-1);
  const reloadedImage = reloadedAssistant?.querySelector('img[src^="/api/files/"]') || null;
  const reloadedArtifact = reloadedAssistant?.querySelector('.hai-member-image-artifact, .hai-legacy-image, .hai-image-artifact, figure') || null;
  const reloadedText = reloadedAssistant?.innerText?.trim() || '';
  const reloadKeepsArtifact = Boolean(
    activeId &&
    reloadedImage &&
    reloadedArtifact &&
    !/<svg|```svg/i.test(reloadedText) &&
    !/https?:\\/\\//i.test(reloadedText)
  );
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

  return {
    ok: Boolean(
      state.hasPrivatePreview &&
      state.previewSrc.startsWith('/api/files/') &&
      state.hasArtifact &&
      !state.hasPublicUrlText &&
      !state.hasRawSvgCode &&
      state.ariaBusy === 'false' &&
      modalOpen &&
      cardLooksCentered &&
      closedByBackdrop &&
      reloadKeepsArtifact &&
      scrollWidth <= innerWidth
    ),
    ...state,
    activeId,
    reloadKeepsArtifact,
    reloadedPreviewSrc: reloadedImage?.getAttribute('src') || '',
    reloadedHasArtifact: Boolean(reloadedArtifact),
    reloadedHasRawSvgCode: /<svg|```svg/i.test(reloadedText),
    reloadedHasPublicUrlText: /https?:\\/\\//i.test(reloadedText),
    modalOpen,
    cardLooksCentered,
    closedByBackdrop,
    modalRect: modalRect ? { width: modalRect.width, height: modalRect.height } : null,
    cardRect: cardRect ? { width: cardRect.width, height: cardRect.height } : null,
    innerWidth,
    innerHeight,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


HISTORY_CONTROLS_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const beforePath = location.pathname;
  const newChat = document.querySelector('#new-chat');
  if (!newChat) return { ok: false, reason: 'missing_new_chat_button', beforePath };
  newChat.click();
  await wait(600);

  const idFromPath = (location.pathname.match(/^\\/c\\/([^/?#]+)/) || [])[1] || '';
  let active = document.querySelector('#chat-history .conversation-item.active');
  const initialTitle = active?.querySelector('.conversation-text span')?.textContent?.trim() || '';
  const initialGroupLabels = [...document.querySelectorAll('#chat-history .conversation-group-header')].map((item) => item.textContent.trim());
  const localizedGroupLabels = initialGroupLabels.length > 0 && initialGroupLabels.every((label) => ['Hari ini', 'Kemarin', '7 hari terakhir', 'Lebih lama'].includes(label));
  const renameButton = active?.querySelector('.rename-button');
  const deleteButtonInitial = active?.querySelector('.delete-button');
  if (!idFromPath || !active || !renameButton) {
    return {
      ok: false,
      reason: 'missing_initial_history_state',
      idFromPath,
      activeFound: Boolean(active),
      renameFound: Boolean(renameButton),
      deleteFound: Boolean(deleteButtonInitial),
      historyCount: document.querySelectorAll('#chat-history .conversation-item').length
    };
  }
  const renameOpacityIdle = Number(getComputedStyle(renameButton).opacity || 0);
  const deleteOpacityIdle = deleteButtonInitial ? Number(getComputedStyle(deleteButtonInitial).opacity || 0) : 0;
  const desktopHistoryControlsQuiet = innerWidth < 821 || (renameOpacityIdle <= 0.05 && deleteOpacityIdle <= 0.05);
  renameButton.focus();
  await wait(120);
  const renameOpacityFocused = Number(getComputedStyle(renameButton).opacity || 0);
  const deleteOpacityFocused = deleteButtonInitial ? Number(getComputedStyle(deleteButtonInitial).opacity || 0) : 0;
  const historyControlsFocusVisible = innerWidth < 821 || (renameOpacityFocused >= 0.9 && (!deleteButtonInitial || deleteOpacityFocused >= 0.9));

  const renamedTitle = `QA History ${Date.now()}`;
  const originalPrompt = window.prompt;
  const originalConfirm = window.confirm;
  window.prompt = () => renamedTitle;
  renameButton.click();
  await wait(700);
  window.prompt = originalPrompt;
  active = document.querySelector('#chat-history .conversation-item.active');
  const titleAfterRename = active?.querySelector('.conversation-text span')?.textContent?.trim() || '';

  const search = document.querySelector('#history-search');
  if (search) {
    search.value = 'QA History';
    search.dispatchEvent(new Event('input', { bubbles: true }));
    await wait(300);
  }
  const filteredTitles = [...document.querySelectorAll('#chat-history .conversation-item .conversation-text span')]
    .map((item) => item.textContent.trim());
  const searchMatched = !search || (filteredTitles.length >= 1 && filteredTitles.every((title) => title.includes('QA History')));

  if (search) {
    search.value = '';
    search.dispatchEvent(new Event('input', { bubbles: true }));
    await wait(300);
  }

  active = document.querySelector(`#conversation-${CSS.escape(idFromPath)}`);
  const deleteButton = active?.querySelector('.delete-button');
  window.confirm = () => true;
  deleteButton?.click();
  await wait(900);
  window.confirm = originalConfirm;
  const remainingIds = [...document.querySelectorAll('#chat-history .conversation-item')]
    .map((item) => item.id.replace(/^conversation-/, ''));
  const deletedGone = !remainingIds.includes(idFromPath);
  const returnedToBase = location.pathname === '/' || !location.pathname.startsWith('/c/');
  const emptyVisible = Boolean(document.querySelector('#chat-history .hai-history-empty')) || remainingIds.length === 0;
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

  return {
    ok: Boolean(
      titleAfterRename === renamedTitle &&
      desktopHistoryControlsQuiet &&
      historyControlsFocusVisible &&
      localizedGroupLabels &&
      searchMatched &&
      Boolean(deleteButton) &&
      deletedGone &&
      returnedToBase &&
      emptyVisible &&
      scrollWidth <= innerWidth
    ),
    beforePath,
    idFromPath,
    initialTitle,
    initialGroupLabels,
    localizedGroupLabels,
    historyControlOpacity: {
      renameIdle: renameOpacityIdle,
      deleteIdle: deleteOpacityIdle,
      renameFocused: renameOpacityFocused,
      deleteFocused: deleteOpacityFocused,
      desktopHistoryControlsQuiet,
      historyControlsFocusVisible
    },
    renamedTitle,
    titleAfterRename,
    searchMatched,
    filteredTitles,
    deleteFound: Boolean(deleteButton),
    deletedGone,
    returnedToBase,
    emptyVisible,
    afterPath: location.pathname,
    remainingCount: remainingIds.length,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth,
    ariaBusy: document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null
  };
})()
"""


LIBRARY_PANEL_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  if (document.body.classList.contains('hai-sidebar-collapsed')) {
    document.querySelector('.sidebar-buttons .sidebar-button')?.click();
    await wait(250);
  }
  await wait(600);
  const panel = document.querySelector('#hai-library-panel');
  const search = document.querySelector('#hai-library-search');
  const upload = document.querySelector('#hai-library-upload');
  const groundingToggle = document.querySelector('#hai-library-grounding-toggle');
  const contextToggle = document.querySelector('#hai-library-context-toggle');
  const list = document.querySelector('#hai-library-list');
  const count = document.querySelector('#hai-library-count');
  const input = document.querySelector('#user-input');
  if (!panel || !search || !upload || !groundingToggle || !contextToggle || !list || !count || !input) {
    return {
      ok: false,
      reason: 'missing_library_dom',
      hasPanel: Boolean(panel),
      hasSearch: Boolean(search),
      hasUpload: Boolean(upload),
      hasGroundingToggle: Boolean(groundingToggle),
      hasContextToggle: Boolean(contextToggle),
      hasList: Boolean(list),
      hasCount: Boolean(count),
      hasInput: Boolean(input)
    };
  }

  let renderError = '';
  try {
    haiLibraryLoading = false;
    haiLibraryDocuments = [
      {
        id: 'lib_1234567890abcdef1234',
        name: 'qa-library-router.txt',
        mime: 'text/plain',
        size_bytes: 2048,
        text_chars: 148,
        preview: 'Dokumen QA Library berisi kode panel LIB-PANEL-261 dan catatan router rumah.'
      },
      {
        id: 'lib_abcdef1234567890abcd',
        name: 'qa-library-promosi.csv',
        mime: 'text/csv',
        size_bytes: 1024,
        text_chars: 96,
        preview: 'Catatan promosi makanan rumahan untuk uji filter Library.'
      }
    ];
    renderLibraryPanel();
  } catch (error) {
    renderError = String(error?.message || error);
  }
  await wait(150);

  const itemsBefore = [...list.querySelectorAll('.hai-library-item')];
  const useButton = list.querySelector('.hai-library-use');
  const deleteButton = list.querySelector('.hai-library-delete');
  const initialCount = count.textContent.trim();
  const panelRect = panel.getBoundingClientRect();
  const searchRect = search.getBoundingClientRect();
  const uploadRect = upload.getBoundingClientRect();
  const listRect = list.getBoundingClientRect();
  const deleteRect = deleteButton?.getBoundingClientRect() || null;
  const panelStyle = getComputedStyle(panel);
  const itemStyle = itemsBefore[0] ? getComputedStyle(itemsBefore[0]) : null;
  const uploadLabel = upload.getAttribute('aria-label') || '';
  const groundingInitial = {
    text: groundingToggle.textContent.trim(),
    mode: groundingToggle.dataset.mode || '',
    pressed: groundingToggle.getAttribute('aria-pressed') || ''
  };
  groundingToggle.click();
  await wait(80);
  const groundingForce = {
    text: groundingToggle.textContent.trim(),
    mode: groundingToggle.dataset.mode || '',
    pressed: groundingToggle.getAttribute('aria-pressed') || ''
  };
  groundingToggle.click();
  await wait(80);
  const groundingOff = {
    text: groundingToggle.textContent.trim(),
    mode: groundingToggle.dataset.mode || '',
    pressed: groundingToggle.getAttribute('aria-pressed') || ''
  };
  groundingToggle.click();
  await wait(80);
  const groundingRestored = {
    text: groundingToggle.textContent.trim(),
    mode: groundingToggle.dataset.mode || '',
    pressed: groundingToggle.getAttribute('aria-pressed') || ''
  };
  const contextInitial = {
    text: contextToggle.textContent.trim(),
    mode: contextToggle.dataset.mode || '',
    pressed: contextToggle.getAttribute('aria-pressed') || ''
  };
  contextToggle.click();
  await wait(80);
  const contextFull = {
    text: contextToggle.textContent.trim(),
    mode: contextToggle.dataset.mode || '',
    pressed: contextToggle.getAttribute('aria-pressed') || ''
  };
  contextToggle.click();
  await wait(80);
  const contextRestored = {
    text: contextToggle.textContent.trim(),
    mode: contextToggle.dataset.mode || '',
    pressed: contextToggle.getAttribute('aria-pressed') || ''
  };
  const deleteLabel = deleteButton?.getAttribute('aria-label') || '';
  const originalConfirm = window.confirm;
  const originalFetch = window.fetch;
  let backendSearchCalled = false;
  window.fetch = async (url, options = {}) => {
    const method = String(options?.method || 'GET').toUpperCase();
    if (String(url).includes('/api/library/search') && method === 'POST') {
      backendSearchCalled = true;
      return new Response(JSON.stringify({
        ok: true,
        results: [{
          id: 'lib_abcdef1234567890abcd',
          name: 'qa-library-promosi.csv',
          mime: 'text/csv',
          size_bytes: 1024,
          text_chars: 96,
          preview: 'Catatan promosi makanan rumahan untuk uji filter Library.',
          snippet: 'Hasil backend isi dokumen: HIDDEN-LIB-262 strategi bundling pelanggan.'
        }],
        count: 1
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    if (String(url).includes('/api/library/documents/') && method === 'DELETE') {
      return new Response(JSON.stringify({ ok: true, deleted: true, message: 'Dokumen dihapus.' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    return originalFetch(url, options);
  };

  search.value = 'hidden-lib-262';
  search.dispatchEvent(new Event('input', { bubbles: true }));
  await wait(520);
  const filteredItems = [...list.querySelectorAll('.hai-library-item')];
  const filteredText = list.innerText || '';

  search.value = '';
  search.dispatchEvent(new Event('input', { bubbles: true }));
  await wait(120);
  const restoredItems = [...list.querySelectorAll('.hai-library-item')];

  const beforePrompt = input.value;
  useButton?.click();
  await wait(120);
  const promptAfterUse = input.value;

  window.confirm = () => true;
  deleteButton?.click();
  await wait(250);
  window.confirm = originalConfirm;
  window.fetch = originalFetch;
  const countAfterDelete = count.textContent.trim();
  const itemsAfterDelete = [...list.querySelectorAll('.hai-library-item')];
  const toastText = document.querySelector('.toast-message, .hai-toast, #toast')?.innerText || '';

  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  const visible = panelRect.width > 120 && panelRect.height > 80 && panelStyle.display !== 'none' && panelStyle.visibility !== 'hidden';
  const touchTargetsOk = searchRect.height >= 32 && uploadRect.height >= 32 && (!deleteRect || deleteRect.height >= 28);
  const restoredOk = restoredItems.length === 2;
  const filterOk = backendSearchCalled && filteredItems.length === 1 && /HIDDEN-LIB-262/i.test(filteredText) && !/router rumah/i.test(filteredText);
  const promptOk = /Gunakan dokumen Library "qa-library-router\\.txt" untuk menjawab:/i.test(promptAfterUse);
  const deleteOk = itemsAfterDelete.length === 1 && countAfterDelete === '1' && !list.innerText.includes('qa-library-router.txt');
  const groundingOk = Boolean(
    groundingInitial.mode === 'auto' &&
    groundingForce.mode === 'force' &&
    groundingOff.mode === 'off' &&
    groundingOff.pressed === 'false' &&
    groundingRestored.mode === 'auto'
  );
  const contextOk = Boolean(
    contextInitial.mode === 'snippet' &&
    contextFull.mode === 'full' &&
    contextFull.pressed === 'true' &&
    contextRestored.mode === 'snippet'
  );

  return {
    ok: Boolean(
      !renderError &&
      visible &&
      initialCount === '2' &&
      itemsBefore.length === 2 &&
      restoredOk &&
      filterOk &&
      promptOk &&
      deleteOk &&
      groundingOk &&
      contextOk &&
      uploadLabel.toLowerCase().includes('upload') &&
      deleteLabel.toLowerCase().includes('hapus') &&
      touchTargetsOk &&
      scrollWidth <= innerWidth
    ),
    renderError,
    initialCount,
    countAfterDelete,
    itemsBefore: itemsBefore.map((item) => item.innerText.trim()),
    filteredCount: filteredItems.length,
    filteredText,
    backendSearchCalled,
    restoredCount: restoredItems.length,
    itemsAfterDelete: itemsAfterDelete.map((item) => item.innerText.trim()),
    beforePrompt,
    promptAfterUse,
    promptOk,
    deleteOk,
    groundingOk,
    contextOk,
    groundingInitial,
    groundingForce,
    groundingOff,
    groundingRestored,
    contextInitial,
    contextFull,
    contextRestored,
    uploadLabel,
    deleteLabel,
    toastText,
    panelRect: { width: panelRect.width, height: panelRect.height },
    searchRect: { width: searchRect.width, height: searchRect.height },
    uploadRect: { width: uploadRect.width, height: uploadRect.height },
    deleteRect: deleteRect ? { width: deleteRect.width, height: deleteRect.height } : null,
    listRect: { width: listRect.width, height: listRect.height },
    panelBorderColor: panelStyle.borderColor,
    itemBackground: itemStyle?.backgroundColor || '',
    touchTargetsOk,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth,
    ariaBusy: document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null
  };
})()
"""


STOP_STREAM_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  document.querySelector('#new-chat')?.click();
  await wait(450);
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  if (!input || !submit) return { ok: false, reason: 'missing_composer' };
  input.value = 'Tulis daftar sangat panjang 80 poin tentang tips keamanan jaringan rumah. Buat setiap poin satu kalimat.';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const startedAt = Date.now();
  let stopVisible = false;
  while (Date.now() - startedAt < 12000) {
    await wait(150);
    stopVisible = submit.classList.contains('is-stop') || /stop/i.test(submit.innerHTML);
    if (stopVisible) break;
  }
  if (!stopVisible) {
    return {
      ok: false,
      reason: 'stop_button_not_visible',
      buttonClass: submit.className,
      ariaBusy: document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null,
      assistantText: ([...document.querySelectorAll('.assistant-message-container')].at(-1)?.innerText || '').slice(0, 240)
    };
  }

  submit.click();
  const stoppedAt = Date.now();
  let ariaBusy = null;
  let stillStreaming = true;
  while (Date.now() - stoppedAt < 12000) {
    await wait(250);
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null;
    stillStreaming = Boolean(document.querySelector('.assistant-message-container.is-streaming')) || submit.classList.contains('is-stop');
    if (ariaBusy === 'false' && !stillStreaming) break;
  }

  const assistant = [...document.querySelectorAll('.assistant-message-container')].at(-1);
  const assistantText = assistant?.innerText?.trim() || '';
  const hasThinkLeak = /<\\/?think>|Sedang menyusun jawaban/i.test(assistantText);
  const stillWaitingText = /Harmonika AI sedang menyusun jawaban|Harmonika AI sedang mendesain gambar/i.test(assistantText);
  const visibleAssistantActions = [...document.querySelectorAll('.assistant-message-container .message-buttons button')]
    .filter((button) => getComputedStyle(button).display !== 'none' && getComputedStyle(button).visibility !== 'hidden')
    .map((button) => button.getAttribute('aria-label') || button.title || button.className);
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

  return {
    ok: Boolean(stopVisible && ariaBusy === 'false' && !stillStreaming && assistant && assistantText.length > 0 && !stillWaitingText && !hasThinkLeak && visibleAssistantActions.length <= 4 && scrollWidth <= innerWidth),
    stopVisible,
    ariaBusy,
    stillStreaming,
    assistantLength: assistantText.length,
    assistantSample: assistantText.slice(0, 240),
    visibleAssistantActions,
    hasThinkLeak,
    stillWaitingText,
    buttonClass: submit.className,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


REGENERATE_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  document.querySelector('#new-chat')?.click();
  await wait(450);
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  if (!input || !submit) return { ok: false, reason: 'missing_composer' };
  input.value = 'Jawab tepat satu kalimat dan jangan mengulang: apa fungsi router?';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const startedAt = Date.now();
  let firstText = '';
  while (Date.now() - startedAt < 45000) {
    await wait(300);
    firstText = [...document.querySelectorAll('.assistant-message-container')].at(-1)?.innerText?.trim() || '';
    const ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null;
    if (firstText.length > 8 && ariaBusy === 'false' && !document.querySelector('.assistant-message-container.is-streaming')) break;
  }

  const beforeContainer = [...document.querySelectorAll('.assistant-message-container')].at(-1);
  const beforeMessageId = beforeContainer?.dataset?.messageId || '';
  const regen = beforeContainer?.querySelector('.message-regenerate-button');
  if (!regen || getComputedStyle(regen).display === 'none') {
    return { ok: false, reason: 'missing_regenerate_button', firstText: firstText.slice(0, 240), beforeMessageId };
  }
  regen.click();

  const regenStartedAt = Date.now();
  let finalText = '';
  let ariaBusy = null;
  while (Date.now() - regenStartedAt < 50000) {
    await wait(300);
    const assistant = [...document.querySelectorAll('.assistant-message-container')].at(-1);
    finalText = assistant?.innerText?.trim() || '';
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null;
    const newId = assistant?.dataset?.messageId || '';
    if (finalText.length > 8 && ariaBusy === 'false' && newId && newId !== beforeMessageId && !document.querySelector('.assistant-message-container.is-streaming')) break;
  }

  const afterContainer = [...document.querySelectorAll('.assistant-message-container')].at(-1);
  const afterMessageId = afterContainer?.dataset?.messageId || '';
  const hasThinkLeak = /<\\/?think>|Sedang menyusun jawaban/i.test(finalText);
  const compactFinal = finalText.replace(/\\s+/g, ' ').trim();
  const firstSentence = (compactFinal.match(/^[^.!?]+[.!?]/) || [''])[0].trim();
  const duplicateFirstSentence = firstSentence.length > 25 && compactFinal.indexOf(firstSentence, firstSentence.length) !== -1;
  const sentenceCount = (compactFinal.match(/[.!?](?=\\s|$)/g) || []).length || (compactFinal ? 1 : 0);
  const visibleAssistantActions = [...document.querySelectorAll('.assistant-message-container .message-buttons button')]
    .filter((button) => getComputedStyle(button).display !== 'none' && getComputedStyle(button).visibility !== 'hidden')
    .map((button) => button.getAttribute('aria-label') || button.title || button.className);
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

  return {
    ok: Boolean(firstText.length > 8 && finalText.length > 8 && beforeMessageId && afterMessageId && afterMessageId !== beforeMessageId && ariaBusy === 'false' && !hasThinkLeak && !duplicateFirstSentence && sentenceCount <= 1 && visibleAssistantActions.length <= 4 && scrollWidth <= innerWidth),
    beforeMessageId,
    afterMessageId,
    firstSample: firstText.slice(0, 200),
    finalSample: finalText.slice(0, 200),
    firstSentence,
    duplicateFirstSentence,
    sentenceCount,
    ariaBusy,
    visibleAssistantActions,
    hasThinkLeak,
    assistantCount: document.querySelectorAll('.assistant-message-container').length,
    userCount: document.querySelectorAll('.user-message-container').length,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


ATTACHMENT_CHAT_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  document.querySelector('#new-chat')?.click();
  let input = null;
  let submit = null;
  let fileInput = null;
  for (let i = 0; i < 24; i += 1) {
    await wait(250);
    input = document.querySelector('#user-input');
    submit = document.querySelector('#submit-button');
    fileInput = document.querySelector('input[type="file"]');
    if (input && submit && fileInput) break;
  }
  if (!input || !submit || !fileInput) {
    return { ok: false, reason: 'missing_composer_or_file_input', hasInput: Boolean(input), hasSubmit: Boolean(submit), hasFileInput: Boolean(fileInput) };
  }

  const marker = `HAI-UI-ATTACH-${Date.now()}`;
  const file = new File([`Dokumen QA Harmonika AI. Kode verifikasi: ${marker}`], 'hai-ui-attachment.txt', { type: 'text/plain' });
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  fileInput.dispatchEvent(new Event('change', { bubbles: true }));

  const uploadStartedAt = Date.now();
  let chipText = '';
  let retriedChange = false;
  while (Date.now() - uploadStartedAt < 30000) {
    await wait(250);
    chipText = document.querySelector('#hai-attachment-tray')?.innerText?.trim() || '';
    const uploadIdle = !document.querySelector('#upload-files')?.disabled;
    if (/hai-ui-attachment\\.txt/i.test(chipText) && uploadIdle) break;
    if (!retriedChange && Date.now() - uploadStartedAt > 5000 && !chipText && uploadIdle) {
      retriedChange = true;
      fileInput.files = transfer.files;
      fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }
  if (!/hai-ui-attachment\\.txt/i.test(chipText)) {
    return {
      ok: false,
      reason: 'attachment_not_ready',
      marker,
      chipText,
      retriedChange,
      uploadDisabled: Boolean(document.querySelector('#upload-files')?.disabled),
      trayText: document.querySelector('#hai-attachment-tray')?.innerText?.trim() || '',
      innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth
    };
  }

  input.value = `Baca lampiran dan sebutkan kode verifikasi saja.`;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const startedAt = Date.now();
  let assistantText = '';
  let ariaBusy = null;
  while (Date.now() - startedAt < 60000) {
    await wait(400);
    assistantText = [...document.querySelectorAll('.assistant-message-container')].at(-1)?.innerText?.trim() || '';
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null;
    if (ariaBusy === 'false' && assistantText.length > 4 && !document.querySelector('.assistant-message-container.is-streaming')) break;
  }

  const userText = [...document.querySelectorAll('.user-message-container')].at(-1)?.innerText?.trim() || '';
  const trayAfterSend = document.querySelector('#hai-attachment-tray')?.innerText?.trim() || '';
  const hasThinkLeak = /<\\/?think>|Sedang menyusun jawaban/i.test(assistantText);
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  return {
    ok: Boolean(
      chipText.includes('hai-ui-attachment.txt') &&
      userText.includes('hai-ui-attachment.txt') &&
      assistantText.includes(marker) &&
      trayAfterSend === '' &&
      ariaBusy === 'false' &&
      !hasThinkLeak &&
      scrollWidth <= innerWidth
    ),
    marker,
    chipText,
    userText: userText.slice(0, 320),
    assistantSample: assistantText.slice(0, 420),
    trayAfterSend,
    ariaBusy,
    hasThinkLeak,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""

ATTACHMENT_PREVIEW_A11Y_FLOW_JS = """
(() => {
  if (typeof attachmentChipHtml !== 'function') {
    return { ok: false, reason: 'missing_attachment_chip_helper' };
  }
  const holder = document.createElement('div');
  holder.innerHTML = attachmentChipHtml({
    type: 'image',
    name: 'gambar-qa.png',
    mime: 'image/png',
    sizeLabel: '12 KB',
    base64: '/static/images/hai-logo.png'
  }, 'ready', 0, true);
  document.body.appendChild(holder);
  const thumb = holder.querySelector('.hai-attachment-thumb');
  const remove = holder.querySelector('.hai-attachment-remove');
  const chipText = holder.innerText.trim();
  const alt = thumb?.getAttribute('alt') || '';
  const removeLabel = remove?.getAttribute('aria-label') || '';
  const ok = Boolean(
    thumb &&
    alt === 'Pratinjau lampiran' &&
    removeLabel === 'Hapus lampiran' &&
    /gambar-qa\\.png/.test(chipText) &&
    /Gambar siap dianalisis AI/.test(chipText) &&
    !/\\bPreview\\b/.test(alt)
  );
  holder.remove();
  return {
    ok,
    alt,
    removeLabel,
    chipText,
    hasThumb: Boolean(thumb)
  };
})()
"""

ATTACHMENT_IMAGE_CHAT_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const makeRedPngFile = async () => {
    const canvas = document.createElement('canvas');
    canvas.width = 96;
    canvas.height = 96;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ff0000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'));
    return new File([blob], 'hai-red-vision-qa.png', { type: 'image/png' });
  };

  document.querySelector('#new-chat')?.click();
  let input = null;
  let submit = null;
  let fileInput = null;
  for (let i = 0; i < 24; i += 1) {
    await wait(250);
    input = document.querySelector('#user-input');
    submit = document.querySelector('#submit-button');
    fileInput = document.querySelector('input[type="file"]');
    if (input && submit && fileInput) break;
  }
  if (!input || !submit || !fileInput) {
    return { ok: false, reason: 'missing_composer_or_file_input', hasInput: Boolean(input), hasSubmit: Boolean(submit), hasFileInput: Boolean(fileInput) };
  }
  const accept = fileInput.getAttribute('accept') || '';
  const acceptHasImages = ['image/png', 'image/jpeg', 'image/webp'].every((type) => accept.includes(type));

  const file = await makeRedPngFile();
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  fileInput.dispatchEvent(new Event('change', { bubbles: true }));

  const uploadStartedAt = Date.now();
  let chipText = '';
  let thumbReady = false;
  let retriedChange = false;
  while (Date.now() - uploadStartedAt < 30000) {
    await wait(250);
    const tray = document.querySelector('#hai-attachment-tray');
    chipText = tray?.innerText?.trim() || '';
    const thumb = tray?.querySelector('.hai-attachment-thumb');
    thumbReady = Boolean(thumb && /^data:image\\/(png|jpeg|webp);base64,/i.test(thumb.getAttribute('src') || ''));
    const uploadIdle = !document.querySelector('#upload-files')?.disabled;
    if (/hai-red-vision-qa\\.png/i.test(chipText) && /Gambar siap dianalisis AI/i.test(chipText) && thumbReady && uploadIdle) break;
    if (!retriedChange && Date.now() - uploadStartedAt > 5000 && !chipText && uploadIdle) {
      retriedChange = true;
      fileInput.files = transfer.files;
      fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }
  const chipHasSize = /\\b\\d+(?:\\.\\d+)?\\s*(?:B|KB|MB)\\b/i.test(chipText);
  if (!/hai-red-vision-qa\\.png/i.test(chipText) || !/Gambar siap dianalisis AI/i.test(chipText) || !thumbReady || !chipHasSize || !acceptHasImages) {
    return {
      ok: false,
      reason: 'image_attachment_not_ready',
      chipText,
      thumbReady,
      chipHasSize,
      accept,
      acceptHasImages,
      retriedChange,
      uploadDisabled: Boolean(document.querySelector('#upload-files')?.disabled),
      trayText: document.querySelector('#hai-attachment-tray')?.innerText?.trim() || '',
      innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth
    };
  }

  input.value = 'Gambar ini warna dominannya apa? Jawab satu kata dalam bahasa Indonesia.';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const startedAt = Date.now();
  let assistantText = '';
  let ariaBusy = null;
  while (Date.now() - startedAt < 70000) {
    await wait(500);
    assistantText = [...document.querySelectorAll('.assistant-message-container')].at(-1)?.innerText?.trim() || '';
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null;
    if (ariaBusy === 'false' && assistantText.length > 2 && !document.querySelector('.assistant-message-container.is-streaming')) break;
  }

  const userText = [...document.querySelectorAll('.user-message-container')].at(-1)?.innerText?.trim() || '';
  const userHtml = [...document.querySelectorAll('.user-message-container')].at(-1)?.outerHTML || '';
  const assistantHtml = [...document.querySelectorAll('.assistant-message-container')].at(-1)?.outerHTML || '';
  const trayAfterSend = document.querySelector('#hai-attachment-tray')?.innerText?.trim() || '';
  const hasThinkLeak = /<\\/?think>|Sedang menyusun jawaban/i.test(assistantText);
  const base64LeakInText = /data:image\\/|iVBOR|base64/i.test(`${assistantText}\\n${userText}`);
  const publicLeakCorpus = `${assistantText}\\n${userText}\\n${assistantHtml}\\n${userHtml}`;
  const publicMediaLeak = /(?:https?:\\/\\/[^\\s"'<>]+)?\\/(?:media|download|downloads?|files?)\\//i.test(publicLeakCorpus);
  const assistantLooksRed = /^\\s*(merah|red)\\s*[.!?。]*\\s*$/i.test(assistantText);
  const assistantLooksError = /tidak terbaca|gagal|error|maaf/i.test(assistantText);
  const userHasSize = /\\b\\d+(?:\\.\\d+)?\\s*(?:B|KB|MB)\\b/i.test(userText);
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  return {
    ok: Boolean(
      acceptHasImages &&
      chipText.includes('hai-red-vision-qa.png') &&
      /Gambar siap dianalisis AI/i.test(chipText) &&
      chipHasSize &&
      userText.includes('hai-red-vision-qa.png') &&
      userHasSize &&
      assistantLooksRed &&
      !assistantLooksError &&
      trayAfterSend === '' &&
      ariaBusy === 'false' &&
      !hasThinkLeak &&
      !base64LeakInText &&
      !publicMediaLeak &&
      scrollWidth <= innerWidth
    ),
    chipText,
    thumbReady,
    chipHasSize,
    accept,
    acceptHasImages,
    userText: userText.slice(0, 320),
    assistantSample: assistantText.slice(0, 420),
    assistantLooksRed,
    assistantLooksError,
    userHasSize,
    trayAfterSend,
    ariaBusy,
    hasThinkLeak,
    base64LeakInText,
    publicMediaLeak,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


ATTACHMENT_MULTI_CHAT_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  document.querySelector('#new-chat')?.click();
  let input = null;
  let submit = null;
  let fileInput = null;
  for (let i = 0; i < 24; i += 1) {
    await wait(250);
    input = document.querySelector('#user-input');
    submit = document.querySelector('#submit-button');
    fileInput = document.querySelector('input[type="file"]');
    if (input && submit && fileInput) break;
  }
  if (!input || !submit || !fileInput) {
    return { ok: false, reason: 'missing_composer_or_file_input', hasInput: Boolean(input), hasSubmit: Boolean(submit), hasFileInput: Boolean(fileInput) };
  }

  const stamp = Date.now();
  const markerTxt = `HAI-MULTI-TXT-${stamp}`;
  const markerCsv = `HAI-MULTI-CSV-${stamp}`;
  const txt = new File([`Dokumen teks QA. Kode teks: ${markerTxt}`], 'hai-multi-a.txt', { type: 'text/plain' });
  const csv = new File([`jenis,kode\\ncsv,${markerCsv}\\n`], 'hai-multi-b.csv', { type: 'text/csv' });
  const transfer = new DataTransfer();
  transfer.items.add(txt);
  transfer.items.add(csv);
  fileInput.files = transfer.files;
  fileInput.dispatchEvent(new Event('change', { bubbles: true }));

  const uploadStartedAt = Date.now();
  let chipText = '';
  while (Date.now() - uploadStartedAt < 30000) {
    await wait(250);
    chipText = document.querySelector('#hai-attachment-tray')?.innerText?.trim() || '';
    const uploadIdle = !document.querySelector('#upload-files')?.disabled;
    if (/hai-multi-a\\.txt/i.test(chipText) && /hai-multi-b\\.csv/i.test(chipText) && uploadIdle) break;
  }
  if (!/hai-multi-a\\.txt/i.test(chipText) || !/hai-multi-b\\.csv/i.test(chipText)) {
    return {
      ok: false,
      reason: 'attachments_not_ready',
      markerTxt,
      markerCsv,
      chipText,
      uploadDisabled: Boolean(document.querySelector('#upload-files')?.disabled),
      trayText: document.querySelector('#hai-attachment-tray')?.innerText?.trim() || '',
      innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth
    };
  }

  input.value = 'Baca dua lampiran. Balas hanya dua kode verifikasi dari file TXT dan CSV.';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const startedAt = Date.now();
  let assistantText = '';
  let ariaBusy = null;
  while (Date.now() - startedAt < 70000) {
    await wait(400);
    assistantText = [...document.querySelectorAll('.assistant-message-container')].at(-1)?.innerText?.trim() || '';
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null;
    if (ariaBusy === 'false' && assistantText.length > 4 && !document.querySelector('.assistant-message-container.is-streaming')) break;
  }

  const userText = [...document.querySelectorAll('.user-message-container')].at(-1)?.innerText?.trim() || '';
  const trayAfterSend = document.querySelector('#hai-attachment-tray')?.innerText?.trim() || '';
  const hasThinkLeak = /<\\/?think>|Sedang menyusun jawaban/i.test(assistantText);
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  const userHasBothFiles = /hai-multi-a\\.txt/i.test(userText) && /hai-multi-b\\.csv/i.test(userText);
  const assistantHasBothMarkers = assistantText.includes(markerTxt) && assistantText.includes(markerCsv);
  return {
    ok: Boolean(
      /hai-multi-a\\.txt/i.test(chipText) &&
      /hai-multi-b\\.csv/i.test(chipText) &&
      userHasBothFiles &&
      assistantHasBothMarkers &&
      trayAfterSend === '' &&
      ariaBusy === 'false' &&
      !hasThinkLeak &&
      scrollWidth <= innerWidth
    ),
    markerTxt,
    markerCsv,
    chipText,
    userText: userText.slice(0, 420),
    assistantSample: assistantText.slice(0, 520),
    trayAfterSend,
    userHasBothFiles,
    assistantHasBothMarkers,
    ariaBusy,
    hasThinkLeak,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


SOURCES_WEB_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  document.querySelector('#new-chat')?.click();
  await wait(450);
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  if (!input || !submit) {
    return { ok: false, reason: 'missing_composer', hasInput: Boolean(input), hasSubmit: Boolean(submit) };
  }

  input.value = '@s https://hai.harmonika.id/healthz jelaskan singkat status service ini';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const startedAt = Date.now();
  let assistantText = '';
  let ariaBusy = null;
  let chips = [];
  let stackLinks = [];
  while (Date.now() - startedAt < 110000) {
    await wait(500);
    const assistant = [...document.querySelectorAll('.assistant-message-container')].at(-1);
    assistantText = assistant?.innerText?.trim() || '';
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || null;
    chips = [...(assistant?.querySelectorAll('.hai-source-chip, .hai-source-count, .hai-source-stack-link') || [])];
    stackLinks = [...(assistant?.querySelectorAll('.hai-source-stack-link') || [])];
    if (ariaBusy === 'false' && assistantText.length > 10 && chips.length > 0 && !document.querySelector('.assistant-message-container.is-streaming')) break;
  }

  const assistant = [...document.querySelectorAll('.assistant-message-container')].at(-1);
  const sourceWrap = assistant?.querySelector('.hai-source-chips') || null;
  const sourceText = sourceWrap?.innerText?.trim() || '';
  const sourceCountButton = sourceWrap?.querySelector('.hai-source-count') || null;
  sourceCountButton?.click();
  await wait(250);
  const detailsOpen = Boolean(sourceWrap?.classList.contains('is-expanded') || sourceWrap?.querySelector('.hai-source-details:not([hidden])'));
  const sourceDetailText = sourceWrap?.querySelector('.hai-source-details')?.innerText?.trim() || '';
  const hasImageArtifact = Boolean(assistant?.querySelector('.hai-member-image-artifact, .hai-legacy-image, .hai-image-artifact, figure'));
  const hasThinkLeak = /<\\/?think>|Sedang menyusun jawaban/i.test(assistantText);
  const assistantHasFullUrl = /https?:\\/\\//i.test(assistantText);
  const sourceUiHasFullUrl = /https?:\\/\\//i.test(sourceText);
  const hasImageClaim = /sudah\\s+(buat|membuat)|preview gambar|download/i.test(assistantText);
  const hasSourceVisual = Boolean(sourceWrap && (chips.length > 0 || stackLinks.length > 0));
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  return {
    ok: Boolean(
      assistantText.length > 10 &&
      ariaBusy === 'false' &&
      hasSourceVisual &&
      !sourceUiHasFullUrl &&
      !hasImageArtifact &&
      !hasImageClaim &&
      !hasThinkLeak &&
      scrollWidth <= innerWidth
    ),
    assistantSample: assistantText.slice(0, 320),
    sourceText: sourceText.slice(0, 320),
    sourceDetailText: sourceDetailText.slice(0, 420),
    chipsCount: chips.length,
    stackLinksCount: stackLinks.length,
    detailsOpen,
    hasImageArtifact,
    hasImageClaim,
    assistantHasFullUrl,
    sourceUiHasFullUrl,
    ariaBusy,
    hasThinkLeak,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


SOURCES_STACK_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  document.querySelector('#new-chat')?.click();
  await wait(300);
  const chatMessages = document.querySelector('#chat-messages');
  if (!chatMessages || typeof appendSourceChips !== 'function') {
    return {
      ok: false,
      reason: 'missing_chat_or_source_renderer',
      hasChatMessages: Boolean(chatMessages),
      hasAppendSourceChips: typeof appendSourceChips === 'function'
    };
  }

  const welcome = document.querySelector('#welcome-screen');
  if (welcome) welcome.style.display = 'none';
  chatMessages.innerHTML = '';
  chatMessages.setAttribute('aria-busy', 'false');
  document.body.classList.remove('hai-chat-empty');
  document.body.classList.add('hai-chat-active');

  const assistant = document.createElement('div');
  assistant.className = 'assistant-message-container';
  const message = document.createElement('div');
  message.className = 'assistant-message';
  message.innerHTML = '<p>Ringkasan singkat sudah dibuat. Referensi tampil ringkas di bawah tanpa membuka URL panjang di chat.</p>';
  assistant.appendChild(message);
  chatMessages.appendChild(assistant);

  const sources = [
    {
      title: 'Dokumentasi Harmonika AI',
      url: 'https://hai.harmonika.id/docs',
      domain: 'hai.harmonika.id',
      snippet: 'Status, kemampuan, dan dokumentasi internal Harmonika AI.'
    },
    {
      title: 'OpenAI Platform Docs',
      url: 'https://platform.openai.com/docs',
      domain: 'platform.openai.com',
      snippet: 'Referensi API, streaming, dan pola integrasi AI.'
    },
    {
      title: 'MDN Server-Sent Events',
      url: 'https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events',
      domain: 'developer.mozilla.org',
      snippet: 'Dokumentasi browser untuk event stream satu arah.'
    },
    {
      title: 'Flask Documentation',
      url: 'https://flask.palletsprojects.com/',
      domain: 'flask.palletsprojects.com',
      snippet: 'Dokumentasi framework backend Python.'
    }
  ];
  appendSourceChips(assistant, sources);
  await wait(450);

  const sourceWrap = assistant.querySelector('.hai-source-chips');
  const stack = assistant.querySelector('.hai-source-stack');
  const stackLinks = [...assistant.querySelectorAll('.hai-source-stack-link')];
  const icons = [...assistant.querySelectorAll('.hai-source-icon.is-stacked')];
  const count = assistant.querySelector('.hai-source-count');
  const detailPanel = assistant.querySelector('.hai-source-details');
  const sourceTextBefore = sourceWrap?.innerText?.trim() || '';
  const stackRect = stack?.getBoundingClientRect();
  const linkRects = stackLinks.map((link) => link.getBoundingClientRect());
  const iconRects = icons.map((icon) => icon.getBoundingClientRect());
  const sourceIconStates = icons.map((icon) => {
    const img = icon.querySelector('img');
    return {
      text: (icon.textContent || '').trim(),
      hasLoadedImage: Boolean(img && img.complete && img.naturalWidth > 0 && img.naturalHeight > 0),
      className: icon.className
    };
  });
  const noEmptySourceIcons = sourceIconStates.every((state) => Boolean(state.text) || state.hasLoadedImage);
  const hasOverlappingStack = linkRects.length > 2 && linkRects.some((rect, index) => {
    const next = linkRects[index + 1];
    return next ? rect.right > next.left : false;
  });
  const compactStackWidth = Boolean(stackRect && stackRect.width <= 70);
  const countAriaBefore = count?.getAttribute('aria-expanded') || '';
  const countControls = count?.getAttribute('aria-controls') || '';
  const controlsPanel = Boolean(countControls && document.getElementById(countControls) === detailPanel);
  count?.focus();
  await wait(80);
  const countFocusStyle = count ? getComputedStyle(count) : null;
  const countFocusVisible = Boolean(countFocusStyle && countFocusStyle.outlineStyle !== 'none' && Number.parseFloat(countFocusStyle.outlineWidth || '0') >= 1);

  count?.click();
  await wait(450);
  const detailsOpen = Boolean(sourceWrap?.classList.contains('is-expanded') && detailPanel && !detailPanel.hidden);
  const countAriaAfter = count?.getAttribute('aria-expanded') || '';
  const detailItems = [...(detailPanel?.querySelectorAll('.hai-source-detail-item') || [])];
  const detailItemMetrics = detailItems.map((item) => {
    const rect = item.getBoundingClientRect();
    const style = getComputedStyle(item);
    return {
      height: rect.height,
      tag: item.tagName.toLowerCase(),
      target: item.getAttribute('target') || '',
      rel: item.getAttribute('rel') || '',
      ariaLabel: item.getAttribute('aria-label') || '',
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth
    };
  });
  const detailsTapTargetsOk = detailItemMetrics.every((item) => item.height >= 44);
  const detailLinksSafe = detailItems.every((item) => {
    if (item.tagName.toLowerCase() !== 'a') return true;
    const rel = item.getAttribute('rel') || '';
    return item.getAttribute('target') === '_blank' && rel.includes('noopener') && rel.includes('noreferrer') && Boolean(item.getAttribute('aria-label'));
  });
  detailItems[0]?.focus();
  await wait(80);
  const firstDetailFocusStyle = detailItems[0] ? getComputedStyle(detailItems[0]) : null;
  const firstDetailFocusVisible = Boolean(firstDetailFocusStyle && firstDetailFocusStyle.outlineStyle !== 'none' && Number.parseFloat(firstDetailFocusStyle.outlineWidth || '0') >= 1);
  const sourceTextAfter = sourceWrap?.innerText?.trim() || '';
  const detailsText = detailPanel?.innerText?.trim() || '';
  const assistantText = assistant.innerText.trim();
  const visibleText = sourceTextAfter || sourceTextBefore;
  const hasFullUrlInSources = /https?:\\/\\//i.test(visibleText);
  const detailsHaveSnippets = /Status, kemampuan/i.test(detailsText) && /event stream/i.test(detailsText);
  const countLabelOk = /4\\s+sumber|Tutup sumber/i.test(visibleText);
  const iconSizeOk = iconRects.every((rect) => rect.width >= 18 && rect.height >= 18 && rect.width <= 30 && rect.height <= 30);
  const detailBounds = detailPanel?.getBoundingClientRect();
  const detailWithinViewport = !detailBounds || (detailBounds.left >= -1 && detailBounds.right <= innerWidth + 1);
  const stackHasNoFullUrlAttributesVisible = stackLinks.every((link) => Boolean(link.getAttribute('aria-label')) && !/https?:\\/\\//i.test(link.textContent || ''));
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  return {
    ok: Boolean(
      sourceWrap &&
      sourceWrap.classList.contains('is-compact-stack') &&
      stackLinks.length === 4 &&
      icons.length === 4 &&
      count &&
      hasOverlappingStack &&
      compactStackWidth &&
      iconSizeOk &&
      noEmptySourceIcons &&
      countAriaBefore === 'false' &&
      countAriaAfter === 'true' &&
      controlsPanel &&
      countFocusVisible &&
      detailsTapTargetsOk &&
      detailLinksSafe &&
      firstDetailFocusVisible &&
      countLabelOk &&
      detailsOpen &&
      detailsHaveSnippets &&
      stackHasNoFullUrlAttributesVisible &&
      !hasFullUrlInSources &&
      detailWithinViewport &&
      scrollWidth <= innerWidth
    ),
    assistantSample: assistantText.slice(0, 280),
    sourceTextBefore: sourceTextBefore.slice(0, 320),
    sourceTextAfter: sourceTextAfter.slice(0, 420),
    detailsText: detailsText.slice(0, 520),
    stackLinksCount: stackLinks.length,
    iconCount: icons.length,
    sourceIconStates,
    noEmptySourceIcons,
    countAriaBefore,
    countAriaAfter,
    countControls,
    controlsPanel,
    countFocusVisible,
    detailsTapTargetsOk,
    detailLinksSafe,
    firstDetailFocusVisible,
    detailItemMetrics,
    hasOverlappingStack,
    compactStackWidth,
    stackWidth: stackRect?.width || 0,
    iconSizes: iconRects.map((rect) => ({ width: rect.width, height: rect.height })),
    detailsOpen,
    detailsHaveSnippets,
    hasFullUrlInSources,
    detailWithinViewport,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


A11Y_SMOKE_FLOW_JS = """
(() => {
  const isVisible = (element) => {
    if (!element || element.hidden || element.getAttribute('aria-hidden') === 'true') return false;
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const accessibleName = (element) => {
    const aria = element.getAttribute('aria-label') || element.getAttribute('aria-labelledby');
    const title = element.getAttribute('title');
    const text = element.innerText || element.value || element.placeholder || '';
    const imgAlt = [...element.querySelectorAll('img[alt]')].map(img => img.getAttribute('alt')).join(' ');
    return `${aria || ''} ${title || ''} ${text || ''} ${imgAlt || ''}`.replace(/\\s+/g, ' ').trim();
  };
  const visibleControls = [...document.querySelectorAll('button,a[href],input,textarea,select,[role="button"],[tabindex]:not([tabindex="-1"])')]
    .filter(isVisible);
  const missingNames = visibleControls
    .filter(element => !accessibleName(element))
    .map(element => ({
      tag: element.tagName.toLowerCase(),
      id: element.id || '',
      className: String(element.className || '').slice(0, 80)
    }));
  const ids = [...document.querySelectorAll('[id]')].map(element => element.id).filter(Boolean);
  const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
  const clickableDivs = [...document.querySelectorAll('div[onclick],span[onclick]')].filter(isVisible);
  const nonKeyboardClickables = clickableDivs
    .filter(element => element.getAttribute('role') !== 'button' || !element.hasAttribute('tabindex'))
    .map(element => ({
      tag: element.tagName.toLowerCase(),
      id: element.id || '',
      className: String(element.className || '').slice(0, 80)
    }));
  const chatMessages = document.querySelector('#chat-messages');
  const userInput = document.querySelector('#user-input');
  const composer = document.querySelector('form[aria-label]');
  if (typeof window.showToast === 'function') {
    window.showToast('Aksesibilitas toast sukses', 'success');
  }
  const toast = document.querySelector('.toast');
  const composerHeightValue = getComputedStyle(document.documentElement).getPropertyValue('--hai-composer-height').trim();
  const composerHeightPx = Number((composerHeightValue.match(/[0-9.]+/) || [0])[0]);
  const toastRoleOk = Boolean(
    toast &&
    toast.classList.contains('success') &&
    toast.getAttribute('role') === 'status' &&
    toast.getAttribute('aria-live') === 'polite' &&
    toast.getAttribute('aria-atomic') === 'true' &&
    toast.querySelector('.toast-icon')?.classList.contains('fa-check-circle')
  );
  const reducedMotion = [...document.styleSheets].some(sheet => {
    try {
      return [...sheet.cssRules].some(rule => String(rule.cssText || '').includes('prefers-reduced-motion'));
    } catch (_) {
      return false;
    }
  });
  const liveRegions = [...document.querySelectorAll('[aria-live]')].filter(isVisible).length;
  const focusableCount = visibleControls.filter(element => !element.disabled).length;
  return {
    ok: Boolean(
      document.documentElement.lang &&
      document.documentElement.lang.toLowerCase().startsWith('id') &&
      duplicateIds.length === 0 &&
      missingNames.length === 0 &&
      nonKeyboardClickables.length === 0 &&
      chatMessages?.getAttribute('role') === 'log' &&
      chatMessages?.getAttribute('aria-live') === 'polite' &&
      chatMessages?.getAttribute('aria-busy') === 'false' &&
      Boolean(userInput?.getAttribute('aria-label')) &&
      Boolean(composer) &&
      composerHeightPx >= 72 &&
      toastRoleOk &&
      reducedMotion &&
      liveRegions >= 2 &&
      focusableCount >= 3
    ),
    lang: document.documentElement.lang || '',
    duplicateIds,
    missingNames,
    nonKeyboardClickables,
    chatRole: chatMessages?.getAttribute('role') || '',
    chatLive: chatMessages?.getAttribute('aria-live') || '',
    chatBusy: chatMessages?.getAttribute('aria-busy') || '',
    inputLabel: userInput?.getAttribute('aria-label') || '',
    hasComposerLabel: Boolean(composer),
    composerHeightValue,
    composerHeightPx,
    toastRoleOk,
    toastRole: toast?.getAttribute('role') || '',
    toastLive: toast?.getAttribute('aria-live') || '',
    toastIcon: toast?.querySelector('.toast-icon')?.className || '',
    reducedMotion,
    liveRegions,
    visibleControls: visibleControls.length,
    focusableCount,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth
  };
})()
"""


STREAMING_STATES_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      return new Promise((resolve, reject) => {
        const signal = init?.signal;
        if (signal?.aborted) {
          reject(new DOMException('Aborted', 'AbortError'));
          return;
        }
        signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
      });
    }
    return originalFetch(input, init);
  };

  const sendPromptAndInspect = async (prompt) => {
    document.querySelector('#new-chat')?.click();
    await wait(450);
    const input = document.querySelector('#user-input');
    const submit = document.querySelector('#submit-button');
    if (!input || !submit) return { ok: false, reason: 'missing_composer' };
    input.value = prompt;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    submit.click();
    await wait(450);
    const container = [...document.querySelectorAll('.assistant-message-container')].at(-1);
    const message = container?.querySelector('.assistant-message');
    const status = document.querySelector('#hai-status');
    const connectionPill = document.querySelector('#hai-connection-pill');
    const imageCard = container?.querySelector('.hai-image-generating');
    const livebar = container?.querySelector(':scope > .hai-stream-livebar');
    const stepCount = container?.querySelectorAll('.hai-image-steps li').length || 0;
    const typing = message?.querySelector('.hai-typing');
    const robot = typing?.querySelector('.hai-typing-robot');
    const robotFace = typing?.querySelector('.hai-robot-face');
    const robotImg = typing?.querySelector('.hai-typing-robot-img');
    const typingDotCount = typing?.querySelectorAll('.hai-typing-dots i').length || 0;
    const imageOrb = imageCard?.querySelector('.hai-image-preview-orb');
    const imageScan = imageCard?.querySelector('.hai-image-preview-scan');
    const imageProgress = imageCard?.querySelector('.hai-image-progressbar span');
    const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
    const streamBadge = container ? getComputedStyle(container, '::after').content.replace(/^["']|["']$/g, '') : '';
    const state = {
      ok: Boolean(container && submit.classList.contains('is-stop') && document.querySelector('#chat-messages')?.getAttribute('aria-busy') === 'true'),
      intent: container?.dataset?.intent || '',
      streamPhase: container?.dataset?.streamPhase || '',
      isStreaming: Boolean(container?.classList.contains('is-streaming')),
      isThinking: Boolean(container?.classList.contains('is-thinking')),
      isWriting: Boolean(container?.classList.contains('is-writing')),
      isImageStreaming: Boolean(container?.classList.contains('is-image-streaming')),
      hasTyping: Boolean(typing),
      assistantMessageEmpty: Boolean(message && !message.textContent.trim() && !message.children.length),
      hasLivebar: Boolean(livebar),
      livebarTone: livebar?.dataset?.tone || '',
      livebarPhase: livebar?.dataset?.phase || '',
      livebarText: livebar?.textContent?.trim() || '',
      livebarIconSrc: livebar?.querySelector('.hai-stream-livebar-icon img')?.getAttribute('src') || '',
      livebarDotCount: livebar?.querySelectorAll('.hai-stream-livebar-dots i').length || 0,
      hasRobot: Boolean(robot),
      hasRobotFace: Boolean(robotFace),
      hasRobotImg: Boolean(robotImg),
      robotImgSrc: robotImg?.getAttribute('src') || '',
      typingDotCount,
      typingText: typing?.textContent?.trim() || '',
      hasImageCard: Boolean(imageCard),
      hasImageOrb: Boolean(imageOrb),
      hasImageScan: Boolean(imageScan),
      hasImageProgress: Boolean(imageProgress),
      imageStepCount: stepCount,
      submitIsStop: Boolean(submit.classList.contains('is-stop')),
      submitIsQueue: Boolean(submit.classList.contains('is-queue')),
      statusText: status?.textContent?.trim() || '',
      statusIsImage: Boolean(status?.classList.contains('is-image')),
      connectionPillHidden: !connectionPill,
      connectionState: connectionPill?.dataset?.state || '',
      connectionText: connectionPill?.textContent?.trim() || '',
      streamBadge,
      ariaBusy: document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '',
      horizontalOverflow: scrollWidth > innerWidth
    };
    const firstTokenProbe = (() => {
      if (!container || typeof window.markAssistantFirstVisibleChunk !== 'function') {
        return { ok: false, reason: 'missing_helper' };
      }
      window.markAssistantFirstVisibleChunk(container, state.intent || 'text', {
        status: state.intent === 'image' ? 'imageDesigning' : 'textWriting',
        progressStep: 2
      });
      const nextBadge = getComputedStyle(container, '::after').content.replace(/^["']|["']$/g, '');
      return {
        ok: Boolean(
          (state.intent === 'image' && container.dataset.streamPhase === 'image-rendering' && container.classList.contains('is-rendering') && /mendesain gambar/i.test(nextBadge)) ||
          (state.intent !== 'image' && container.dataset.streamPhase === 'writing' && container.classList.contains('is-writing') && /mengetik jawaban/i.test(status?.textContent?.trim() || ''))
        ),
        streamPhase: container.dataset.streamPhase || '',
        isWriting: Boolean(container.classList.contains('is-writing')),
        isRendering: Boolean(container.classList.contains('is-rendering')),
        streamBadge: nextBadge,
        statusText: status?.textContent?.trim() || ''
      };
    })();
    state.firstTokenProbe = firstTokenProbe;
    if (state.intent !== 'image') {
      submit.click();
      await wait(250);
    }
    return state;
  };

  const textState = await sendPromptAndInspect('streaming qa teks normal jawab pelan');
  const imageState = await sendPromptAndInspect('Buatkan gambar ikon robot lucu sederhana');
  window.fetch = originalFetch;

  const ok = Boolean(
    textState.ok &&
    textState.intent === 'text' &&
    textState.isStreaming &&
    !textState.isImageStreaming &&
    !textState.hasTyping &&
    !textState.hasRobot &&
    textState.assistantMessageEmpty &&
    textState.hasLivebar &&
    textState.livebarTone === 'text' &&
    /menyiapkan jawaban|sedang berpikir|sedang mengetik|diketik realtime/i.test(textState.livebarText) &&
    /robot-typing\.svg/i.test(textState.livebarIconSrc) &&
    textState.livebarDotCount === 3 &&
    textState.streamPhase === 'thinking' &&
    /memikirkan/i.test(textState.streamBadge) &&
    textState.firstTokenProbe?.ok &&
    /mengetik jawaban/i.test(textState.firstTokenProbe?.statusText || '') &&
    textState.isThinking &&
    !textState.hasImageCard &&
    textState.submitIsStop &&
    textState.connectionPillHidden &&
    textState.ariaBusy === 'true' &&
    !textState.horizontalOverflow &&
    imageState.ok &&
    imageState.intent === 'image' &&
    imageState.isStreaming &&
    imageState.isImageStreaming &&
    imageState.hasLivebar &&
    imageState.livebarTone === 'image' &&
    /menyiapkan gambar|desain gambar|dirender/i.test(imageState.livebarText) &&
    /image-rendering\.svg/i.test(imageState.livebarIconSrc) &&
    imageState.livebarDotCount === 3 &&
    imageState.streamPhase === 'image-preparing' &&
    /mendesain gambar/i.test(imageState.streamBadge) &&
    imageState.firstTokenProbe?.ok &&
    imageState.firstTokenProbe?.streamPhase === 'image-rendering' &&
    imageState.hasImageCard &&
    imageState.hasImageOrb &&
    imageState.hasImageScan &&
    imageState.hasImageProgress &&
    imageState.imageStepCount >= 4 &&
    !imageState.hasTyping &&
    imageState.submitIsStop &&
    imageState.statusIsImage &&
    imageState.connectionPillHidden &&
    imageState.ariaBusy === 'true' &&
    !imageState.horizontalOverflow
  );

  return { ok, textState, imageState, innerWidth };
})()
"""


STREAM_STALL_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      const encoder = new TextEncoder();
      let pingTimer = null;
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('Jawaban stall QA sudah lengkap dalam satu kalimat.'));
          pingTimer = setInterval(() => {
            try {
              controller.enqueue(encoder.encode('\\n: hai-ping\\n\\n'));
            } catch (_) {}
          }, 350);
        },
        cancel() {
          if (pingTimer) clearInterval(pingTimer);
        }
      });
      init?.signal?.addEventListener('abort', () => {
        if (pingTimer) clearInterval(pingTimer);
      }, { once: true });
      return Promise.resolve(new Response(stream, {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream; charset=utf-8',
          'X-HAI-Intent': 'text'
        }
      }));
    }
    return originalFetch(input, init);
  };

  document.querySelector('#new-chat')?.click();
  await wait(450);
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  if (!input || !submit) return { ok: false, reason: 'missing_composer' };
  input.value = 'stream stall qa';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const started = Date.now();
  let assistantText = '';
  let ariaBusy = '';
  let isStreaming = true;
  while (Date.now() - started < 32000) {
    await wait(500);
    const container = [...document.querySelectorAll('.assistant-message-container')].at(-1);
    assistantText = container?.innerText?.trim() || '';
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '';
    isStreaming = Boolean(container?.classList.contains('is-streaming'));
    if (/Jawaban stall QA/i.test(assistantText) && ariaBusy === 'false' && !isStreaming) break;
  }
  const actions = [...document.querySelectorAll('.assistant-message-container .message-buttons button')]
    .filter((button) => getComputedStyle(button).display !== 'none' && getComputedStyle(button).visibility !== 'hidden')
    .map((button) => button.getAttribute('aria-label') || button.title || button.className);
  let allChats = Object.values(JSON.parse(localStorage.getItem('conversations') || '{}'));
  if (window.db?.conversations?.toArray) {
    try {
      allChats = await window.db.conversations.toArray();
    } catch (_) {}
  }
  const latestAssistant = allChats
    .flatMap((chat) => Array.isArray(chat?.messages) ? chat.messages : [])
    .reverse()
    .find((message) => message?.role === 'assistant' && /Jawaban stall QA/i.test(JSON.stringify(message))) || {};
  const historyContainsAssistant = Boolean(latestAssistant.role === 'assistant');
  window.fetch = originalFetch;
  return {
    ok: Boolean(/Jawaban stall QA/i.test(assistantText) && ariaBusy === 'false' && !isStreaming && actions.includes('Salin pesan')),
    assistantText,
    ariaBusy,
    isStreaming,
    actions,
    historyContainsAssistant,
    finalizedByClient: latestAssistant.finalizedByClient === true,
    elapsedMs: Date.now() - started,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth
  };
})()
"""

EMPTY_STREAM_FALLBACK_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      const stream = new ReadableStream({
        start(controller) {
          controller.close();
        }
      });
      return Promise.resolve(new Response(stream, {
        status: 200,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'X-HAI-Intent': 'text'
        }
      }));
    }
    return originalFetch(input, init);
  };

  document.querySelector('#new-chat')?.click();
  await wait(450);
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  if (!input || !submit) return { ok: false, reason: 'missing_composer' };
  input.value = 'qa empty stream fallback';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const started = Date.now();
  let assistantText = '';
  let ariaBusy = '';
  let isStreaming = true;
  while (Date.now() - started < 9000) {
    await wait(160);
    const container = [...document.querySelectorAll('.assistant-message-container')].at(-1);
    assistantText = container?.innerText?.trim() || '';
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '';
    isStreaming = Boolean(container?.classList.contains('is-streaming'));
    if (ariaBusy === 'false' && !isStreaming && assistantText) break;
  }
  await wait(250);
  const container = [...document.querySelectorAll('.assistant-message-container')].at(-1);
  const message = container?.querySelector('.assistant-message') || null;
  const finalText = message?.innerText?.trim() || assistantText;
  const actions = [...container?.querySelectorAll?.('.message-buttons button') || []]
    .filter((button) => getComputedStyle(button).display !== 'none' && getComputedStyle(button).visibility !== 'hidden')
    .map((button) => button.getAttribute('aria-label') || button.title || button.className);
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  window.fetch = originalFetch;
  return {
    ok: Boolean(
      container &&
      message &&
      finalText.includes('Maaf, jawaban kosong') &&
      actions.includes('Buat ulang jawaban') &&
      ariaBusy === 'false' &&
      !isStreaming &&
      !message.hasAttribute('data-loading') &&
      scrollWidth <= innerWidth
    ),
    finalText,
    actions,
    ariaBusy,
    isStreaming,
    messageLoading: message?.getAttribute('data-loading') || '',
    containerClass: container?.className || '',
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""

REALTIME_RESUME_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  let replayCalled = false;
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('Jawaban awal yang putus. '));
          setTimeout(() => controller.error(new Error('QA simulated stream disconnect')), 120);
        }
      });
      return Promise.resolve(new Response(stream, {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream; charset=utf-8',
          'X-HAI-Intent': 'text',
          'X-HAI-Response-ID': 'resp_qa_realtime_resume'
        }
      }));
    }
    if (url.includes('/api/realtime/events')) {
      replayCalled = true;
      return Promise.resolve(new Response(JSON.stringify({
        ok: true,
        response_id: 'resp_qa_realtime_resume',
        status: 'completed',
        count: 3,
        events: [
          { type: 'response.created', sequence: 1, data: {} },
          { type: 'response.output_text.delta', sequence: 2, data: { text: 'Jawaban berhasil dipulihkan dari realtime replay.' } },
          { type: 'response.completed', sequence: 3, data: {} }
        ]
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    return originalFetch(input, init);
  };

  document.querySelector('#new-chat')?.click();
  await wait(450);
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  if (!input || !submit) return { ok: false, reason: 'missing_composer' };
  input.value = 'QA realtime resume';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();
  await wait(2600);

  const assistant = document.querySelector('.assistant-message-container:last-of-type .assistant-message');
  const assistantText = assistant?.innerText || '';
  const ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '';
  const connectionPill = document.querySelector('#hai-connection-pill');
  const connectionState = connectionPill?.dataset?.state || '';
  const connectionText = connectionPill?.textContent?.trim() || '';
  const bodyText = document.body?.innerText || '';
  const ok = Boolean(
    replayCalled &&
    assistantText.includes('Jawaban berhasil dipulihkan dari realtime replay') &&
    !assistantText.includes('koneksi ke Harmonika AI terputus') &&
    !bodyText.includes('QA simulated stream disconnect') &&
    !connectionPill &&
    ariaBusy === 'false'
  );
  return {
    ok,
    replayCalled,
    assistantText,
    connectionPillHidden: !connectionPill,
    connectionState,
    connectionText,
    ariaBusy,
    horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth
  };
})()
"""


QUALITY_CLEANUP_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      const encoder = new TextEncoder();
      const raw = 'Router menghubungkan jaringan berbeda dan mengarahkan lalu lintas data antarafakat perangkat. Router menghubungkan jaringan berbeda dan mengarahkan lalu lintas data antarafakat perangkat.';
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode(raw));
          controller.close();
        }
      });
      return Promise.resolve(new Response(stream, {
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream; charset=utf-8',
          'X-HAI-Intent': 'text'
        }
      }));
    }
    return originalFetch(input, init);
  };

  document.querySelector('#new-chat')?.click();
  await wait(450);
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  if (!input || !submit) return { ok: false, reason: 'missing_composer' };
  input.value = 'quality cleanup qa';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();
  const started = Date.now();
  let assistantText = '';
  let ariaBusy = '';
  while (Date.now() - started < 10000) {
    await wait(250);
    const container = [...document.querySelectorAll('.assistant-message-container')].at(-1);
    assistantText = container?.innerText?.trim() || '';
    ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '';
    if (assistantText && ariaBusy === 'false' && !container?.classList.contains('is-streaming')) break;
  }
  window.fetch = originalFetch;
  const typoGone = !/antarafakat/i.test(assistantText);
  const duplicateGone = (assistantText.match(/Router menghubungkan/g) || []).length === 1;
  return {
    ok: Boolean(typoGone && duplicateGone && /antara perangkat/i.test(assistantText) && ariaBusy === 'false'),
    assistantText,
    typoGone,
    duplicateGone,
    ariaBusy,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > innerWidth
  };
})()
"""


QUEUE_COMPOSER_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  let chatCalls = 0;
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      chatCalls += 1;
      if (chatCalls === 1) {
        return new Promise((resolve, reject) => {
          const signal = init?.signal;
          if (signal?.aborted) {
            reject(new DOMException('Aborted', 'AbortError'));
            return;
          }
          signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
        });
      }
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('Pesan antrean terkirim dengan rapi.'));
          controller.close();
        }
      });
      return Promise.resolve(new Response(stream, {
        status: 200,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'X-HAI-Intent': 'text'
        }
      }));
    }
    if (url === '/generate-title' || url.endsWith('/generate-title')) {
      return Promise.resolve(new Response(JSON.stringify({ title: 'QA Queue Composer' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    return originalFetch(input, init);
  };

  try {
    document.querySelector('#new-chat')?.click();
    await wait(450);
    const input = document.querySelector('#user-input');
    const submit = document.querySelector('#submit-button');
    const form = document.querySelector('.bottom-panel form');
    const queueStatus = document.querySelector('#hai-queue-status');
    if (!input || !submit || !form || !queueStatus) {
      return { ok: false, reason: 'missing_composer_queue_nodes' };
    }

    input.value = 'queue qa pesan pertama dibuat menggantung';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    submit.click();

    const startedAt = Date.now();
    while (Date.now() - startedAt < 6000) {
      await wait(150);
      if (submit.classList.contains('is-stop') && document.querySelector('#chat-messages')?.getAttribute('aria-busy') === 'true') break;
    }
    const firstStreaming = Boolean(submit.classList.contains('is-stop') && document.querySelector('.assistant-message-container.is-streaming'));

    input.value = 'queue qa pesan kedua otomatis setelah stop';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    await wait(150);
    const queueReadyBeforeClick = Boolean(form.classList.contains('is-queue-ready') && submit.classList.contains('is-queue') && /antrean/i.test(submit.getAttribute('aria-label') || ''));
    submit.click();
    await wait(350);
    const queuedVisible = Boolean(queueStatus.classList.contains('is-visible') && /pesan kedua/i.test(queueStatus.textContent || ''));
    const inputClearedAfterQueue = input.value.trim() === '';
    const stopReadyAfterQueue = Boolean(submit.classList.contains('is-stop') && !submit.classList.contains('is-queue'));

    submit.click();

    const waitFinalStarted = Date.now();
    let finalText = '';
    let ariaBusy = '';
    while (Date.now() - waitFinalStarted < 12000) {
      await wait(250);
      const assistants = [...document.querySelectorAll('.assistant-message-container')];
      finalText = assistants.at(-1)?.innerText?.trim() || '';
      ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '';
      if (/Pesan antrean terkirim/i.test(finalText) && ariaBusy === 'false' && !document.querySelector('.assistant-message-container.is-streaming')) break;
    }

    const userTexts = [...document.querySelectorAll('.user-message-container')]
      .map(node => node.innerText.trim());
    const assistantTexts = [...document.querySelectorAll('.assistant-message-container')]
      .map(node => node.innerText.trim());
    const queueHiddenAfterFinal = !queueStatus.classList.contains('is-visible');
    const submitIdle = !submit.classList.contains('is-stop') && !submit.classList.contains('is-queue');
    const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
    const hasThinkLeak = assistantTexts.some(text => /<\\/?think>|Sedang menyusun jawaban/i.test(text));

    return {
      ok: Boolean(
        firstStreaming &&
        queueReadyBeforeClick &&
        queuedVisible &&
        inputClearedAfterQueue &&
        stopReadyAfterQueue &&
        userTexts.some(text => /pesan kedua otomatis/i.test(text)) &&
        /Pesan antrean terkirim/i.test(finalText) &&
        queueHiddenAfterFinal &&
        submitIdle &&
        ariaBusy === 'false' &&
        !hasThinkLeak &&
        scrollWidth <= innerWidth
      ),
      firstStreaming,
      queueReadyBeforeClick,
      queuedVisible,
      inputClearedAfterQueue,
      stopReadyAfterQueue,
      queueHiddenAfterFinal,
      submitIdle,
      chatCalls,
      userTexts,
      assistantTexts,
      finalText,
      ariaBusy,
      hasThinkLeak,
      innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      horizontalOverflow: scrollWidth > innerWidth
    };
  } finally {
    window.fetch = originalFetch;
  }
})()
"""


ERROR_RETRY_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  let chatCalls = 0;
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      chatCalls += 1;
      if (chatCalls === 1) {
        return Promise.resolve(new Response(JSON.stringify({
          message: 'Harmonika AI belum bisa menjawab. Kode: 502'
        }), {
          status: 502,
          headers: { 'Content-Type': 'application/json' }
        }));
      }
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('Retry berhasil menjawab singkat.'));
          controller.close();
        }
      });
      return Promise.resolve(new Response(stream, {
        status: 200,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'X-HAI-Intent': 'text'
        }
      }));
    }
    if (url === '/generate-title' || url.endsWith('/generate-title')) {
      return Promise.resolve(new Response(JSON.stringify({ title: 'QA Error Retry' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    return originalFetch(input, init);
  };

  try {
    document.querySelector('#new-chat')?.click();
    await wait(450);
    const input = document.querySelector('#user-input');
    const submit = document.querySelector('#submit-button');
    if (!input || !submit) return { ok: false, reason: 'missing_composer' };

    input.value = 'qa error retry pertama gagal lalu regenerate';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    submit.click();

    const errorStartedAt = Date.now();
    let errorContainer = null;
    let errorText = '';
    while (Date.now() - errorStartedAt < 8000) {
      await wait(200);
      errorContainer = [...document.querySelectorAll('.assistant-message-container')].at(-1);
      errorText = errorContainer?.innerText?.trim() || '';
      if (/502|belum bisa menjawab/i.test(errorText) && document.querySelector('#chat-messages')?.getAttribute('aria-busy') === 'false') break;
    }

    const regen = errorContainer?.querySelector('.message-regenerate-button');
    const hasErrorAction = Boolean(regen && getComputedStyle(regen).display !== 'none');
    const errorAssistantActions = [...(errorContainer?.querySelectorAll('.message-buttons button') || [])]
      .filter((button) => getComputedStyle(button).display !== 'none' && getComputedStyle(button).visibility !== 'hidden')
      .map((button) => button.getAttribute('aria-label') || button.title || button.className);
    regen?.click();

    const retryStartedAt = Date.now();
    let finalContainer = null;
    let finalText = '';
    let ariaBusy = '';
    while (Date.now() - retryStartedAt < 12000) {
      await wait(250);
      finalContainer = [...document.querySelectorAll('.assistant-message-container')].at(-1);
      finalText = finalContainer?.innerText?.trim() || '';
      ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '';
      if (/Retry berhasil/i.test(finalText) && ariaBusy === 'false' && !document.querySelector('.assistant-message-container.is-streaming')) break;
    }

    const visibleAssistantActions = [...document.querySelectorAll('.assistant-message-container .message-buttons button')]
      .filter((button) => getComputedStyle(button).display !== 'none' && getComputedStyle(button).visibility !== 'hidden')
      .map((button) => button.getAttribute('aria-label') || button.title || button.className);
    const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

    return {
      ok: Boolean(
        chatCalls === 2 &&
        /502|belum bisa menjawab/i.test(errorText) &&
        hasErrorAction &&
        errorAssistantActions.includes('Buat ulang jawaban') &&
        !errorAssistantActions.includes('Lanjutkan jawaban') &&
        !errorAssistantActions.includes('Edit pesan') &&
        /Retry berhasil menjawab singkat/i.test(finalText) &&
        ariaBusy === 'false' &&
        visibleAssistantActions.includes('Buat ulang jawaban') &&
        scrollWidth <= innerWidth
      ),
      chatCalls,
      errorText,
      hasErrorAction,
      errorAssistantActions,
      finalText,
      ariaBusy,
      visibleAssistantActions,
      innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      horizontalOverflow: scrollWidth > innerWidth
    };
  } finally {
    window.fetch = originalFetch;
  }
})()
"""


ERROR_HISTORY_HYGIENE_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  const originalConfirm = window.confirm;
  let chatCalls = 0;
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      chatCalls += 1;
      return Promise.resolve(new Response(JSON.stringify({
        message: 'Harmonika AI belum bisa menjawab. Kode: 502'
      }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    return originalFetch(input, init);
  };
  window.confirm = () => true;

  const sendErrorPrompt = async (text) => {
    const input = document.querySelector('#user-input');
    const submit = document.querySelector('#submit-button');
    input.value = text;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    submit.click();
    const startedAt = Date.now();
    let container = null;
    let textOut = '';
    while (Date.now() - startedAt < 8000) {
      await wait(200);
      container = [...document.querySelectorAll('.assistant-message-container')].at(-1);
      textOut = container?.innerText?.trim() || '';
      if (/Kode: 502/i.test(textOut) && document.querySelector('#chat-messages')?.getAttribute('aria-busy') === 'false') break;
    }
    return { container, textOut };
  };

  try {
    document.querySelector('#new-chat')?.click();
    await wait(450);
    if (!document.querySelector('#user-input') || !document.querySelector('#submit-button')) {
      return { ok: false, reason: 'missing_composer' };
    }

    const first = await sendErrorPrompt('qa error hygiene pesan pertama');
    const second = await sendErrorPrompt('qa error hygiene pesan kedua');
    const secondId = second.container?.dataset?.messageId || '';
    const secondActions = [...(second.container?.querySelectorAll('.message-buttons button') || [])]
      .map((button) => button.getAttribute('aria-label') || button.title || button.className);
    const deleteButton = second.container?.querySelector('.message-delete-button');
    deleteButton?.click();
    await wait(700);

    const beforeReload = {
      userCount: document.querySelectorAll('.user-message-container').length,
      assistantCount: document.querySelectorAll('.assistant-message-container').length,
      text: document.querySelector('#chat-messages')?.innerText || ''
    };

    const activeId = document.querySelector('#chat-history .conversation-item.active')?.id?.replace(/^conversation-/, '') || '';
    if (activeId && typeof loadConversation === 'function') {
      await loadConversation(activeId, false);
    }
    await wait(700);

    const afterReloadText = document.querySelector('#chat-messages')?.innerText || '';
    const errorContainers = [...document.querySelectorAll('.assistant-message-container')];
    const remainingErrorActions = [...(errorContainers.at(-1)?.querySelectorAll('.message-buttons button') || [])]
      .map((button) => button.getAttribute('aria-label') || button.title || button.className);
    const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

    return {
      ok: Boolean(
        chatCalls === 2 &&
        /qa error hygiene pesan pertama/i.test(afterReloadText) &&
        /qa error hygiene pesan kedua/i.test(afterReloadText) &&
        errorContainers.length === 1 &&
        document.querySelectorAll('.user-message-container').length === 2 &&
        secondId &&
        activeId &&
        secondActions.includes('Buat ulang jawaban') &&
        !secondActions.includes('Lanjutkan jawaban') &&
        remainingErrorActions.includes('Buat ulang jawaban') &&
        !remainingErrorActions.includes('Lanjutkan jawaban') &&
        scrollWidth <= innerWidth
      ),
      chatCalls,
      secondId,
      activeId,
      secondActions,
      beforeReload,
      afterReloadText: afterReloadText.slice(0, 500),
      userCount: document.querySelectorAll('.user-message-container').length,
      assistantCount: errorContainers.length,
      remainingErrorActions,
      innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      horizontalOverflow: scrollWidth > innerWidth
    };
  } finally {
    window.fetch = originalFetch;
    window.confirm = originalConfirm;
  }
})()
"""


EDIT_ERROR_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  let chatCalls = 0;
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      chatCalls += 1;
      if (chatCalls === 1) {
        const encoder = new TextEncoder();
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(encoder.encode('Jawaban awal untuk QA edit.'));
            controller.close();
          }
        });
        return Promise.resolve(new Response(stream, {
          status: 200,
          headers: { 'Content-Type': 'text/plain; charset=utf-8', 'X-HAI-Intent': 'text' }
        }));
      }
      return Promise.resolve(new Response(JSON.stringify({
        message: 'Harmonika AI belum bisa menjawab edit QA. Kode: 502'
      }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    if (url === '/generate-title' || url.endsWith('/generate-title')) {
      return Promise.resolve(new Response(JSON.stringify({ title: 'QA Edit Error' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    return originalFetch(input, init);
  };

  try {
    document.querySelector('#new-chat')?.click();
    await wait(450);
    const input = document.querySelector('#user-input');
    const submit = document.querySelector('#submit-button');
    if (!input || !submit) return { ok: false, reason: 'missing_composer' };

    input.value = 'qa edit error pesan awal';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    submit.click();
    const firstStartedAt = Date.now();
    while (Date.now() - firstStartedAt < 8000) {
      await wait(200);
      const text = [...document.querySelectorAll('.assistant-message-container')].at(-1)?.innerText || '';
      if (/Jawaban awal untuk QA edit/i.test(text) && document.querySelector('#chat-messages')?.getAttribute('aria-busy') === 'false') break;
    }

    const userEdit = document.querySelector('.user-message-container .message-edit-button');
    userEdit?.click();
    await wait(300);
    const editText = document.querySelector('.edit-textarea');
    const editSend = document.querySelector('.edit-send-button');
    if (!editText || !editSend) return { ok: false, reason: 'missing_edit_controls', chatCalls };
    const editControlLabels = [...document.querySelectorAll('.edit-buttons button')]
      .map((button) => ({
        text: button.textContent.trim(),
        aria: button.getAttribute('aria-label') || '',
        title: button.getAttribute('title') || ''
      }));
    editText.value = 'qa edit error pesan setelah diedit';
    editText.dispatchEvent(new Event('input', { bubbles: true }));
    editSend.click();

    const errorStartedAt = Date.now();
    let errorContainer = null;
    let errorText = '';
    let ariaBusy = '';
    while (Date.now() - errorStartedAt < 9000) {
      await wait(200);
      errorContainer = [...document.querySelectorAll('.assistant-message-container')].at(-1);
      errorText = errorContainer?.innerText?.trim() || '';
      ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '';
      if (/edit QA|Kode: 502|belum bisa menjawab/i.test(errorText) && ariaBusy === 'false') break;
    }
    const actions = [...(errorContainer?.querySelectorAll('.message-buttons button') || [])]
      .map((button) => button.getAttribute('aria-label') || button.title || button.className);
    const userText = [...document.querySelectorAll('.user-message-container')].at(-1)?.innerText || '';
    const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

    return {
      ok: Boolean(
        chatCalls === 2 &&
        /setelah diedit/i.test(userText) &&
        editControlLabels.some((item) => item.text === 'Simpan' && /Simpan perubahan pesan/i.test(item.aria)) &&
        editControlLabels.some((item) => item.text === 'Batal' && /Batal edit pesan/i.test(item.aria)) &&
        editControlLabels.some((item) => item.text === 'Kirim' && /Kirim ulang pesan/i.test(item.aria)) &&
        !editControlLabels.some((item) => /^(Save|Cancel|Send)$/i.test(item.text)) &&
        /edit QA|Kode: 502|belum bisa menjawab/i.test(errorText) &&
        ariaBusy === 'false' &&
        actions.includes('Buat ulang jawaban') &&
        !actions.includes('Lanjutkan jawaban') &&
        !actions.includes('Edit pesan') &&
        scrollWidth <= innerWidth
      ),
      chatCalls,
      editControlLabels,
      userText,
      errorText,
      actions,
      ariaBusy,
      innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      horizontalOverflow: scrollWidth > innerWidth
    };
  } finally {
    window.fetch = originalFetch;
  }
})()
"""


CONTINUE_ERROR_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  let chatCalls = 0;
  let continueCalls = 0;
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      chatCalls += 1;
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('Jawaban awal untuk QA continue.'));
          controller.close();
        }
      });
      return Promise.resolve(new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/plain; charset=utf-8', 'X-HAI-Intent': 'text' }
      }));
    }
    if (url === '/continue_generation' || url.endsWith('/continue_generation')) {
      continueCalls += 1;
      return Promise.resolve(new Response(JSON.stringify({
        message: 'Harmonika AI belum bisa melanjutkan QA. Kode: 503'
      }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    if (url === '/generate-title' || url.endsWith('/generate-title')) {
      return Promise.resolve(new Response(JSON.stringify({ title: 'QA Continue Error' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      }));
    }
    return originalFetch(input, init);
  };

  try {
    document.querySelector('#new-chat')?.click();
    await wait(450);
    const input = document.querySelector('#user-input');
    const submit = document.querySelector('#submit-button');
    if (!input || !submit) return { ok: false, reason: 'missing_composer' };

    input.value = 'qa continue error pesan awal';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    submit.click();
    const firstStartedAt = Date.now();
    let firstContainer = null;
    while (Date.now() - firstStartedAt < 8000) {
      await wait(200);
      firstContainer = [...document.querySelectorAll('.assistant-message-container')].at(-1);
      const text = firstContainer?.innerText || '';
      if (/Jawaban awal untuk QA continue/i.test(text) && document.querySelector('#chat-messages')?.getAttribute('aria-busy') === 'false') break;
    }
    const continueButton = firstContainer?.querySelector('.message-continue-button');
    if (!continueButton) return { ok: false, reason: 'missing_continue_button', chatCalls };
    continueButton.click();

    const errorStartedAt = Date.now();
    let errorContainer = null;
    let errorText = '';
    let ariaBusy = '';
    while (Date.now() - errorStartedAt < 9000) {
      await wait(200);
      errorContainer = [...document.querySelectorAll('.assistant-message-container')].at(-1);
      errorText = errorContainer?.innerText?.trim() || '';
      ariaBusy = document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '';
      if (/melanjutkan QA|Kode: 503|belum bisa melanjutkan/i.test(errorText) && ariaBusy === 'false') break;
    }
    const originalText = firstContainer?.innerText || '';
    const restoredOpacity = getComputedStyle(continueButton).opacity;
    const restoredPointer = getComputedStyle(continueButton).pointerEvents;
    const actions = [...(errorContainer?.querySelectorAll('.message-buttons button') || [])]
      .map((button) => button.getAttribute('aria-label') || button.title || button.className);
    const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);

    return {
      ok: Boolean(
        chatCalls === 1 &&
        continueCalls === 1 &&
        /Jawaban awal untuk QA continue/i.test(originalText) &&
        /melanjutkan QA|Kode: 503|belum bisa melanjutkan/i.test(errorText) &&
        ariaBusy === 'false' &&
        restoredOpacity === '1' &&
        restoredPointer !== 'none' &&
        actions.includes('Buat ulang jawaban') &&
        !actions.includes('Lanjutkan jawaban') &&
        scrollWidth <= innerWidth
      ),
      chatCalls,
      continueCalls,
      originalText,
      errorText,
      restoredOpacity,
      restoredPointer,
      actions,
      ariaBusy,
      innerWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      bodyScrollWidth: document.body.scrollWidth,
      horizontalOverflow: scrollWidth > innerWidth
    };
  } finally {
    window.fetch = originalFetch;
  }
})()
"""


COMPOSER_QUEUE_STATE_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = String(typeof input === 'string' ? input : (input?.url || ''));
    if (url === '/chat' || url.endsWith('/chat')) {
      return new Promise((resolve, reject) => {
        const signal = init?.signal;
        if (signal?.aborted) {
          reject(new DOMException('Aborted', 'AbortError'));
          return;
        }
        signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
      });
    }
    return originalFetch(input, init);
  };

  document.querySelector('#new-chat')?.click();
  await wait(450);
  const input = document.querySelector('#user-input');
  const submit = document.querySelector('#submit-button');
  const form = document.querySelector('.bottom-panel form');
  const queueStatus = document.querySelector('#hai-queue-status');
  const status = document.querySelector('#hai-status');
  if (!input || !submit || !form || !queueStatus) {
    return { ok: false, reason: 'missing_composer_queue_nodes' };
  }

  input.value = 'visual qa pesan pertama sedang dijawab';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  submit.click();

  const startedAt = Date.now();
  while (Date.now() - startedAt < 6000) {
    await wait(150);
    if (submit.classList.contains('is-stop') && document.querySelector('.assistant-message-container.is-streaming')) break;
  }

  input.value = 'visual qa pesan kedua masuk antrean';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  await wait(200);
  const queueReadyBeforeClick = Boolean(form.classList.contains('is-queue-ready') && submit.classList.contains('is-queue'));
  submit.click();
  await wait(450);

  const submitRect = submit.getBoundingClientRect();
  const submitStyle = getComputedStyle(submit);
  const submitIcon = submit.querySelector('i');
  const submitIconStyle = submitIcon ? getComputedStyle(submitIcon) : null;
  const parseRgb = (value) => {
    const match = String(value || '').match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/i);
    return match ? match.slice(1, 4).map(Number) : null;
  };
  const bgRgb = parseRgb(submitStyle.backgroundColor);
  const iconRgb = parseRgb(submitIconStyle?.color || '');
  const borderRgb = parseRgb(submitStyle.borderTopColor);
  const stopBackgroundIsNeutral = Boolean(
    bgRgb &&
    bgRgb[0] >= 240 &&
    bgRgb[1] >= 240 &&
    bgRgb[2] >= 240
  );
  const stopIconIsAttention = Boolean(
    iconRgb &&
    iconRgb[0] >= 170 &&
    iconRgb[1] <= 100 &&
    iconRgb[2] <= 100
  );
  const stopBorderVisible = Boolean(
    borderRgb &&
    submitStyle.borderTopStyle !== 'none' &&
    parseFloat(submitStyle.borderTopWidth || '0') >= 1 &&
    !(borderRgb[0] >= 248 && borderRgb[1] >= 248 && borderRgb[2] >= 248)
  );
  const stopVisualNeutral = Boolean(
    stopBackgroundIsNeutral &&
    stopIconIsAttention &&
    stopBorderVisible &&
    parseFloat(submitStyle.opacity || '1') >= 0.95 &&
    submitRect.width >= 34 &&
    submitRect.height >= 34
  );

  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  const assistantText = [...document.querySelectorAll('.assistant-message-container')].at(-1)?.innerText?.trim() || '';
  const userTexts = [...document.querySelectorAll('.user-message-container')].map(node => node.innerText.trim());
  const state = {
    ok: Boolean(
      queueReadyBeforeClick &&
      queueStatus.classList.contains('is-visible') &&
      /pesan kedua masuk antrean/i.test(queueStatus.textContent || '') &&
      submit.classList.contains('is-stop') &&
      !submit.classList.contains('is-queue') &&
      document.querySelector('#chat-messages')?.getAttribute('aria-busy') === 'true' &&
      document.querySelector('.assistant-message-container.is-streaming') &&
      stopVisualNeutral &&
      !/https?:\\/\\//i.test(assistantText) &&
      scrollWidth <= innerWidth
    ),
    queueReadyBeforeClick,
    queueVisible: Boolean(queueStatus.classList.contains('is-visible')),
    queueText: queueStatus.textContent || '',
    statusText: status?.textContent || '',
    submitIsStop: Boolean(submit.classList.contains('is-stop')),
    submitIsQueue: Boolean(submit.classList.contains('is-queue')),
    stopVisualNeutral,
    stopButtonBackground: submitStyle.backgroundColor,
    stopButtonBorderColor: submitStyle.borderTopColor,
    stopButtonIconColor: submitIconStyle?.color || '',
    stopButtonOpacity: submitStyle.opacity,
    stopButtonRect: {
      width: submitRect.width,
      height: submitRect.height
    },
    formIsQueueReady: Boolean(form.classList.contains('is-queue-ready')),
    inputValue: input.value,
    userTexts,
    assistantText,
    ariaBusy: document.querySelector('#chat-messages')?.getAttribute('aria-busy') || '',
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
  window.fetch = originalFetch;
  return state;
})()
"""


SIDEBAR_COLLAPSE_FLOW_JS = """
(async () => {
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const rectOf = (node) => {
    if (!node) return null;
    const box = node.getBoundingClientRect();
    return {
      left: box.left,
      top: box.top,
      right: box.right,
      bottom: box.bottom,
      width: box.width,
      height: box.height
    };
  };
  const intersects = (a, b) => Boolean(
    a && b &&
    a.right > b.left &&
    a.left < b.right &&
    a.bottom > b.top &&
    a.top < b.bottom
  );
  const closeBtn = document.querySelector('#close-sidebar');
  const source = document.querySelector('link[href*="styles"]');
  const assetMarker = source ? new URL(source.href, location.href).searchParams.get('v') : '';
  if (!document.body.classList.contains('hai-sidebar-collapsed') && closeBtn) {
    closeBtn.click();
  }
  for (let i = 0; i < 20; i += 1) {
    if (document.body.classList.contains('hai-sidebar-collapsed')) break;
    await wait(100);
  }
  await wait(250);
  const sidebarButtons = document.querySelector('.sidebar-buttons');
  const title = document.querySelector('.hai-top-title');
  const topPanel = document.querySelector('.top-panel');
  const buttonsStyle = sidebarButtons ? getComputedStyle(sidebarButtons) : null;
  const titleStyle = title ? getComputedStyle(title) : null;
  const buttonsRect = rectOf(sidebarButtons);
  const titleRect = rectOf(title);
  const topPanelRect = rectOf(topPanel);
  const icons = [...document.querySelectorAll('.sidebar-buttons img.icon-svg')].map((icon) => {
    const box = icon.getBoundingClientRect();
    return {
      src: icon.getAttribute('src') || '',
      complete: Boolean(icon.complete),
      naturalWidth: icon.naturalWidth || 0,
      naturalHeight: icon.naturalHeight || 0,
      width: box.width || 0,
      height: box.height || 0,
      paints: Boolean(icon.complete && icon.naturalWidth > 0 && icon.naturalHeight > 0 && box.width >= 16 && box.height >= 16)
    };
  });
  const visibleButtons = Boolean(
    sidebarButtons &&
    buttonsStyle &&
    buttonsStyle.display !== 'none' &&
    buttonsStyle.visibility !== 'hidden' &&
    Number(buttonsStyle.opacity || 1) > 0 &&
    buttonsRect &&
    buttonsRect.width >= 70 &&
    buttonsRect.height >= 30
  );
  const visibleTitle = Boolean(
    title &&
    titleStyle &&
    titleStyle.display !== 'none' &&
    titleStyle.visibility !== 'hidden' &&
    titleRect &&
    titleRect.width > 120 &&
    titleRect.height > 20
  );
  const overlap = intersects(buttonsRect, titleRect);
  const scrollWidth = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
  const iconPaintOk = Boolean(assetMarker) && icons.length >= 2 && icons.every((item) => item.paints && item.src.includes(`?v=${assetMarker}`));
  const collapsed = document.body.classList.contains('hai-sidebar-collapsed');
  const topPanelPadded = Boolean(
    topPanelRect &&
    buttonsRect &&
    titleRect &&
    titleRect.left >= buttonsRect.right + 8
  );
  const ok = Boolean(collapsed && visibleButtons && visibleTitle && !overlap && topPanelPadded && iconPaintOk && scrollWidth <= innerWidth);
  return {
    ok,
    url: location.href,
    bodyClass: document.body.className,
    assetMarker,
    collapsed,
    visibleButtons,
    visibleTitle,
    overlap,
    topPanelPadded,
    iconPaintOk,
    icons,
    buttonsRect,
    titleRect,
    topPanelRect,
    innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    horizontalOverflow: scrollWidth > innerWidth
  };
})()
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://hai.harmonika.id/")
    parser.add_argument("--viewport", choices=sorted(VIEWPORTS), default="mobile")
    parser.add_argument("--flow", choices=["empty", "new-chat", "chat-text", "image-artifact", "image-modal", "export-localization", "markdown-rich", "history-controls", "library-panel", "stop-stream", "regenerate", "attachment-chat", "attachment-preview-a11y", "attachment-image-chat", "attachment-multi-chat", "sources-web", "sources-stack", "a11y-smoke", "streaming-states", "stream-stall", "empty-stream-fallback", "realtime-resume", "quality-cleanup", "queue-composer", "composer-queue-state", "composer-keyboard", "layout-metrics", "error-retry", "error-history-hygiene", "edit-error", "continue-error", "sidebar-collapse"], default="empty")
    parser.add_argument("--screenshot", help="Optional output PNG path")
    parser.add_argument("--component-crops-dir", help="Optional directory for cropped component screenshots for supported flows.")
    parser.add_argument("--json-out", help="Optional path to write JSON summary. Stdout remains JSON-only too.")
    parser.add_argument("--port", type=int, default=0, help="CDP port. Default 0 picks a free local port.")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--mock-chat", action="store_true", help="Use deterministic mocked /chat stream for visual-only snapshots.")
    args = parser.parse_args()

    chrome = find_chrome()
    width, height, is_mobile = VIEWPORTS[args.viewport]
    port = args.port or find_free_port()
    profile = tempfile.mkdtemp(prefix=f"hai-browser-qa-{args.viewport}-")
    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            f"--remote-debugging-port={port}",
            args.url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    sock: socket.socket | None = None
    try:
        page = wait_for_page(port, args.timeout)
        sock = connect_ws(page["webSocketDebuggerUrl"])
        sock.settimeout(args.timeout + 50)
        cdp_call(sock, 1, "Emulation.setDeviceMetricsOverride", {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": is_mobile,
        })
        cdp_call(sock, 2, "Page.enable")
        time.sleep(0.5)
        readiness = cdp_eval_readiness(sock, 30, APP_READY_JS)
        if not readiness.get("ok"):
            summary = {
                "ok": False,
                "reason": "app_not_ready",
                "readiness": readiness,
            }
            if args.json_out:
                out_json = pathlib.Path(args.json_out)
                out_json.parent.mkdir(parents=True, exist_ok=True)
                out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 1
        if args.flow == "new-chat":
            expression = NEW_CHAT_FLOW_JS
        elif args.flow == "chat-text":
            expression = CHAT_TEXT_FLOW_JS
        elif args.flow == "image-artifact":
            expression = IMAGE_ARTIFACT_FLOW_JS
        elif args.flow == "image-modal":
            expression = IMAGE_MODAL_FLOW_JS
        elif args.flow == "export-localization":
            expression = EXPORT_LOCALIZATION_FLOW_JS
        elif args.flow == "markdown-rich":
            expression = MARKDOWN_RICH_FLOW_JS
        elif args.flow == "history-controls":
            expression = HISTORY_CONTROLS_FLOW_JS
        elif args.flow == "library-panel":
            expression = LIBRARY_PANEL_FLOW_JS
        elif args.flow == "stop-stream":
            expression = STOP_STREAM_FLOW_JS
        elif args.flow == "regenerate":
            expression = REGENERATE_FLOW_JS
        elif args.flow == "attachment-chat":
            expression = ATTACHMENT_CHAT_FLOW_JS
        elif args.flow == "attachment-preview-a11y":
            expression = ATTACHMENT_PREVIEW_A11Y_FLOW_JS
        elif args.flow == "attachment-image-chat":
            expression = ATTACHMENT_IMAGE_CHAT_FLOW_JS
        elif args.flow == "attachment-multi-chat":
            expression = ATTACHMENT_MULTI_CHAT_FLOW_JS
        elif args.flow == "sources-web":
            expression = SOURCES_WEB_FLOW_JS
        elif args.flow == "sources-stack":
            expression = SOURCES_STACK_FLOW_JS
        elif args.flow == "a11y-smoke":
            expression = A11Y_SMOKE_FLOW_JS
        elif args.flow == "streaming-states":
            expression = STREAMING_STATES_FLOW_JS
        elif args.flow == "stream-stall":
            expression = STREAM_STALL_FLOW_JS
        elif args.flow == "empty-stream-fallback":
            expression = EMPTY_STREAM_FALLBACK_FLOW_JS
        elif args.flow == "realtime-resume":
            expression = REALTIME_RESUME_FLOW_JS
        elif args.flow == "quality-cleanup":
            expression = QUALITY_CLEANUP_FLOW_JS
        elif args.flow == "queue-composer":
            expression = QUEUE_COMPOSER_FLOW_JS
        elif args.flow == "composer-queue-state":
            expression = COMPOSER_QUEUE_STATE_FLOW_JS
        elif args.flow == "composer-keyboard":
            expression = COMPOSER_KEYBOARD_FLOW_JS
        elif args.flow == "layout-metrics":
            expression = LAYOUT_METRICS_FLOW_JS
        elif args.flow == "error-retry":
            expression = ERROR_RETRY_FLOW_JS
        elif args.flow == "error-history-hygiene":
            expression = ERROR_HISTORY_HYGIENE_FLOW_JS
        elif args.flow == "edit-error":
            expression = EDIT_ERROR_FLOW_JS
        elif args.flow == "continue-error":
            expression = CONTINUE_ERROR_FLOW_JS
        elif args.flow == "sidebar-collapse":
            expression = SIDEBAR_COLLAPSE_FLOW_JS
        else:
            expression = BASELINE_METRICS_JS
        if args.mock_chat and args.flow == "chat-text":
            expression = with_mock_chat_stream(expression)
        metrics = cdp_eval(sock, 3, expression)
        screenshot_info = None
        if args.screenshot:
            shot = cdp_call(sock, 4, "Page.captureScreenshot", {
                "format": "png",
                "fromSurface": True,
                "captureBeyondViewport": False,
            })
            out = pathlib.Path(args.screenshot)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(base64.b64decode(shot["result"]["data"]))
            screenshot_info = {
                "path": str(out),
                "bytes": out.stat().st_size,
            }
        component_crops = []
        if args.component_crops_dir:
            component_crops = capture_component_crops(
                sock,
                args.viewport,
                args.flow,
                pathlib.Path(args.component_crops_dir),
            )
        summary = dict(metrics)
        summary["qa"] = {
            "url": args.url,
            "viewport": args.viewport,
            "flow": args.flow,
            "screenshot": screenshot_info,
            "component_crops": component_crops,
        }
        failed = bool(metrics.get("horizontalOverflow"))
        if args.flow == "empty" and "ok" in metrics:
            failed = failed or not metrics.get("ok")
        if args.flow != "empty":
            failed = failed or not metrics.get("ok")
        if args.component_crops_dir:
            failed = failed or any(not item.get("ok") for item in component_crops)
        summary["ok"] = bool(not failed)
        if args.json_out:
            out_json = pathlib.Path(args.json_out)
            out_json.parent.mkdir(parents=True, exist_ok=True)
            out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 1 if failed else 0
    finally:
        if sock:
            sock.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
