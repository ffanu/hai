# Phase 219 — Current Gemini Consultation Report

Tanggal: 2026-10-07

Dokumen ini adalah ringkasan terbaru untuk konsultasi lanjutan ke Gemini/owner tentang status `hai.harmonika.id` sebagai web chat AI publik bergaya ChatGPT/Claude dengan tema classic rapi.

## Status production terbaru

- Domain: `https://hai.harmonika.id`
- Release aktif: `/srv/harmonika-chat-webui` — symlink production ke release timestamp terbaru
- Readiness endpoint: `/api/readiness`
- Public MVP: `ready`
- Full platform complete: `false`
- Gate terbaru: `phase319-public-release-gate`
- Gate result: `72/72 OK`
- Visual snapshots: `17/17 OK`
- Release audit terbaru: `6/6 OK` — sekarang termasuk `/api/readiness` dan halaman `/admin`
- Readiness QA terbaru: `7/7 OK`
- Routing backend terbaru: Phase 262 aktif — Google Mode menjadi default untuk jawaban umum, pertanyaan, analisa biasa, teman ngobrol, web/file/image input; Codex hanya untuk tugas teknis berat yang jelas dan sinyal pembuatan gambar private artifact.
- Public full gate terbaru: Phase 319 aktif — full public release gate production lulus stabil `72/72 OK`, termasuk routing policy QA, shared rate-limit QA, Library API/UI QA, browser Library panel desktop/mobile, attachment dokumen/gambar, source chips, a11y, streaming states, stream-stall, realtime replay, queue composer, keyboard/layout, image modal, Markdown rich, visual snapshots `17/17`, admin dashboard, release audit `6/6`, dan asset marker `20261007-phase319`.
- Targeted UI gate terbaru: Phase 319 aktif — targeted streaming/Markdown checks hijau, full gate besar hijau, dan runner browser flow berat sudah diberi retry/cooldown untuk menghindari false negative saat provider lambat.
- Patch UI terbaru: Phase 325 aktif — bug robot typing yang terlihat pucat/ghost, dobel avatar, dobel panel, dots mobile kepotong, dan badge hijau vertikal saat bot mulai mengetik ditutup dengan final EOF CSS guard. Jawaban streaming tetap memakai client-side typewriter buffer dengan bubble stabil; status composer diberi animasi robot/dots untuk "menyiapkan jawaban", "mencari referensi", dan "mengetik realtime" agar tidak terasa kosong. Saat backend selesai cepat, buffer dikuras bertahap dulu agar jawaban tidak langsung dump sekaligus. Loading membuat gambar tetap dibedakan dengan kartu render compact, code block bergaya editor, dan fallback stream kosong dirender sinkron agar tidak muncul bubble assistant kosong. Admin analytics Phase 316 tetap aktif. Marker UI `20261007-phase325`.
- Observability terbaru: Phase 302 aktif — `/api/admin/overview` tersedia sebagai overview aggregate-only tanpa chat content, document text, device IDs, atau secret.
- Dashboard admin terbaru: Phase 303 aktif — halaman `/admin` menampilkan dashboard aggregate-only classic yang membaca `/api/admin/overview`, tanpa inline script dan tanpa menampilkan data sensitif.
- Command full gate terakhir: `python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --public-release-gate --expected-asset-marker 20261007-phase319 --visual-out-dir qa-screenshots/phase319-public-release-gate-stable --json-out qa-reports/phase319-public-release-gate-stable.json`
- Realtime terbaru: Phase 292 aktif di source — `/chat` dan `/continue_generation` menyiapkan `X-HAI-Response-ID`, replay endpoint `/api/realtime/events`, dan kontrak ticket `/api/realtime/ticket` yang fail-safe; WSS tetap belum diklaim production.
- Library/RAG terbaru: Phase 318 aktif di source — Library memakai private hybrid sparse+hash-vector chunk index, BM25-lite/vector rerank, semantic alias expansion, dan tetap tidak mengekspos embedding/vector/full text di response publik. Full RAG tetap belum diklaim karena external managed vector DB/embedding lintas dokumen belum production.
- Hardening terbaru: Phase 250 aktif — rate-limit production memakai storage `file` bersama antar gunicorn worker (`shared_across_workers=true`), bukan bucket in-memory per worker.
- Bridge isolation terbaru: Phase 251 aktif — payload Google Mode web publik menginstruksikan backend `chat.harmonika.id/member-ai` agar menjawab pesan/lampiran terbaru dan mengabaikan konteks session internal lama. Focused production QA pasca deploy lulus `27/27 OK`, termasuk attachment TXT dan image vision.
- Session isolation terbaru: Phase 281 aktif — bridge chat web publik memakai lock server-side dan reset session upstream member-AI sebelum request, supaya lampiran/request paralel tidak saling terseret melalui token server bersama.
- Deploy safety terbaru: Phase 283 menambahkan finalizer release server-side yang mencegah `.venv` symlink loop saat deploy dan memvalidasi gunicorn/healthz sebelum release dianggap aktif.
- Deploy health retry terbaru: Phase 285 memperkuat finalizer agar `/healthz` ditunggu dengan retry setelah restart, sehingga gunicorn startup singkat tidak dianggap deploy gagal palsu.

