# Phase 199 — Gemini Readiness Checkpoint

Tanggal: 2026-10-06

Tujuan dokumen ini adalah memberi bahan konsultasi ulang ke Gemini/owner tentang posisi terbaru `hai.harmonika.id` setelah Phase 198. Isinya dipisahkan antara yang sudah terbukti oleh source/QA production dan yang masih menjadi gap roadmap.

## Ringkasan status production

- Domain production: `https://hai.harmonika.id`
- Release aktif terakhir yang diverifikasi: `/srv/harmonika-chat-webui-release-20261006180228`
- Asset marker aktif: `20261006-phase198`
- Public release gate terakhir: `49/49` lulus
- Visual snapshot gate terakhir: `17/17` lulus
- Health endpoint: `/healthz` OK, secret production terkonfigurasi
- Capabilities publik utama aktif: chat, streaming, web search/source chips, file upload, PDF input, memory ringan, message queue, artifact canvas

## Matriks saran Gemini vs implementasi

| Area saran Gemini | Status | Evidence saat ini | Catatan |
| --- | --- | --- | --- |
| Empty state modern seperti ChatGPT/Claude/Z.ai | Selesai MVP | Welcome sederhana dengan logo HAI, teks “Selamat datang di Harmonika AI”, prompt chips; browser QA `empty` desktop/mobile hijau | Sudah lebih sederhana dari fase dashboard lama |
| Layout chat readable desktop/mobile | Selesai MVP | Lebar baca stabil, no horizontal overflow, screenshot desktop/mobile/tablet/landscape hijau | Tema saat ini mengikuti arahan owner: classic/AdminLTE, bukan neon/glass |
| Sidebar responsive/mobile | Selesai MVP | Sidebar overlay mobile, collapse desktop, topbar mobile compact; QA `sidebar-collapse`, `history-controls` hijau | Perlu tetap diawasi saat fitur history multi-chat bertambah |
| Auto-scroll streaming sopan | Selesai MVP | Smart scroll Phase 52, tombol “Ke terbaru”, QA layout/visual hijau | Sudah tidak menarik paksa user saat membaca atas |
| Composer modern | Selesai MVP | State kirim/stop/queue, attachment tray, keyboard/IME guard; QA `composer-keyboard`, `queue-composer` hijau | Composer sengaja classic netral |
| Stop generation | Selesai | QA `stop-stream` desktop/mobile hijau | Tombol submit berubah menjadi Stop saat streaming |
| Regenerate response | Selesai | QA `regenerate` desktop/mobile hijau | Dibatas untuk jawaban terakhir agar riwayat tidak bercabang liar |
| Markdown rich + code block | Selesai MVP | QA `markdown-rich` desktop/mobile/compact hijau, copy code lokal Indonesia | Tabel/code mobile sudah punya containment/scroll affordance |
| Web reference/citation rapi | Selesai MVP | `sources[]`, favicon/source stack, detail panel kecil, tanpa full URL di bubble; QA `sources-web` dan `sources-stack` hijau | Search/RAG masih bukan vector knowledge base penuh |
| Upload multimodal composer | Selesai sebagian | PDF/TXT/CSV/DOCX/XLSX dan image chip UI; max 3 file; QA attachment/multi-attachment hijau | Image upload web diteruskan per-request; vision production masih perlu audit engine |
| Attachment bubble/history | Selesai MVP | Bubble user menampilkan ringkasan file, history/export aman | Raw/base64 tidak disimpan ke history |
| Image generation loading/progress | Selesai UX dasar | Intent image punya step preview dan modal artifact; QA `image-modal` hijau | Provider gambar production masih gap utama |
| Image thumbnail modal | Selesai Phase 198 | Klik dalam modal tidak menutup; backdrop/Escape/tombol menutup; QA desktop/mobile hijau | Tidak expose link publik di UI |
| Artifact/canvas | Selesai dasar | Kanvas artefak, preview/copy/download, localization QA hijau | Dynamic artifacts/canvas seperti app mini belum ada |
| Persistent memory | Selesai ringan | Memory lokal per device/browser, `memoryContext` kecil | Belum memory akun/server-side multi-device |
| RAG/library/vector database | Belum | Tidak ada vector DB/library ingestion production | Web search ada, tetapi knowledge base permanen belum |
| Realtime resume/replay/WSS | Belum | SSE streaming ada, namun event replay/WSS belum production | Android/web bisa fallback history |
| Voice/video/STT/TTS | Belum | Tidak ada modul voice/video production | Bukan prioritas MVP web saat ini |
| Calendar/automation/analytics/admin | Belum | Tidak ada modul production | Modul besar terpisah dari chat MVP |

