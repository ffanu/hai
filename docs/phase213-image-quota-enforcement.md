# Phase 213 — Image Generation Quota Enforcement

Phase ini menutup temuan audit opencode: `/api/capabilities` mengiklankan kuota `image_generations_per_day`, tetapi endpoint `/api/images/generations` belum memiliki rate-limit gambar khusus.

## Perubahan

- Menambahkan rate-limit scope `image`:
  - `HAI_RATE_IMAGE_COUNT` default `24`
  - `HAI_RATE_IMAGE_WINDOW` default `86400` detik
- `POST /api/images/generations` sekarang mengecek `_check_rate_limit("image", RATE_LIMIT_IMAGE)` sebelum memproses prompt.
- `/api/capabilities.limits` sekarang mengembalikan:
  - `image_generations_per_day`
  - `image_generation_window_seconds`

## Catatan

- Request pertama tanpa cookie tetap memakai IP sebagai bucket, lalu Phase 211 memastikan browser normal menerima cookie device agar request berikutnya memakai bucket device.
- `/chat` intent gambar tetap berada di rate-limit chat karena itu bagian dari stream chat utama. Endpoint gambar eksplisit `/api/images/generations` memakai kuota gambar khusus.

## Acceptance

- Capabilities mencerminkan env `HAI_RATE_IMAGE_COUNT`.
- Dengan `HAI_RATE_IMAGE_COUNT=1`, request gambar pertama sukses dan request kedua mengembalikan `429 rate_limited`.
