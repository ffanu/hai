# Phase 233 — Codex Image Bridge Timeout Fix

Tanggal: 2026-10-06

## Temuan

User melaporkan pembuatan gambar web tidak memakai endpoint Codex/backend `chat.harmonika.id`.

Audit production menunjukkan:

- `hai.harmonika.id` sudah punya bridge aktif:
  - `HAI_MEMBER_AI_IMAGE_BRIDGE=1`
  - `HAI_MEMBER_AI_BASE_URL=http://127.0.0.1:3210/v1/member-ai`
  - token server-side tersedia.
- Request web ke `/api/images/generations` jatuh ke fallback lokal:
  - `fallback_reason=member_ai_bridge_unavailable`
  - `mode=local_svg_file_fallback`
- Log production menunjukkan:
  - `member_ai_image_generation_api_error: timed out`
  - `member_ai_image_bridge_error: timed out`

Smoke langsung ke bridge member-AI berhasil, tetapi butuh sekitar 49 detik dan mengembalikan PNG private:

- HTTP `201 Created`
- `mime_type=image/png`
- `file_id=file_*`
- `status=ready`
- ukuran hasil `1536x1024`

## Perubahan

- Default `HAI_MEMBER_AI_TIMEOUT` dinaikkan dari `75` ke `180` detik.
- Default `HAI_MEMBER_AI_IMAGE_TIMEOUT` dinaikkan dari `18` ke `120` detik.
- Production env perlu selaras:
  - `HAI_MEMBER_AI_TIMEOUT=180`
  - `HAI_MEMBER_AI_IMAGE_TIMEOUT=120`
  - `HAI_MEMBER_AI_RASTER_PUBLIC=1` setelah smoke bridge private file lulus.

## Harapan hasil

Saat user meminta gambar:

- `/chat` dan `/api/images/generations` menunggu bridge Codex cukup lama.
- Output memakai artifact private PNG dari backend bridge, bukan fallback SVG lokal.
- Thumbnail tetap lewat proxy lokal `/api/files/{file_id}/preview`, tanpa public URL/token.

## Catatan

Phase 232 heartbeat menjaga stream chat tetap hidup selama image bridge menunggu hasil.
