# Phase 209 — Gemini Readiness Contract

Tujuan fase ini adalah membuat status kesiapan `hai.harmonika.id` bisa diaudit tanpa membaca README panjang. Endpoint baru `/api/readiness` memisahkan dua hal:

- `production.public_mvp_ready=true`: fitur inti chat web publik sudah siap dipakai.
- `production.full_platform_complete=false`: fitur platform besar seperti RAG library permanen, realtime replay/WSS, voice/video, calendar/automation/admin analytics, dan raster image provider penuh masih roadmap.

## Endpoint

`GET /api/readiness`

Kontrak utama:

- `core`: flag fitur MVP yang sudah siap, seperti chat, streaming, history, responsive UI, web search/source chips, upload file, PDF/image input, queue, memory ringan, artifact canvas dasar, dan release gate.
- `roadmap`: modul yang belum boleh diklaim selesai, dengan `status=planned|pending|ready` dan alasan singkat.
- `contracts`: guard penting untuk client/public, termasuk tidak membuka public media URL, referensi web tidak menampilkan full URL di bubble, batas lampiran, dan format hasil gambar.

## QA

Ditambahkan `scripts/hai_readiness_qa.py`.

Yang diverifikasi:

- `/api/readiness` HTTP 200 dan JSON `ok=true`.
- `public_mvp_ready=true` tetapi `full_platform_complete=false`.
- Core MVP flags wajib bernilai true.
- Roadmap wajib memuat:
  - `raster_image_generation`
  - `rag_library`
  - `realtime_resume_wss`
  - `voice_video`
  - `calendar_automation_admin`
- `contracts.raster_public` harus selaras dengan `/api/capabilities.features.raster_image_generation`.
- Response tidak boleh membocorkan kata/field secret seperti token, bearer, password, api key, atau secret.

`scripts/hai_production_qa.py` sekarang memasukkan `readiness_api` ke public release gate.

## Catatan untuk konsultasi Gemini

Status yang aman diklaim:

- Public MVP web chat sudah siap berdasarkan gate produksi.
- Generate gambar aman di UI sebagai private artifact preview/download, tetapi raster image provider production masih belum diklaim penuh jika `raster_image_generation=false`.
- Web references sudah rapi tanpa full URL di bubble, tetapi belum sama dengan RAG/vector library permanen.
- Memory yang tersedia masih lightweight per device/browser, bukan persistent semantic memory penuh lintas akun.
