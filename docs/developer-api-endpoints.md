# Harmonika AI Web Developer API

Dokumen ini adalah ringkasan endpoint production untuk developer Harmonika yang mengintegrasikan web `hai.harmonika.id`.

Base URL production:

```text
https://hai.harmonika.id
```

Catatan keamanan:

- Endpoint web memakai cookie device/session browser. Jangan expose token backend `chat.harmonika.id` ke frontend.
- File/artifact gambar dilayani lewat `file_id` privat dan proxy `/api/files/...`, bukan URL publik permanen.
- UI publik cukup memakai `/chat`; routing Google Mode/Codex/image bridge dipilih server-side.
- Semua response error API sebaiknya diperlakukan customer-safe dan ditampilkan singkat di UI.

## Endpoint utama chat

### `POST /chat`

Streaming jawaban chat utama. Browser/web UI memakai endpoint ini untuk teks umum, upload/vision context, pencarian sumber, dan intent gambar.

Headers:

```http
Content-Type: application/json
Accept: text/event-stream
```

Body minimal:

```json
{
  "message": "Jelaskan apa itu router dalam satu kalimat"
}
```

Body dengan riwayat/lampiran/context opsional:

```json
{
  "message": "Ringkas dokumen ini",
  "conversation": [
    {"role": "user", "content": "Halo"},
    {"role": "assistant", "content": "Halo, ada yang bisa dibantu?"}
  ],
  "attachments": [
    {
      "id": "local-or-client-id",
      "name": "dokumen.pdf",
      "mime_type": "application/pdf",
      "content": "Cuplikan teks hasil parse bila dikirim dari client"
    }
  ],
  "libraryGrounding": "auto",
  "libraryContextMode": "snippet"
}
```

Response:

- Body dikirim streaming sebagai teks/SSE-compatible chunks.
- Header penting:
  - `X-HAI-Response-ID`: ID response untuk replay/resume.
  - `X-HAI-Mode`: mode internal aman seperti `google`.
  - `X-HAI-Intent`: `text` atau `image`.
  - `X-HAI-Sources`: metadata sumber aman, bila ada.
  - `X-HAI-Library-Grounding`: metadata Library grounding aman, bila dipakai.

Contoh curl:

```bash
curl -N https://hai.harmonika.id/chat \
  -H 'Content-Type: application/json' \
  -H 'Accept: text/event-stream' \
  --data '{"message":"Beri 3 ide promosi usaha makanan rumahan"}'
```

### `POST /continue_generation`

Melanjutkan jawaban yang terpotong.

```json
{
  "conversation": [{"role": "user", "content": "Tulis outline artikel"}],
  "previous_response": "Bagian jawaban sebelumnya..."
}
```

### `POST /generate-title`

Membuat judul percakapan dari pesan.

```json
{
  "message": "Diskusi strategi promosi makanan rumahan"
}
```

## Capabilities dan readiness

### `GET /api/capabilities`

Dipakai frontend/developer untuk mengetahui fitur yang aktif.

Field penting:

- `features.chat`
- `features.streaming`
- `features.google_mode`
- `features.web_search`
- `features.file_upload`
- `features.pdf_input`
- `features.rag_library_ui`
- `features.rag_library_grounding`
- `features.realtime_replay_api`
- `features.admin_overview`
- `image_features.image_generation`
- `image_features.image_preview`
- `image_features.image_download`
- `limits.attachments_per_message`
- `limits.max_upload_bytes`
- `limits.image_generations_per_day`
- `limits.image_sizes`
- `chat_routing.default_mode`
- `chat_routing.google_mode_policy`
- `chat_routing.codex_policy`

### `GET /api/readiness`

Ringkasan status production untuk owner/developer.

Field penting:

- `production.public_mvp_ready`
- `production.full_platform_complete`
- `production.gate`
- `production.gate_result`
- `core`
- `roadmap_status`
- `next_priority_ids`

### `GET /healthz`

Health check ringan untuk load balancer/monitoring.

## Upload dan lampiran

### `POST /api/attachments/parse`

Parse file dari web UI sebelum dikirim ke chat.

Headers:

```http
Content-Type: multipart/form-data
```

Form field:

```text
file=<PDF/TXT/CSV/DOCX/XLSX/PNG/JPEG/WebP>
```

Kontrak:

- Maksimal upload mengikuti `GET /api/capabilities.limits.max_upload_bytes` saat ini 10 MB.
- Maksimal lampiran per pesan mengikuti `limits.attachments_per_message` saat ini 3.
- Response berisi metadata file dan teks hasil parse bila tipe dokumen bisa dibaca.
- Gambar dipakai untuk vision context; jangan tampilkan base64/data URL di UI.

Error umum:

- `file_required`
- `file_too_large`
- `unsupported_file_type`
- `file_content_unreadable`
- `vision_unavailable`

