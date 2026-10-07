# Phase 235 — Production Image QA Timeout

Tanggal: 2026-10-06

## Masalah

Setelah Phase 233/234, Codex/member-AI image bridge sengaja ditunggu lebih lama karena smoke production menunjukkan pembuatan PNG private membutuhkan sekitar 47–50 detik.

`scripts/hai_image_contract_qa.py` sudah dinaikkan ke timeout 150 detik, tetapi wrapper di `scripts/hai_production_qa.py` masih memberi batas 140 detik untuk check `image_contract_api`.

Ini bisa menyebabkan QA utama gagal palsu ketika:

- `POST /api/images/generations` membutuhkan sekitar 50 detik;
- `chat_image_intent_stream_contract` juga membutuhkan sekitar 50 detik;
- preview/download dicek setelahnya.

## Perubahan

- Timeout `image_contract_api` di `scripts/hai_production_qa.py` dinaikkan menjadi 240 detik.

## Tujuan

Production QA utama sekarang selaras dengan realita jalur gambar Codex/member-AI dan tetap dapat mengunci:

- `mode=member_ai_bridge`;
- `raster_image_generation=true`;
- preview/download `image/png`;
- tidak ada terminal leak;
- tidak ada public media URL;
- chat image stream memakai private `/api/files/file_*/preview`.
