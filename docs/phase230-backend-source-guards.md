# Phase 230 — Backend Source Guards

Tanggal: 2026-10-06

Phase ini menindaklanjuti audit opencode terhadap risiko runtime backend `hai.harmonika.id`.

## Perubahan

- `SOURCE_HEADER_MAX_BYTES` default diturunkan dari `6000` menjadi `2800` agar header `X-HAI-Sources` lebih aman untuk reverse proxy.
- Teks sumber web/search/YouTube/arXiv diclamp:
  - per source: `HAI_SOURCE_TEXT_MAX_CHARS` default `12000`
  - total tambahan prompt: `HAI_ADDITIONAL_TEXT_MAX_CHARS` default `24000`
  - riwayat teks masuk engine: `HAI_HISTORY_TEXT_MAX_CHARS` default `8000`
- Error search/YouTube tidak lagi dimasukkan mentah ke prompt; error detail masuk log server, sedangkan user menerima teks aman.
- Fetch arXiv/web direct di `/chat` dibungkus `try/except` dan mengembalikan JSON error `source_fetch_failed` yang ramah pelanggan, bukan HTML 500.
- `POST /api/attachments/parse` kini memakai scope rate-limit `file`, bukan `chat`.

## Verifikasi lokal

- `python -m py_compile app.py scripts/hai_production_qa.py`
- `scripts/hai_sources_header_qa.py` lulus `4/4` dengan budget baru `2800`.

## Catatan

Perubahan ini tidak mengubah kontrak UI/chat normal. Tujuannya menutup risiko prompt blow-up, header terlalu besar, dan error sumber yang tidak rapi sebelum publik traffic makin besar.
