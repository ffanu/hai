# Phase 210 — File Artifact Endpoint Hardening

Phase ini menindaklanjuti audit opencode setelah Phase 209.

## Masalah

Endpoint preview/download artifact gambar sudah memakai `file_id` privat dan tidak mengekspos URL publik, tetapi request ke `local-svg-*` yang tidak ada masih diteruskan ke upstream member AI. Akibatnya file lokal yang jelas tidak ada bisa menghasilkan `502 file_preview_unavailable`, bukan `404 file_not_found`.

Selain itu endpoint `/api/files/{file_id}/preview|download` belum memiliki rate-limit sendiri.

## Perubahan

- Menambahkan `RATE_LIMIT_FILE` dengan env:
  - `HAI_RATE_FILE_COUNT` default `120`
  - `HAI_RATE_FILE_WINDOW` default `60`
- `/api/files/<file_id>/preview` dan `/download` sekarang memakai rate-limit scope `file`.
- `local-svg-*` yang tidak ditemukan langsung mengembalikan:

```json
{"ok": false, "error": "file_not_found", "message": "File tidak tersedia."}
```

dengan HTTP `404`.

- Jika upstream member AI mengembalikan `404`, endpoint lokal meneruskan sebagai `404 file_not_found`, bukan `502`.
- `scripts/hai_image_contract_qa.py` sekarang menguji unknown local preview/download wajib `404`.

## Acceptance

- Artifact valid tetap bisa preview/download.
- Unknown local file id tidak memanggil upstream.
- Unknown local file id tidak menghasilkan `502`.
- Endpoint file tidak membuka URL publik dan tetap melalui `/api/files/...`.
