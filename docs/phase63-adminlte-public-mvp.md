# Phase 63 — AdminLTE Public MVP Polish

Tanggal: 2026-10-05

## Tujuan

Membuat tampilan `hai.harmonika.id` terasa lebih siap publik dengan arah AdminLTE classic: dashboard bersih, chat surface stabil, composer rapi, dan tetap nyaman dipakai untuk percakapan AI modern.

## Perubahan

- Cache-bust asset dinaikkan ke `20261005-phase63`.
- Layer CSS final ditambahkan di akhir `styles.css` agar override tema lama tidak kembali mengalahkan tema classic.
- Topbar diperkuat dengan ellipsis title/subtitle dan action spacing stabil.
- Chat surface diperluas ke `--hai-readable: 920px` dengan background light-gray classic.
- Bubble assistant/user, message actions, source chips, dan artifact width dipoles agar mengikuti card/form AdminLTE.
- Composer dibuat lebih stabil: form width sama dengan area chat, textarea height wajar, quick prompts horizontal, attachment tray punya batas tinggi.
- Mobile layout diperketat: title/action ringkas, bubble tidak overflow, artifact panel full-width saat dibuka.

## Verifikasi lokal

- `node --check static/js/scripts.js`: OK
- `.venv/bin/python -m py_compile app.py`: OK
- CSS brace count: `1284 / 1284`
- HTML asset marker: `20261005-phase63`
- CSS marker: `Phase 63: AdminLTE public MVP polish`

## Catatan audit Claude

Claude merekomendasikan fase berikutnya:

1. Hardening sanitizer/CSP dan guard endpoint settings.
2. Konsolidasi state streaming agar status teks/gambar/queue konsisten.
3. Aksesibilitas: `lang="id"`, aria-label tombol ikon, dialog semantics, kontras sidebar.
4. Konsolidasi CSS agar class `chatgpt-pattern` lama tidak menjadi sumber regresi.

## Acceptance Criteria Production

- Body tetap memakai `hai-theme-adminlte-classic`.
- Asset live memuat `20261005-phase63`.
- Service `harmonika-hai-web.service` aktif.
- Smoke `/`, `/api/capabilities`, `/api/attachments/parse`, dan `/chat` tetap sehat.
