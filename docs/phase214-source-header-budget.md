# Phase 214 — Source Header Budget Guard

Phase ini menindaklanjuti audit opencode tentang potensi header `X-HAI-Sources` terlalu besar bila URL/snippet sumber web sangat panjang.

## Masalah

Metadata sumber dikirim lewat header `X-HAI-Sources` agar body SSE tetap streaming teks. Tanpa budget, banyak sumber dengan URL/snippet panjang bisa mendekati atau melewati batas header reverse proxy.

## Perubahan

- Menambahkan env guard:
  - `HAI_SOURCE_HEADER_MAX_BYTES` default `6000`
  - `HAI_SOURCE_HEADER_MAX_ITEMS` default `6`
  - `HAI_SOURCE_HEADER_MAX_URL` default `1024`
  - `HAI_SOURCE_HEADER_MAX_SNIPPET` default `160`
- `_encode_sources_header()` sekarang:
  - memangkas URL untuk header ke batas aman,
  - memangkas snippet untuk header,
  - menambah item hanya bila hasil base64 masih di bawah budget,
  - tetap mengirim sumber valid tanpa full URL tampil di UI.
- Ditambahkan `scripts/hai_sources_header_qa.py`.

## Acceptance

- Header encoded tidak melewati budget.
- Jumlah sumber tetap dibatasi.
- URL/snippet panjang tidak bisa membuat response header membengkak.
- Source chips tetap bekerja karena format `sources[]` tidak berubah.