## Saran Gemini yang sudah dikerjakan

| Saran Gemini | Status production | Bukti |
| --- | --- | --- |
| Empty state sederhana seperti ChatGPT/Claude | Selesai MVP | Welcome HAI, quick prompt, visual QA desktop/mobile/tablet |
| Layout chat readable | Selesai MVP | Visual snapshots active chat desktop/mobile/tablet/landscape |
| Responsive sidebar/mobile | Selesai MVP | Browser QA sidebar/history/mobile |
| Smart auto-scroll | Selesai MVP | QA layout/streaming; tombol ke terbaru |
| Composer modern | Selesai MVP | Kirim/Stop/Queue, attachment tray, keyboard guard |
| Stop generation | Selesai | QA `stop-stream` desktop/mobile |
| Regenerate response | Selesai | QA `regenerate` desktop/mobile |
| Markdown rich | Selesai MVP | Heading/list/table/code/copy/localization QA |
| Web references rapi | Selesai MVP | Source stack/favicon kecil, detail panel, tanpa full URL di bubble |
| Upload dokumen | Selesai MVP | PDF/TXT/CSV/DOCX/XLSX, max 3 lampiran |
| Upload gambar/vision web | Selesai MVP | PNG/JPEG/WebP capabilities, QA vision/image picker |
| Bubble lampiran/history | Selesai MVP | Attachment metadata tanpa URL publik/base64 |
| Image loading/progress | Selesai UX dasar | Step preview, kartu render, orb/scan/progressbar, dan artifact thumbnail/modal |
| Artifact/canvas basic | Selesai dasar | Kanvas/pratinjau/unduh/copy |
| Memory ringan | Selesai dasar | Per device/browser, bukan akun server-side |
| QA release otomatis | Selesai | Full public release gate terbaru `phase319-public-release-gate` `72/72`; visual snapshots `17/17` |
| Release audit readiness | Selesai | HTTP release audit ikut mengunci `/api/readiness`, gate `phase319-public-release-gate` `72/72`, visual `17/17`, dan previous full gate `72/72` |
| Backend source/runtime guard | Selesai fase awal | Source prompt clamp, source header budget aman proxy, error web/arXiv aman, rate-limit attachment dipisah |
| Streaming TTFB guard | Selesai fase awal | Frame awal internal `hai-open` difilter frontend dan dikunci QA default |
| Streaming idle-timeout guard | Selesai fase awal | Heartbeat internal `hai-ping` menjaga koneksi saat upstream lambat |
| Realtime connection pill | Selesai UX dasar | Topbar menampilkan `Siap`, `Realtime`, `Menyambung ulang`, dan `Dipulihkan` untuk stream/replay recovery tanpa mengekspos detail WSS |
| Realtime WSS ticket contract | Selesai kontrak awal | `POST /api/realtime/ticket` ada dan fail-safe `realtime_wss_not_ready`; clients tetap fallback ke `/chat` + `/api/realtime/events` sampai gateway WSS siap |
| Raster image generation provider | Selesai production | Codex/member-AI bridge `member_ai_bridge`, PNG private `file_id`, preview/download Bearer proxy lokal, QA gambar `6/6` |
| Google Mode sebagai jawaban utama | Selesai production | `chat_routing.default_mode=google`, `question_analysis_story_mode=google`, `file_input_mode=google`, `image_input_mode=google`, `codex_policy=heavy_technical_only` |
| Codex khusus tugas berat/gambar | Selesai production | `technical_task_mode=codex`, `image_creation_task_mode=codex`, `image_creation_request_mode=codex`; body image punya retry aman bila backend strict |
| Shared rate-limit multi-worker | Selesai production | `HAI_RATE_LIMIT_STORAGE=file`, `/api/capabilities.rate_limit.shared_across_workers=true`, `scripts/hai_rate_limit_qa.py` |
| Google Mode payload/session isolation | Selesai production | `_member_ai_text_payload()` membungkus pesan terbaru dan blok `[Document: ...]`; attachment browser QA kembali menyebut marker dari file |
| Member-AI shared session isolation | Selesai production | Bridge web publik mengunci request chat member-AI dan reset session upstream per request; readiness mengekspos `member_ai_chat_session_isolation=true` |
| RAG/library backend foundation | Selesai pondasi | `/api/library/documents`, `/api/library/search`, per-device storage, upload/list/search/delete |
| RAG/library UI + snippet grounding | Selesai fase awal | Sidebar Library untuk upload/list/search/delete; backend `/chat` memakai snippet relevan atau full-context terbatas sebagai konteks internal dan mengirim source `library` tanpa URL; vector DB embedding masih pending |
| RAG/library retrieval hardening | Selesai fase awal | Chunk scoring untuk konteks jauh, `409 library_full` tanpa silent eviction, dan bucket rate-limit `library` terpisah |
| RAG/library semantic/BM25/vector rerank lite | Selesai fase lanjut | Search Library memakai `hybrid_vector_lexical_semantic_rerank`, private hybrid sparse+hash-vector index, BM25-lite length normalization, semantic alias expansion, cosine similarity lokal, `chunk_index`, `match_coverage`, `vector_similarity`, dan `ranking` tanpa full text/embedding/vector publik |
| RAG/library grounding toggle | Selesai fase awal | Panel Library punya `Otomatis/Selalu/Mati`; backend `/chat` menerima `libraryGrounding`, konteks tetap server-side, dan header `X-HAI-Library-Grounding` memberi status aman |
| Library search sidebar backend | Selesai fase awal | Panel Library memanggil `/api/library/search` dan menampilkan snippet backend; browser QA mengunci hasil `HIDDEN-LIB-262` |

