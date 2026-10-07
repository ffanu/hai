# Phase 200 — Image Generation Contract QA

Tanggal: 2026-10-06

## Tujuan

Mengunci kontrak pembuatan gambar di web publik `hai.harmonika.id` agar aman untuk pelanggan:

- Tidak membocorkan output terminal seperti `$ mkdir`, `Write`, path server, atau file manager.
- Tidak menampilkan URL publik legacy `/media`, `/download`, `/files`.
- Tetap memberi hasil/fallback visual yang bisa dirender sebagai artifact.
- Endpoint dan `/chat` image intent bisa diuji otomatis.

## Perubahan

- Menambahkan `scripts/hai_image_contract_qa.py`.
- Public release gate kini menjalankan `image_contract_api`.
- Backend image bridge diberi timeout khusus `HAI_MEMBER_AI_IMAGE_TIMEOUT` dengan default 18 detik.
- Jika bridge member AI lambat/error tetapi mode SVG fallback aktif, `POST /api/images/generations` mengembalikan `mode: "svg_artifact_fallback"` alih-alih timeout/503.

## Hasil QA production

Command:

```bash
python3 scripts/hai_image_contract_qa.py \
  --base-url https://hai.harmonika.id \
  --json-out qa-reports/phase200-image-contract-production.json
```

Hasil:

- `ok: true`
- `passed: 4/4`
- `/api/capabilities` sehat dan `public_urls: false`
- Prompt kosong memberi error stabil `invalid_prompt`
- `POST /api/images/generations` sukses dengan `mode: svg_artifact_fallback`
- `/chat` intent gambar memberi header `X-HAI-Intent: image`
- Tidak ada terminal leak
- Tidak ada URL publik `/media`/`/download`
- Tidak ada markdown media legacy

## Catatan penting

Production saat QA masih mengiklankan bridge member AI/raster siap:

- `features.member_ai_image_bridge: true`
- `features.raster_image_generation: true`
- `image_generation.mode: member_ai_bridge`

Namun request nyata ke bridge tidak menghasilkan private raster artifact tepat waktu, sehingga fallback SVG dipakai. Ini aman untuk user, tetapi belum membuktikan image generation raster production benar-benar siap.

## Rekomendasi berikutnya

1. Audit backend `chat.harmonika.id/v1/member-ai/images/generations` agar mengembalikan `file_id` raster tepat waktu.
2. Jika bridge belum sehat, turunkan capability raster di env production agar UI/owner tidak salah klaim.
3. Tambahkan QA khusus provider raster setelah backend siap:
   - `images[]`/`artifacts[]` berisi `file_id`
   - `/api/files/{file_id}/preview` mengembalikan `image/*`
   - `/api/files/{file_id}/download` mengembalikan file valid
   - artifact history tetap tidak menyimpan URL publik.

