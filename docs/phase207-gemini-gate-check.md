# Phase 207 — Gemini Gate Check & QA Retry Hardening

Tanggal: 2026-10-06

## Tujuan

Menjawab checkpoint saran Gemini dengan evidence production terbaru, sekaligus menutup flake QA yang muncul saat browser/CDP reload context terlalu cepat.

## Hasil audit production

Targeted gate `release-audit + web-sources + visual-snapshots` menemukan dua kegagalan awal:

- `browser_regenerate_desktop`
- `visual_snapshots` pada child `desktop_chat-text`

Keduanya memiliki root cause yang sama di runner: Chromium/CDP melempar `Execution context was destroyed` saat evaluasi readiness awal. Rerun langsung membuktikan flow produk sehat:

- `regenerate` desktop rerun: OK, tidak duplikasi kalimat, action bar tetap rapi, no horizontal overflow.
- `visual_snapshots` rerun: 17/17 OK untuk desktop/mobile/tablet/landscape, Markdown, source stack, queue/composer, dan component crops.

## Perubahan

- `scripts/hai_production_qa.py` memberi retry terbatas untuk `browser_regenerate_desktop`.
- `scripts/hai_production_qa.py` memberi retry terbatas untuk `visual_snapshots`.
- Runner production juga memberi satu retry ekstra otomatis bila browser/CDP gagal dengan `Execution context was destroyed` atau `Cannot find context with specified id`.
- `image_contract_api` mendapat retry terbatas karena `/chat` image intent dapat terkena 502 transient dari edge/upstream; rerun kontrak gambar production terbukti 5/5 OK.
- `scripts/hai_visual_qa.py` kini retry per-snapshot untuk error browser context yang sama, sehingga satu viewport transient tidak perlu mengulang seluruh visual suite dari awal.
- `scripts/hai_browser_qa.py` kini retry readiness evaluation saat Chromium mengganti execution context pada load awal, terutama di viewport mobile/landscape.

Ini mengikuti pola yang sudah dipakai pada flow live-provider lain: kegagalan transient runner tidak langsung menggagalkan release bila rerun bersih.

## Evidence tambahan

- Image contract production Phase 206: 5/5 OK.
- Release audit production Phase 206: 4/4 OK.
- Capability gambar kini tidak lagi mengklaim raster production: `raster_image_generation=false` sampai provider raster private `file_id` benar-benar siap.

## Status Gemini items

Yang siap sebagai MVP publik:

- Empty state modern.
- Layout desktop/mobile/tablet/landscape.
- Sidebar responsive.
- Smart auto-scroll.
- Composer modern dengan stop/queue/attachment.
- Stop generation dan regenerate.
- Markdown rich, table, code block, copy code.
- Source chips rapi tanpa full URL di bubble.
- Attachment dokumen/gambar input.
- Thumbnail/modal image artifact private.
- Memory ringan per device.
- QA release gate dan visual snapshot.

Yang masih roadmap besar:

- Raster image provider asli.
- RAG/library permanen dengan vector DB.
- Realtime resume/replay/WSS.
- Voice/video.
- Calendar/automation/admin analytics.