## Yang belum boleh diklaim selesai penuh

| Gap | Status | Catatan |
| --- | --- | --- |
| RAG/library/vector DB permanen | Pending advanced | UI library, snippet/full-context grounding, private sparse chunk index, BM25 sparse rerank, dan semantic alias expansion sudah ada; belum external vector DB embedding production |
| Realtime replay/WSS | Foundation | SSE dasar aktif, replay JSON/SSE endpoint punya state resume eksplisit; WSS gateway penuh belum production |
| Voice/video/STT/TTS | Planned | Belum bagian MVP web |
| Calendar/automation/scheduling | Planned | Modul besar terpisah |
| Admin analytics/cost/model evaluation | Planned | Belum dashboard admin production |
| Enterprise/team/channel workflow | Planned | Web publik saat ini tanpa login |

## Kontrak readiness yang bisa dicek owner/Gemini

```bash
curl -fsS https://hai.harmonika.id/api/readiness | python3 -m json.tool
```

Poin penting di response:

- `production.public_mvp_ready=true`
- `production.full_platform_complete=false`
- `production.gate="phase319-public-release-gate"`
- `production.gate_result.passed=72`
- `production.gate_result.total=72`
- `production.gate_result.visual_snapshots_passed=17`
- `production.gate_result.visual_snapshots_total=17`
- `production.gate_result.previous_full_public_gate_total=72`
- `next_priorities[0].id="rag_library"`
- `next_priorities[1].id="realtime_resume_wss"`

## Catatan update Phase 220–256

