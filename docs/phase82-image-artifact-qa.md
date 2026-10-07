# Phase 82 — Image Artifact Browser QA

Tanggal: 2026-10-06

## Tujuan

Menambahkan regression test untuk requirement gambar: saat user meminta gambar, UI harus menampilkan thumbnail/artifact private, bukan link publik atau kode mentah.

## Perubahan

- `scripts/hai_browser_qa.py` mendapat flow `--flow image-artifact`.
- Flow ini menjalankan prompt gambar dari browser nyata, lalu memverifikasi:
  - ada preview image dengan `src` private `/api/files/{file_id}/preview`;
  - ada artifact/thumbnail di bubble assistant;
  - teks assistant tidak memuat URL publik;
  - teks assistant tidak memuat raw SVG/code fence;
  - `aria-busy=false` setelah selesai;
  - klik thumbnail membuka `.hai-image-modal`;
  - modal card berada sekitar 50% viewport;
  - klik backdrop menutup modal;
  - tidak ada horizontal overflow.

## Contoh

```bash
python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow image-artifact --timeout 90
```

Catatan: flow ini memanggil image generation production, jadi jangan dijalankan terlalu sering tanpa kebutuhan.

## Acceptance Criteria

- Flow menghasilkan `ok=true`.
- `previewSrc` diawali `/api/files/`.
- `hasPublicUrlText=false`.
- `modalOpen=true` dan `closedByBackdrop=true`.
