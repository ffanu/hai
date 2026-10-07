# Phase 81 — Public Image Copy

Tanggal: 2026-10-06

## Tujuan

Merapikan wording onboarding agar fitur gambar terasa sebagai fitur produk publik, bukan detail teknis SVG.

## Perubahan

- Label kemampuan `Gambar SVG` diganti menjadi `Gambar/visual`.
- Prompt suggestion gambar diganti dari `Buatkan gambar SVG...` menjadi `Buatkan gambar...`.
- Deskripsi suggestion gambar menjadi “Buat gambar atau ilustrasi yang tampil di chat.”
- Fallback welcome JS juga disamakan.
- Asset cache-bust dinaikkan ke `20261006-phase81`.

## Acceptance Criteria

- Empty state desktop/mobile tidak lagi menonjolkan format teknis SVG.
- Browser QA empty/chat-text tetap tanpa overflow.
- Kontrak backend/render artifact tidak berubah.