## Gap terbesar sebelum klaim “production lengkap”

1. **Generate gambar production**
   - UI sudah siap untuk artifact/thumbnail/modal.
   - Backend web sudah punya fallback SVG dan bridge opsional ke member AI.
   - Yang belum terbukti: provider/worker gambar raster private `file_id` yang stabil, kuota, recovery job, dan preview/download bearer end-to-end.

2. **Vision image input**
   - UI dan MIME image sudah ada di web capabilities.
   - Perlu audit engine agar PNG/JPEG/WebP benar-benar dibaca sebagai visual, bukan sekadar file diterima.
   - Jangan klaim image vision siap publik tanpa smoke test gambar nyata.

3. **RAG/library permanen**
   - Web search/reference sudah rapi.
   - Belum ada koleksi dokumen permanen, vector DB, reranking, atau library user/team seperti Open WebUI.

4. **Realtime recovery**
   - SSE dasar stabil.
   - Belum ada `response_id`, event replay, Last-Event-ID, atau WSS gateway production.

5. **Observability/admin**
   - QA release kuat, tetapi dashboard admin analytics/cost/usage belum ada.

## Rekomendasi fase berikut

### Phase 200 — Image generation contract smoke

Fokus: jangan tambah UI baru dulu. Buktikan kontrak gambar private dari backend:

- `/api/capabilities` menandai mode gambar yang benar.
- Prompt “buat gambar ...” menghasilkan artifact private atau fallback aman.
- Tidak ada URL `/media` atau `/download` publik di bubble.
- Thumbnail tampil, modal terbuka, download aman.
- QA `image-artifact` dijalankan dengan mode provider aktif bila kuota memungkinkan.

### Phase 201 — Vision image input smoke

Fokus: upload gambar nyata dan minta AI menjelaskan isi gambar.

- Validasi MIME + magic bytes.
- Max 10 MB.
- Error aman: `unsupported_image`, `vision_unavailable`, `file_content_unreadable`.
- History tidak menyimpan base64/raw image.

### Phase 202 — Readiness UI polish after screenshots

Fokus: cek screenshot terbaru manual/visual dari:

- Desktop empty state.
- Desktop active chat long answer.
- Mobile empty state.
- Mobile chat long answer + keyboard/composer.
- Source stack + artifact modal.

### Phase 203 — RAG/search contract

Fokus: bedakan jelas “web search cepat” vs “library/RAG permanen”.

- Capabilities field untuk library belum aktif.
- Source chips tetap kecil.
- Tidak tampilkan full link kecuali user membuka detail.

## Acceptance untuk konsultasi Gemini berikutnya

Tanyakan ke Gemini/owner:

1. Apakah arah classic/AdminLTE masih disetujui, atau perlu kembali ke soft-modern ala ChatGPT?
2. Apakah prioritas berikutnya gambar production, vision upload, atau RAG library?
3. Untuk generate gambar, hasil harus raster image asli atau SVG/artifact lokal masih cukup sebagai MVP?
4. Apakah web publik tanpa login boleh punya memory server-side, atau tetap per device/browser?
5. Apakah fitur voice/video/calendar/automation masuk roadmap dekat atau ditahan setelah core chat stabil?

