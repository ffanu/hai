# Phase 66 — Streaming State Clarity

Tanggal: 2026-10-05

## Tujuan

Merapikan status live agar pengalaman chat terasa konsisten seperti aplikasi chat AI modern:

- teks biasa: berpikir → menulis;
- web/referensi: membaca referensi → menulis dengan referensi;
- gambar: menyiapkan kanvas → mendesain → render;
- stop: menghentikan → dihentikan;
- queue: pesan masuk antrean → dikirim dari antrean.

## Perubahan

- Menambahkan map status `HAI_LIVE_STATUS` dan helper `setHaiLiveStatus()`.
- `setHaiStatus()` kini membersihkan class status lama dan mendukung `info`, `image`, `error`, `queue`, `stopping`, dan `success`.
- Jalur send utama memakai helper status untuk koneksi, web sources, image intent, stop, dan queue.
- CSS AdminLTE classic ditambah badge status `queue` dan `stopping`.
- Cache-bust asset dinaikkan ke `20261005-phase66`.

## Verifikasi lokal

- `node --check static/js/scripts.js`: OK
- `.venv/bin/python -m py_compile app.py`: OK
- CSS brace count: `1293 / 1293`
- Marker HTML: `20261005-phase66`
- Marker CSS: `Phase 66: AdminLTE streaming state clarity`

## Catatan

Phase ini sengaja tidak menyentuh refactor besar parser streaming yang masih duplikat di beberapa jalur. Refactor itu perlu fase tersendiri karena risiko regression lebih tinggi.
