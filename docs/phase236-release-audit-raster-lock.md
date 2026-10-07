# Phase 236 — Release Audit Raster Lock

Tanggal: 2026-10-06

## Tujuan

Setelah jalur gambar Codex/member-AI menjadi production ready, release audit perlu ikut mengunci capability tersebut. Tanpa guard ini, `/api/capabilities` bisa diam-diam turun kembali ke fallback SVG lokal tetapi release audit tetap hijau.

## Perubahan

`scripts/hai_release_audit.py` sekarang memeriksa:

- `features.image_generation=true`
- `features.image_generation_sse=true`
- `features.image_preview=true`
- `features.image_download=true`
- `features.raster_image_generation=true`
- `features.member_ai_image_bridge=true`
- `image_generation.mode="member_ai_bridge"`
- `image_generation.result_format="private_file_artifact"`
- `image_generation.public_urls=false`
- `image_generation.raster_public=true`
- `image_generation.backend="chat.harmonika.id"`
- `limits.image_generations_per_day > 0`
- `limits.image_sizes` tidak kosong

## Dampak

Jika production kembali ke mode fallback lokal/SVG, release audit akan gagal. Ini menjaga kontrak yang user minta: gambar web harus memakai backend Codex/member-AI di balik layar, bukan link publik atau artifact lokal palsu.
