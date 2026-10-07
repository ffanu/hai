# Phase 83 — QA Composer Wait

Tanggal: 2026-10-06

## Tujuan

Membuat `image-artifact` browser QA lebih stabil. Run pertama sempat mengembalikan `missing_composer`, sementara run ulang lulus. Ini menunjukkan harness perlu menunggu composer siap, bukan langsung gagal.

## Perubahan

- Flow `image-artifact` menunggu `#user-input` dan `#submit-button` sampai 5 detik.
- Jika tetap gagal, output menyertakan `url` dan cuplikan `bodyText` untuk diagnosis.

## Hasil rujukan

Run ulang production sebelum patch sudah membuktikan fitur gambar valid:

- `ok=true`
- `previewSrc=/api/files/.../preview`
- `hasPublicUrlText=false`
- `modalOpen=true`
- `cardLooksCentered=true`
- `closedByBackdrop=true`

## Acceptance Criteria

- Script lolos `py_compile`.
- Flow image-artifact tetap lulus saat composer tersedia.