- Phase 220 memasukkan `/api/readiness` ke `scripts/hai_release_audit.py`, sehingga release audit terbaru menjadi `5/5 OK`.
- Phase 221 membuat release audit tetap menghasilkan JSON report gagal terstruktur saat target unreachable, bukan crash tanpa artefak audit.
- Dengan ini, bahan konsultasi Gemini tidak hanya menyebut status MVP, tetapi juga punya guard otomatis agar readiness tidak mundur tanpa ketahuan.
- Phase 230 menutup risiko prompt blow-up dari sumber web/arXiv/YouTube, memperkecil header referensi, dan membuat error fetch sumber tidak bocor sebagai HTML 500.
- Phase 231 menambahkan frame awal stream untuk text/image/continue agar koneksi segera aktif sebelum engine lambat merespons; frontend memfilter control frame supaya tidak tampil di bubble/riwayat.
- Phase 232 membungkus text/image/continue stream dengan worker queue + heartbeat berkala agar SSE tidak idle saat upstream lambat.
- Phase 233 memperbaiki timeout bridge gambar Codex/member-AI: request langsung ke bridge sukses ±49 detik, sehingga timeout 18 detik terlalu pendek dan menyebabkan fallback SVG.
- Phase 235 menyelaraskan timeout runner QA utama dengan realita image bridge agar kontrak `member_ai_bridge` tetap terkunci dalam production QA.
- Phase 246 memperbaiki source chip `@s`, touch target mobile, dan visual QA crops.
- Phase 247 menyinkronkan routing backend agar Google Mode menjadi jawaban utama sementara Codex hanya menangani tugas development/teknis berat.
- Phase 248 menambahkan QA deterministik untuk routing policy.
- Phase 249 menjalankan ulang full public release gate production dan lulus `63/63 OK`, lalu menyinkronkan readiness/report ke total gate terbaru.
- Phase 250 menutup gap opencode: rate-limit tidak lagi murni in-memory per worker, tetapi bisa memakai storage file bersama dengan lock dan write atomik.
- Phase 251 menutup bug attachment Google Mode: request web publik kini mengirim instruksi isolasi pesan terbaru/lampiran terbaru agar session backend internal tidak mencampur konteks QA sebelumnya.
- Phase 252 memperbarui report Gemini agar mencatat shared rate-limit dan isolasi payload.
- Phase 253 menjalankan ulang full public release gate setelah Phase 250–252 dan lulus `64/64 OK`; tambahan check adalah `rate_limit_storage_local`, visual snapshots tetap `17/17`.
- Phase 254 menambahkan `next_priorities` ke `/api/readiness` agar roadmap berikutnya eksplisit: RAG/library permanen, realtime resume/WSS, lalu admin analytics/observability.
- Phase 255 menambahkan pondasi backend library/RAG per device: upload/list/search/delete dokumen dengan storage privat per cookie device dan QA lokal `scripts/hai_library_qa.py`.
- Phase 255 public gate dijalankan ulang setelah library foundation dan lulus `65/65 OK`; readiness/report disinkronkan ke `phase255-public-release-gate`.
- Phase 256 memperkuat arahan routing owner: Google Mode tetap menjadi primary answer engine untuk jawaban, pertanyaan, analisa umum, teman cerita, web, file, dan image input; Codex hanya untuk coding/debug/deploy/stacktrace atau pembuatan gambar private artifact. Guard baru memastikan istilah umum seperti `kode promo` tetap Google Mode, bukan Codex.
- Phase 257 menambahkan UI Library di sidebar dan grounding snippet otomatis: dokumen per device bisa diupload/list/search/delete, lalu snippet relevan dikirim sebagai konteks internal chat tanpa mengekspos full text/ID internal ke UI.
- Phase 258 memindahkan grounding Library ke backend `/chat`, menghapus kebutuhan frontend menyisipkan blok `Konteks Library...`, dan mengaktifkan metadata source Library tanpa URL publik di `X-HAI-Sources`.
- Phase 259 memperkeras retrieval Library dan routing owner terbaru: snippet dicari per chunk agar konteks jauh tetap ditemukan, Library penuh mengembalikan `409 library_full` tanpa menghapus dokumen lama, endpoint Library memakai bucket rate-limit sendiri, dan Google Mode tetap menjadi jawaban utama untuk pertanyaan/analisa/teman cerita/web/file/image input sementara Codex hanya handoff teknis berat atau pembuatan gambar private artifact.
- Phase 260 menjalankan ulang full public release gate production setelah Phase 259 dan lulus `66/66 OK`; readiness/report sempat disinkronkan ke `phase260-public-release-gate`, visual snapshots tetap `17/17`, dan release audit tetap `5/5 OK`.
- Phase 261 menambahkan browser QA nyata untuk panel Library desktop/mobile, menaikkan touch target tombol hapus Library, cache-bust asset `20261007-phase261`, dan menjalankan ulang full public release gate production `68/68 OK`.
- Phase 262 mengunci ulang arahan owner: Google Mode tetap primary answer engine untuk jawaban/pertanyaan/analisa/teman cerita/web/file/baca gambar, sedangkan pembuatan gambar memberi sinyal `mode=codex` + header task ke backend gambar `chat.harmonika.id/member-ai` dengan retry body v1 bila endpoint strict.
- Phase 263 memperbaiki search sidebar Library agar memakai endpoint backend search dan menampilkan snippet isi dokumen, bukan hanya filter lokal `name/preview`; asset cache-bust naik ke `20261007-phase268` dan full public release gate production lulus `68/68 OK`.
- Phase 264 menambahkan pondasi realtime replay: header `X-HAI-Response-ID`, file-backed temporary event log, endpoint replay JSON/SSE `/api/realtime/events`, QA lokal `scripts/hai_realtime_qa.py`, dan full public release gate production `69/69 OK`.
- Phase 270–273 memoles loading realtime, loading gambar, action mobile, capability strip, dan typography jawaban panjang; release targeted Phase 273 lulus release audit, Markdown rich, chat-text, dan streaming-states.
- Phase 274 menutup gap first-token typing: saat chunk pertama masuk bubble pindah ke state `sedang diketik`, image request pindah ke render/progress gambar, badge loading dilokalkan, dan targeted production gate lulus `6/6 OK` tanpa mengubah klaim `full_platform_complete=false`.
- Phase 279 memperjelas UX loading realtime: sebelum token pertama ada robot kecil animasi + dots, saat jawaban mulai streaming muncul badge `Jawaban sedang diketik realtime`, loading gambar memakai kartu render/orb/scan/progressbar, code block menampilkan tombol `Salin`, dan targeted production gate `phase279-targeted-ui-gate` lulus `6/6 OK`.
- Phase 281 menutup risiko context bleed pada bridge web publik: request chat member-AI kini single-flight dan reset session upstream sebelum streaming, sehingga lampiran paralel dari browser berbeda tidak mencampur jawaban melalui session token server yang sama.
- Phase 282 menambahkan livebar realtime yang berupa elemen nyata di atas bubble, bukan hanya pseudo-element: ikon robot SVG animasi untuk teks, ikon render animasi untuk gambar, dots, status `Jawaban sedang diketik realtime`, dan targeted gate `phase282-targeted-ui-gate` mengunci marker `20261007-phase282`.
- Phase 283 menutup risiko deploy yang sempat terlihat sebagai 502 Cloudflare setelah Phase 282: finalizer baru resolve venv real sebelum switch symlink, memvalidasi `bin/gunicorn`, restart service, dan mengecek `/healthz`.
- Phase 284 melakukan visual audit screenshot production `17/17` dan menutup temuan rasa UI: placeholder `.hai-typing` lama dihapus dari waiting state teks agar tidak ada dua kartu loading. Saat menunggu token pertama hanya livebar yang tampil; bubble jawaban muncul setelah teks sungguhan mulai streaming.
- Phase 285 memperkuat deploy finalizer dengan retry `/healthz` pasca restart systemd agar release yang sebenarnya sehat tidak dilaporkan gagal karena race startup port.
- Phase 287 merespons feedback UX terbaru: waiting state teks kini kembali eksplisit dengan robot SVG animasi, dots, dan label “Jawaban sedang disiapkan”; saat token pertama muncul UI berpindah ke badge “Jawaban sedang diketik realtime”. Loading gambar tetap dibedakan dengan kartu desain/orb/scan/progress, dan code block tampil seperti editor/terminal modern.
- Phase 287 juga menjalankan ulang full public release gate production setelah patch realtime typing dan lulus `71/71 OK`; `/api/readiness`, release audit, readiness QA, dan report Gemini saat itu disinkronkan ke `phase287-public-release-gate`.
- Phase 298 menjalankan ulang full public release gate production setelah patch robot typing Phase 297 dan lulus `71/71 OK` dengan asset marker `20261007-phase297`; `/api/readiness`, release audit, readiness QA, dan report Gemini disinkronkan ke `phase297-public-release-gate`.
- Phase 289 memperkuat prioritas `rag_library`: search Library tidak lagi sekadar hitung frekuensi dokumen global, tetapi memakai lexical chunk rerank yang memprioritaskan coverage istilah query per chunk. API tetap tidak mengekspos full text, tetapi mengirim metadata aman `retrieval.mode`, `chunk_index`, dan `match_coverage`.
- Phase 294 menaikkan retrieval Library menjadi `lexical_semantic_bm25_sparse_rerank`: semantic alias expansion lokal membantu query seperti `gateway wifi rumah` menemukan dokumen `router/koneksi internet`, exact query tetap prioritas utama, dan API tetap tidak mengekspos full text.
- Phase 295 menambah kontrol konteks Library `Cuplikan/Penuh`: full-context tetap server-side, dibatasi `library_full_context_chars`, tidak masuk history, dan status dikirim lewat `X-HAI-Library-Grounding.context_mode`.
- Phase 296 menambah private sparse chunk index saat dokumen di-upload ke Library. Index term-vector disimpan server-side per device, dipakai search/grounding, tidak muncul di list/search public response, dan menjadi pondasi sebelum external vector DB embedding.
- Phase 299 menambah BM25-lite sparse rerank di atas private index. Search memakai `ranking=bm25_sparse_coverage_rerank`, panjang chunk dinormalisasi, dan query coverage tetap dominan agar dokumen panjang/spam tidak mengalahkan chunk ringkas relevan.
- Phase 290 menambah connection pill di topbar agar status stream/replay terlihat: `Realtime` selama jawaban/gambar berjalan, `Menyambung ulang` saat mencoba replay, dan `Dipulihkan` saat jawaban berhasil dipulihkan dari `/api/realtime/events`. WSS tetap belum diklaim production.
- Phase 291 menambah kontrol grounding Library `Otomatis/Selalu/Mati`. Konteks dokumen tetap disisipkan server-side, tidak masuk riwayat visible, dan `/chat` mengirim header aman `X-HAI-Library-Grounding` untuk status UI.
- Phase 292 menambah kontrak ticket WSS `/api/realtime/ticket` yang sengaja fail-safe `503 realtime_wss_not_ready` sampai gateway websocket/tool workflow benar-benar production. Capabilities tetap `realtime_wss=false`.
- Phase 300 menambah realtime replay state eksplisit di `/api/realtime/events`: JSON dan SSE `replay.state` kini membawa `terminal`, `last_sequence`, `last_event_id`, `next_after_sequence`, `replay_after_sequence`, dan `expires_at` agar reconnect/recovery lebih deterministik tanpa mengklaim WSS production.
- Phase 302 memperbaiki rasa realtime public chat: backend memecah chunk besar upstream menjadi display chunk kecil, UI loading teks menampilkan robot SVG/livebar/cursor typing, loading gambar tetap beda dengan kartu render modern, dan full public release gate production lulus ulang `71/71 OK` dengan asset marker `20261007-phase302`.
- Phase 302 juga menambahkan `/api/admin/overview` untuk observability aggregate-only. Endpoint ini hanya mengembalikan hitungan history/library/realtime/rate-limit/storage dan QA mengunci agar chat content, document text, device IDs, serta secret tidak bocor.
- Phase 303 menambahkan halaman `/admin` sebagai dashboard overview classic untuk owner: kartu history, library, realtime, rate-limit, privacy guard, dan storage aggregate. Halaman memakai script eksternal `admin-overview.js`, CSP tetap aman, dan release audit mengecek `/admin`.
- Phase 304 mempertegas rasa loading realtime: display chunk default diperkecil ke 24 karakter, delay dinaikkan ke 18 ms agar tidak terlihat langsung lompat paragraf, livebar robot menampilkan badge LIVE/RENDER, code block memakai chrome editor modern, dan kartu pembuatan gambar tampil lebih jelas sebelum thumbnail/artifact siap.
- Phase 305 menambah status chip visual di header dan composer: connection pill kini punya ikon robot/gambar kecil, shimmer saat live/reconnecting, dan status bawah composer memakai ikon sesuai intent teks/gambar agar loading tidak terasa kosong saat user melihat composer.
- Phase 277 menambahkan `scripts/hai_targeted_ui_gate.py` agar evidence `phase279-targeted-ui-gate` bisa dijalankan ulang sebagai satu command repeatable. Runner utama juga punya flag `--targeted-ui-gate`.

