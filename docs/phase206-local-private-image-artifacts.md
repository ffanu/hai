# Phase 206 — Local Private Image Artifacts

Tanggal: 2026-10-06

## Tujuan

Menutup gap penting pada fitur “buat gambar” web: saat provider/member AI raster belum siap, fallback lokal tidak lagi mengirim SVG panjang sebagai code block utama. Fallback kini dibuat sebagai artifact privat berbasis `file_id`, sehingga UI tetap menampilkan thumbnail/preview/download melalui endpoint internal `/api/files/...`.

## Perubahan

- Fallback SVG lokal disimpan server-side di `HAI_DATA_DIR/generated-images`.
- `/api/images/generations` fallback kini mengembalikan:
  - `mode: local_svg_file`
  - `images[]` berisi `file_id`, `mime_type`, `width`, `height`, `size_bytes`, `source_prompt`, `requested_size`
  - `content` berupa kartu thumbnail privat `/api/files/{file_id}/preview`
- Intent gambar lewat `/chat` juga memakai kartu thumbnail privat, bukan fenced SVG panjang.
- `/api/files/{file_id}/preview` melayani artifact lokal sebagai `image/svg+xml`.
- `/api/files/{file_id}/download` melayani download lokal dengan `Content-Disposition` `.svg`.
- Capability `/api/capabilities` kini menandai fallback lokal sebagai `result_format: private_file_artifact`; `raster_image_generation` tetap `false` sampai provider raster benar-benar siap dan flag publik `HAI_MEMBER_AI_RASTER_PUBLIC=1` dinyalakan.
- Kontrak QA gambar diperluas untuk mengetes preview/download `file_id` bila `images[]` tersedia.

## Batasan

- Ini belum menggantikan provider raster production. Output fallback masih SVG lokal, tetapi sudah private artifact dan tidak mengekspos URL publik `/media` atau `/download`.
- `raster_image_generation=true` tetap hanya boleh aktif saat member/provider image raster siap dan sudah lulus smoke preview/download private `file_id`.

## Acceptance

- Prompt gambar tidak menampilkan terminal/path/file-manager.
- Tidak ada URL publik legacy `/media`, `/download`, `/files`.
- Thumbnail memakai `/api/files/{file_id}/preview`.
- Preview/download hanya lewat endpoint aplikasi.
- UI tetap bisa membuka modal/kanvas dari thumbnail.