## Image generation dan artifact privat

### `POST /api/images/generations`

Membuat gambar lewat backend server-side. Frontend tidak tahu provider internal.

Headers:

```http
Content-Type: application/json
Idempotency-Key: <uuid-opsional>
```

Body:

```json
{
  "prompt": "Buat gambar logo robot biru futuristik",
  "size": "1024x1024",
  "count": 1
}
```

Success:

```json
{
  "ok": true,
  "mode": "member_ai_bridge",
  "images": [
    {
      "file_id": "file_xxx",
      "mime_type": "image/png",
      "width": 1024,
      "height": 1024,
      "size_bytes": 123456,
      "status": "ready",
      "source_prompt": "Buat gambar logo robot biru futuristik",
      "requested_size": "1024x1024",
      "preview_url": "/api/files/file_xxx/preview",
      "download_url": "/api/files/file_xxx/download"
    }
  ]
}
```

Error umum:

- `invalid_prompt`
- `image_generation_disabled`
- `image_quota_exceeded`
- `image_generation_failed`
- `image_bridge_unavailable`

### `GET /api/files/{file_id}/preview`

Preview artifact privat. Gunakan untuk thumbnail/canvas. Response harus `image/*` untuk gambar.

### `GET /api/files/{file_id}/download`

Download artifact privat. UI boleh memakai nama file dari `Content-Disposition` setelah disanitasi.

## Library / RAG per device

### `GET /api/library/documents`

List dokumen Library milik cookie device saat ini. Tidak mengirim full text.

### `POST /api/library/documents`

Upload dokumen Library.

Form field:

```text
file=<PDF/TXT/CSV/DOCX/XLSX>
```

### `DELETE /api/library/documents/{doc_id}`

Hapus dokumen Library milik device.

### `POST /api/library/search`

Cari snippet dokumen Library.

```json
{
  "query": "kata kunci yang dicari",
  "limit": 3
}
```

Response mengirim snippet aman, ranking/retrieval metadata, dan tidak mengekspos full text.

## History lokal web

### `GET /api/history`

Mengambil history percakapan device/browser saat ini.

### `PUT /api/history`

Menyimpan history percakapan dari frontend.

### `POST /api/history`

Operasi history kompatibilitas untuk client lama.

## Realtime resume/replay

### `GET /api/realtime/events?response_id=...&after_sequence=...`

Replay event response bila koneksi streaming putus.

Mode JSON default:

```json
{
  "ok": true,
  "response_id": "resp_xxx",
  "events": [
    {
      "event_id": "resp_xxx:1",
      "response_id": "resp_xxx",
      "sequence": 1,
      "timestamp": "2026-10-07T09:00:00Z",
      "type": "response.output_text.delta",
      "data": {"text": "Halo"}
    }
  ],
  "terminal": true,
  "last_sequence": 1,
  "next_after_sequence": 1,
  "expires_at": "2026-10-07T09:05:00Z"
}
```

SSE replay:

```http
Accept: text/event-stream
Last-Event-ID: <sequence-opsional>
```

### `POST /api/realtime/ticket`

Kontrak ticket WSS masa depan. Saat WSS gateway belum aktif, endpoint fail-safe dengan `503 realtime_wss_not_ready` dan memberi fallback `/chat` + `/api/realtime/events`.

## Admin/observability

### `GET /admin`

Dashboard owner/admin aggregate-only.

### `GET /api/admin/overview`

Mengirim statistik aggregate saja:

- jumlah history/library/realtime/rate-limit/storage
- chat aktif 24 jam/7 hari
- pesan user/assistant
- attachment/artifact/source counts

Endpoint ini tidak boleh mengirim isi chat, teks dokumen, device ID, token, atau secret.

## Model/settings compatibility

### `GET /fetch-models`

Endpoint kompatibilitas untuk UI model selector.

### `POST /save-settings`

Endpoint kompatibilitas penyimpanan setting UI.

## Ringkasan flow developer

1. Saat app dibuka, panggil `GET /api/capabilities`.
2. Untuk chat normal, selalu kirim ke `POST /chat` dengan `Accept: text/event-stream`.
3. Simpan `X-HAI-Response-ID` bila ingin replay saat stream putus.
4. Untuk file sementara dalam chat, parse lewat `POST /api/attachments/parse`, lalu kirim metadata/teks aman ke `/chat`.
5. Untuk Library permanen per device, gunakan `/api/library/documents` dan `/api/library/search`; backend `/chat` dapat melakukan grounding server-side.
6. Untuk gambar, gunakan intent natural lewat `/chat` atau endpoint eksplisit `/api/images/generations`; render hanya dari `file_id` preview/download privat.
7. Untuk status produksi, baca `/api/readiness` dan `/healthz`.