## Rekomendasi pertanyaan ke Gemini berikutnya

1. Apakah tema classic/AdminLTE ini sudah cukup untuk publik, atau perlu soft-modern lebih mirip ChatGPT?
2. Setelah raster image provider sudah ready, prioritas selanjutnya sebaiknya RAG/library permanen atau realtime replay/WSS?
3. Untuk fitur gambar, apakah perlu variasi ukuran/style/editing, atau cukup generate PNG private dulu?
4. Apakah memory tetap per device/browser, atau harus naik menjadi server-side/account memory?
5. Modul voice/video/calendar/automation/admin analytics perlu masuk roadmap dekat atau ditahan setelah core chat stabil?

- Phase 306 memperbaiki compact topbar mobile active chat setelah Phase305: connection pill dibuat icon-only di mobile active agar judul chat tetap terbaca; full public release gate production lulus `72/72 OK` dengan asset marker `20261007-phase306` dan visual snapshots `17/17 OK`.
- Phase 307 aktif mempertegas realtime loading UX: asset marker naik ke `20261007-phase307`, livebar/ikon robot kecil/progress rail teks dan shimmer/scan loading gambar dipertegas, mode coding memakai editor modern; targeted UI gate lulus `6/6 OK`, full public release gate `phase307-public-release-gate` production lulus `72/72 OK`, dan visual snapshots `17/17 OK`.
- Phase 309 memoles tampilan jawaban: asset marker naik ke `20261007-phase309`, assistant answer card memakai avatar HAI, code block/Markdown compact mobile lebih rapi, source details tidak overflow, targeted UI gate lulus `6/6 OK`, full public release gate production lulus `72/72 OK`, dan visual snapshots `17/17 OK`.
- Phase 310 memperbaiki visual loading gambar mobile: asset marker naik ke `20261007-phase310`, screenshot QA streaming-states menangkap loading aktif, bubble kosong saat render gambar disembunyikan, kartu render mobile tidak terpotong, targeted UI gate lulus `6/6 OK`, dan release audit `6/6 OK`, lalu full gate rerun production lulus `72/72 OK`.

