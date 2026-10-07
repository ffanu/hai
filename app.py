import asyncio
import base64
import hashlib
import hmac
import json
import math
import os
import queue
import re
import secrets
import socket
import tempfile
import threading
import zipfile
from collections import defaultdict, deque
import ipaddress
from xml.etree import ElementTree as ET
import aiohttp
import httpx
import openai
import fitz
import time
from contextlib import contextmanager
from io import BytesIO
from urllib.parse import quote, urljoin, urlparse
from xml.sax.saxutils import escape as xml_escape
from flask import Flask, render_template, request, jsonify, Response, make_response, g
from flask_cors import CORS
from lxml import html
from youtube_transcript_api import YouTubeTranscriptApi


# Initialize Flask app
app = Flask(__name__)
_configured_cors_origins = [
    origin.strip()
    for origin in os.getenv("HAI_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
if _configured_cors_origins:
    CORS(app, origins=_configured_cors_origins, supports_credentials=True)

_fallback_secret = "harmonika-hai-webui-secret"
_uses_default_flask_secret = not os.getenv("HAI_FLASK_SECRET")
app.secret_key = os.getenv("HAI_FLASK_SECRET", _fallback_secret)  # Set a secret key for session management
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("HAI_MAX_CONTENT_LENGTH", str(10 * 1024 * 1024)))

DATA_DIR = os.getenv("HAI_DATA_DIR", "/var/lib/harmonika-hai-web")
HISTORY_FILE = os.path.join(DATA_DIR, "chatwebui-history.json")
LIBRARY_FILE = os.path.join(DATA_DIR, "rag-library.json")
LOCAL_IMAGE_DIR = os.path.join(DATA_DIR, "generated-images")
LOCAL_IMAGE_ID_PREFIX = "local-svg-"
DEVICE_COOKIE = "__Host-hai_device"
DEVICE_SECRET = os.getenv("HAI_DEVICE_SECRET") or app.secret_key
_uses_derived_device_secret = not os.getenv("HAI_DEVICE_SECRET")
_flask_secret_configured = bool(os.getenv("HAI_FLASK_SECRET")) and len(os.getenv("HAI_FLASK_SECRET", "")) >= 32
_device_secret_configured = bool(os.getenv("HAI_DEVICE_SECRET")) and len(os.getenv("HAI_DEVICE_SECRET", "")) >= 32
HISTORY_MAX_BODY = int(os.getenv("HAI_HISTORY_MAX_BODY", str(4 * 1024 * 1024)))
HISTORY_MAX_DEVICES = int(os.getenv("HAI_HISTORY_MAX_DEVICES", "500"))
HISTORY_MAX_CHATS = int(os.getenv("HAI_HISTORY_MAX_CHATS", "200"))
HISTORY_MAX_MESSAGES = int(os.getenv("HAI_HISTORY_MAX_MESSAGES", "400"))
HISTORY_MAX_DELETED = int(os.getenv("HAI_HISTORY_MAX_DELETED", "400"))
HISTORY_MAX_TEXT = int(os.getenv("HAI_HISTORY_MAX_TEXT", str(200 * 1024)))
LIBRARY_MAX_DOCS_PER_DEVICE = int(os.getenv("HAI_LIBRARY_MAX_DOCS_PER_DEVICE", "50"))
LIBRARY_MAX_TEXT = int(os.getenv("HAI_LIBRARY_MAX_TEXT", str(200 * 1024)))
LIBRARY_SEARCH_LIMIT = int(os.getenv("HAI_LIBRARY_SEARCH_LIMIT", "8"))
LIBRARY_SNIPPET_CHARS = int(os.getenv("HAI_LIBRARY_SNIPPET_CHARS", "420"))
LIBRARY_FULL_CONTEXT_CHARS = int(os.getenv("HAI_LIBRARY_FULL_CONTEXT_CHARS", "6000"))
LIBRARY_GROUNDING_ENABLED = os.getenv("HAI_LIBRARY_GROUNDING_ENABLED", "1") != "0"
LIBRARY_GROUNDING_LIMIT = int(os.getenv("HAI_LIBRARY_GROUNDING_LIMIT", "3"))
LIBRARY_CHUNK_CHARS = int(os.getenv("HAI_LIBRARY_CHUNK_CHARS", "1200"))
LIBRARY_CHUNK_OVERLAP = int(os.getenv("HAI_LIBRARY_CHUNK_OVERLAP", "180"))
LIBRARY_VECTOR_DIMS = int(os.getenv("HAI_LIBRARY_VECTOR_DIMS", "96"))
LIBRARY_RETRIEVAL_MODE = "hybrid_vector_lexical_semantic_rerank"
LIBRARY_GROUNDING_MODE = "auto_toggle_server_side"
LIBRARY_CONTEXT_MODE = "snippet_or_full_context_server_side"
LIBRARY_INDEX_MODE = "private_hybrid_sparse_vector_chunk_index"
LIBRARY_RANKING_MODE = "hybrid_vector_bm25_coverage_rerank"
LIBRARY_SEMANTIC_EXPANSION_ENABLED = os.getenv("HAI_LIBRARY_SEMANTIC_EXPANSION_ENABLED", "1") != "0"
CHAT_MAX_BODY = int(os.getenv("HAI_CHAT_MAX_BODY", str(6 * 1024 * 1024)))
TITLE_MAX_BODY = int(os.getenv("HAI_TITLE_MAX_BODY", str(128 * 1024)))
MEMORY_CONTEXT_MAX_TEXT = int(os.getenv("HAI_MEMORY_CONTEXT_MAX_TEXT", "1600"))
RATE_LIMIT_CHAT = (int(os.getenv("HAI_RATE_CHAT_COUNT", "24")), int(os.getenv("HAI_RATE_CHAT_WINDOW", "60")))
RATE_LIMIT_TITLE = (int(os.getenv("HAI_RATE_TITLE_COUNT", "40")), int(os.getenv("HAI_RATE_TITLE_WINDOW", "60")))
RATE_LIMIT_HISTORY = (int(os.getenv("HAI_RATE_HISTORY_COUNT", "120")), int(os.getenv("HAI_RATE_HISTORY_WINDOW", "60")))
RATE_LIMIT_FILE = (int(os.getenv("HAI_RATE_FILE_COUNT", "120")), int(os.getenv("HAI_RATE_FILE_WINDOW", "60")))
RATE_LIMIT_LIBRARY = (int(os.getenv("HAI_RATE_LIBRARY_COUNT", "90")), int(os.getenv("HAI_RATE_LIBRARY_WINDOW", "60")))
RATE_LIMIT_IMAGE = (int(os.getenv("HAI_RATE_IMAGE_COUNT", "24")), int(os.getenv("HAI_RATE_IMAGE_WINDOW", str(24 * 60 * 60))))
RATE_LIMIT_MAX_KEYS = int(os.getenv("HAI_RATE_LIMIT_MAX_KEYS", "10000"))
RATE_LIMIT_STORAGE = os.getenv("HAI_RATE_LIMIT_STORAGE", "memory").strip().lower() or "memory"
RATE_LIMIT_FILE_PATH = os.getenv("HAI_RATE_LIMIT_FILE", os.path.join(DATA_DIR, "rate-limits.json"))
REALTIME_EVENT_DIR = os.getenv("HAI_REALTIME_EVENT_DIR", os.path.join(DATA_DIR, "realtime-events"))
REALTIME_EVENT_TTL_SECONDS = int(os.getenv("HAI_REALTIME_EVENT_TTL_SECONDS", "600"))
REALTIME_EVENT_MAX_EVENTS = int(os.getenv("HAI_REALTIME_EVENT_MAX_EVENTS", "500"))
REALTIME_EVENT_MAX_CHARS = int(os.getenv("HAI_REALTIME_EVENT_MAX_CHARS", "1200"))
REALTIME_WSS_READY = os.getenv("HAI_REALTIME_WSS_READY", "0") == "1"
REALTIME_WSS_PATH = os.getenv("HAI_REALTIME_WSS_PATH", "/api/realtime/ws")
TRUST_PROXY_HEADERS = os.getenv("HAI_TRUST_PROXY_HEADERS", "0") == "1"
_rate_buckets = defaultdict(deque)
_rate_file_lock = threading.Lock()
_history_lock = threading.Lock()
_library_lock = threading.Lock()
_realtime_lock = threading.Lock()
_member_ai_chat_lock = threading.Lock()
try:
    import fcntl
except ImportError:  # pragma: no cover - non-Unix fallback
    fcntl = None

if _uses_default_flask_secret:
    app.logger.warning("HAI_FLASK_SECRET belum diset; gunakan secret unik untuk production.")
if _uses_derived_device_secret:
    app.logger.warning(
        "HAI_DEVICE_SECRET belum diset; cookie device mengikuti HAI_FLASK_SECRET. "
        "Set HAI_DEVICE_SECRET terpisah agar rotasi Flask secret tidak memutus riwayat device."
    )

# System message for the chat model
SYSTEM_CONTENT = os.getenv(
    "HAI_SYSTEM_CONTENT",
    "Anda adalah Harmonika AI, asisten umum yang natural, rapi, dan membantu. "
    "Jawab dalam bahasa pengguna. Jangan menyebut engine internal, API key, atau routing backend. "
    "Jangan menggandakan jawaban atau mengulang kalimat yang sama; jika diminta singkat, jawab langsung dan padat."
)
RESPONSE_QUALITY_RULES = (
    "Aturan kualitas jawaban: jangan menggandakan jawaban, jangan mengulang kalimat/paragraf yang sama, "
    "dan jika pengguna meminta jawaban singkat maka jawab langsung tanpa pembuka panjang."
)


def _with_response_quality_rules(system_content):
    value = (system_content or SYSTEM_CONTENT or "").strip()
    if "jangan menggandakan jawaban" in value.lower():
        return value
    return f"{value}\n\n{RESPONSE_QUALITY_RULES}".strip()

# Constants for web search
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
DEFAULT_RESULTS = 3
TIMEOUT = 10  # seconds
RETRY_LIMIT = 3
RATE_LIMIT = 0.5  # seconds
AUTO_WEB_GROUNDING = os.getenv("HAI_AUTO_WEB_GROUNDING", "1") != "0"
PUBLIC_FETCH_MAX_REDIRECTS = int(os.getenv("HAI_PUBLIC_FETCH_MAX_REDIRECTS", "3"))
SOURCE_HEADER_MAX_BYTES = int(os.getenv("HAI_SOURCE_HEADER_MAX_BYTES", "2800"))
SOURCE_HEADER_MAX_ITEMS = int(os.getenv("HAI_SOURCE_HEADER_MAX_ITEMS", "6"))
SOURCE_HEADER_MAX_URL = int(os.getenv("HAI_SOURCE_HEADER_MAX_URL", "1024"))
SOURCE_HEADER_MAX_SNIPPET = int(os.getenv("HAI_SOURCE_HEADER_MAX_SNIPPET", "160"))
SOURCE_TEXT_MAX_CHARS = int(os.getenv("HAI_SOURCE_TEXT_MAX_CHARS", "12000"))
ADDITIONAL_TEXT_MAX_CHARS = int(os.getenv("HAI_ADDITIONAL_TEXT_MAX_CHARS", "24000"))
HISTORY_TEXT_MAX_CHARS = int(os.getenv("HAI_HISTORY_TEXT_MAX_CHARS", "8000"))
STREAM_OPEN_COMMENT = os.getenv("HAI_STREAM_OPEN_COMMENT", ": hai-open\n\n")
STREAM_HEARTBEAT_COMMENT = os.getenv("HAI_STREAM_HEARTBEAT_COMMENT", ": hai-ping\n\n")
STREAM_HEARTBEAT_SECONDS = float(os.getenv("HAI_STREAM_HEARTBEAT_SECONDS", "12"))


# Global variables to store API key, base URL, and models
api_key = os.getenv("HAI_ENGINE_TOKEN") or os.getenv("OPENAI_API_KEY") or "hai-local"
base_url = (os.getenv("HAI_ENGINE_URL") or os.getenv("OPENAI_BASE_URL") or "http://127.0.0.1:17890/v1/openwebui").rstrip("/")
openai_client = None
preloaded_models = ["harmonika-ai"]
DEFAULT_MODEL = os.getenv("HAI_DEFAULT_MODEL", "harmonika-ai")
IMAGE_MODEL = os.getenv("HAI_IMAGE_MODEL", "harmonika-team")
DISABLE_USER_API_SETTINGS = os.getenv("HAI_DISABLE_USER_API_SETTINGS", "1") != "0"
IMAGE_GENERATION_ENABLED = os.getenv("HAI_IMAGE_GENERATION_ENABLED", "1") != "0"
IMAGE_ARTIFACT_MODE = os.getenv("HAI_IMAGE_ARTIFACT_MODE", "svg").strip().lower() or "svg"
MEMBER_AI_BASE_URL = (os.getenv("HAI_MEMBER_AI_BASE_URL") or "https://chat.harmonika.id/v1/member-ai").rstrip("/")
MEMBER_AI_TOKEN = os.getenv("HAI_MEMBER_AI_TOKEN", "").strip()
MEMBER_AI_IMAGE_BRIDGE = os.getenv("HAI_MEMBER_AI_IMAGE_BRIDGE", "1") != "0"
MEMBER_AI_CHAT_BRIDGE = os.getenv("HAI_MEMBER_AI_CHAT_BRIDGE", "1") != "0"
MEMBER_AI_CHAT_MODE = os.getenv("HAI_MEMBER_AI_CHAT_MODE", "google").strip().lower() or "google"
MEMBER_AI_CODEX_MODE = os.getenv("HAI_MEMBER_AI_CODEX_MODE", "codex").strip().lower() or "codex"
MEMBER_AI_IMAGE_MODE = os.getenv("HAI_MEMBER_AI_IMAGE_MODE", MEMBER_AI_CODEX_MODE).strip().lower() or MEMBER_AI_CODEX_MODE
MEMBER_AI_ROUTE_CODEX = os.getenv("HAI_MEMBER_AI_ROUTE_CODEX", "1") != "0"
MEMBER_AI_RASTER_READY = os.getenv("HAI_MEMBER_AI_RASTER_READY", "0") == "1"
MEMBER_AI_RASTER_PUBLIC = os.getenv("HAI_MEMBER_AI_RASTER_PUBLIC", "0") == "1"
MEMBER_AI_TIMEOUT = float(os.getenv("HAI_MEMBER_AI_TIMEOUT", "180"))
MEMBER_AI_IMAGE_TIMEOUT = min(MEMBER_AI_TIMEOUT, float(os.getenv("HAI_MEMBER_AI_IMAGE_TIMEOUT", "180")))
MEMBER_AI_CHAT_TIMEOUT = min(MEMBER_AI_TIMEOUT, float(os.getenv("HAI_MEMBER_AI_CHAT_TIMEOUT", "90")))
MEMBER_AI_FILE_TIMEOUT = min(MEMBER_AI_TIMEOUT, float(os.getenv("HAI_MEMBER_AI_FILE_TIMEOUT", "45")))
MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST = os.getenv("HAI_MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST", "1") != "0"

IMAGE_RE = re.compile(r"\b(buat|buatkan|membuat|bikin|generate|hasilkan|desain|rancang|render|ciptakan|gambarkan|create|draw)\b[^.?!]{0,100}\b(gambar|gamar|gamber|gmbar|image|foto|photo|poster|render|visual|ilustrasi|illustration|thumbnail|logo|banner)\b", re.I)
IMAGE_RE2 = re.compile(r"\b(gambar|gamar|gamber|gmbar|image|foto|photo|poster|ilustrasi|logo|banner)\b[^.?!]{0,80}\b(buat|buatkan|membuat|bikin|generate|hasilkan|desain|ciptakan|create)\b", re.I)
IMAGE_CMD_RE = re.compile(r"^(gambar|image|foto|photo|poster|ilustrasi|logo|banner)\s*[:,-]", re.I)
CODEX_EXPLICIT_RE = re.compile(r"\b(codex|opencode|glm\s*5|claude\s+code)\b", re.I)
CODEX_STACKTRACE_RE = re.compile(
    r"(traceback \(most recent call last\)|stack\s*trace|exception in thread|"
    r"\b(?:error|exception):\s+[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)\b|"
    r"^\s*(?:at\s+[\w.$]+\(.*:\d+\)|File \"[^\"]+\", line \d+))",
    re.I | re.M,
)
CODEX_TASK_RE = re.compile(
    r"\b("
    r"coding|program|script|skrip|debug|bug|bugh|exception|stacktrace|stack\s+trace|"
    r"terminal|shell|ssh|server|backend|frontend|api\s*endpoint|endpoint|deploy|docker|nginx|gunicorn|"
    r"flask|fastapi|node|react|vue|svelte|kotlin|android|gradle|compose|sql|database|redis|git|github|"
    r"repo|repository|unit\s*test|lint|build|log|crash"
    r")\b",
    re.I,
)
CODEX_CODE_CONTEXT_RE = re.compile(
    r"\b("
    r"source\s+code|kode\s+(?:program|aplikasi|python|javascript|typescript|php|java|kotlin|go|rust|html|css|sql|flask|fastapi|node|react|vue|svelte)|"
    r"(?:python|javascript|typescript|php|java|kotlin|go|rust|html|css|sql)\s+(?:code|kode|script|function|class)"
    r")\b",
    re.I,
)
CODEX_ACTION_RE = re.compile(
    r"\b("
    r"perbaiki|debug|audit|cek\s+bug|cek\s+log|implementasi|implement|buatkan?\s+(?:kode|script|endpoint|api|backend|frontend|fitur)|"
    r"bangun|build|deploy|release|install|konfigurasi|setting|refactor|compile|jalankan|test|uji|push|pull|merge|"
    r"fix|repair|troubleshoot|review\s+kode"
    r")\b",
    re.I,
)
CODEX_SYMPTOM_RE = re.compile(
    r"("
    r"\b(?:500|502|503|504)\b|bad\s+gateway|force\s+close|exit\s+code\s+\d+|"
    r"\bcrash(?:ed|ing)?\b|\bdown\b|tidak\s+running|tidak\s+jalan|gagal\s+(?:build|deploy|compile|start|jalan|running)|"
    r"(?:nginx|gunicorn|docker|container|server|backend|database|android|gradle)[^.?!\n]{0,80}"
    r"(?:error|crash|down|lambat|lemot|macet|timeout|gagal|502|500|exit\s+code|force\s+close)"
    r")",
    re.I,
)

IMAGE_ARTIFACT_SYSTEM = """Anda adalah Harmonika AI. Jika pengguna meminta membuat gambar, poster, logo, thumbnail, ilustrasi, visual, atau desain:
- Jangan menjalankan terminal, jangan menulis perintah shell, jangan menyebut mkdir, Write, file manager, path server, /media, atau /download.
- Hasilkan artifact visual langsung sebagai SATU SVG lengkap dalam blok kode fenced: ```svg ... ```.
- SVG harus self-contained, aman, tanpa script, tanpa foreignObject, tanpa link eksternal, tanpa gambar eksternal, dan ukuran wajar.
- Buat visual yang rapi, berwarna, proporsional, dengan viewBox jelas. Jika perlu teks, gunakan teks singkat.
- Boleh beri satu kalimat pendek sebelum/sesudah SVG, tetapi jangan menggandakan jawaban.
"""

def is_image_intent_text(text):
    text = text or ""
    return bool(IMAGE_RE.search(text) or IMAGE_RE2.search(text) or IMAGE_CMD_RE.search(text))

def _split_svg_lines(text, max_chars=26, max_lines=4):
    words = re.sub(r"\s+", " ", text or "").strip().split(" ")
    lines = []
    current = ""
    for word in words:
        next_line = f"{current} {word}".strip()
        if len(next_line) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = next_line
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        lines = ["Harmonika AI"]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines

def _image_prompt_subject(prompt):
    value = _clean_text(prompt, 240)
    value = re.sub(r"\b(tolong|coba|please|buatkan|buat|bikin|generate|hasilkan|desain|rancang|gambar|image|foto|poster|logo|thumbnail|ilustrasi|visual)\b", " ", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" .,:;-")
    return value[:120] or "visual kreatif Harmonika AI"

def _build_svg_artifact(prompt):
    subject = _image_prompt_subject(prompt)
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()
    palettes = [
        ("#07111f", "#00d5ff", "#2f6bff", "#ffffff", "#7ee8fa"),
        ("#160b2c", "#ff6ec7", "#7c3cff", "#fff4ff", "#ffd166"),
        ("#071f16", "#50f2a5", "#02a676", "#f4fff8", "#f9d65c"),
        ("#1d1010", "#ff8a3d", "#ffcf5a", "#fff8ee", "#d94b4b"),
    ]
    bg, accent, accent2, text_color, glow = palettes[int(digest[:2], 16) % len(palettes)]
    title_lines = _split_svg_lines(subject.title(), max_chars=24, max_lines=3)
    safe_title = [xml_escape(line) for line in title_lines]
    seed_a = int(digest[2:4], 16)
    seed_b = int(digest[4:6], 16)
    circle_x = 150 + seed_a % 500
    circle_y = 120 + seed_b % 260
    text_spans = "\n".join(
        f'<tspan x="400" y="{250 + (index * 54)}">{line}</tspan>'
        for index, line in enumerate(safe_title)
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" role="img" aria-labelledby="title desc">
  <title id="title">Gambar Harmonika AI</title>
  <desc id="desc">Artifact visual aman berdasarkan prompt pengguna.</desc>
  <defs>
    <radialGradient id="halo" cx="50%" cy="50%" r="65%">
      <stop offset="0%" stop-color="{glow}" stop-opacity="0.95"/>
      <stop offset="48%" stop-color="{accent}" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="{bg}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="wave" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{accent}"/>
      <stop offset="55%" stop-color="{accent2}"/>
      <stop offset="100%" stop-color="{glow}"/>
    </linearGradient>
    <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="10" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect width="800" height="500" rx="36" fill="{bg}"/>
  <circle cx="{circle_x}" cy="{circle_y}" r="210" fill="url(#halo)" opacity="0.9"/>
  <circle cx="{620 - seed_b % 120}" cy="{130 + seed_a % 90}" r="78" fill="none" stroke="{accent}" stroke-width="14" opacity="0.8" filter="url(#softGlow)"/>
  <path d="M70 330 C170 210 250 430 360 300 S535 205 730 320" fill="none" stroke="url(#wave)" stroke-width="34" stroke-linecap="round" opacity="0.92" filter="url(#softGlow)"/>
  <g opacity="0.92">
    <rect x="92" y="98" width="58" height="58" rx="15" fill="{accent}" opacity="0.78"/>
    <rect x="165" y="66" width="46" height="46" rx="13" fill="{glow}" opacity="0.9"/>
    <rect x="220" y="124" width="34" height="34" rx="9" fill="{accent2}" opacity="0.9"/>
  </g>
  <text x="400" y="250" text-anchor="middle" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="46" font-weight="800" fill="{text_color}" letter-spacing="0.5">
    {text_spans}
  </text>
  <text x="400" y="426" text-anchor="middle" font-family="Inter, Segoe UI, Arial, sans-serif" font-size="18" fill="{text_color}" opacity="0.72" letter-spacing="5">HARMONIKA AI</text>
</svg>"""
    return (
        "Berikut draft gambar dari Harmonika AI. Klik thumbnail untuk melihat lebih besar.\n\n"
        f"```svg\n{svg}\n```"
    )

def _stream_plain_text(text, delay=0.012, chunk_size=96):
    for index in range(0, len(text), chunk_size):
        yield text[index:index + chunk_size]
        if delay:
            time.sleep(delay)

STREAM_DISPLAY_CHUNK_CHARS = int(os.environ.get("HAI_STREAM_DISPLAY_CHUNK_CHARS", "24") or 24)
STREAM_DISPLAY_CHUNK_DELAY = float(os.environ.get("HAI_STREAM_DISPLAY_CHUNK_DELAY", "0.018") or 0.018)
_STREAM_DONE = object()

def _iter_display_stream_chunks(text, chunk_size=None):
    """Split large upstream chunks so the browser visibly types in realtime.

    Some engines or proxies flush text in paragraph-sized blocks.  The UI can
    only animate token-by-token if we release smaller display chunks, while the
    replay log still records the exact visible text in the same order.
    """
    value = str(text or "")
    if not value:
        return
    chunk_size = max(12, min(96, int(chunk_size or STREAM_DISPLAY_CHUNK_CHARS or 24)))
    if len(value) <= chunk_size:
        yield value
        return
    cursor = 0
    while cursor < len(value):
        end = min(len(value), cursor + chunk_size)
        if end < len(value):
            soft_end = max(
                value.rfind(" ", cursor, end + 1),
                value.rfind("\n", cursor, end + 1),
                value.rfind("\t", cursor, end + 1),
            )
            if soft_end > cursor + 10:
                end = soft_end + 1
        yield value[cursor:end]
        cursor = end

def _realtime_event_path(response_id):
    clean_id = _safe_file_id(response_id)
    if not clean_id:
        return ""
    return os.path.join(REALTIME_EVENT_DIR, f"{clean_id}.json")

def _realtime_load_record(response_id):
    path = _realtime_event_path(response_id)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            record = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(record, dict) or record.get("response_id") != _safe_file_id(response_id):
        return None
    return record

def _realtime_save_record(record):
    if not isinstance(record, dict):
        return
    response_id = _safe_file_id(record.get("response_id"))
    if not response_id:
        return
    try:
        os.makedirs(REALTIME_EVENT_DIR, exist_ok=True)
    except OSError as error:
        app.logger.warning("realtime_event_dir_unavailable: %s", error)
        return
    now_ms = int(time.time() * 1000)
    record["updated_at"] = now_ms
    record["expires_at"] = now_ms + max(60, REALTIME_EVENT_TTL_SECONDS) * 1000
    events = record.get("events") if isinstance(record.get("events"), list) else []
    record["events"] = events[-max(10, REALTIME_EVENT_MAX_EVENTS):]
    path = _realtime_event_path(response_id)
    tmp_file = ""
    try:
        tmp_handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=REALTIME_EVENT_DIR, prefix=f"{response_id}.", suffix=".tmp", delete=False)
        tmp_file = tmp_handle.name
        with tmp_handle as file:
            json.dump(record, file, ensure_ascii=False, separators=(",", ":"))
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp_file, path)
    except OSError as error:
        app.logger.warning("realtime_event_save_failed: %s", error)
        if tmp_file:
            try:
                os.unlink(tmp_file)
            except OSError:
                pass

def _realtime_cleanup_old():
    try:
        names = os.listdir(REALTIME_EVENT_DIR)
    except OSError:
        return
    now_ms = int(time.time() * 1000)
    for name in names[:1000]:
        if not name.endswith(".json"):
            continue
        path = os.path.join(REALTIME_EVENT_DIR, name)
        try:
            with open(path, "r", encoding="utf-8") as file:
                record = json.load(file)
            expires_at = int(record.get("expires_at") or 0)
            if expires_at and expires_at < now_ms:
                os.unlink(path)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            continue

def _realtime_record_event(response_id, event_type, data=None):
    response_id = _safe_file_id(response_id)
    if not response_id:
        return None
    now_ms = int(time.time() * 1000)
    clean_data = data if isinstance(data, dict) else {}
    if isinstance(clean_data.get("text"), str):
        clean_data = dict(clean_data)
        clean_data["text"] = _clean_text(clean_data.get("text"), REALTIME_EVENT_MAX_CHARS)
    with _realtime_lock:
        record = _realtime_load_record(response_id) or {
            "response_id": response_id,
            "created_at": now_ms,
            "updated_at": now_ms,
            "status": "active",
            "events": [],
        }
        events = record.setdefault("events", [])
        sequence = int(events[-1].get("sequence", 0)) + 1 if events else 1
        event = {
            "event_id": f"{response_id}:{sequence}",
            "response_id": response_id,
            "sequence": sequence,
            "timestamp": now_ms,
            "type": _clean_text(event_type, 80),
            "data": clean_data,
        }
        events.append(event)
        if event_type == "response.completed" and record.get("status") in {"error", "stopped"}:
            pass
        elif event_type in {"response.completed", "response.error", "response.stopped"}:
            record["status"] = event_type.split(".")[-1]
        else:
            record["status"] = "active"
        _realtime_save_record(record)
    return event

def _realtime_events_after(response_id, after_sequence=0):
    record = _realtime_load_record(response_id)
    if not record:
        return None, []
    try:
        after_sequence = int(after_sequence or 0)
    except (TypeError, ValueError):
        after_sequence = 0
    events = [
        event for event in record.get("events", [])
        if isinstance(event, dict) and int(event.get("sequence") or 0) > after_sequence
    ]
    return record, events

def _realtime_record_state(record, events=None, after_sequence=0):
    if not isinstance(record, dict):
        return {}
    source_events = record.get("events") if isinstance(record.get("events"), list) else []
    replay_events = events if isinstance(events, list) else []
    last_event = source_events[-1] if source_events else {}
    status = record.get("status") or "unknown"
    try:
        last_sequence = int(last_event.get("sequence") or 0)
    except (TypeError, ValueError):
        last_sequence = 0
    try:
        after_sequence = int(after_sequence or 0)
    except (TypeError, ValueError):
        after_sequence = 0
    next_after_sequence = replay_events[-1].get("sequence") if replay_events else after_sequence
    return {
        "response_id": _safe_file_id(record.get("response_id")) or "",
        "status": status,
        "terminal": status in {"completed", "error", "stopped"},
        "last_sequence": last_sequence,
        "last_event_id": last_event.get("event_id") or "",
        "next_after_sequence": next_after_sequence,
        "replay_after_sequence": after_sequence,
        "expires_at": record.get("expires_at"),
        "event_count": len(source_events),
        "replay_count": len(replay_events),
    }

def _realtime_ws_url():
    scheme = "wss" if request.is_secure or request.headers.get("X-Forwarded-Proto", "").lower() == "https" else "ws"
    host = request.headers.get("X-Forwarded-Host") or request.host or "hai.harmonika.id"
    path = REALTIME_WSS_PATH if str(REALTIME_WSS_PATH).startswith("/") else f"/{REALTIME_WSS_PATH}"
    return f"{scheme}://{host}{path}"

def _stream_with_heartbeat(producer, *, log_name="stream", fallback_message="Maaf, koneksi ke Harmonika AI terputus. Silakan coba lagi.", response_id=None):
    """Run a blocking producer in a worker and keep the HTTP stream alive.

    The frontend filters `: hai-open`/`: hai-ping` control frames, so these
    comments never become visible chat text. They only prevent silent/idle
    streams when an upstream engine, web source, or image bridge is slow.
    """
    output_queue = queue.Queue()

    response_id = _safe_file_id(response_id)
    if response_id:
        _realtime_cleanup_old()
        _realtime_record_event(response_id, "response.created", {"log_name": _clean_text(log_name, 80)})

    def emit(value):
        if value:
            output_queue.put(str(value))

    def worker():
        try:
            producer(emit)
        except Exception as error:
            app.logger.warning("%s_error: %s", log_name, error)
            if response_id:
                _realtime_record_event(response_id, "response.error", {"message": fallback_message})
            emit(f"\n\n{fallback_message}")
        finally:
            output_queue.put(_STREAM_DONE)

    threading.Thread(target=worker, name=f"hai-{log_name}", daemon=True).start()

    if STREAM_OPEN_COMMENT:
        yield STREAM_OPEN_COMMENT

    timeout = max(0.05, STREAM_HEARTBEAT_SECONDS)
    while True:
        try:
            item = output_queue.get(timeout=timeout)
        except queue.Empty:
            if STREAM_HEARTBEAT_COMMENT:
                yield STREAM_HEARTBEAT_COMMENT
            continue
        if item is _STREAM_DONE:
            if response_id:
                _realtime_record_event(response_id, "response.completed", {})
            break
        for display_chunk in _iter_display_stream_chunks(item):
            if response_id:
                _realtime_record_event(response_id, "response.output_text.delta", {"text": display_chunk})
            yield display_chunk
            if STREAM_DISPLAY_CHUNK_DELAY and len(str(item or "")) > len(display_chunk):
                time.sleep(STREAM_DISPLAY_CHUNK_DELAY)

def _image_generation_unavailable_message():
    return (
        "Pembuatan gambar belum tersedia. "
        "Untuk saat ini saya bisa membantu membuat konsep visual, prompt gambar, atau arahan desain."
    )

def _member_ai_bridge_ready():
    return bool(MEMBER_AI_IMAGE_BRIDGE and MEMBER_AI_BASE_URL and MEMBER_AI_TOKEN)

def _member_ai_chat_ready():
    return bool(MEMBER_AI_CHAT_BRIDGE and MEMBER_AI_BASE_URL and MEMBER_AI_TOKEN and MEMBER_AI_CHAT_MODE)

def _member_ai_headers(extra=None):
    headers = {
        "Authorization": f"Bearer {MEMBER_AI_TOKEN}",
        "Accept": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers

def _member_ai_reset_chat_session():
    """Best-effort reset for the shared web bridge member-AI token.

    The public web app sends its own local conversation context on every
    request, so it must not rely on the upstream member-AI session attached to
    the shared server token. Resetting inside a server-side lock prevents two
    public web requests from mixing attachments/history in the same upstream
    session.
    """
    if not MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST:
        return False
    response = httpx.delete(
        f"{MEMBER_AI_BASE_URL}/chat/session",
        headers=_member_ai_headers({"Accept": "application/json"}),
        timeout=min(MEMBER_AI_FILE_TIMEOUT, 20),
    )
    if response.status_code in {404, 405, 501}:
        return False
    response.raise_for_status()
    return True

def _safe_html_attr(value):
    return xml_escape(str(value or ""), {'"': "&quot;", "'": "&#x27;"})

def _safe_file_id(file_id):
    value = _clean_text(file_id, 180).strip()
    if not value or "/" in value or "\\" in value or ".." in value:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,180}", value):
        return ""
    return value

def _is_local_image_file_id(file_id):
    return bool(str(file_id or "").startswith("local-svg-"))

def _extract_member_ai_images(payload):
    if not isinstance(payload, dict):
        return []
    candidates = []
    for key in ("images", "artifacts"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("images", "artifacts"):
            value = data.get(key)
            if isinstance(value, list):
                candidates.extend(value)
    clean = []
    seen = set()
    for item in candidates[:4]:
        if not isinstance(item, dict):
            continue
        file_id = _safe_file_id(item.get("file_id") or item.get("id"))
        if not file_id or file_id in seen:
            continue
        seen.add(file_id)
        clean.append({
            "file_id": file_id,
            "mime_type": _clean_text(item.get("mime_type") or item.get("mime") or "image/png", 80),
            "width": item.get("width"),
            "height": item.get("height"),
            "size_bytes": item.get("size_bytes"),
            "status": _clean_text(item.get("status") or "ready", 40),
            "source_prompt": _clean_text(item.get("source_prompt"), 500),
            "requested_size": _clean_text(item.get("requested_size"), 40),
        })
    return clean

def _member_ai_sse_events(response):
    buffer = ""
    for chunk in response.iter_text():
        if not chunk:
            continue
        buffer += chunk
        while "\n\n" in buffer:
            raw_event, buffer = buffer.split("\n\n", 1)
            lines = [line.strip() for line in raw_event.splitlines() if line.strip()]
            data_lines = []
            for line in lines:
                if line.startswith(":"):
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[5:].strip())
            if not data_lines:
                continue
            data_text = "\n".join(data_lines).strip()
            if not data_text or data_text == "[DONE]":
                continue
            try:
                payload = json.loads(data_text)
            except json.JSONDecodeError:
                payload = {"type": "delta", "text": data_text}
            if isinstance(payload, dict):
                yield payload
    tail = buffer.strip()
    if tail:
        for line in tail.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            data_text = line[5:].strip()
            if not data_text or data_text == "[DONE]":
                continue
            try:
                payload = json.loads(data_text)
            except json.JSONDecodeError:
                payload = {"type": "delta", "text": data_text}
            if isinstance(payload, dict):
                yield payload

def _history_context_for_member_ai(conversation_history, max_messages=8, max_chars=6000):
    if not conversation_history:
        return ""
    lines = []
    for item in conversation_history[-max_messages:]:
        if not isinstance(item, dict):
            continue
        role = _clean_text(item.get("role") or "", 20)
        if role not in {"user", "assistant"}:
            continue
        content = item.get("content")
        if isinstance(content, dict):
            content = content.get("raw") or content.get("content") or ""
        text = message_text(content) if isinstance(content, list) else _clean_text(content, 1200)
        text = _strip_reasoning_blocks(text).strip()
        if text:
            label = "User" if role == "user" else "Harmonika AI"
            lines.append(f"{label}: {text}")
    context = "\n".join(lines).strip()
    if not context:
        return ""
    return _clamp_text(
        "Konteks percakapan web saat ini. Gunakan hanya jika relevan dan abaikan konteks lain di luar blok ini:\n"
        f"{context}\n\nPesan terbaru:",
        max_chars,
    )

def _strip_reasoning_blocks(text):
    value = _clean_text(text or "", HISTORY_TEXT_MAX_CHARS)
    value = re.sub(r"<think>.*?</think>", "", value, flags=re.I | re.S)
    value = re.sub(r"<\\|end_of_thought\\|>", "", value, flags=re.I)
    return value

def _member_ai_text_payload(user_content, conversation_history=None):
    text = message_text(user_content).strip()
    if text.lower().startswith("@s") and (len(text) == 2 or text[2].isspace()):
        text = text[2:].strip()
    context = _history_context_for_member_ai(conversation_history or [])
    latest_block = (
        "Instruksi isolasi untuk chat web publik:\n"
        "- Jawab hanya untuk PESAN TERBARU DI BAWAH INI dan konteks percakapan web yang ikut dikirim di payload ini.\n"
        "- Abaikan riwayat/session internal backend lain yang mungkin tersimpan dari request sebelumnya.\n"
        "- Jika PESAN TERBARU berisi blok `[Document: ...]`, perlakukan blok itu sebagai lampiran terbaru yang harus dibaca.\n"
        "- Jangan menanyakan dokumen/kode lain bila jawaban bisa ditemukan di lampiran terbaru.\n\n"
        "PESAN TERBARU:\n"
        f"{text}"
    ).strip()
    if context:
        return f"{context}\n{latest_block}".strip()
    return latest_block

DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,(.+)$", re.I | re.S)

def _member_ai_upload_data_url(data_url, filename_prefix="hai-image"):
    match = DATA_URL_RE.match(str(data_url or ""))
    if not match:
        return ""
    mime_type = match.group(1).lower()
    try:
        file_bytes = base64.b64decode(match.group(2), validate=True)
    except Exception:
        return ""
    if not file_bytes or len(file_bytes) > 10 * 1024 * 1024:
        return ""
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(mime_type, "png")
    filename = f"{filename_prefix}.{ext}"
    files = {"file": (filename, file_bytes, mime_type)}
    response = httpx.post(
        f"{MEMBER_AI_BASE_URL}/files",
        headers=_member_ai_headers({"Accept": "application/json"}),
        files=files,
        timeout=MEMBER_AI_FILE_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    nested = data.get("data") if isinstance(data.get("data"), dict) else {}
    file_id = _safe_file_id(data.get("id") or data.get("file_id") or nested.get("id") or nested.get("file_id"))
    if not file_id and isinstance(data.get("file"), dict):
        file_id = _safe_file_id(data["file"].get("id") or data["file"].get("file_id"))
    return file_id

def _member_ai_prepare_chat_request(user_content, conversation_history=None):
    attachment_ids = []
    if isinstance(user_content, list):
        for index, item in enumerate(user_content[:4]):
            if not isinstance(item, dict):
                continue
            image_url = item.get("image_url")
            if isinstance(image_url, dict):
                image_url = image_url.get("url")
            if isinstance(image_url, str) and image_url.startswith("data:image/"):
                file_id = _member_ai_upload_data_url(image_url, f"hai-image-{index + 1}")
                if file_id:
                    attachment_ids.append(file_id)
    message = _member_ai_text_payload(user_content, conversation_history)
    return message, attachment_ids[:3]

def _member_ai_route_mode(user_content, attachment_ids=None):
    """Pick a server-side member-AI mode without exposing engines to the UI.

    Product routing:
    - Google Mode is the primary answer engine for normal questions, general
      analysis, casual conversation/story, web-grounded answers, and every
      file/image-understanding request.
    - Codex is reserved only for explicit heavy development work: coding,
      debugging, deployment, logs/stacktraces, backend/frontend/API builds,
      terminal/server tasks, clear technical failure symptoms, or when the
      user explicitly asks for Codex.
    - Image creation is handled before this function by the dedicated private
      artifact bridge. This router only handles text/attachment understanding.
    """
    default_mode = MEMBER_AI_CHAT_MODE or "google"
    if attachment_ids:
        return default_mode
    text = message_text(user_content)
    if not isinstance(text, str) or not text.strip():
        return default_mode
    if (
        MEMBER_AI_ROUTE_CODEX
        and MEMBER_AI_CODEX_MODE
        and (
            CODEX_EXPLICIT_RE.search(text)
            or CODEX_STACKTRACE_RE.search(text)
            or (CODEX_CODE_CONTEXT_RE.search(text) and CODEX_ACTION_RE.search(text))
            or (CODEX_TASK_RE.search(text) and CODEX_ACTION_RE.search(text))
            or (CODEX_TASK_RE.search(text) and CODEX_SYMPTOM_RE.search(text))
        )
    ):
        return MEMBER_AI_CODEX_MODE
    return default_mode

def _member_ai_stream_chat_payload(payload, emit):
    emitted = False
    headers = _member_ai_headers({
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    })
    with httpx.stream(
        "POST",
        f"{MEMBER_AI_BASE_URL}/chat/messages",
        headers=headers,
        json=payload,
        timeout=MEMBER_AI_CHAT_TIMEOUT,
    ) as response:
        response.raise_for_status()
        for event in _member_ai_sse_events(response):
            event_type = _clean_text(event.get("type"), 40)
            if event_type == "delta":
                text = event.get("text")
                if text:
                    emit(str(text))
                    emitted = True
            elif event_type == "error":
                message_text_value = _clean_text(event.get("message") or event.get("error"), 500)
                if message_text_value:
                    raise RuntimeError(message_text_value)
            elif event_type in {"stopped"}:
                break
    return emitted

def _member_ai_emit_chat(user_content, conversation_history, emit):
    message, attachment_ids = _member_ai_prepare_chat_request(user_content, conversation_history)
    if not message and not attachment_ids:
        return False
    route_mode = _member_ai_route_mode(user_content, attachment_ids)
    payload = {
        "message": message or "Jelaskan lampiran ini.",
        "mode": route_mode,
    }
    if attachment_ids:
        payload["attachment_ids"] = attachment_ids
    modes = []
    for mode in [route_mode, MEMBER_AI_CHAT_MODE, "google"]:
        mode = _clean_text(mode, 40).strip().lower()
        if mode and mode not in modes:
            modes.append(mode)
    last_error = None
    # The public web bridge uses a shared server-side member token. Keep the
    # upstream session single-flight and reset it before each web request so
    # simultaneous users/QA flows cannot cross-read each other's attachments.
    with _member_ai_chat_lock:
        if MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST:
            try:
                _member_ai_reset_chat_session()
            except Exception as error:
                app.logger.warning("member_ai_chat_session_reset_error: %s", error)
        for mode in modes:
            payload["mode"] = mode
            emitted_any = False
            def tracked_emit(chunk):
                nonlocal emitted_any
                emitted_any = True
                emit(chunk)
            try:
                emitted = _member_ai_stream_chat_payload(payload, tracked_emit)
                return emitted
            except Exception as error:
                last_error = error
                if emitted_any:
                    raise
                app.logger.warning("member_ai_chat_mode_%s_error: %s", mode, error)
                continue
    if last_error:
        raise last_error
    return False

def _image_artifacts_markdown(images, prompt):
    if not images:
        return ""
    title = "Gambar Harmonika AI"
    cards = []
    for index, image in enumerate(images[:4], start=1):
        file_id = image["file_id"]
        preview = f"/api/files/{quote(file_id, safe='')}/preview"
        download = f"/api/files/{quote(file_id, safe='')}/download"
        label = title if len(images) == 1 else f"{title} {index}"
        meta = []
        if image.get("requested_size"):
            meta.append(image["requested_size"])
        if image.get("mime_type"):
            meta.append(image["mime_type"].split("/")[-1].upper())
        meta_text = " · ".join(meta) or "Klik thumbnail untuk melihat preview"
        download_label = "Unduh SVG" if str(image.get("mime_type") or "").lower().endswith("svg+xml") else "Unduh PNG"
        cards.append(
            '<figure class="hai-legacy-image hai-member-image-artifact">'
            f'<button type="button" class="hai-legacy-thumb" data-hai-preview="{_safe_html_attr(preview)}" title="Lihat gambar">'
            f'<img src="{_safe_html_attr(preview)}" alt="{_safe_html_attr(label)}" loading="lazy" referrerpolicy="same-origin">'
            '</button>'
            f'<figcaption><strong>{_safe_html_attr(label)}</strong><span>{_safe_html_attr(meta_text)}</span>'
            '<div class="hai-image-card-actions">'
            f'<button type="button" data-hai-preview="{_safe_html_attr(preview)}">Lihat</button>'
            f'<a href="{_safe_html_attr(download)}" download>{download_label}</a>'
            '</div></figcaption>'
            '</figure>'
        )
    intro = "Gambar sudah selesai dibuat. Klik thumbnail untuk melihat lebih besar."
    return f"{intro}\n\n" + "\n".join(cards)

def _extract_svg_markup(artifact_text):
    text = str(artifact_text or "")
    match = re.search(r"```svg\s*([\s\S]*?<svg[\s\S]*?</svg>)\s*```", text, re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"(<svg[\s\S]*?</svg>)", text, re.I)
    return match.group(1).strip() if match else ""

def _local_image_path(file_id):
    clean_file_id = _safe_file_id(file_id)
    if not clean_file_id or not clean_file_id.startswith(LOCAL_IMAGE_ID_PREFIX):
        return ""
    return os.path.join(LOCAL_IMAGE_DIR, f"{clean_file_id}.json")

def _store_local_svg_image(prompt, artifact_text):
    svg = _extract_svg_markup(artifact_text)
    if not svg:
        return []
    os.makedirs(LOCAL_IMAGE_DIR, exist_ok=True)
    digest = hashlib.sha256(f"{prompt}\n{time.time()}\n{secrets.token_hex(8)}".encode("utf-8")).hexdigest()[:24]
    file_id = f"{LOCAL_IMAGE_ID_PREFIX}{digest}"
    record = {
        "file_id": file_id,
        "mime_type": "image/svg+xml",
        "width": 800,
        "height": 500,
        "size_bytes": len(svg.encode("utf-8")),
        "status": "ready",
        "source_prompt": _clean_text(prompt, 500),
        "requested_size": "800x500",
        "content": svg,
        "created_at": int(time.time() * 1000),
    }
    tmp_handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=LOCAL_IMAGE_DIR, prefix=f"{file_id}.", suffix=".tmp", delete=False)
    tmp_file = tmp_handle.name
    with tmp_handle as file:
        json.dump(record, file, ensure_ascii=False, separators=(",", ":"))
        file.flush()
        os.fsync(file.fileno())
    os.replace(tmp_file, _local_image_path(file_id))
    return [{
        "file_id": file_id,
        "mime_type": record["mime_type"],
        "width": record["width"],
        "height": record["height"],
        "size_bytes": record["size_bytes"],
        "status": record["status"],
        "source_prompt": record["source_prompt"],
        "requested_size": record["requested_size"],
    }]

def _load_local_image(file_id):
    path = _local_image_path(file_id)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            record = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(record, dict) or _safe_file_id(record.get("file_id")) != _safe_file_id(file_id):
        return None
    if record.get("mime_type") != "image/svg+xml" or not str(record.get("content") or "").lstrip().lower().startswith("<svg"):
        return None
    return record

def _local_svg_image_response(prompt):
    artifact = _build_svg_artifact(prompt)
    images = _store_local_svg_image(prompt, artifact)
    markdown = _image_artifacts_markdown(images, prompt)
    return markdown or artifact, images

def _member_ai_collect_job_events(job_id, prompt):
    if not job_id:
        return []
    url = f"{MEMBER_AI_BASE_URL}/images/generations/{quote(str(job_id), safe='')}/events"
    with httpx.stream("GET", url, headers=_member_ai_headers({"Accept": "text/event-stream"}), timeout=MEMBER_AI_IMAGE_TIMEOUT) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            line = line.strip()
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            event_type = _clean_text(event.get("type") or event.get("status"), 80).lower()
            images = _extract_member_ai_images(event)
            if images:
                return images
            if event_type in ("error", "failed"):
                raise RuntimeError(_clean_text(event.get("message") or event.get("error") or "image_generation_failed", 240))
            if event_type in ("final", "completed", "response.completed"):
                return []
    return []

def _member_ai_fetch_job(job_id):
    if not job_id:
        return []
    url = f"{MEMBER_AI_BASE_URL}/images/generations/{quote(str(job_id), safe='')}"
    response = httpx.get(url, headers=_member_ai_headers(), timeout=MEMBER_AI_IMAGE_TIMEOUT)
    response.raise_for_status()
    return _extract_member_ai_images(response.json())

def _member_ai_generate_image(prompt, size=None, count=1):
    if not _member_ai_bridge_ready():
        return None
    base_payload = {
        "prompt": prompt,
        "count": max(1, min(int(count or 1), 4)),
    }
    if size:
        base_payload["size"] = _clean_text(size, 40)
    payload = dict(base_payload)
    if MEMBER_AI_IMAGE_MODE:
        payload["mode"] = MEMBER_AI_IMAGE_MODE
    headers = _member_ai_headers({
        "Content-Type": "application/json",
        "X-Harmonika-Task": "image_generation",
        "X-Harmonika-Mode": MEMBER_AI_IMAGE_MODE or MEMBER_AI_CODEX_MODE,
        "Idempotency-Key": secrets.token_hex(16),
    })
    url = f"{MEMBER_AI_BASE_URL}/images/generations"
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=MEMBER_AI_IMAGE_TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        # Some member-AI image handlers are intentionally strict about body
        # fields. Keep the Codex/image-mode signal in headers, but retry the
        # stable v1 body so production image creation does not break.
        if "mode" in payload and error.response is not None and error.response.status_code in {400, 422}:
            retry_headers = dict(headers)
            retry_headers["Idempotency-Key"] = secrets.token_hex(16)
            response = httpx.post(url, headers=retry_headers, json=base_payload, timeout=MEMBER_AI_IMAGE_TIMEOUT)
            response.raise_for_status()
        else:
            raise
    data = response.json()
    images = _extract_member_ai_images(data)
    if images:
        return images
    job_id = data.get("job_id") or data.get("id") or data.get("response_id")
    if job_id:
        images = _member_ai_collect_job_events(job_id, prompt)
        if images:
            return images
        return _member_ai_fetch_job(job_id)
    return []

def _image_response_for_prompt(prompt):
    if _member_ai_bridge_ready():
        try:
            images = _member_ai_generate_image(prompt)
            markdown = _image_artifacts_markdown(images or [], prompt)
            if markdown:
                return markdown, "member_ai"
        except Exception as error:
            app.logger.warning("member_ai_image_bridge_error: %s", error)
            if MEMBER_AI_RASTER_READY and MEMBER_AI_RASTER_PUBLIC:
                return "Pembuatan gambar belum bisa diselesaikan dari backend gambar. Coba lagi sebentar.", "member_ai_unavailable"
    if not IMAGE_GENERATION_ENABLED or IMAGE_ARTIFACT_MODE != "svg":
        return _image_generation_unavailable_message(), "disabled"
    response_text, images = _local_svg_image_response(prompt)
    return response_text, "local_svg_file" if images else "svg"

AUTO_WEB_PATTERNS = [
    r"\b(terbaru|terkini|hari ini|sekarang|saat ini|update|berita|viral|tren|trend|rilis|launching)\b",
    r"\b(jadwal|harga|kurs|cuaca|skor|hasil pertandingan|lowongan|promo|diskon|event)\b",
    r"\b(202[4-9]|203[0-9])\b",
    r"\b(cari(?:kan)?|search|googling|cek(?:kan)? di web|lihat di web|info terbaru)\b",
    r"\b(siapa (?:presiden|menteri|gubernur|walikota|ceo|direktur)|apa kabar terbaru)\b",
]
AUTO_WEB_RE = re.compile("|".join(f"(?:{pattern})" for pattern in AUTO_WEB_PATTERNS), re.I)

def should_auto_web_ground(text):
    value = (text or "").strip()
    if not AUTO_WEB_GROUNDING or not value:
        return False
    if value.lower().startswith("@s"):
        return False
    if re.search(r"https?://", value, re.I):
        return False
    if len(value) > 500:
        return False
    return bool(AUTO_WEB_RE.search(value))

def search_system_prompt(user_query, auto=False):
    mode = "otomatis memakai referensi web" if auto else "berdasarkan perintah pencarian pengguna"
    return f"""CURRENT_SYSTEM_TIME = "{time.strftime("%Y-%m-%d %H:%M:%S")}"

Anda adalah Harmonika AI yang sedang {mode}.
Jawab pertanyaan pengguna dengan natural, ringkas, rapi, dan dalam bahasa pengguna.
Gunakan hanya source text yang diberikan untuk fakta terbaru; jika sumber kurang kuat, katakan dengan jujur.
Jangan menampilkan daftar URL mentah di isi jawaban karena UI sudah menampilkan chip sumber.
Jika pertanyaan pengguna bukan permintaan membuat gambar, jangan mengatakan sudah membuat gambar, jangan menampilkan instruksi preview/download gambar, dan jangan mengubah jawaban web menjadi artifact visual.

Pertanyaan pengguna:
{user_query}

Panduan format:
- Mulai langsung dengan jawaban, bukan menjelaskan proses pencarian.
- Gunakan poin/bullet bila membantu.
- Jangan menyebut engine internal, routing backend, atau API.
"""

def message_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item.get("text"))
        return "\n".join(parts)
    return ""

def sanitize_model_parameters(parameters):
    if not isinstance(parameters, dict):
        return {}

    numeric_limits = {
        "temperature": (0.0, 2.0),
        "top_p": (0.0, 1.0),
        "presence_penalty": (-2.0, 2.0),
        "frequency_penalty": (-2.0, 2.0),
        "max_tokens": (1, 8192),
    }
    cleaned = {}
    for key, (min_value, max_value) in numeric_limits.items():
        if key not in parameters:
            continue
        value = parameters.get(key)
        try:
            if key == "max_tokens":
                value = int(value)
            else:
                value = float(value)
        except (TypeError, ValueError):
            continue
        cleaned[key] = max(min_value, min(max_value, value))
    return cleaned

# File to store settings
SETTINGS_FILE = 'settings.json'

# Function to load settings from file
def load_settings():
    global api_key, base_url, openai_client
    if DISABLE_USER_API_SETTINGS:
        openai_client = openai.OpenAI(api_key=api_key, base_url=base_url)
        return
    try:
        with open(SETTINGS_FILE, 'r') as file:
            settings = json.load(file)
            api_key = settings.get('api_key')
            base_url = settings.get('base_url')
            if api_key and base_url:
                openai_client = openai.OpenAI(
                    api_key=api_key,
                    base_url=base_url,
                )
    except (FileNotFoundError, json.JSONDecodeError):
        api_key = None
        base_url = None
        openai_client = None

# Function to save settings to file
def save_settings(api_key, base_url):
    if DISABLE_USER_API_SETTINGS:
        return
    settings = {
        'api_key': api_key,
        'base_url': base_url
    }
    with open(SETTINGS_FILE, 'w') as file:
        json.dump(settings, file)

# Function to fetch models from the API
def fetch_models():
    if DISABLE_USER_API_SETTINGS:
        return [DEFAULT_MODEL]
    if not api_key or not base_url:
        return [DEFAULT_MODEL]
    
    models_url = f"{base_url}/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = httpx.get(models_url, headers=headers)
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                if isinstance(response_data, list):
                    models = response_data
                elif isinstance(response_data, dict):
                    models = response_data.get('data', [])
                else:
                    print("Unexpected response format")
                    return []
                
                # Extracting the 'id' field from each dictionary
                ids = [model['id'] for model in models if 'id' in model]
                return ids or [DEFAULT_MODEL]
            except ValueError:
                print("Failed to parse JSON response")
                return [DEFAULT_MODEL]
        else:
            print(f"Failed to retrieve models. Status code: {response.status_code}")
            return [DEFAULT_MODEL]
    except httpx.RequestError as e:
        print(f"An error occurred while making the request: {e}")
        return [DEFAULT_MODEL]


# Function to preload models on app startup
def preload_models():
    global preloaded_models
    preloaded_models = fetch_models()

# Function to fetch search results from DuckDuckGo Lite
async def fetch_results(session, query, results=DEFAULT_RESULTS, retries=RETRY_LIMIT):
    url = 'https://lite.duckduckgo.com/lite/'
    data = {
        'q': query
    }
    headers = {
        'User-Agent': USER_AGENT
    }
    for attempt in range(retries + 1):
        try:
            async with session.post(url, data=data, headers=headers, timeout=TIMEOUT) as response:
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError:
            if attempt < retries:
                await asyncio.sleep(RATE_LIMIT)
            else:
                return None

# Function to parse search results from HTML content
def parse_results(html_content, results=DEFAULT_RESULTS):
    if html_content is None:
        return []
    
    tree = html.fromstring(html_content)
    results_list = tree.xpath('//tr//td//a[@href]')
    if not results_list:
        return []
    
    links = []
    countLink = 0
    print()

    for a in results_list:
        href = a.get('href')
        if 'duckduckgo.com' not in href and 'reddit.com' not in href and 'youtube.com' not in href:
            countLink += 1
            print(f'Source URL number {countLink}: {href}')
            links.append(href)
            if len(links) == results:
                break
    print()
    countLink = 0
    return links

def _source_title_from_url(url):
    try:
        host = re.sub(r"^www\.", "", httpx.URL(url).host or "")
        return host or url
    except Exception:
        return url

def _source_metadata(url="", title=None, snippet="", source="web"):
    return {
        "title": (title or (_source_title_from_url(url) if url else source or "Sumber"))[:180],
        "url": url or "",
        "snippet": (snippet or "")[:260],
        "source": source
    }

def _source_header_payload_bytes(sources):
    return json.dumps(sources, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

def _encode_sources_header(sources):
    clean_sources = []
    seen = set()
    for item in sources or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()[:SOURCE_HEADER_MAX_URL]
        source = str(item.get("source") or "web")[:40] or "web"
        title = str(item.get("title") or "")[:180]
        snippet = str(item.get("snippet") or "")[:SOURCE_HEADER_MAX_SNIPPET]
        is_library_source = source == "library"
        if url and not re.match(r"^https?://", url, re.I):
            continue
        if not url and not is_library_source:
            continue
        key = url or f"{source}|{title}|{snippet[:120]}"
        if key in seen:
            continue
        seen.add(key)
        candidate = _source_metadata(
            url=url,
            title=title or None,
            snippet=snippet,
            source=source,
        )
        next_sources = clean_sources + [candidate]
        if len(base64.urlsafe_b64encode(_source_header_payload_bytes(next_sources)).decode("ascii")) > SOURCE_HEADER_MAX_BYTES:
            break
        clean_sources = next_sources
        if len(clean_sources) >= SOURCE_HEADER_MAX_ITEMS:
            break
    if not clean_sources:
        return ""
    payload = _source_header_payload_bytes(clean_sources)
    return base64.urlsafe_b64encode(payload).decode("ascii")

def _validate_public_http_url(url):
    value = str(url or "").strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("URL harus memakai http/https publik.")
    host = parsed.hostname.strip().rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise ValueError("URL localhost/internal tidak diizinkan.")
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError("Host URL tidak bisa di-resolve.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("URL internal/private tidak diizinkan.")
    return value

def _safe_location_url(base_url, location):
    if not location:
        raise ValueError("Redirect URL tidak valid.")
    return _validate_public_http_url(urljoin(base_url, location))

def _safe_httpx_get_public_url(url, **kwargs):
    current_url = _validate_public_http_url(url)
    headers = kwargs.pop("headers", None) or {"User-Agent": USER_AGENT}
    timeout = kwargs.pop("timeout", TIMEOUT)
    for _ in range(PUBLIC_FETCH_MAX_REDIRECTS + 1):
        response = httpx.get(current_url, headers=headers, timeout=timeout, follow_redirects=False, **kwargs)
        if 300 <= response.status_code < 400:
            current_url = _safe_location_url(current_url, response.headers.get("Location"))
            continue
        return response
    raise ValueError("Terlalu banyak redirect saat mengambil URL.")

def handle_search_payload(user_content, results=DEFAULT_RESULTS):
    query = user_content
    if not query:
        return "Please provide a search query", []

    try:
        links, formatted_texts = asyncio.run(get_duckduckgo_results_and_texts(query, results))
        if not links:
            return "No results found", []
        sources = [_source_metadata(link, source="web") for link in links]
        return _clamp_additional_text(''.join(formatted_texts)), sources
    except Exception as e:
        app.logger.warning("search_payload_error: %s", e)
        return "Pencarian web belum bisa diambil saat ini. Jawab dengan pengetahuan umum bila memungkinkan.", []

def clean_html_text(text):
    """Quick HTML text cleaning that preserves structure and readability"""
    try:
        tree = html.fromstring(text)
        
        # Remove script and style elements completely
        for element in tree.xpath('//script | //style'):
            element.getparent().remove(element)
        
        # Extract text content
        text_content = tree.text_content()
        
        # Quick and simple cleaning for speed
        # Normalize line breaks
        text_content = text_content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Split and quickly process lines
        lines = text_content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Strip and only add non-empty lines
            stripped = line.strip()
            if stripped:
                # Quick space normalization
                stripped = ' '.join(stripped.split())
                cleaned_lines.append(stripped)
        
        return '\n'.join(cleaned_lines)
    except Exception as e:
        # Return empty string if HTML parsing fails
        return ""

async def fetch_and_format_text(session, url, index, retries=RETRY_LIMIT):
    try:
        _validate_public_http_url(url)
    except ValueError:
        return ""
    for attempt in range(retries + 1):
        try:
            current_url = _validate_public_http_url(url)
            for _ in range(PUBLIC_FETCH_MAX_REDIRECTS + 1):
                async with session.get(
                    current_url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=TIMEOUT,
                    allow_redirects=False,
                ) as response:
                    if 300 <= response.status < 400:
                        current_url = _safe_location_url(current_url, response.headers.get("Location"))
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get('Content-Type', '')
                    if 'text/html' not in content_type:
                        return ""
                    html_content = await response.text()
                    cleaned_text = clean_html_text(html_content)
                    return _source_block(f"Source text {index} from website {current_url}", cleaned_text)
            return ""
        except (aiohttp.ClientError, ValueError, Exception):
            if attempt < retries:
                await asyncio.sleep(RATE_LIMIT)
            else:
                return ""

# Function to get DuckDuckGo search results and texts
async def get_duckduckgo_results_and_texts(query, results=DEFAULT_RESULTS):
    async with aiohttp.ClientSession() as session:
        html_content = await fetch_results(session, query, results)
        links = parse_results(html_content, results)
        if not links:
            return [], []
        tasks = [fetch_and_format_text(session, link, i + 1) for i, link in enumerate(links)]
        formatted_texts = await asyncio.gather(*tasks)
        return links, formatted_texts

def filter_reasoning_content(conversation_history, start_tag='<think>', end_tag='</think>'):
    """
    Filter out reasoning content (between start and end tags) from conversation history
    only if the assistant message starts with start tag and has a corresponding end tag.
    Only removes the first reasoning section between the first start tag and its end tag.
    """
    filtered_history = []
    for message in conversation_history:
        if not isinstance(message, dict):
            continue
        role = message.get('role')
        content = message.get('content')
        content = _strip_omitted_history_images(content)
        if isinstance(content, str) and not content.strip():
            continue
        if role == 'assistant' and isinstance(content, str):
            # Check if content starts with start_tag and contains end_tag
            if content.startswith(start_tag) and end_tag in content:
                # Find the first occurrence of end_tag
                first_end_pos = content.find(end_tag)
                if first_end_pos != -1:
                    # Keep content after the first end_tag
                    filtered_content = content[first_end_pos + len(end_tag):].strip()
                    if filtered_content:
                        filtered_history.append({'role': 'assistant', 'content': filtered_content})
                    else:
                        # If no content after end_tag, skip this message
                        continue
                else:
                    # If no end_tag found after start_tag, keep the entire message
                    filtered_history.append(message)
            else:
                # Keep the message as is if it doesn't start with start_tag or doesn't have end_tag
                filtered_history.append({'role': role, 'content': content})
        else:
            # Keep non-assistant messages as is
            if role in {"system", "user", "assistant"} and _is_valid_chat_content(content):
                filtered_history.append({'role': role, 'content': content})
    return filtered_history

def _strip_omitted_history_images(content):
    if not isinstance(content, list):
        return content
    clean_parts = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text":
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                clean_parts.append({"type": "text", "text": text})
        elif part_type == "image_url":
            image_url = part.get("image_url") if isinstance(part.get("image_url"), dict) else {}
            url = image_url.get("url")
            if not isinstance(url, str):
                continue
            if url == "[image omitted from history]" or url.startswith("data:image/"):
                continue
            clean_parts.append({"type": "image_url", "image_url": {"url": url}})
    if not clean_parts:
        return ""
    if not any(part.get("type") == "image_url" for part in clean_parts):
        return "\n\n".join(part.get("text", "") for part in clean_parts if part.get("type") == "text").strip()
    return clean_parts

def _is_valid_chat_content(content):
    if isinstance(content, str):
        return True
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, dict):
            return False
        part_type = part.get("type")
        if part_type == "text":
            if not isinstance(part.get("text"), str):
                return False
        elif part_type == "image_url":
            image_url = part.get("image_url")
            if not isinstance(image_url, dict) or not isinstance(image_url.get("url"), str):
                return False
        else:
            return False
    return True

def _clamp_chat_content(content, max_chars=HISTORY_TEXT_MAX_CHARS):
    if isinstance(content, str):
        return _clamp_text(content, max_chars)
    if not isinstance(content, list):
        return content
    clean_parts = []
    remaining = max_chars
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text":
            text = _clamp_text(part.get("text") or "", max(0, remaining))
            if text:
                clean_parts.append({"type": "text", "text": text})
                remaining -= len(text)
        elif part_type == "image_url":
            clean_parts.append(part)
        if remaining <= 0 and part_type == "text":
            break
    return clean_parts

def _validate_conversation_history(value, *, max_messages=HISTORY_MAX_MESSAGES):
    if value is None:
        return [], None
    if not isinstance(value, list):
        return [], "conversation must be an array"

    normalized = []
    allowed_roles = {"system", "user", "assistant"}
    for index, message in enumerate(value[-max_messages:]):
        if not isinstance(message, dict):
            return [], f"conversation[{index}] must be an object"
        role = message.get("role")
        content = message.get("content")
        if role not in allowed_roles:
            return [], f"conversation[{index}].role is invalid"
        if not _is_valid_chat_content(content):
            return [], f"conversation[{index}].content is invalid"
        normalized.append({"role": role, "content": _clamp_chat_content(content)})
    return normalized, None

# Function to handle web search command
def handle_search_command(user_content, results=DEFAULT_RESULTS):
    text, _sources = handle_search_payload(user_content, results)
    return text

# Function to handle YouTube command
def handle_youtube_command(user_content):
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',  # URLs
        r'^[a-zA-Z0-9_-]{11}$'  # Direct video ID
    ]
    
    video_id = None
    for pattern in patterns:
        match = re.search(pattern, user_content)
        if match:
            video_id = match.group(1) if len(match.groups()) > 0 else match.group(0)
            break
    
    if video_id:
        try:
            # Fetch the list of available transcripts
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            language_available = []
            for transcript in transcript_list:
              transcript_language = transcript.language_code
              language_available.append(transcript_language)
            
            # Check if there is an English transcript available
            if 'en' in language_available:
                transcript = transcript_list.find_transcript(['en']).fetch()
            else:
                # If no English transcript, get the first available language
                transcript = transcript_list.find_transcript([language_available[0]]).fetch()
            
            # Join the transcript entries into a single string with no newlines
            transcript_text = ' '.join(snippet.text for snippet in transcript.snippets)
            return _source_block("Source text from YouTube transcript", transcript_text)
        except Exception as e:
            app.logger.warning("youtube_transcript_error: %s", e)
            return "Transkrip YouTube belum bisa diambil saat ini."
    else:
        return "Please provide a valid YouTube URL or video ID"


# Function to handle webpage command
def handle_webpage_command(user_content):
    """Handle general webpage URLs, returning the extracted text."""
    pattern = r'https?://[^\s]+'
    match = re.search(pattern, user_content)
    
    if not match:
        return None
        
    url = match.group(0)
    try:
        response = _safe_httpx_get_public_url(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        response.raise_for_status()
        
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            return ""
        
        cleaned_text = clean_html_text(response.text)

        return _source_block(f"Source text from website {url}", cleaned_text)
    except httpx.HTTPStatusError as e:
        # Specifically handle HTTP errors like 404, 403, etc., after following redirects
        raise Exception(f"HTTP error {e.response.status_code} while fetching the webpage: {e}")
    except httpx.RequestError as e:
        # Handle network errors, timeouts, etc.
        raise Exception(f"Network error occurred while fetching the webpage: {e}")
    except Exception as e:
        # Handle any other unexpected errors during fetching/parsing
        raise Exception(f"An unexpected error occurred while fetching the webpage: {e}")

def handle_arxiv_command(user_content):
    """Handle arXiv PDF and abstract URLs, returning the extracted text."""
    arxiv_pattern = r'https?://arxiv\.org/(abs|pdf)/\d+\.\d+(v\d+)?'
    arxiv_match = re.search(arxiv_pattern, user_content)
    
    if not arxiv_match:
        return None
        
    arxiv_link = arxiv_match.group(0)
    arxiv_type = arxiv_match.group(1)  # 'abs' or 'pdf'
    
    try:
        response = _safe_httpx_get_public_url(arxiv_link, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        response.raise_for_status()
        
        if arxiv_type == 'abs':
            # Extract abstract from HTML
            text = response.text
            start_marker = "Abstract:</span>"
            end_marker = "Comments:"
            start_index = text.find(start_marker) + len(start_marker)
            end_index = text.find(end_marker, start_index)
            
            if start_index == -1 or end_index == -1:
                raise Exception("Abstract not found in the response.")
            
            return _source_block(f"Source text from arXiv {arxiv_link}", text[start_index:end_index].strip())
        else:
            # Handle PDF
            pdf_file = BytesIO(response.content)
            pdf_document = fitz.open(stream=pdf_file, filetype="pdf")
            return _source_block(f"Source text from arXiv {arxiv_link}", " ".join(page.get_text() for page in pdf_document))
            
    except Exception as e:
        raise Exception(f"Failed to process arXiv {arxiv_type}: {str(e)}")

def _device_signature(device_id):
    return hmac.new(DEVICE_SECRET.encode("utf-8"), device_id.encode("utf-8"), hashlib.sha256).hexdigest()

def _sign_device_id(device_id):
    return f"{device_id}.{_device_signature(device_id)}"

def _verify_device_cookie(cookie_value):
    if not cookie_value or "." not in cookie_value:
        return None
    device_id, signature = cookie_value.split(".", 1)
    if not re.fullmatch(r"[a-f0-9]{32}", device_id or ""):
        return None
    if hmac.compare_digest(signature, _device_signature(device_id)):
        return device_id
    return None

def _get_or_create_device_id():
    device_id = _verify_device_cookie(request.cookies.get(DEVICE_COOKIE))
    if device_id:
        return device_id, False
    device_id = secrets.token_hex(16)
    g.hai_device_id_to_set = device_id
    return device_id, True

def _queue_device_cookie_if_missing():
    if _verify_device_cookie(request.cookies.get(DEVICE_COOKIE)):
        return
    if not getattr(g, "hai_device_id_to_set", None):
        g.hai_device_id_to_set = secrets.token_hex(16)

def _response_already_sets_device_cookie(response):
    for value in response.headers.getlist("Set-Cookie"):
        if value.startswith(f"{DEVICE_COOKIE}="):
            return True
    return False

def _set_device_cookie(response, device_id):
    response.set_cookie(
        DEVICE_COOKIE,
        _sign_device_id(device_id),
        max_age=60 * 60 * 24 * 365,
        secure=True,
        httponly=True,
        samesite="Lax",
        path="/",
    )
    return response

def _response_with_device_cookie(payload, device_id, should_set_cookie, status=200, headers=None):
    response = make_response(jsonify(payload), status)
    for name, value in (headers or {}).items():
        response.headers[name] = value
    if should_set_cookie:
        _set_device_cookie(response, device_id)
    return response

@app.after_request
def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "worker-src 'self' blob:; "
        "media-src 'self' blob:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'",
    )
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.path.startswith(("/api/", "/chat", "/continue_generation", "/generate-title", "/save-settings")):
        response.headers.setdefault("Cache-Control", "no-store")
    queued_device_id = getattr(g, "hai_device_id_to_set", None)
    if queued_device_id and not _response_already_sets_device_cookie(response):
        _set_device_cookie(response, queued_device_id)
    return response

def _json_error(error, message, status=400, extra=None):
    payload = {"ok": False, "error": error, "message": message}
    if extra:
        payload.update(extra)
    return jsonify(payload), status

def _client_rate_key(scope):
    device_id = _verify_device_cookie(request.cookies.get(DEVICE_COOKIE))
    if not device_id:
        _queue_device_cookie_if_missing()
    forwarded_for = ""
    if TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For", "")
    ip = forwarded_for.split(",", 1)[0].strip() or request.remote_addr or "unknown"
    return f"{scope}:{device_id or ip}"

@contextmanager
def _rate_limit_store_lock():
    rate_dir = os.path.dirname(RATE_LIMIT_FILE_PATH) or DATA_DIR
    os.makedirs(rate_dir, exist_ok=True)
    lock_path = f"{RATE_LIMIT_FILE_PATH}.lock"
    with _rate_file_lock:
        lock_file = open(lock_path, "a+", encoding="utf-8")
        try:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

def _load_rate_limit_store():
    try:
        with open(RATE_LIMIT_FILE_PATH, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict) and isinstance(data.get("buckets"), dict):
                return data
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as error:
        app.logger.warning("rate_limit_store_read_error: %s", error)
    return {"version": 1, "buckets": {}}

def _safe_file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0

def _safe_dir_json_count(path):
    try:
        return sum(1 for name in os.listdir(path) if str(name).endswith(".json"))
    except OSError:
        return 0

def _admin_overview_snapshot():
    now_ms = int(time.time() * 1000)
    try:
        with _history_store_lock():
            history_store = _load_history_store()
    except OSError as error:
        app.logger.warning("admin_overview_history_unavailable: %s", error)
        history_store = {"devices": {}}
    history_devices = history_store.get("devices", {}) if isinstance(history_store.get("devices"), dict) else {}
    history_chat_count = 0
    history_message_count = 0
    active_chat_devices = 0
    history_user_message_count = 0
    history_assistant_message_count = 0
    history_attachment_count = 0
    history_artifact_count = 0
    history_source_count = 0
    active_chats_24h = 0
    active_chats_7d = 0
    latest_chat_updated = 0
    for device_record in history_devices.values():
        if not isinstance(device_record, dict):
            continue
        history_payload = device_record.get("history") if isinstance(device_record.get("history"), dict) else device_record
        chats = history_payload.get("chats") if isinstance(history_payload.get("chats"), list) else []
        if chats:
            active_chat_devices += 1
        history_chat_count += len(chats)
        for chat in chats:
            if not isinstance(chat, dict):
                continue
            try:
                updated_ms = int(chat.get("updated") or chat.get("createdAt") or 0)
            except (TypeError, ValueError):
                updated_ms = 0
            if updated_ms > 0:
                latest_chat_updated = max(latest_chat_updated, updated_ms)
                if updated_ms >= now_ms - 24 * 60 * 60 * 1000:
                    active_chats_24h += 1
                if updated_ms >= now_ms - 7 * 24 * 60 * 60 * 1000:
                    active_chats_7d += 1
            if isinstance(chat.get("messages"), list):
                messages = chat.get("messages") or []
                history_message_count += len(messages)
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    role = str(message.get("role") or "").lower()
                    if role == "user":
                        history_user_message_count += 1
                    elif role == "assistant":
                        history_assistant_message_count += 1
                    attachments = message.get("attachments")
                    if isinstance(attachments, list):
                        history_attachment_count += len(attachments)
                    elif isinstance(attachments, dict):
                        history_attachment_count += 1
                    artifacts = message.get("artifacts")
                    if isinstance(artifacts, list):
                        history_artifact_count += len(artifacts)
                    elif isinstance(artifacts, dict):
                        history_artifact_count += 1
                    sources = message.get("sources")
                    if isinstance(sources, list):
                        history_source_count += len(sources)

    try:
        with _library_store_lock():
            library_store = _load_library_store()
    except OSError as error:
        app.logger.warning("admin_overview_library_unavailable: %s", error)
        library_store = {"devices": {}}
    library_devices = library_store.get("devices", {}) if isinstance(library_store.get("devices"), dict) else {}
    library_document_count = 0
    library_text_chars = 0
    library_indexed_chunks = 0
    for device_record in library_devices.values():
        if not isinstance(device_record, dict):
            continue
        documents = device_record.get("documents") if isinstance(device_record.get("documents"), list) else []
        library_document_count += len(documents)
        for doc in documents:
            if not isinstance(doc, dict):
                continue
            try:
                library_text_chars += int(doc.get("text_chars") or len(doc.get("text") or ""))
            except (TypeError, ValueError):
                pass
            chunks = doc.get("chunks") if isinstance(doc.get("chunks"), list) else []
            library_indexed_chunks += len(chunks)

    rate_buckets = {}
    if RATE_LIMIT_STORAGE == "file":
        try:
            with _rate_limit_store_lock():
                rate_store = _load_rate_limit_store()
        except OSError as error:
            app.logger.warning("admin_overview_rate_limit_unavailable: %s", error)
            rate_store = {"buckets": {}}
        rate_buckets = rate_store.get("buckets", {}) if isinstance(rate_store.get("buckets"), dict) else {}

    realtime_records = _safe_dir_json_count(REALTIME_EVENT_DIR)
    return {
        "ok": True,
        "service": "harmonika-chat-webui",
        "generated_at": now_ms,
        "privacy": {
            "aggregate_only": True,
            "no_chat_content": True,
            "no_document_text": True,
            "no_device_ids": True,
            "no_secrets": True,
        },
        "storage": {
            "history_file_bytes": _safe_file_size(HISTORY_FILE),
            "library_file_bytes": _safe_file_size(LIBRARY_FILE),
            "rate_limit_file_bytes": _safe_file_size(RATE_LIMIT_FILE_PATH) if RATE_LIMIT_STORAGE == "file" else 0,
            "realtime_event_files": realtime_records,
        },
        "history": {
            "devices": len(history_devices),
            "devices_with_chats": active_chat_devices,
            "chats": history_chat_count,
            "messages": history_message_count,
            "max_devices": HISTORY_MAX_DEVICES,
            "max_chats_per_device": HISTORY_MAX_CHATS,
        },
        "analytics": {
            "mode": "aggregate_only_no_content",
            "active_chats_24h": active_chats_24h,
            "active_chats_7d": active_chats_7d,
            "latest_chat_updated": latest_chat_updated,
            "user_messages": history_user_message_count,
            "assistant_messages": history_assistant_message_count,
            "attachment_messages": history_attachment_count,
            "image_artifacts": history_artifact_count,
            "source_references": history_source_count,
            "avg_messages_per_chat": round(history_message_count / history_chat_count, 2) if history_chat_count else 0,
            "library_docs_per_device": round(library_document_count / len(library_devices), 2) if library_devices else 0,
        },
        "library": {
            "devices": len(library_devices),
            "documents": library_document_count,
            "indexed_chunks": library_indexed_chunks,
            "text_chars": library_text_chars,
            "retrieval_mode": LIBRARY_RETRIEVAL_MODE,
            "ranking_mode": LIBRARY_RANKING_MODE,
            "vector_mode": "private_local_hash_embedding",
            "vector_dimensions": LIBRARY_VECTOR_DIMS,
            "max_documents_per_device": LIBRARY_MAX_DOCS_PER_DEVICE,
        },
        "realtime": {
            "replay_api": True,
            "replay_state": True,
            "event_files": realtime_records,
            "ttl_seconds": REALTIME_EVENT_TTL_SECONDS,
            "max_events_per_response": REALTIME_EVENT_MAX_EVENTS,
            "wss_ready": REALTIME_WSS_READY,
        },
        "rate_limit": {
            "storage": RATE_LIMIT_STORAGE,
            "shared_across_workers": RATE_LIMIT_STORAGE == "file",
            "bucket_count": len(rate_buckets),
            "max_keys": RATE_LIMIT_MAX_KEYS,
        },
    }

def _save_rate_limit_store(store):
    rate_dir = os.path.dirname(RATE_LIMIT_FILE_PATH) or DATA_DIR
    os.makedirs(rate_dir, exist_ok=True)
    tmp_handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=rate_dir, prefix="rate-limits.", suffix=".tmp", delete=False)
    tmp_file = tmp_handle.name
    with tmp_handle as file:
        json.dump(store, file, ensure_ascii=False, separators=(",", ":"))
        file.flush()
        os.fsync(file.fileno())
    os.replace(tmp_file, RATE_LIMIT_FILE_PATH)

def _prune_rate_limit_store(buckets, max_keys=RATE_LIMIT_MAX_KEYS):
    if len(buckets) <= max_keys:
        return
    sorted_items = sorted(
        buckets.items(),
        key=lambda item: max(item[1] or [0]) if isinstance(item[1], list) else 0,
        reverse=True,
    )
    buckets.clear()
    buckets.update(dict(sorted_items[:max_keys]))

def _check_rate_limit_memory(key, limit, window_seconds, now):
    bucket = _rate_buckets[key]
    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    if len(_rate_buckets) > RATE_LIMIT_MAX_KEYS:
        for old_key in list(_rate_buckets.keys()):
            old_bucket = _rate_buckets[old_key]
            while old_bucket and old_bucket[0] <= now - window_seconds:
                old_bucket.popleft()
            if not old_bucket:
                _rate_buckets.pop(old_key, None)
            if len(_rate_buckets) <= RATE_LIMIT_MAX_KEYS:
                break
        while len(_rate_buckets) > RATE_LIMIT_MAX_KEYS:
            _rate_buckets.pop(next(iter(_rate_buckets)), None)
    if len(bucket) >= limit:
        retry_after = max(1, int(window_seconds - (now - bucket[0])))
        return False, retry_after
    bucket.append(now)
    return True, 0

def _check_rate_limit_file(key, limit, window_seconds, now):
    try:
        with _rate_limit_store_lock():
            store = _load_rate_limit_store()
            buckets = store.setdefault("buckets", {})
            raw_bucket = buckets.get(key, [])
            if not isinstance(raw_bucket, list):
                raw_bucket = []
            bucket = []
            for item in raw_bucket[-max(limit * 2, 10):]:
                try:
                    timestamp = float(item)
                except (TypeError, ValueError):
                    continue
                if timestamp > now - window_seconds:
                    bucket.append(timestamp)
            if len(bucket) >= limit:
                buckets[key] = bucket
                _prune_rate_limit_store(buckets)
                _save_rate_limit_store(store)
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
            buckets[key] = bucket
            _prune_rate_limit_store(buckets)
            _save_rate_limit_store(store)
            return True, 0
    except OSError as error:
        app.logger.warning("rate_limit_file_fallback_memory: %s", error)
        return _check_rate_limit_memory(key, limit, window_seconds, now)

def _check_rate_limit(scope, limit_tuple):
    limit, window_seconds = limit_tuple
    now = time.time()
    key = _client_rate_key(scope)
    if RATE_LIMIT_STORAGE == "file":
        return _check_rate_limit_file(key, limit, window_seconds, now)
    return _check_rate_limit_memory(key, limit, window_seconds, now)

def _rate_limited_response(retry_after):
    response, status = _json_error(
        "rate_limited",
        "Terlalu banyak request. Tunggu sebentar lalu coba lagi.",
        429,
        {"retry_after": retry_after},
    )
    response.headers["Retry-After"] = str(retry_after)
    return response, status

def _get_json_payload(max_body):
    if request.content_length and request.content_length > max_body:
        return None, _json_error(
            "payload_too_large",
            "Request terlalu besar.",
            413,
            {"max_bytes": max_body},
        )
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, _json_error("invalid_json", "Format JSON tidak valid.", 400)
    return payload, None

def _load_history_store():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict) and isinstance(data.get("devices"), dict):
                return data
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as error:
        app.logger.warning("history_store_json_decode_error: %s", error)
    except OSError as error:
        app.logger.warning("history_store_read_error: %s", error)
    return {"version": 1, "devices": {}}

@contextmanager
def _history_store_lock():
    os.makedirs(DATA_DIR, exist_ok=True)
    lock_path = f"{HISTORY_FILE}.lock"
    with _history_lock:
        lock_file = open(lock_path, "a+", encoding="utf-8")
        try:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

def _save_history_store(store):
    os.makedirs(DATA_DIR, exist_ok=True)
    devices = store.setdefault("devices", {})
    if len(devices) > HISTORY_MAX_DEVICES:
        sorted_items = sorted(
            devices.items(),
            key=lambda item: item[1].get("updated", 0) if isinstance(item[1], dict) else 0,
            reverse=True,
        )
        store["devices"] = dict(sorted_items[:HISTORY_MAX_DEVICES])
    tmp_handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=DATA_DIR, prefix="chatwebui-history.", suffix=".tmp", delete=False)
    tmp_file = tmp_handle.name
    with tmp_handle as file:
        json.dump(store, file, ensure_ascii=False, separators=(",", ":"))
        file.flush()
        os.fsync(file.fileno())
    os.replace(tmp_file, HISTORY_FILE)

def _load_library_store():
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict) and isinstance(data.get("devices"), dict):
                return data
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as error:
        app.logger.warning("library_store_json_decode_error: %s", error)
    except OSError as error:
        app.logger.warning("library_store_read_error: %s", error)
    return {"version": 1, "devices": {}}

@contextmanager
def _library_store_lock():
    os.makedirs(DATA_DIR, exist_ok=True)
    lock_path = f"{LIBRARY_FILE}.lock"
    with _library_lock:
        lock_file = open(lock_path, "a+", encoding="utf-8")
        try:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

def _save_library_store(store):
    os.makedirs(DATA_DIR, exist_ok=True)
    devices = store.setdefault("devices", {})
    if len(devices) > HISTORY_MAX_DEVICES:
        sorted_items = sorted(
            devices.items(),
            key=lambda item: item[1].get("updated", 0) if isinstance(item[1], dict) else 0,
            reverse=True,
        )
        store["devices"] = dict(sorted_items[:HISTORY_MAX_DEVICES])
    tmp_handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=DATA_DIR, prefix="rag-library.", suffix=".tmp", delete=False)
    tmp_file = tmp_handle.name
    with tmp_handle as file:
        json.dump(store, file, ensure_ascii=False, separators=(",", ":"))
        file.flush()
        os.fsync(file.fileno())
    os.replace(tmp_file, LIBRARY_FILE)

def _clean_text(value, max_len=HISTORY_MAX_TEXT):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value[:max_len]

def _clamp_text(value, max_chars, marker="… [dipotong agar respons tetap stabil]"):
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    keep = max(0, max_chars - len(marker))
    return value[:keep].rstrip() + marker

def _source_block(label, text, max_chars=SOURCE_TEXT_MAX_CHARS):
    clean = _clamp_text(text or "", max_chars)
    if not clean.strip():
        return ""
    return f"{label}: \n \n {clean} \n \n"

def _clamp_additional_text(text):
    return _clamp_text(text or "", ADDITIONAL_TEXT_MAX_CHARS)

def _sanitize_memory_context(value):
    if not value:
        return ""
    if isinstance(value, list):
        lines = []
        for item in value[:12]:
            if isinstance(item, dict):
                text = item.get("text") or item.get("value") or ""
            else:
                text = item
            text = _clean_text(text, 180).strip()
            if text:
                lines.append(f"- {text}")
        return "\n".join(lines)[:MEMORY_CONTEXT_MAX_TEXT]
    if isinstance(value, str):
        clean = _clean_text(value, MEMORY_CONTEXT_MAX_TEXT).strip()
        clean_lines = [line.strip() for line in clean.splitlines() if line.strip()]
        return "\n".join(clean_lines[:12])[:MEMORY_CONTEXT_MAX_TEXT]
    return ""

def _apply_memory_context(system_content, memory_context):
    memory_context = _sanitize_memory_context(memory_context)
    if not memory_context:
        return system_content
    memory_block = (
        "\n\nKonteks memory ringan pengguna dari device ini:\n"
        f"{memory_context}\n\n"
        "Gunakan konteks memory hanya bila relevan untuk membantu jawaban. "
        "Jangan menyebut bahwa Anda memakai memory, jangan menganggapnya selalu benar bila user mengoreksi, "
        "dan jangan memakai memory untuk topik sensitif atau keputusan berisiko."
    )
    return f"{system_content or SYSTEM_CONTENT}{memory_block}"

def _sanitize_multimodal_content(content):
    clean_items = []
    if not isinstance(content, list):
        return clean_items
    for item in content[:20]:
        if not isinstance(item, dict):
            continue
        item_type = _clean_text(item.get("type"), 40)
        if item_type == "text":
            clean_items.append({"type": "text", "text": _clean_text(item.get("text"), 4000)})
        elif item_type == "image_url":
            image_url = item.get("image_url") if isinstance(item.get("image_url"), dict) else {}
            url = image_url.get("url", "")
            if isinstance(url, str) and url.startswith("data:image/"):
                url = "[image omitted from history]"
            else:
                url = _clean_text(url, 2048)
            clean_items.append({"type": "image_url", "image_url": {"url": url}})
        else:
            clean_items.append({"type": item_type or "attachment"})
    return clean_items

def _sanitize_sources(sources):
    clean_sources = []
    seen = set()
    if not isinstance(sources, list):
        return clean_sources
    for item in sources[:6]:
        if not isinstance(item, dict):
            continue
        url = _clean_text(item.get("url"), 2048).strip()
        if url and not re.match(r"^https?://", url, re.I):
            url = ""
        title = _clean_text(item.get("title") or (_source_title_from_url(url) if url else item.get("source")) or "Sumber", 180)
        source = _clean_text(item.get("source") or "web", 40)
        snippet = _clean_text(item.get("snippet"), 260)
        domain = _clean_text(item.get("domain"), 120)
        key = url or f"{title}|{source}|{snippet[:80]}".lower()
        if not key or key in seen:
            continue
        seen.add(key)
        source_item = {
            "title": title,
            "snippet": snippet,
            "source": source,
        }
        if url:
            source_item["url"] = url
        if domain:
            source_item["domain"] = domain
        clean_sources.append(source_item)
    return clean_sources

def _safe_attachment_name(value):
    name = os.path.basename(str(value or "attachment"))
    name = re.sub(r"[\x00-\x1f\x7f/\\]+", "", name).strip()
    return name[:180] or "attachment"

def _xlsx_cell_text(cell, shared_strings):
    cell_type = cell.attrib.get("t", "")
    value = ""
    if cell_type == "inlineStr":
        texts = [node.text or "" for node in cell.findall(".//{*}t")]
        value = " ".join(texts)
    else:
        node = cell.find("{*}v")
        value = node.text if node is not None and node.text is not None else ""
        if cell_type == "s":
            try:
                value = shared_strings[int(value)]
            except Exception:
                value = ""
    return re.sub(r"\s+", " ", value).strip()

def _extract_xlsx_text(file_bytes, max_chars=HISTORY_MAX_TEXT):
    output = []
    total = 0
    with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall(".//{*}si"):
                text = " ".join((node.text or "") for node in item.findall(".//{*}t"))
                shared_strings.append(re.sub(r"\s+", " ", text).strip())
        sheet_names = sorted(name for name in archive.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", name))
        for sheet_index, sheet_name in enumerate(sheet_names[:8], 1):
            root = ET.fromstring(archive.read(sheet_name))
            output.append(f"Sheet {sheet_index}:")
            for row in root.findall(".//{*}row")[:200]:
                cells = [_xlsx_cell_text(cell, shared_strings) for cell in row.findall("{*}c")]
                line = " | ".join(cell for cell in cells if cell)
                if not line:
                    continue
                output.append(line)
                total += len(line)
                if total >= max_chars:
                    return "\n".join(output)[:max_chars]
    return "\n".join(output)[:max_chars].strip()

def _extract_docx_text(file_bytes, max_chars=HISTORY_MAX_TEXT):
    with zipfile.ZipFile(BytesIO(file_bytes)) as archive:
        if "word/document.xml" not in archive.namelist():
            return ""
        root = ET.fromstring(archive.read("word/document.xml"))
        lines = []
        for paragraph in root.findall(".//{*}p"):
            text = " ".join((node.text or "") for node in paragraph.findall(".//{*}t"))
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                lines.append(text)
            if sum(len(line) for line in lines) >= max_chars:
                break
        return "\n".join(lines)[:max_chars].strip()

def _extract_pdf_text(file_bytes, max_chars=HISTORY_MAX_TEXT):
    with fitz.open(stream=file_bytes, filetype="pdf") as pdf_document:
        if pdf_document.page_count > 50:
            raise ValueError("PDF maksimal 50 halaman.")
        text = []
        for page in pdf_document:
            text.append(page.get_text())
            if sum(len(item) for item in text) >= max_chars:
                break
        return "\n".join(text)[:max_chars].strip()

def _extract_attachment_text(file_bytes, name, mime):
    ext = os.path.splitext(name.lower())[1]
    mime = (mime or "").lower()
    if ext == ".pdf" or mime == "application/pdf":
        return _extract_pdf_text(file_bytes)
    if ext == ".docx" or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx_text(file_bytes)
    if ext == ".xlsx" or mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        return _extract_xlsx_text(file_bytes)
    if ext in (".txt", ".csv") or mime.startswith("text/") or mime in ("application/csv", "application/vnd.ms-excel"):
        text = file_bytes[:HISTORY_MAX_TEXT].decode("utf-8", errors="replace")
        return text.strip()
    raise ValueError("Format file belum didukung.")

def _library_public_document(doc):
    if not isinstance(doc, dict):
        return None
    text = _clean_text(doc.get("text") or "", LIBRARY_MAX_TEXT)
    preview = re.sub(r"\s+", " ", text).strip()[:LIBRARY_SNIPPET_CHARS]
    return {
        "id": _clean_text(doc.get("id"), 80),
        "name": _safe_attachment_name(doc.get("name")),
        "mime": _clean_text(doc.get("mime"), 120),
        "size_bytes": int(doc.get("size_bytes", 0) or 0),
        "text_chars": len(text),
        "preview": preview,
        "created": int(doc.get("created", 0) or 0),
        "updated": int(doc.get("updated", 0) or 0),
    }

def _library_tokenize(value):
    return [
        item.lower()
        for item in re.findall(r"[\wÀ-ÿ]{2,}", value or "", flags=re.UNICODE)
    ][:64]

LIBRARY_SEMANTIC_ALIASES = {
    "router": ["gateway", "modem", "wifi", "jaringan", "internet"],
    "gateway": ["router", "modem", "jaringan", "internet"],
    "modem": ["router", "gateway", "wifi", "internet"],
    "wifi": ["router", "modem", "wireless", "internet"],
    "wireless": ["wifi", "router", "jaringan"],
    "jaringan": ["network", "router", "gateway", "internet", "koneksi"],
    "network": ["jaringan", "router", "gateway"],
    "koneksi": ["internet", "jaringan", "wifi"],
    "internet": ["router", "modem", "gateway", "koneksi", "jaringan"],
    "tagihan": ["invoice", "billing", "pembayaran", "bayar"],
    "invoice": ["tagihan", "billing", "pembayaran"],
    "billing": ["tagihan", "invoice", "pembayaran"],
    "pembayaran": ["tagihan", "bayar", "invoice"],
    "bayar": ["pembayaran", "tagihan", "invoice"],
    "promo": ["promosi", "diskon", "penawaran", "campaign", "kampanye"],
    "promosi": ["promo", "diskon", "penawaran", "campaign", "kampanye"],
    "campaign": ["kampanye", "promosi", "promo"],
    "kampanye": ["campaign", "promosi", "promo"],
    "kode": ["code", "token", "verifikasi"],
    "code": ["kode", "token", "verification"],
    "verifikasi": ["verification", "kode", "token"],
    "dokumen": ["document", "file", "berkas"],
    "document": ["dokumen", "file", "berkas"],
    "berkas": ["file", "dokumen", "document"],
}

def _library_expand_query_terms(terms):
    unique_terms = list(dict.fromkeys(term for term in terms if term))
    weighted = {}
    for term in unique_terms:
        weighted[term] = max(weighted.get(term, 0.0), 1.0)
        if not LIBRARY_SEMANTIC_EXPANSION_ENABLED:
            continue
        for alias in LIBRARY_SEMANTIC_ALIASES.get(term, []):
            if alias and alias not in weighted:
                weighted[alias] = 0.62
    return weighted

def _library_snippet(text, terms, max_chars=LIBRARY_SNIPPET_CHARS):
    clean = re.sub(r"\s+", " ", _clean_text(text or "", LIBRARY_MAX_TEXT)).strip()
    if not clean:
        return ""
    chunk_chars = max(max_chars, min(max(LIBRARY_CHUNK_CHARS, max_chars), 6000))
    overlap = max(0, min(LIBRARY_CHUNK_OVERLAP, chunk_chars // 2))
    terms = [term.lower() for term in dict.fromkeys(terms or []) if term]
    if not terms:
        return clean[:max_chars].strip()
    best = {"score": -1, "start": 0, "text": clean[:chunk_chars]}
    step = max(1, chunk_chars - overlap)
    lower = clean.lower()
    for start in range(0, len(clean), step):
        chunk = clean[start:start + chunk_chars]
        chunk_lower = lower[start:start + chunk_chars]
        matched_count = sum(1 for term in terms if term in chunk_lower)
        frequency = sum(min(chunk_lower.count(term), 8) for term in terms)
        score = matched_count * 100 + frequency
        if score > best["score"]:
            best = {"score": score, "start": start, "text": chunk}
        if start + chunk_chars >= len(clean):
            break
    best_text = best["text"]
    best_lower = best_text.lower()
    positions = [best_lower.find(term) for term in terms if best_lower.find(term) >= 0]
    local_start = max(0, min(positions) - 100) if positions else 0
    start = best["start"] + local_start
    snippet = clean[start:start + max_chars].strip()
    if start > 0:
        snippet = "…" + snippet
    if start + max_chars < len(clean):
        snippet += "…"
    return snippet

def _library_chunks(text):
    clean = re.sub(r"\s+", " ", _clean_text(text or "", LIBRARY_MAX_TEXT)).strip()
    if not clean:
        return []
    chunk_chars = max(LIBRARY_SNIPPET_CHARS, min(max(LIBRARY_CHUNK_CHARS, LIBRARY_SNIPPET_CHARS), 6000))
    overlap = max(0, min(LIBRARY_CHUNK_OVERLAP, chunk_chars // 2))
    step = max(1, chunk_chars - overlap)
    chunks = []
    for start in range(0, len(clean), step):
        chunk_text = clean[start:start + chunk_chars]
        if not chunk_text:
            continue
        chunks.append({
            "index": len(chunks),
            "start": start,
            "text": chunk_text,
            "lower": chunk_text.lower(),
        })
        if start + chunk_chars >= len(clean):
            break
    return chunks

def _library_sparse_vector(text, max_terms=96):
    tokens = [
        item.lower()
        for item in re.findall(r"[\wÀ-ÿ]{2,}", text or "", flags=re.UNICODE)
    ]
    counts = {}
    for token in tokens:
        counts[token] = min(999, counts.get(token, 0) + 1)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:max_terms])

def _library_hash_vector_from_weights(term_weights, dims=None):
    dims = max(16, min(512, int(dims or LIBRARY_VECTOR_DIMS or 96)))
    vector = [0.0] * dims
    for term, weight in (term_weights or {}).items():
        term = str(term or "").strip().lower()
        if not term:
            continue
        digest = hashlib.blake2b(term.encode("utf-8", errors="ignore"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if (digest[4] & 1) else -1.0
        vector[bucket] += sign * float(weight or 0.0)
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]

def _library_hash_vector(text, dims=None):
    sparse = _library_sparse_vector(text, max_terms=512)
    return _library_hash_vector_from_weights(sparse, dims=dims)

def _library_vector_cosine(left, right):
    if not isinstance(left, list) or not isinstance(right, list) or not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for index in range(size):
        try:
            l_value = float(left[index] or 0.0)
            r_value = float(right[index] or 0.0)
        except (TypeError, ValueError):
            continue
        dot += l_value * r_value
        left_norm += l_value * l_value
        right_norm += r_value * r_value
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return max(0.0, min(1.0, dot / (math.sqrt(left_norm) * math.sqrt(right_norm))))

def _library_build_chunk_index(text):
    indexed = []
    for chunk in _library_chunks(text):
        chunk_text = chunk.get("text") or ""
        indexed.append({
            "index": int(chunk.get("index", len(indexed))),
            "start": int(chunk.get("start", 0) or 0),
            "text": chunk_text,
            "token_count": len(re.findall(r"[\wÀ-ÿ]{2,}", chunk_text, flags=re.UNICODE)),
            "vector": _library_sparse_vector(chunk_text),
            "embedding": _library_hash_vector(chunk_text),
        })
    return indexed

def _library_document_chunks(doc):
    stored_chunks = doc.get("chunks")
    if isinstance(stored_chunks, list) and stored_chunks:
        chunks = []
        for fallback_index, chunk in enumerate(stored_chunks):
            if not isinstance(chunk, dict):
                continue
            text = _clean_text(chunk.get("text") or "", LIBRARY_CHUNK_CHARS + 200).strip()
            if not text:
                continue
            chunks.append({
                "index": int(chunk.get("index", fallback_index) or 0),
                "start": int(chunk.get("start", 0) or 0),
                "text": text,
                "lower": text.lower(),
                "token_count": int(chunk.get("token_count", 0) or len(re.findall(r"[\wÀ-ÿ]{2,}", text, flags=re.UNICODE))),
                "vector": chunk.get("vector") if isinstance(chunk.get("vector"), dict) else _library_sparse_vector(text),
                "embedding": chunk.get("embedding") if isinstance(chunk.get("embedding"), list) else _library_hash_vector(text),
            })
        if chunks:
            return chunks
    return [
        {
            **chunk,
            "token_count": len(re.findall(r"[\wÀ-ÿ]{2,}", chunk.get("text") or "", flags=re.UNICODE)),
            "vector": _library_sparse_vector(chunk.get("text") or ""),
            "embedding": _library_hash_vector(chunk.get("text") or ""),
        }
        for chunk in _library_chunks(doc.get("text") or "")
    ]

def _library_score_chunk(chunk_lower, term_weights, phrase="", vector=None, idf_weights=None, avg_chunk_len=1.0, chunk_len=None, query_embedding=None, chunk_embedding=None):
    matched_terms = []
    primary_matches = []
    semantic_matches = []
    frequency = 0
    weighted_match_score = 0.0
    vector = vector if isinstance(vector, dict) else {}
    idf_weights = idf_weights if isinstance(idf_weights, dict) else {}
    chunk_len = max(1, int(chunk_len or 0) or sum(int(value or 0) for value in vector.values()) or len(re.findall(r"[\wÀ-ÿ]{2,}", chunk_lower or "", flags=re.UNICODE)))
    avg_chunk_len = max(1.0, float(avg_chunk_len or 1.0))
    k1 = 1.25
    b = 0.74
    bm25_score = 0.0
    for term, weight in term_weights.items():
        count = int(vector.get(term, 0) or 0)
        if not count:
            count = chunk_lower.count(term)
        if count:
            matched_terms.append(term)
            weighted_match_score += float(weight)
            frequency += min(count, 6)
            length_norm = k1 * (1 - b + b * (chunk_len / avg_chunk_len))
            bm25_score += float(weight) * float(idf_weights.get(term, 1.0)) * ((count * (k1 + 1)) / (count + length_norm))
            if weight >= 1:
                primary_matches.append(term)
            else:
                semantic_matches.append(term)
    if not matched_terms:
        vector_similarity = _library_vector_cosine(query_embedding, chunk_embedding)
        if vector_similarity <= 0:
            return 0, matched_terms, 0.0, semantic_matches, 0.0
        # Vector-only matches are allowed as weak recall, but exact/semantic
        # term coverage above still dominates final ranking.
        return int(vector_similarity * 120), matched_terms, 0.0, semantic_matches, vector_similarity
    primary_count = sum(1 for weight in term_weights.values() if weight >= 1)
    coverage = len(primary_matches) / max(1, primary_count)
    semantic_bonus = min(sum(term_weights.get(term, 0) for term in semantic_matches), 3.0) * 120
    phrase_bonus = 240 if phrase and phrase in chunk_lower else 0
    vector_similarity = _library_vector_cosine(query_embedding, chunk_embedding)
    # Coverage and BM25-like sparse ranking matter more than raw repetition.
    # This prevents a long document repeating common words from beating a
    # concise chunk that covers the query. Semantic aliases add recall, but
    # exact query terms still dominate ranking so user docs do not drift toward
    # loose synonyms.
    vector_bonus = vector_similarity * 220
    score = int((coverage * 1000) + (bm25_score * 180) + (weighted_match_score * 95) + (min(frequency, 18) * 4) + semantic_bonus + phrase_bonus + vector_bonus)
    return score, matched_terms, coverage, semantic_matches, vector_similarity

def _library_full_context_text(text, chunk_text=""):
    clean = re.sub(r"\s+", " ", _clean_text(text or "", LIBRARY_MAX_TEXT)).strip()
    if not clean:
        return ""
    max_chars = max(LIBRARY_SNIPPET_CHARS, min(LIBRARY_FULL_CONTEXT_CHARS, LIBRARY_MAX_TEXT))
    if len(clean) <= max_chars:
        return clean
    chunk = re.sub(r"\s+", " ", _clean_text(chunk_text or "", max_chars)).strip()
    if chunk:
        lower = clean.lower()
        start = lower.find(chunk[: min(len(chunk), 80)].lower())
        if start >= 0:
            start = max(0, start - 500)
            excerpt = clean[start:start + max_chars].strip()
            if start > 0:
                excerpt = "…" + excerpt
            if start + max_chars < len(clean):
                excerpt += "…"
            return excerpt
    return clean[:max_chars].strip() + "…"

def _library_search_documents(documents, query, limit=LIBRARY_SEARCH_LIMIT, include_private_context=False):
    terms = _library_tokenize(query)
    if not terms:
        return []
    results = []
    unique_terms = list(dict.fromkeys(terms))
    term_weights = _library_expand_query_terms(unique_terms)
    query_embedding = _library_hash_vector_from_weights(term_weights)
    phrase = " ".join(unique_terms)
    indexed_documents = []
    chunk_count = 0
    total_chunk_len = 0
    term_doc_frequency = {term: 0 for term in term_weights}
    for doc in documents:
        if not isinstance(doc, dict):
            continue
        chunks = _library_document_chunks(doc)
        indexed_documents.append((doc, chunks))
        for chunk in chunks:
            vector = chunk.get("vector") if isinstance(chunk.get("vector"), dict) else {}
            chunk_len = max(1, int(chunk.get("token_count", 0) or 0) or sum(int(value or 0) for value in vector.values()) or len(re.findall(r"[\wÀ-ÿ]{2,}", chunk.get("text") or "", flags=re.UNICODE)))
            chunk_count += 1
            total_chunk_len += chunk_len
            chunk_lower = chunk.get("lower") or ""
            for term in term_weights:
                if int(vector.get(term, 0) or 0) or term in chunk_lower:
                    term_doc_frequency[term] = term_doc_frequency.get(term, 0) + 1
    avg_chunk_len = (total_chunk_len / chunk_count) if chunk_count else 1.0
    idf_weights = {
        term: max(0.25, math.log(1 + ((chunk_count - df + 0.5) / (df + 0.5)))) if df else math.log(1 + chunk_count + 1)
        for term, df in term_doc_frequency.items()
    }
    for doc, chunks in indexed_documents:
        doc_text = doc.get("text") or ""
        name_lower = (doc.get("name") or "").lower()
        best = {
            "score": 0,
            "matched": [],
            "semantic_matches": [],
            "coverage": 0.0,
            "vector_similarity": 0.0,
            "chunk_index": 0,
            "chunk_text": "",
        }
        name_matched = []
        name_bonus = 0
        for term in unique_terms:
            if term in name_lower:
                name_matched.append(term)
                name_bonus += 80
        for chunk in chunks:
            score, matched, coverage, semantic_matches, vector_similarity = _library_score_chunk(
                chunk["lower"],
                term_weights,
                phrase,
                chunk.get("vector"),
                idf_weights,
                avg_chunk_len,
                chunk.get("token_count"),
                query_embedding,
                chunk.get("embedding"),
            )
            if name_bonus and matched:
                score += name_bonus
            elif name_bonus and not matched:
                matched = name_matched[:]
                semantic_matches = []
                coverage = len(matched) / max(1, len(unique_terms))
                score = name_bonus + int(coverage * 350)
            if score > best["score"]:
                best = {
                    "score": score,
                    "matched": list(dict.fromkeys([*matched, *name_matched]))[:8],
                    "semantic_matches": list(dict.fromkeys(semantic_matches))[:8],
                    "coverage": coverage,
                    "vector_similarity": vector_similarity,
                    "chunk_index": chunk["index"],
                    "chunk_text": chunk["text"],
                }
        if best["score"] <= 0:
            continue
        public_doc = _library_public_document(doc)
        if not public_doc:
            continue
        public_doc["score"] = best["score"]
        public_doc["matched_terms"] = best["matched"][:8]
        public_doc["match_coverage"] = round(float(best["coverage"]), 3)
        public_doc["chunk_index"] = int(best["chunk_index"])
        public_doc["retrieval_mode"] = LIBRARY_RETRIEVAL_MODE
        public_doc["semantic_expansion"] = bool(LIBRARY_SEMANTIC_EXPANSION_ENABLED)
        public_doc["semantic_matches"] = best.get("semantic_matches", [])[:8]
        public_doc["vector_similarity"] = round(float(best.get("vector_similarity", 0.0) or 0.0), 4)
        public_doc["index_mode"] = LIBRARY_INDEX_MODE
        public_doc["ranking"] = LIBRARY_RANKING_MODE
        public_doc["snippet"] = _library_snippet(best["chunk_text"] or doc_text, best["matched"])
        if include_private_context:
            public_doc["_context_text"] = _library_full_context_text(doc_text, best["chunk_text"])
        results.append(public_doc)
    results.sort(key=lambda item: (item.get("score", 0), item.get("match_coverage", 0), item.get("updated", 0)), reverse=True)
    return results[:max(1, min(limit, LIBRARY_SEARCH_LIMIT))]

def _strip_client_library_context(text):
    if not isinstance(text, str) or "Konteks Library Harmonika AI per device" not in text:
        return text
    return re.sub(
        r"\n{0,3}Konteks Library Harmonika AI per device\..*?(?:\n\n(?=Instruksi isolasi untuk chat web publik:)|\Z)",
        "",
        text,
        flags=re.S,
    ).strip()

def _library_grounding_for_request(query, mode="auto", context_mode="snippet"):
    mode = _clean_text(mode or "auto", 40).lower()
    if mode not in {"auto", "force", "off"}:
        mode = "auto"
    context_mode = _clean_text(context_mode or "snippet", 40).lower()
    if context_mode not in {"snippet", "full"}:
        context_mode = "snippet"
    if mode == "off" or not LIBRARY_GROUNDING_ENABLED:
        return "", [], {"mode": mode, "context_mode": context_mode, "used": False, "count": 0, "reason": "disabled"}
    query = _clean_text(query or "", 800).strip()
    if len(query) < 3:
        return "", [], {"mode": mode, "context_mode": context_mode, "used": False, "count": 0, "reason": "query_too_short"}
    device_id = _verify_device_cookie(request.cookies.get(DEVICE_COOKIE))
    if not device_id:
        return "", [], {"mode": mode, "context_mode": context_mode, "used": False, "count": 0, "reason": "no_device"}
    try:
        with _library_store_lock():
            store = _load_library_store()
        device_library = store.get("devices", {}).get(device_id) or {"documents": []}
        results = _library_search_documents(
            device_library.get("documents", []),
            query,
            limit=max(1, min(LIBRARY_GROUNDING_LIMIT, LIBRARY_SEARCH_LIMIT)),
            include_private_context=True,
        )
    except Exception as error:
        app.logger.warning("library_grounding_error: %s", error)
        return "", [], {"mode": mode, "context_mode": context_mode, "used": False, "count": 0, "reason": "error"}
    snippets = []
    sources = []
    context_chars = 0
    for result in results[:LIBRARY_GROUNDING_LIMIT]:
        max_chars = LIBRARY_FULL_CONTEXT_CHARS if context_mode == "full" else LIBRARY_SNIPPET_CHARS
        snippet = _clean_text(
            (result.get("_context_text") if context_mode == "full" else "")
            or result.get("snippet")
            or result.get("preview")
            or "",
            max_chars,
        ).strip()
        name = _safe_attachment_name(result.get("name") or "Dokumen Library")
        if not snippet:
            continue
        snippets.append(f"[Library: {name}]\n{snippet}")
        context_chars += len(snippet)
        sources.append(_source_metadata(
            "",
            title=name,
            snippet=_clean_text(result.get("snippet") or result.get("preview") or snippet, LIBRARY_SNIPPET_CHARS),
            source="library",
        ))
    if not snippets:
        return "", [], {"mode": mode, "context_mode": context_mode, "used": False, "count": 0, "reason": "no_match"}
    context = (
        "\n\nKonteks Library Harmonika AI per device. "
        f"Mode konteks: {'penuh terbatas' if context_mode == 'full' else 'cuplikan relevan'}. "
        "Gunakan hanya bila relevan dengan pertanyaan terbaru; jangan sebut ID internal dokumen. "
        "Jika jawabannya tidak ada di cuplikan Library, katakan bahwa informasi itu tidak ditemukan di dokumen Library.\n\n"
        + "\n\n---\n\n".join(snippets)
    )
    return _clamp_additional_text(context), sources, {
        "mode": mode,
        "context_mode": context_mode,
        "used": True,
        "count": len(sources),
        "context_chars": context_chars,
        "retrieval_mode": LIBRARY_RETRIEVAL_MODE,
    }

def _sanitize_message(message):
    if not isinstance(message, dict):
        return None
    role = message.get("role")
    if role not in ("user", "assistant", "system"):
        return None

    clean = {"role": role}
    content = message.get("content", "")
    if isinstance(content, dict):
        clean_content = {}
        for key, value in content.items():
            if key == "raw":
                clean_content[key] = _clean_text(value)
            elif key == "reasoningExpanded":
                clean_content[key] = bool(value)
            elif isinstance(value, (str, int, float, bool)) or value is None:
                clean_content[key] = value
        clean["content"] = clean_content or {"raw": ""}
    elif isinstance(content, list):
        clean["content"] = _sanitize_multimodal_content(content)
    else:
        clean["content"] = _clean_text(content)

    if "raw" in message:
        raw = message.get("raw")
        if isinstance(raw, list):
            clean["raw"] = _sanitize_multimodal_content(raw)
        else:
            clean["raw"] = _clean_text(raw)

    for key in ("endTag", "messageId", "thinkingTime", "attachments", "artifacts"):
        if key in message:
            try:
                clean[key] = json.loads(json.dumps(message.get(key), ensure_ascii=False))
            except (TypeError, ValueError):
                pass
    if "sources" in message:
        clean["sources"] = _sanitize_sources(message.get("sources"))
    return clean

def _sanitize_chat(chat):
    if not isinstance(chat, dict):
        return None
    chat_id = _clean_text(chat.get("id"), 80)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", chat_id or ""):
        return None
    now_ms = int(time.time() * 1000)
    messages = chat.get("messages") if isinstance(chat.get("messages"), list) else []
    clean_messages = []
    for message in messages[-HISTORY_MAX_MESSAGES:]:
        clean_message = _sanitize_message(message)
        if clean_message:
            clean_messages.append(clean_message)

    def clean_ts(value, fallback):
        try:
            value = int(value)
            return value if value > 0 else fallback
        except (TypeError, ValueError):
            return fallback

    return {
        "id": chat_id,
        "title": _clean_chat_title(chat.get("title") or "New Chat"),
        "messages": clean_messages,
        "createdAt": clean_ts(chat.get("createdAt"), now_ms),
        "updated": clean_ts(chat.get("updated"), now_ms),
    }

def _sanitize_history_payload(payload):
    if not isinstance(payload, dict):
        return {"chats": [], "active": "", "deleted": []}
    raw_chats = payload.get("chats") if isinstance(payload.get("chats"), list) else []
    chats = []
    seen = set()
    for chat in raw_chats[:HISTORY_MAX_CHATS]:
        clean_chat = _sanitize_chat(chat)
        if clean_chat and clean_chat["id"] not in seen:
            chats.append(clean_chat)
            seen.add(clean_chat["id"])
    active = _clean_text(payload.get("active") or "", 80)
    if active and active not in seen:
        active = ""
    deleted = []
    seen_deleted = set()
    raw_deleted = payload.get("deleted") if isinstance(payload.get("deleted"), list) else []
    for item in raw_deleted[:HISTORY_MAX_DELETED]:
        if not isinstance(item, dict):
            continue
        deleted_id = _clean_text(item.get("id"), 80)
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", deleted_id or "") or deleted_id in seen_deleted:
            continue
        try:
            deleted_updated = int(item.get("updated", 0))
        except (TypeError, ValueError):
            deleted_updated = 0
        if deleted_updated <= 0:
            continue
        deleted.append({"id": deleted_id, "updated": deleted_updated})
        seen_deleted.add(deleted_id)
    return {"chats": chats, "active": active, "deleted": deleted}

def _merge_device_history(existing_history, clean_payload, updated):
    existing_history = existing_history if isinstance(existing_history, dict) else {}
    merged = {}
    tombstones = {}
    for item in existing_history.get("deleted", []) if isinstance(existing_history.get("deleted"), list) else []:
        if isinstance(item, dict) and item.get("id"):
            tombstones[_clean_text(item.get("id"), 80)] = int(item.get("updated", 0) or 0)
    for item in clean_payload.get("deleted", []):
        tombstones[item["id"]] = max(int(tombstones.get(item["id"], 0) or 0), int(item.get("updated", 0) or 0))

    for chat in existing_history.get("chats", []) if isinstance(existing_history.get("chats"), list) else []:
        clean_chat = _sanitize_chat(chat)
        if clean_chat and int(tombstones.get(clean_chat["id"], 0) or 0) < int(clean_chat.get("updated", 0) or 0):
            merged[clean_chat["id"]] = clean_chat
    for chat in clean_payload["chats"]:
        if int(tombstones.get(chat["id"], 0) or 0) >= int(chat.get("updated", 0) or 0):
            continue
        previous = merged.get(chat["id"])
        if not previous or int(chat.get("updated", 0) or 0) >= int(previous.get("updated", 0) or 0):
            merged[chat["id"]] = chat
    chats = sorted(merged.values(), key=lambda chat: int(chat.get("updated", 0) or 0), reverse=True)[:HISTORY_MAX_CHATS]
    deleted = [
        {"id": item_id, "updated": item_updated}
        for item_id, item_updated in sorted(tombstones.items(), key=lambda item: item[1], reverse=True)
        if item_updated > 0
    ][:HISTORY_MAX_DELETED]
    active = clean_payload["active"] if clean_payload["active"] in {chat["id"] for chat in chats} else existing_history.get("active", "")
    if active and active not in {chat["id"] for chat in chats}:
        active = ""
    return {"chats": chats, "active": active, "deleted": deleted, "updated": updated}

def _clean_chat_title(title):
    title = _clean_text(title or "New Chat", 120)
    title = re.sub(r"\s+", " ", title).strip().strip("\"'“”‘’")
    return (title[:80].strip() or "New Chat")

# Route to render the index page
@app.route('/')
def index():
    _queue_device_cookie_if_missing()
    return render_template('index.html')

@app.route('/c/<chat_id>')
def chat_session(chat_id):
    _queue_device_cookie_if_missing()
    return render_template('index.html')

@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')

@app.route('/healthz')
def healthz():
    return jsonify({
        "ok": True,
        "service": "harmonika-chat-webui",
        "security": {
            "flask_secret_configured": _flask_secret_configured,
            "device_secret_configured": _device_secret_configured,
        },
        "features": {
            "sources_without_url": True,
            "shared_rate_limit": RATE_LIMIT_STORAGE == "file",
        },
    })

@app.route('/api/admin/overview', methods=['GET'])
def api_admin_overview():
    return jsonify(_admin_overview_snapshot())

@app.route('/api/capabilities', methods=['GET'])
def api_capabilities():
    image_enabled = IMAGE_GENERATION_ENABLED and IMAGE_ARTIFACT_MODE == "svg"
    bridge_ready = _member_ai_bridge_ready()
    chat_bridge_ready = _member_ai_chat_ready()
    raster_public = bool(bridge_ready and MEMBER_AI_RASTER_READY and MEMBER_AI_RASTER_PUBLIC)
    private_file_mode = bridge_ready or image_enabled
    image_mode = "disabled"
    if raster_public:
        image_mode = "member_ai_bridge"
    elif bridge_ready and image_enabled:
        image_mode = "member_ai_bridge_with_local_fallback"
    elif image_enabled:
        image_mode = "local_svg_file"
    elif bridge_ready:
        image_mode = "member_ai_bridge_pending"
    return jsonify({
        "ok": True,
        "service": "harmonika-chat-webui",
        "features": {
            "chat": True,
            "streaming": True,
            "realtime_replay_api": True,
            "realtime_replay_state": True,
            "realtime_resume": True,
            "realtime_wss": REALTIME_WSS_READY,
            "realtime_wss_ticket_endpoint": True,
            "admin_overview": True,
            "admin_dashboard": True,
            "observability_aggregate": True,
            "admin_analytics": True,
            "web_search": AUTO_WEB_GROUNDING,
            "google_mode": chat_bridge_ready,
            "member_ai_chat_bridge": chat_bridge_ready,
            "member_ai_chat_session_isolation": bool(chat_bridge_ready and MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST),
            "codex_task_routing": bool(chat_bridge_ready and MEMBER_AI_ROUTE_CODEX and MEMBER_AI_CODEX_MODE),
            "sources": True,
            "sources_without_url": True,
            "file_upload": True,
            "rag_library": False,
            "rag_library_api": True,
            "rag_library_ui": True,
            "rag_library_grounding": True,
            "rag_library_server_grounding": True,
            "rag_library_chunked_retrieval": True,
            "rag_library_lexical_rerank": True,
            "rag_library_bm25_sparse_rerank": True,
            "rag_library_vector_index": True,
            "rag_library_hybrid_retrieval": True,
            "rag_library_semantic_expansion": bool(LIBRARY_SEMANTIC_EXPANSION_ENABLED),
            "rag_library_full_context": True,
            "rag_library_sparse_index": True,
            "rag_library_grounding_toggle": True,
            "rag_library_no_silent_eviction": True,
            "library_rate_limit_dedicated": True,
            "library_upload": True,
            "library_search": True,
            "image_input": True,
            "pdf_input": True,
            "memory": True,
            "message_queue": True,
            "artifact_canvas": True,
            "image_generation": private_file_mode,
            "image_generation_sse": private_file_mode,
            "image_preview": private_file_mode,
            "image_download": private_file_mode,
            "raster_image_generation": raster_public,
            "member_ai_image_bridge": bridge_ready,
        },
        "limits": {
            "max_upload_bytes": app.config["MAX_CONTENT_LENGTH"],
            "attachments_per_message": 3,
            "accepted_mime_types": [
                "application/pdf",
                "text/plain",
                "text/csv",
                "application/csv",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "image/png",
                "image/jpeg",
                "image/webp",
            ],
            "max_memory_items": 12,
            "library_max_documents": LIBRARY_MAX_DOCS_PER_DEVICE,
            "library_max_text_chars": LIBRARY_MAX_TEXT,
            "library_full_context_chars": LIBRARY_FULL_CONTEXT_CHARS,
            "library_search_limit": LIBRARY_SEARCH_LIMIT,
            "library_chunk_chars": LIBRARY_CHUNK_CHARS,
            "library_chunk_overlap": LIBRARY_CHUNK_OVERLAP,
            "library_vector_dimensions": LIBRARY_VECTOR_DIMS,
            "library_vector_mode": "private_local_hash_embedding",
            "library_retrieval_mode": LIBRARY_RETRIEVAL_MODE,
            "library_ranking_mode": LIBRARY_RANKING_MODE,
            "library_semantic_expansion": bool(LIBRARY_SEMANTIC_EXPANSION_ENABLED),
            "library_index_mode": LIBRARY_INDEX_MODE,
            "library_context_mode": LIBRARY_CONTEXT_MODE,
            "library_context_modes": ["snippet", "full"],
            "library_grounding_mode": LIBRARY_GROUNDING_MODE,
            "library_grounding_modes": ["auto", "force", "off"],
            "library_rate_limit_count": RATE_LIMIT_LIBRARY[0],
            "library_rate_limit_window_seconds": RATE_LIMIT_LIBRARY[1],
            "image_generations_per_day": RATE_LIMIT_IMAGE[0] if private_file_mode else 0,
            "image_generation_window_seconds": RATE_LIMIT_IMAGE[1] if private_file_mode else 0,
            "image_sizes": (
                ["1024x1024", "1024x768", "768x1024"]
                if raster_public
                else (["800x500"] if private_file_mode else [])
            ),
            "realtime_event_ttl_seconds": REALTIME_EVENT_TTL_SECONDS,
            "realtime_event_max_events": REALTIME_EVENT_MAX_EVENTS,
            "realtime_replay_state_fields": ["terminal", "last_sequence", "last_event_id", "next_after_sequence", "replay_after_sequence", "expires_at"],
            "realtime_wss_ready": REALTIME_WSS_READY,
            "realtime_wss_ticket_endpoint": "/api/realtime/ticket",
            "realtime_wss_path": REALTIME_WSS_PATH,
            "admin_overview_endpoint": "/api/admin/overview",
            "admin_dashboard_path": "/admin",
            "observability_mode": "aggregate_only_no_content",
        },
        "image_generation": {
            "status": "enabled" if private_file_mode else "disabled",
            "mode": image_mode,
            "result_format": "private_file_artifact" if private_file_mode else "disabled",
            "public_urls": False,
            "raster_public": raster_public,
            "local_svg_fallback": image_enabled and not raster_public,
            "backend": "chat.harmonika.id" if bridge_ready else "local_fallback",
        },
        "chat_routing": {
            "default_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "primary_answer_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "answer_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "question_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "analysis_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "conversation_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "story_companion_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "codex_mode": MEMBER_AI_CODEX_MODE if chat_bridge_ready and MEMBER_AI_ROUTE_CODEX else "disabled",
            "text_backend": "chat.harmonika.id/member-ai" if chat_bridge_ready else "openwebui_engine",
            "image_generation_backend": "chat.harmonika.id/member-ai" if bridge_ready else "local_fallback",
            "file_and_image_input_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "attachment_understanding_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "file_input_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "image_input_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "general_chat_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "question_analysis_story_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "web_reference_mode": MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default",
            "image_creation_task_mode": MEMBER_AI_IMAGE_MODE if bridge_ready else ("local_artifact" if image_enabled else "disabled"),
            "image_creation_request_mode": MEMBER_AI_IMAGE_MODE if bridge_ready else ("local_artifact" if image_enabled else "disabled"),
            "technical_task_mode": MEMBER_AI_CODEX_MODE if chat_bridge_ready and MEMBER_AI_ROUTE_CODEX else (MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default"),
            "heavy_task_mode": MEMBER_AI_CODEX_MODE if chat_bridge_ready and MEMBER_AI_ROUTE_CODEX else (MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default"),
            "code_analysis_mode": MEMBER_AI_CODEX_MODE if chat_bridge_ready and MEMBER_AI_ROUTE_CODEX else (MEMBER_AI_CHAT_MODE if chat_bridge_ready else "engine_default"),
            "codex_policy": "heavy_technical_only" if chat_bridge_ready and MEMBER_AI_ROUTE_CODEX else "disabled",
            "google_mode_policy": "primary_for_answers_questions_analysis_story_web_files_images",
            "chat_bridge_session_policy": "locked_reset_per_request" if (chat_bridge_ready and MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST) else "shared_session_prompt_isolation",
            "codex_handoff_policy": "only_for_explicit_heavy_technical_symptom_or_private_image_creation",
            "routing_summary": "google_default_codex_for_heavy_technical_and_image_creation",
            "public_urls": False,
        },
        "rate_limit": {
            "storage": RATE_LIMIT_STORAGE,
            "shared_across_workers": RATE_LIMIT_STORAGE == "file",
            "max_keys": RATE_LIMIT_MAX_KEYS,
            "library_bucket": "library",
        },
    })

@app.route('/api/realtime/events', methods=['GET'])
def api_realtime_events():
    response_id = _safe_file_id(request.args.get("response_id") or request.args.get("id"))
    if not response_id:
        return _json_error("response_id_required", "response_id wajib diisi.", 400)
    after_sequence = request.args.get("after_sequence") or request.headers.get("Last-Event-ID") or 0
    if isinstance(after_sequence, str) and ":" in after_sequence:
        after_sequence = after_sequence.rsplit(":", 1)[-1]
    try:
        after_sequence_int = int(after_sequence or 0)
    except (TypeError, ValueError):
        after_sequence_int = 0
    record, events = _realtime_events_after(response_id, after_sequence_int)
    if not record:
        return _json_error("response_not_found", "Event stream tidak tersedia atau sudah kedaluwarsa.", 404)
    accept = request.headers.get("Accept", "")
    if "text/event-stream" in accept:
        def generate_replay():
            for event in events:
                yield f"id: {event.get('event_id')}\n"
                yield f"event: {event.get('type') or 'event'}\n"
                yield f"data: {json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n\n"
            state = _realtime_record_state(record, events, after_sequence_int)
            yield f"id: {state.get('last_event_id') or response_id + ':' + str(state.get('next_after_sequence') or 0)}\n"
            yield f"event: replay.state\ndata: {json.dumps(state, ensure_ascii=False, separators=(',', ':'))}\n\n"

        return Response(generate_replay(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-HAI-Realtime-Replay": "true",
            "X-HAI-Realtime-State": record.get("status") or "unknown",
        })
    state = _realtime_record_state(record, events, after_sequence_int)
    return jsonify({
        "ok": True,
        "response_id": response_id,
        "status": state.get("status") or "unknown",
        "state": state,
        "terminal": state.get("terminal") is True,
        "events": events,
        "count": len(events),
        "expires_at": record.get("expires_at"),
        "last_sequence": state.get("last_sequence"),
        "last_event_id": state.get("last_event_id"),
        "next_after_sequence": state.get("next_after_sequence"),
        "replay_after_sequence": state.get("replay_after_sequence"),
    })

@app.route('/api/realtime/ticket', methods=['POST'])
def api_realtime_ticket():
    if not REALTIME_WSS_READY:
        return _json_error(
            "realtime_wss_not_ready",
            "Realtime WebSocket belum aktif. Gunakan SSE streaming dan replay HTTP terlebih dahulu.",
            503,
            {
                "retryable": False,
                "realtime_wss": False,
                "ticket": None,
                "expires_at": None,
                "ws_url": _realtime_ws_url(),
                "fallback": {
                    "stream": "/chat",
                    "replay": "/api/realtime/events",
                },
            },
        )
    return _json_error(
        "realtime_wss_gateway_missing",
        "Realtime WebSocket gateway belum dikonfigurasi di service ini.",
        503,
        {
            "retryable": False,
            "realtime_wss": False,
            "ticket": None,
            "expires_at": None,
            "ws_url": _realtime_ws_url(),
            "fallback": {
                "stream": "/chat",
                "replay": "/api/realtime/events",
            },
        },
    )

@app.route('/api/readiness', methods=['GET'])
def api_readiness():
    image_enabled = IMAGE_GENERATION_ENABLED and IMAGE_ARTIFACT_MODE == "svg"
    bridge_ready = _member_ai_bridge_ready()
    chat_bridge_ready = _member_ai_chat_ready()
    raster_public = bool(bridge_ready and MEMBER_AI_RASTER_READY and MEMBER_AI_RASTER_PUBLIC)
    private_file_mode = bridge_ready or image_enabled
    core = {
        "chat": True,
        "streaming": True,
        "history": True,
        "responsive_ui": True,
        "google_mode_backend": chat_bridge_ready,
        "web_search_sources": AUTO_WEB_GROUNDING,
        "file_upload": True,
        "pdf_input": True,
        "image_input": True,
        "image_artifact_preview": private_file_mode,
        "memory_lightweight": True,
        "message_queue": True,
        "artifact_canvas_basic": True,
        "realtime_replay_api": True,
        "realtime_replay_state": True,
        "admin_overview": True,
        "admin_dashboard": True,
        "observability_aggregate": True,
        "admin_analytics": True,
        "a11y_smoke": True,
        "release_gate": True,
    }
    roadmap = {
        "raster_image_generation": {
            "status": "ready" if raster_public else "pending",
            "capability": "raster_image_generation",
            "reason": None if raster_public else "Provider raster private file_id belum dipublikasikan; fallback private SVG tetap aktif.",
        },
        "rag_library": {
            "status": "pending",
            "capability": "rag_library",
            "reason": "Library upload/list/search/delete per device, sidebar UI, server-side grounding toggle, full-context control, private hybrid sparse+vector chunk index, BM25-lite/vector rerank, dan semantic alias expansion sudah ada; external vector DB/managed embeddings lintas dokumen belum production.",
        },
        "realtime_resume_wss": {
            "status": "foundation",
            "capability": "realtime_resume_wss",
            "reason": "SSE dasar, endpoint replay `/api/realtime/events`, dan endpoint ticket `/api/realtime/ticket` sudah ada; WSS gateway penuh/tool workflow belum production.",
        },
        "voice_video": {
            "status": "planned",
            "capability": "voice_video",
            "reason": "STT/TTS/voice/video belum menjadi bagian MVP web.",
        },
        "calendar_automation_admin": {
            "status": "foundation",
            "capability": "calendar_automation_admin",
            "reason": "Fondasi observability dan analytics aggregate tersedia lewat `/api/admin/overview` tanpa chat content, document text, device IDs, atau secret. Calendar, automations, cost dashboard, dan model evaluation tetap modul lanjutan.",
        },
        "admin_analytics": {
            "status": "ready",
            "capability": "admin_analytics",
            "reason": "Analytics aggregate dasar tersedia di `/admin` dan `/api/admin/overview`: chat aktif 24 jam/7 hari, pesan per role, lampiran, artifact gambar, sumber, dan rata-rata pesan/chat tanpa isi chat atau identitas device.",
        },
    }
    next_priorities = [
        {
            "id": "rag_library",
            "title": "Library/RAG dokumen permanen",
            "why": "Membuat knowledge base dan pencarian dokumen lintas chat lebih kuat daripada upload per pesan.",
            "status": roadmap["rag_library"]["status"],
            "suggested_phase": "next",
        },
        {
            "id": "realtime_resume_wss",
            "title": "Realtime resume/replay",
            "why": "Mencegah jawaban terasa hilang saat koneksi mobile putus dan membuka jalan WSS/tool workflow.",
            "status": roadmap["realtime_resume_wss"]["status"],
            "suggested_phase": "next",
        },
        {
            "id": "admin_analytics",
            "title": "Admin analytics dan observability",
            "why": "Membantu owner memantau pemakaian, error, biaya, dan kualitas jawaban setelah publik.",
            "status": roadmap["admin_analytics"]["status"],
            "suggested_phase": "after_core_realtime",
        },
    ]
    return jsonify({
        "ok": True,
        "service": "harmonika-chat-webui",
        "profile": "public_mvp",
        "production": {
            "public_mvp_ready": all(bool(value) for value in core.values()),
            "full_platform_complete": False,
            "gate": "phase319-public-release-gate",
            "gate_result": {
                "passed": 72,
                "total": 72,
                "visual_snapshots_passed": 17,
                "visual_snapshots_total": 17,
                "scope": "full_public_release_gate_after_phase319_realtime_loader_ui_stable",
                "previous_full_public_gate": "phase317-public-release-gate",
                "previous_full_public_gate_passed": 72,
                "previous_full_public_gate_total": 72,
            },
            "last_verified": "2026-10-07",
        },
        "core": core,
        "roadmap": roadmap,
        "next_priorities": next_priorities,
        "contracts": {
            "no_public_media_urls": True,
            "sources_without_full_url_in_bubble": True,
            "realtime_replay_endpoint": "/api/realtime/events",
            "realtime_replay_state": True,
            "realtime_replay_state_fields": ["terminal", "last_sequence", "last_event_id", "next_after_sequence", "replay_after_sequence", "expires_at"],
            "realtime_replay_ttl_seconds": REALTIME_EVENT_TTL_SECONDS,
            "realtime_wss": REALTIME_WSS_READY,
            "realtime_wss_ticket_endpoint": "/api/realtime/ticket",
            "realtime_wss_path": REALTIME_WSS_PATH,
            "admin_overview_endpoint": "/api/admin/overview",
            "admin_dashboard_path": "/admin",
            "admin_overview": True,
            "admin_dashboard": True,
            "observability_aggregate": True,
            "admin_analytics": True,
            "shared_rate_limit": RATE_LIMIT_STORAGE == "file",
            "rate_limit_storage": RATE_LIMIT_STORAGE,
            "member_ai_chat_session_isolation": bool(chat_bridge_ready and MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST),
            "member_ai_chat_session_policy": "locked_reset_per_request" if (chat_bridge_ready and MEMBER_AI_RESET_CHAT_SESSION_PER_REQUEST) else "shared_session_prompt_isolation",
            "attachments_per_message": 3,
            "max_upload_bytes": app.config["MAX_CONTENT_LENGTH"],
            "image_result_format": "private_file_artifact" if private_file_mode else "disabled",
            "raster_public": raster_public,
            "rag_library_ui": True,
            "rag_library_grounding": True,
            "rag_library_server_grounding": True,
            "rag_library_chunked_retrieval": True,
            "rag_library_lexical_rerank": True,
            "rag_library_bm25_sparse_rerank": True,
            "rag_library_vector_index": True,
            "rag_library_hybrid_retrieval": True,
            "rag_library_semantic_expansion": bool(LIBRARY_SEMANTIC_EXPANSION_ENABLED),
            "rag_library_full_context": True,
            "rag_library_sparse_index": True,
            "rag_library_grounding_toggle": True,
            "rag_library_no_silent_eviction": True,
            "library_rate_limit_bucket": "library",
            "library_retrieval_mode": LIBRARY_RETRIEVAL_MODE,
            "library_ranking_mode": LIBRARY_RANKING_MODE,
            "library_vector_mode": "private_local_hash_embedding",
            "library_vector_dimensions": LIBRARY_VECTOR_DIMS,
            "library_semantic_expansion": bool(LIBRARY_SEMANTIC_EXPANSION_ENABLED),
            "library_index_mode": LIBRARY_INDEX_MODE,
            "library_context_mode": LIBRARY_CONTEXT_MODE,
            "library_context_modes": ["snippet", "full"],
            "library_grounding_mode": LIBRARY_GROUNDING_MODE,
            "library_grounding_modes": ["auto", "force", "off"],
        },
    })

@app.route('/api/images/generations', methods=['POST'])
def api_images_generations():
    if not _member_ai_bridge_ready() and (not IMAGE_GENERATION_ENABLED or IMAGE_ARTIFACT_MODE != "svg"):
        return _json_error(
            "image_generation_disabled",
            _image_generation_unavailable_message(),
            503,
            {"retryable": False},
        )
    payload, error_response = _get_json_payload(CHAT_MAX_BODY)
    if error_response:
        return error_response
    prompt = _clean_text(payload.get("prompt") or payload.get("message"), 4000).strip()
    if not prompt:
        return _json_error("invalid_prompt", "Deskripsi gambar tidak boleh kosong.", 400)
    allowed, retry_after = _check_rate_limit("image", RATE_LIMIT_IMAGE)
    if not allowed:
        return _rate_limited_response(retry_after)
    if _member_ai_bridge_ready():
        try:
            images = _member_ai_generate_image(prompt, payload.get("size"), payload.get("count") or 1)
            markdown = _image_artifacts_markdown(images or [], prompt)
            if markdown:
                return jsonify({
                    "ok": True,
                    "status": "completed",
                    "mode": "member_ai_bridge",
                    "images": images,
                    "content": markdown,
                })
        except Exception as error:
            app.logger.warning("member_ai_image_generation_api_error: %s", error)
            if (not MEMBER_AI_RASTER_READY or not MEMBER_AI_RASTER_PUBLIC) and IMAGE_GENERATION_ENABLED and IMAGE_ARTIFACT_MODE == "svg":
                content, images = _local_svg_image_response(prompt)
                return jsonify({
                    "ok": True,
                    "status": "completed",
                    "mode": "local_svg_file_fallback",
                    "fallback_reason": "member_ai_bridge_unavailable",
                    "images": images,
                    "content": content,
                })
            return _json_error(
                "image_generation_backend_unavailable",
                "Pembuatan gambar belum siap. Coba lagi nanti.",
                503,
                {"retryable": True},
            )
    content, images = _local_svg_image_response(prompt)
    return jsonify({
        "ok": True,
        "status": "completed",
        "mode": "local_svg_file",
        "images": images,
        "content": content,
    })

@app.route('/api/files/<file_id>/preview', methods=['GET'])
def api_file_preview(file_id):
    allowed, retry_after = _check_rate_limit("file", RATE_LIMIT_FILE)
    if not allowed:
        return _rate_limited_response(retry_after)
    clean_file_id = _safe_file_id(file_id)
    local_image = _load_local_image(clean_file_id)
    if local_image:
        return Response(
            local_image["content"].encode("utf-8"),
            mimetype="image/svg+xml",
            headers={"Cache-Control": "private, max-age=300"},
        )
    if _is_local_image_file_id(clean_file_id):
        return _json_error("file_not_found", "File tidak tersedia.", 404)
    if not clean_file_id or not _member_ai_bridge_ready():
        return _json_error("file_not_found", "File tidak tersedia.", 404)
    url = f"{MEMBER_AI_BASE_URL}/files/{quote(clean_file_id, safe='')}/preview"
    try:
        upstream = httpx.get(url, headers=_member_ai_headers({"Accept": "image/*"}), timeout=MEMBER_AI_TIMEOUT)
        upstream.raise_for_status()
    except httpx.HTTPStatusError as error:
        status_code = getattr(error.response, "status_code", 502)
        if status_code == 404:
            return _json_error("file_not_found", "File tidak tersedia.", 404)
        app.logger.warning("member_ai_file_preview_http_error: %s", error)
        return _json_error("file_preview_unavailable", "Preview gambar belum tersedia.", 502)
    except Exception as error:
        app.logger.warning("member_ai_file_preview_error: %s", error)
        return _json_error("file_preview_unavailable", "Preview gambar belum tersedia.", 502)
    content_type = upstream.headers.get("content-type", "application/octet-stream")
    if not content_type.startswith("image/"):
        return _json_error("invalid_preview_type", "Preview file tidak valid.", 502)
    return Response(upstream.content, mimetype=content_type, headers={"Cache-Control": "private, max-age=300"})

@app.route('/api/files/<file_id>/download', methods=['GET'])
def api_file_download(file_id):
    allowed, retry_after = _check_rate_limit("file", RATE_LIMIT_FILE)
    if not allowed:
        return _rate_limited_response(retry_after)
    clean_file_id = _safe_file_id(file_id)
    local_image = _load_local_image(clean_file_id)
    if local_image:
        return Response(
            local_image["content"].encode("utf-8"),
            mimetype="image/svg+xml",
            headers={
                "Cache-Control": "private, max-age=300",
                "Content-Disposition": f'attachment; filename="harmonika-ai-{clean_file_id}.svg"',
            },
        )
    if _is_local_image_file_id(clean_file_id):
        return _json_error("file_not_found", "File tidak tersedia.", 404)
    if not clean_file_id or not _member_ai_bridge_ready():
        return _json_error("file_not_found", "File tidak tersedia.", 404)
    url = f"{MEMBER_AI_BASE_URL}/files/{quote(clean_file_id, safe='')}/download"
    try:
        upstream = httpx.get(url, headers=_member_ai_headers({"Accept": "image/*,application/octet-stream"}), timeout=MEMBER_AI_TIMEOUT)
        upstream.raise_for_status()
    except httpx.HTTPStatusError as error:
        status_code = getattr(error.response, "status_code", 502)
        if status_code == 404:
            return _json_error("file_not_found", "File tidak tersedia.", 404)
        app.logger.warning("member_ai_file_download_http_error: %s", error)
        return _json_error("file_download_unavailable", "Download gambar belum tersedia.", 502)
    except Exception as error:
        app.logger.warning("member_ai_file_download_error: %s", error)
        return _json_error("file_download_unavailable", "Download gambar belum tersedia.", 502)
    content_type = upstream.headers.get("content-type", "application/octet-stream")
    headers = {"Cache-Control": "private, max-age=300"}
    disposition = upstream.headers.get("content-disposition")
    if disposition:
        headers["Content-Disposition"] = disposition
    else:
        headers["Content-Disposition"] = f'attachment; filename="harmonika-ai-{clean_file_id}.png"'
    return Response(upstream.content, mimetype=content_type, headers=headers)

@app.route('/api/attachments/parse', methods=['POST'])
def api_parse_attachment():
    allowed, retry_after = _check_rate_limit("file", RATE_LIMIT_FILE)
    if not allowed:
        return _rate_limited_response(retry_after)
    uploaded = request.files.get("file")
    if uploaded is None:
        return _json_error("file_required", "File belum dipilih.", 400)
    name = _safe_attachment_name(uploaded.filename)
    mime = (uploaded.mimetype or "").lower()
    file_bytes = uploaded.read(app.config["MAX_CONTENT_LENGTH"] + 1)
    if not file_bytes:
        return _json_error("empty_file", "File kosong.", 400)
    if len(file_bytes) > app.config["MAX_CONTENT_LENGTH"]:
        return _json_error("file_too_large", "Ukuran file maksimal 10 MB.", 413)
    try:
        text = _extract_attachment_text(file_bytes, name, mime)
    except ValueError as error:
        return _json_error("unsupported_or_unreadable_file", str(error), 422)
    except Exception as error:
        app.logger.warning("attachment_parse_error: %s", error)
        return _json_error("file_content_unreadable", "Isi file belum bisa dibaca. Coba PDF/TXT/CSV/DOCX/XLSX lain.", 422)
    if not text:
        return _json_error("file_content_empty", "File terbaca, tetapi tidak ada teks yang bisa dianalisis.", 422)
    return jsonify({
        "ok": True,
        "file": {
            "name": name,
            "mime": mime,
            "size_bytes": len(file_bytes),
            "text": text[:HISTORY_MAX_TEXT],
        },
    })

@app.route('/api/library/documents', methods=['GET', 'POST'])
def api_library_documents():
    device_id, should_set_cookie = _get_or_create_device_id()
    allowed, retry_after = _check_rate_limit("library", RATE_LIMIT_LIBRARY)
    if not allowed:
        response, status = _rate_limited_response(retry_after)
        return _response_with_device_cookie(
            response.get_json(),
            device_id,
            should_set_cookie,
            status,
            {"Retry-After": str(retry_after)},
        )

    if request.method == 'GET':
        with _library_store_lock():
            store = _load_library_store()
        device_library = store.get("devices", {}).get(device_id) or {"documents": [], "updated": 0}
        docs = [
            public_doc
            for public_doc in (_library_public_document(doc) for doc in device_library.get("documents", []))
            if public_doc
        ]
        return _response_with_device_cookie({
            "ok": True,
            "device": device_id[:8],
            "documents": docs,
            "count": len(docs),
            "limits": {
                "max_documents": LIBRARY_MAX_DOCS_PER_DEVICE,
                "max_upload_bytes": app.config["MAX_CONTENT_LENGTH"],
                "max_text_chars": LIBRARY_MAX_TEXT,
            },
        }, device_id, should_set_cookie)

    uploaded = request.files.get("file")
    if uploaded is None:
        return _response_with_device_cookie({
            "ok": False,
            "error": "file_required",
            "message": "File belum dipilih.",
        }, device_id, should_set_cookie, 400)
    name = _safe_attachment_name(uploaded.filename)
    mime = (uploaded.mimetype or "").lower()
    file_bytes = uploaded.read(app.config["MAX_CONTENT_LENGTH"] + 1)
    if not file_bytes:
        return _response_with_device_cookie({
            "ok": False,
            "error": "empty_file",
            "message": "File kosong.",
        }, device_id, should_set_cookie, 400)
    if len(file_bytes) > app.config["MAX_CONTENT_LENGTH"]:
        return _response_with_device_cookie({
            "ok": False,
            "error": "file_too_large",
            "message": "Ukuran file maksimal 10 MB.",
        }, device_id, should_set_cookie, 413)
    try:
        text = _extract_attachment_text(file_bytes, name, mime)
    except ValueError as error:
        return _response_with_device_cookie({
            "ok": False,
            "error": "unsupported_or_unreadable_file",
            "message": str(error),
        }, device_id, should_set_cookie, 422)
    except Exception as error:
        app.logger.warning("library_document_parse_error: %s", error)
        return _response_with_device_cookie({
            "ok": False,
            "error": "file_content_unreadable",
            "message": "Isi file belum bisa dibaca. Coba PDF/TXT/CSV/DOCX/XLSX lain.",
        }, device_id, should_set_cookie, 422)
    text = _clamp_text(text, LIBRARY_MAX_TEXT).strip()
    if not text:
        return _response_with_device_cookie({
            "ok": False,
            "error": "file_content_empty",
            "message": "File terbaca, tetapi tidak ada teks yang bisa disimpan.",
        }, device_id, should_set_cookie, 422)

    now_ms = int(time.time() * 1000)
    doc = {
        "id": f"lib_{secrets.token_hex(10)}",
        "name": name,
        "mime": mime,
        "size_bytes": len(file_bytes),
        "text": text,
        "chunks": _library_build_chunk_index(text),
        "index_mode": LIBRARY_INDEX_MODE,
        "ranking_mode": LIBRARY_RANKING_MODE,
        "created": now_ms,
        "updated": now_ms,
    }
    with _library_store_lock():
        store = _load_library_store()
        devices = store.setdefault("devices", {})
        device_library = devices.setdefault(device_id, {"documents": [], "updated": now_ms})
        documents = device_library.get("documents") if isinstance(device_library.get("documents"), list) else []
        if len(documents) >= LIBRARY_MAX_DOCS_PER_DEVICE:
            return _response_with_device_cookie({
                "ok": False,
                "error": "library_full",
                "message": "Library penuh. Hapus dokumen lama sebelum menambah dokumen baru.",
                "limit": LIBRARY_MAX_DOCS_PER_DEVICE,
                "count": len(documents),
            }, device_id, should_set_cookie, 409)
        documents.insert(0, doc)
        device_library["documents"] = documents
        device_library["updated"] = now_ms
        devices[device_id] = device_library
        _save_library_store(store)
    return _response_with_device_cookie({
        "ok": True,
        "device": device_id[:8],
        "document": _library_public_document(doc),
        "count": len(device_library["documents"]),
    }, device_id, should_set_cookie)

@app.route('/api/library/documents/<doc_id>', methods=['DELETE'])
def api_library_delete_document(doc_id):
    device_id, should_set_cookie = _get_or_create_device_id()
    allowed, retry_after = _check_rate_limit("library", RATE_LIMIT_LIBRARY)
    if not allowed:
        response, status = _rate_limited_response(retry_after)
        return _response_with_device_cookie(response.get_json(), device_id, should_set_cookie, status, {"Retry-After": str(retry_after)})
    clean_doc_id = _clean_text(doc_id, 80)
    if not re.fullmatch(r"lib_[a-f0-9]{20}", clean_doc_id or ""):
        return _response_with_device_cookie({
            "ok": False,
            "error": "invalid_document_id",
            "message": "ID dokumen tidak valid.",
        }, device_id, should_set_cookie, 400)
    with _library_store_lock():
        store = _load_library_store()
        device_library = store.setdefault("devices", {}).setdefault(device_id, {"documents": [], "updated": 0})
        documents = device_library.get("documents") if isinstance(device_library.get("documents"), list) else []
        next_docs = [doc for doc in documents if isinstance(doc, dict) and doc.get("id") != clean_doc_id]
        removed = len(next_docs) != len(documents)
        device_library["documents"] = next_docs
        device_library["updated"] = int(time.time() * 1000)
        _save_library_store(store)
    status = 200 if removed else 404
    return _response_with_device_cookie({
        "ok": removed,
        "deleted": removed,
        "document_id": clean_doc_id,
        "error": None if removed else "document_not_found",
        "message": "Dokumen dihapus." if removed else "Dokumen tidak ditemukan.",
    }, device_id, should_set_cookie, status)

@app.route('/api/library/search', methods=['POST'])
def api_library_search():
    device_id, should_set_cookie = _get_or_create_device_id()
    allowed, retry_after = _check_rate_limit("library", RATE_LIMIT_LIBRARY)
    if not allowed:
        response, status = _rate_limited_response(retry_after)
        return _response_with_device_cookie(response.get_json(), device_id, should_set_cookie, status, {"Retry-After": str(retry_after)})
    payload, error_response = _get_json_payload(64 * 1024)
    if error_response:
        response, status = error_response
        return _response_with_device_cookie(response.get_json(), device_id, should_set_cookie, status)
    query = _clean_text(payload.get("query") or "", 500).strip()
    if not query:
        return _response_with_device_cookie({
            "ok": False,
            "error": "query_required",
            "message": "Query pencarian belum diisi.",
        }, device_id, should_set_cookie, 400)
    try:
        limit = int(payload.get("limit", LIBRARY_SEARCH_LIMIT))
    except (TypeError, ValueError):
        limit = LIBRARY_SEARCH_LIMIT
    with _library_store_lock():
        store = _load_library_store()
    device_library = store.get("devices", {}).get(device_id) or {"documents": []}
    results = _library_search_documents(device_library.get("documents", []), query, limit=limit)
    return _response_with_device_cookie({
        "ok": True,
        "device": device_id[:8],
        "query": query,
        "retrieval": {
            "mode": LIBRARY_RETRIEVAL_MODE,
            "chunk_chars": LIBRARY_CHUNK_CHARS,
            "chunk_overlap": LIBRARY_CHUNK_OVERLAP,
            "rerank": LIBRARY_RANKING_MODE,
            "vector_mode": "private_local_hash_embedding",
            "vector_dimensions": LIBRARY_VECTOR_DIMS,
            "semantic_expansion": bool(LIBRARY_SEMANTIC_EXPANSION_ENABLED),
        },
        "results": results,
        "count": len(results),
    }, device_id, should_set_cookie)

@app.route('/api/history', methods=['GET', 'PUT', 'POST'])
def device_history():
    device_id, should_set_cookie = _get_or_create_device_id()
    allowed, retry_after = _check_rate_limit("history", RATE_LIMIT_HISTORY)
    if not allowed:
        response, status = _rate_limited_response(retry_after)
        return _response_with_device_cookie(
            response.get_json(),
            device_id,
            should_set_cookie,
            status,
            {"Retry-After": str(retry_after)},
        )

    if request.method == 'GET':
        with _history_store_lock():
            store = _load_history_store()
        device_history = store.get("devices", {}).get(device_id) or {
            "chats": [],
            "active": "",
            "deleted": [],
            "updated": int(time.time() * 1000),
        }
        return _response_with_device_cookie({
            "ok": True,
            "device": device_id[:8],
            "chats": device_history.get("chats", []),
            "active": device_history.get("active", ""),
            "deleted": device_history.get("deleted", []),
            "updated": device_history.get("updated", 0),
        }, device_id, should_set_cookie)

    if request.content_length and request.content_length > HISTORY_MAX_BODY:
        return _response_with_device_cookie({
            "ok": False,
            "error": "history_payload_too_large",
            "message": "Riwayat terlalu besar untuk disimpan.",
        }, device_id, should_set_cookie, 413)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _response_with_device_cookie({
            "ok": False,
            "error": "invalid_json",
            "message": "Format JSON tidak valid.",
        }, device_id, should_set_cookie, 400)
    with _history_store_lock():
        clean_payload = _sanitize_history_payload(payload)
        store = _load_history_store()
        updated = int(time.time() * 1000)
        devices = store.setdefault("devices", {})
        devices[device_id] = _merge_device_history(devices.get(device_id), clean_payload, updated)
        _save_history_store(store)
    return _response_with_device_cookie({
        "ok": True,
        "device": device_id[:8],
        "saved": len(store["devices"][device_id]["chats"]),
        "active": store["devices"][device_id]["active"],
        "updated": updated,
    }, device_id, should_set_cookie)

# Route to fetch models
@app.route('/fetch-models', methods=['GET'])
def fetch_models_route():
    return jsonify(preloaded_models)

# Route to handle saving settings
@app.route('/save-settings', methods=['POST'])
def save_settings_route():
    global api_key, base_url, openai_client, preloaded_models
    if DISABLE_USER_API_SETTINGS:
        preloaded_models = [DEFAULT_MODEL]
        return _json_error(
            "settings_locked",
            "Pengaturan API dikunci di server production.",
            403,
            {"models": preloaded_models},
        )
    payload, error_response = _get_json_payload(TITLE_MAX_BODY)
    if error_response:
        return error_response
    api_key = payload.get('apiKey')
    base_url = payload.get('baseUrl')
    openai_client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url,
    )
    save_settings(api_key, base_url)
    preloaded_models = fetch_models()
    return jsonify({"status": "success"})

# Route to handle chat requests
@app.route('/chat', methods=['POST'])
def chat():
    allowed, retry_after = _check_rate_limit("chat", RATE_LIMIT_CHAT)
    if not allowed:
        return _rate_limited_response(retry_after)
    payload, error_response = _get_json_payload(CHAT_MAX_BODY)
    if error_response:
        return error_response
    user_content = payload.get('message')
    conversation_history = payload.get('conversation', [])
    selected_model = payload.get('model') or DEFAULT_MODEL
    system_content = SYSTEM_CONTENT
    parameters = sanitize_model_parameters(payload.get('parameters', {}))
    is_deep_query_mode = payload.get('isDeepQueryMode', False)
    start_tag = payload.get('startTag', '<think>')
    memory_context = payload.get('memoryContext') or payload.get('memory')
    library_grounding_mode = _clean_text(payload.get("libraryGrounding") or "auto", 40).lower()
    if library_grounding_mode not in {"auto", "force", "off"}:
        library_grounding_mode = "auto"
    library_context_mode = _clean_text(payload.get("libraryContextMode") or "snippet", 40).lower()
    if library_context_mode not in {"snippet", "full"}:
        library_context_mode = "snippet"
    sources_metadata = []

    if isinstance(user_content, str):
        user_content = _strip_client_library_context(user_content)
    original_latest_text = message_text(user_content)

    if user_content is None or (isinstance(user_content, str) and not user_content.strip()):
        return _json_error("empty_message", "Pesan tidak boleh kosong.", 400)
    conversation_history, conversation_error = _validate_conversation_history(conversation_history)
    if conversation_error:
        return _json_error(
            "invalid_conversation",
            "Format riwayat percakapan tidak valid.",
            400,
            {"detail": conversation_error},
        )
    image_intent = is_image_intent_text(message_text(user_content))
    hai_intent = "image" if image_intent else "text"
    member_ai_chat_intent = bool(not image_intent and _member_ai_chat_ready())
    response_id = f"resp_{secrets.token_hex(16)}"
    if image_intent:
        prompt_text = message_text(user_content)

        def produce_image(emit):
            image_response, _image_mode = _image_response_for_prompt(prompt_text)
            for chunk in _stream_plain_text(image_response):
                emit(chunk)

        return Response(
            _stream_with_heartbeat(
                produce_image,
                log_name="chat_image_stream",
                fallback_message="Pembuatan gambar belum bisa diselesaikan. Silakan coba lagi.",
                response_id=response_id,
            ),
            mimetype='text/event-stream',
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "X-HAI-Intent": "image",
                "X-HAI-Artifact-Mode": "streaming",
                "X-HAI-Response-ID": response_id,
            },
        )
    if not image_intent:
        system_content = _apply_memory_context(system_content, memory_context)

    additional_text = ""
    member_ai_user_content = None
    # Only process search commands if user_content is a string (not an image message)
    if isinstance(user_content, str):
        if user_content.lower().startswith("@s") and (len(user_content) == 2 or user_content[2].isspace()):
            user_content = user_content[2:].strip()

            # Check for YouTube link
            if re.search(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+', user_content):
                additional_text = handle_youtube_command(user_content)
                source_match = re.search(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/[^ ]+', user_content)
                if source_match:
                    source_url = source_match.group(0)
                    if not source_url.startswith("http"):
                        source_url = "https://" + source_url
                    sources_metadata.append(_source_metadata(source_url, title="YouTube", source="youtube"))
                user_content = re.sub(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/[^ ]+', '', user_content).strip()
                if user_content:
                    system_content = "You are an assistant specialized in Question & Answer. Please provide a clear and concise response to the user query based on the video transcript. Query: {}".format(user_content)
                    user_content = f"{user_content} \n\n "
                else:
                    system_content = "You are an assistant specialized in summarizing videos. Please provide a clear, concise and well-formatted summary of the video content."

            # Check for arXiv link
            elif re.search(r'https?://arxiv\.org/(abs|pdf)/\d+\.\d+(v\d+)?', user_content):
                source_match = re.search(r'https?://arxiv\.org/(abs|pdf)/\d+\.\d+(v\d+)?', user_content)
                try:
                    additional_text = handle_arxiv_command(user_content)
                except Exception as e:
                    app.logger.warning("arxiv_fetch_failed: %s", e)
                    return _json_error("source_fetch_failed", "Sumber arXiv belum bisa dibaca saat ini. Coba lagi nanti atau kirim ringkasan/PDF sebagai lampiran.", 502)
                if additional_text is None:
                    return "Invalid arXiv URL"
                if source_match:
                    sources_metadata.append(_source_metadata(source_match.group(0), title="arXiv paper", source="arxiv"))
                # Extract any user query after the arXiv link
                user_content = re.sub(r'https?://arxiv\.org/(abs|pdf)/\d+\.\d+(v\d+)?[^ ]*', '', user_content).strip()
                if user_content:
                    system_content = system_content = "You are an assistant specialized in Question & Answer. Please provide a clear and concise response to the user query based on the arXiv paper. Query: {}".format(user_content)
                    user_content = f"{user_content} \n\n "
                else:
                    system_content = "You are an assistant specialized in summarizing arXiv papers. Please provide a clear, concise and well-formatted summary of the paper's content."

            # Check for general link
            elif re.search(r'https?://[^\s]+', user_content):
                source_match = re.search(r'https?://[^\s]+', user_content)
                try:
                    additional_text = handle_webpage_command(user_content)
                except Exception as e:
                    app.logger.warning("webpage_fetch_failed: %s", e)
                    return _json_error("source_fetch_failed", "Halaman web belum bisa dibaca saat ini. Coba lagi nanti atau kirim teks pentingnya langsung.", 502)
                if additional_text is None:
                    return "Please provide a valid URL"
                if source_match:
                    sources_metadata.append(_source_metadata(source_match.group(0), source="webpage"))
                user_content = re.sub(r'https?://[^\s]+[^ ]*', '', user_content).strip()
                if user_content:
                    system_content = "You are an assistant specialized in Question & Answer. Please provide a clear and concise response to the user query based on the webpage content. Query: {}".format(user_content)
                    user_content = f"{user_content} \n\n "
                else:
                    system_content = "You are an assistant specialized in summarizing webpages. Please provide a clear, concise and well-formatted summary of the webpage content."

            # No link, treat as general search
            else:
                additional_text, sources_metadata = handle_search_payload(user_content)
                user_content = f"SEARCH QUERY: {user_content} \n\n "
                system_content = search_system_prompt(user_content, auto=False)
        elif (not member_ai_chat_intent) and not image_intent and should_auto_web_ground(user_content):
            original_query = user_content
            additional_text, sources_metadata = handle_search_payload(original_query)
            if sources_metadata:
                user_content = f"SEARCH QUERY: {original_query} \n\n "
                system_content = search_system_prompt(original_query, auto=True)

    library_grounding_meta = {"mode": library_grounding_mode, "context_mode": library_context_mode, "used": False, "count": 0}
    if not image_intent and isinstance(user_content, str):
        library_context, library_sources, library_grounding_meta = _library_grounding_for_request(
            original_latest_text or user_content,
            library_grounding_mode,
            library_context_mode,
        )
        if library_context:
            additional_text = _clamp_additional_text(f"{additional_text}\n\n{library_context}".strip())
            sources_metadata.extend(library_sources)
    additional_text = _clamp_additional_text(additional_text)
    if member_ai_chat_intent and isinstance(user_content, str):
        member_ai_user_content = user_content
        if additional_text:
            member_ai_user_content = (
                f"{user_content}\n\n"
                "Konteks sumber terverifikasi dari perintah pencarian/web. "
                "Gunakan hanya jika relevan, jangan tampilkan URL mentah di jawaban:\n"
                f"{additional_text}"
            ).strip()

    if not image_intent:
        system_content = _with_response_quality_rules(system_content)

    # Filter reasoning content from conversation history
    filtered_history = filter_reasoning_content(conversation_history, start_tag, end_tag='</think>')
    
    # Handle messages with images
    if isinstance(user_content, list):
        # The message contains both text and image
        messages = [{"role": "system", "content": IMAGE_ARTIFACT_SYSTEM if image_intent else system_content}] if (system_content or image_intent) else []
        messages.extend(filtered_history)
        messages.append({"role": "user", "content": user_content})
    else:
        # Regular text message
        final_system = IMAGE_ARTIFACT_SYSTEM if image_intent else system_content
        if final_system:
            messages = [{"role": "system", "content": final_system}] + filtered_history + [{"role": "user", "content": user_content + additional_text}]
        else:
            messages = filtered_history + [{"role": "user", "content": user_content + additional_text}]

    # Add deep query mode message if enabled
    if is_deep_query_mode:
        messages.append({"role": "assistant", "content": f"{start_tag}"})

    def produce_chat(emit):
        if member_ai_chat_intent:
            try:
                if _member_ai_emit_chat(member_ai_user_content if member_ai_user_content is not None else user_content, conversation_history, emit):
                    return
            except Exception as error:
                app.logger.warning("member_ai_google_chat_bridge_error: %s", error)

        if openai_client is None:
            emit("Harmonika AI belum siap. Coba lagi sebentar.")
            return

        # Track the current state: None, 'reasoning', or 'content'
        current_mode = None

        try:
            # Create the stream (keeping your existing parameter logic)
            if parameters:
                stream = openai_client.chat.completions.create(
                    model=selected_model,
                    messages=messages,
                    stream=True,
                    **parameters
                )
            else:
                stream = openai_client.chat.completions.create(
                    model=selected_model,
                    messages=messages,
                    stream=True
                )

            for chunk in stream:
                if not chunk.choices or not chunk.choices[0].delta:
                    continue
                
                delta = chunk.choices[0].delta
                
                # 1. Handle Reasoning Content
                # We check truthiness (val) to ignore empty strings often sent as keep-alives
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    if current_mode != 'reasoning':
                        # We are entering reasoning mode
                        emit("<think>")
                        current_mode = 'reasoning'
                    emit(delta.reasoning_content)
                
                # 2. Handle Regular Content
                # Use elif because a delta usually contains one or the other
                elif delta.content:
                    if current_mode == 'reasoning':
                        # We are leaving reasoning mode
                        emit("</think>")
                        current_mode = 'content'
                    emit(delta.content)
            
        except Exception as e:
            # If an error occurs, ensure we close the tag if we are inside reasoning
            if current_mode == 'reasoning':
                emit("</think>")
                current_mode = None # Update state so finally doesn't double-close
            app.logger.warning("chat_stream_error: %s", e)
            emit("\n\nMaaf, koneksi ke Harmonika AI terputus. Silakan coba lagi.")
        
        finally:
            # FINAL SAFETY NET: Ensure the tag is closed even if the stream 
            # ends abruptly without sending a final content chunk.
            if current_mode == 'reasoning':
                emit("</think>")

    def generate():
        yield from _stream_with_heartbeat(produce_chat, log_name="chat_stream", response_id=response_id)

    response_headers = {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "X-HAI-Intent": hai_intent,
        "X-HAI-Response-ID": response_id,
        "X-HAI-Library-Grounding": base64.urlsafe_b64encode(
            json.dumps(library_grounding_meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).decode("ascii"),
    }
    if member_ai_chat_intent:
        inline_attachments = ["inline-image"] if isinstance(user_content, list) else []
        response_headers["X-HAI-Mode"] = _member_ai_route_mode(user_content, inline_attachments)
    encoded_sources = _encode_sources_header(sources_metadata)
    if encoded_sources:
        response_headers["X-HAI-Sources"] = encoded_sources
    return Response(generate(), mimetype='text/event-stream', headers=response_headers)

# Route to handle chat requests
@app.route('/continue_generation', methods=['POST'])
def continue_generation():
    allowed, retry_after = _check_rate_limit("chat", RATE_LIMIT_CHAT)
    if not allowed:
        return _rate_limited_response(retry_after)
    payload, error_response = _get_json_payload(CHAT_MAX_BODY)
    if error_response:
        return error_response
    conversation_history = payload.get('conversation', [])
    selected_model = payload.get('model') or DEFAULT_MODEL
    system_content = SYSTEM_CONTENT
    parameters = sanitize_model_parameters(payload.get('parameters', {}))
    memory_context = payload.get('memoryContext') or payload.get('memory')
    conversation_history, conversation_error = _validate_conversation_history(conversation_history)
    if conversation_error:
        return _json_error(
            "invalid_conversation",
            "Format riwayat percakapan tidak valid.",
            400,
            {"detail": conversation_error},
        )
    system_content = _apply_memory_context(system_content, memory_context)
    system_content = _with_response_quality_rules(system_content)
    response_id = f"resp_{secrets.token_hex(16)}"

    # Filter reasoning content from conversation history
    filtered_history = filter_reasoning_content(conversation_history, start_tag='<think>', end_tag='</think>')
    
    if system_content == '':
        messages = filtered_history
    else:
        messages = [{"role": "system", "content": system_content}] + filtered_history

    def produce_continue(emit):
        if openai_client is None:
            emit("Harmonika AI belum siap. Coba lagi sebentar.")
            return

        # Track the current state: None, 'reasoning', or 'content'
        current_mode = None

        try:
            # Create the stream (keeping your existing parameter logic)
            if parameters:
                stream = openai_client.chat.completions.create(
                    model=selected_model,
                    messages=messages,
                    stream=True,
                    **parameters
                )
            else:
                stream = openai_client.chat.completions.create(
                    model=selected_model,
                    messages=messages,
                    stream=True
                )

            for chunk in stream:
                if not chunk.choices or not chunk.choices[0].delta:
                    continue
                
                delta = chunk.choices[0].delta
                
                # 1. Handle Reasoning Content
                # We check truthiness (val) to ignore empty strings often sent as keep-alives
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    if current_mode != 'reasoning':
                        # We are entering reasoning mode
                        emit("<think>")
                        current_mode = 'reasoning'
                    emit(delta.reasoning_content)
                
                # 2. Handle Regular Content
                # Use elif because a delta usually contains one or the other
                elif delta.content:
                    if current_mode == 'reasoning':
                        # We are leaving reasoning mode
                        emit("</think>")
                        current_mode = 'content'
                    emit(delta.content)
            
        except Exception as e:
            # If an error occurs, ensure we close the tag if we are inside reasoning
            if current_mode == 'reasoning':
                emit("</think>")
                current_mode = None # Update state so finally doesn't double-close
            app.logger.warning("continue_stream_error: %s", e)
            emit("\n\nMaaf, koneksi ke Harmonika AI terputus. Silakan coba lagi.")
        
        finally:
            # FINAL SAFETY NET: Ensure the tag is closed even if the stream 
            # ends abruptly without sending a final content chunk.
            if current_mode == 'reasoning':
                emit("</think>")

    def generate():
        yield from _stream_with_heartbeat(produce_continue, log_name="continue_stream", response_id=response_id)

    return Response(generate(), mimetype='text/event-stream', headers={
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
        "X-HAI-Response-ID": response_id,
    })

# Route to generate a title for the conversation
@app.route('/generate-title', methods=['POST'])
def generate_title():
    allowed, retry_after = _check_rate_limit("title", RATE_LIMIT_TITLE)
    if not allowed:
        return _rate_limited_response(retry_after)
    payload, error_response = _get_json_payload(TITLE_MAX_BODY)
    if error_response:
        return error_response
    message = _clean_text(payload.get('message'), 12000)
    selected_model = payload.get('model') or DEFAULT_MODEL
    assistant_response = _clean_text(payload.get('assistantResponse', ''), 4000)
    
    try:
        messages = [
            {
                "role": "system",
                "content": "Generate a 5-word max title for this conversation. Focus on the main topic. Respond ONLY with the title without any quotation."
            },
            {
                "role": "user",
                "content": f"User message: {message} \n \n Assistant response: {assistant_response}"
            }
        ]
        
        response = openai_client.chat.completions.create(
            model=selected_model,
            messages=messages,
            temperature=0
        )
        
        title = _clean_chat_title(response.choices[0].message.content)
        return jsonify({"title": title})
    except Exception as e:
        print(f"Error generating title: {e}")
        return jsonify({"title": None})

# Load settings and preload models when the app starts
print("Starting Harmonika AI Chat WebUI")
load_settings()
preload_models()

# Run the Flask app
if __name__ == '__main__':
    app.run(
        host=os.getenv("HAI_HOST", "127.0.0.1"),
        port=int(os.getenv("HAI_PORT", "3002")),
        debug=os.getenv("HAI_FLASK_DEBUG", "0") == "1",
    )
