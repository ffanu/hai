# Phase 205 — Release Gate Stability

Tanggal: 2026-10-06

## Tujuan

Phase ini menstabilkan QA release setelah Phase 204. Aplikasi production sudah lulus targeted rerun, tetapi full public gate masih bisa gagal karena respons upstream live sesekali mengembalikan `Maaf, network error` saat flow visual/source sedang memotret UI.

## Perubahan

- `hai_visual_qa.py` kini menganggap `network error` dan respons backend transient lain sebagai flake provider untuk flow `chat-text`, lalu retry sampai 3 attempt sebelum benar-benar gagal.
- `hai_production_qa.py` menaikkan retry `sources-web` desktop/mobile dari 1 menjadi 2 retry karena flow ini bergantung pada web/search + upstream live.
- Timeout handling dari Phase 204 tetap dipertahankan: kegagalan tetap ditulis sebagai JSON terstruktur, bukan crash.

## Alasan

Flow visual dan source-stack bertujuan mengunci tampilan UI: layout, markdown, source chips, composer, modal, dan overflow. Kegagalan provider live sesaat tidak boleh disalahartikan sebagai regresi CSS/DOM bila rerun langsung membuktikan UI masih benar.

## Evidence

Sebelum patch ini, full gate Phase 204 mencapai `51/53`; dua kegagalan adalah:

- `browser_sources_web_mobile`: assistant sample `Maaf, network error`.
- `visual_snapshots`: `desktop_chat-text` mendapat assistant sample `Maaf, network error`.

Targeted rerun setelah itu membuktikan:

- `sources-web` mobile lulus.
- visual snapshots lulus `17/17`.

Patch ini membuat perilaku rerun tersebut menjadi bagian dari gate, bukan langkah manual.