- Phase 311 menstabilkan kontrak image generation: `/api/images/generations` kini memvalidasi prompt kosong sebagai `400 invalid_prompt` sebelum rate-limit, dan `scripts/hai_image_contract_qa.py` membuat cookie device QA lebih dulu agar tidak memakai bucket IP bersama. Kontrak production image lulus `6/6 OK` dan full public release gate rerun lulus `72/72 OK`.
- Phase 312 memadatkan kartu loading pembuatan gambar desktop/tablet agar mengikuti lebar chat response modern, bukan banner terlalu lebar. Marker UI naik ke `20261007-phase312`; fix mobile Phase 310 tetap dipertahankan. Full public release gate production lulus `72/72 OK`, visual snapshots `17/17 OK`, release audit `6/6`, dan readiness disinkronkan ke `phase312-public-release-gate`.
- Phase 313 memperbaiki containment jawaban mobile: bubble assistant untuk Markdown/tabel/code block tidak lagi bergeser dan terpotong ke kanan; code/table scroll di dalam bubble. Marker UI naik ke `20261007-phase313`.
- Phase 314 memperbaiki readability tabel mobile: tabel jawaban diuji dengan horizontal scroll dan min-width kolom, tetapi kontrak mobile QA meminta tabel tetap tidak melebihi bubble.
- Phase 315 memperbaiki realtime loading dan koreksi tabel mobile: robot/loading teks dibuat lebih jelas, loading gambar dipertegas dengan kartu render modern, code block tetap editor-style, dan tabel mobile kembali compact di dalam bubble tanpa clipping. Marker UI naik ke `20261007-phase315`.
- Phase 315 juga menjalankan ulang full public release gate production memakai asset marker `20261007-phase315` dan lulus `72/72 OK`; visual snapshots `17/17 OK`, release audit `6/6`, streaming states desktop/mobile hijau, Markdown rich desktop/mobile hijau, dan readiness disinkronkan ke `phase315-public-release-gate`.
- Phase 316 menambahkan analytics aggregate aman untuk admin: `/api/admin/overview` mengirim chat aktif 24 jam/7 hari, pesan user/AI, lampiran, artifact gambar, source references, dan rata-rata pesan/chat; `/admin` menampilkan card Usage dan panel Analytics. Data tetap aggregate-only tanpa isi chat, teks dokumen, device ID, URL sumber penuh, token, atau secret. Marker UI naik ke `20261007-phase316`.
- Phase 317 memoles loading realtime sesuai feedback owner: placeholder assistant muncul sebagai kartu robot kecil + skeleton line, teks ditampilkan dengan typewriter buffer lokal meski backend mengirim chunk besar, loading gambar dibedakan dengan kartu animasi render modern, dan code block mendapat lock style editor. Marker UI naik ke `20261007-phase317`.
- Phase 317 juga menjalankan ulang full public release gate production memakai asset marker `20261007-phase317` dan lulus `72/72 OK`; visual snapshots `17/17 OK`, release audit `6/6`, streaming states desktop/mobile hijau, Markdown rich desktop/mobile hijau, dan readiness disinkronkan ke `phase317-public-release-gate`.
- Phase 318 memperkuat roadmap `rag_library`: dokumen Library kini disimpan dengan private hybrid sparse+hash-vector chunk index, search memberi rerank gabungan coverage/BM25-lite/semantic alias/cosine similarity lokal, response publik hanya mengirim snippet aman plus `vector_similarity` terukur tanpa embedding/vector/full text, dan readiness tetap jujur `full_platform_complete=false` karena managed vector DB eksternal belum production.
- Phase 319 memoles lagi loading realtime/image/code sesuai feedback terbaru owner: loader robot jawaban punya badge `LIVE`, ikon robot kecil bergaya animasi GIF, teks helper lebih eksplisit bahwa jawaban sedang diketik, kartu `DESIGN` untuk loading gambar punya orb/scan/progress, dan code block tetap editor-style. Full public release gate production stabil lulus `72/72 OK`; visual snapshots `17/17 OK`, release audit `6/6`, dan readiness disinkronkan ke `phase319-public-release-gate`.
- Phase 325 menutup catatan user-facing pada streaming: robot typing kini tampil sebagai satu kartu solid/readable, bukan ghost/dobel panel, avatar HAI kiri disembunyikan selama waiting state teks, dots mobile yang kepotong dihilangkan secara visual, dan badge lama `is-writing::after` yang membuat tulisan hijau vertikal di samping bubble dimatikan. Sebagai pengganti visual yang kosong, status composer sekarang punya activity animation berupa robot/dots/progress untuk fase menyiapkan jawaban, mencari referensi, mengetik realtime, dan membuat gambar. Finalisasi stream juga tidak lagi memaksa semua sisa buffer muncul sekaligus saat backend selesai cepat. Loading gambar memakai kartu render compact yang tetap berbeda dari teks; edge case upstream `/chat` selesai tanpa token juga tetap aman karena render Markdown immediate memakai `ReactDOM.flushSync` bila tersedia. Browser QA `streaming-states` desktop/mobile hijau dan `empty-stream-fallback` tetap mengunci bubble assistant agar tidak kosong. Marker UI naik ke `20261007-phase325`; readiness gate tetap Phase319 sampai full public gate besar dijalankan ulang.
