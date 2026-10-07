# Phase 78 — Message Actions Polish

Tanggal: 2026-10-05

## Tujuan

Merapi tampilan action bar pesan agar tidak terasa seperti toolbar debug. Screenshot Phase 77 menunjukkan action bar sudah berfungsi, tetapi masih terlalu lebar/kaku dan tombol `Continue` selalu muncul sehingga membingungkan.

## Perubahan

- Action bar pesan dibuat compact `inline-flex` dengan ukuran tombol konsisten.
- Tombol `Continue` disembunyikan dari tampilan publik default karena belum punya deteksi truncation yang akurat dan selalu muncul setelah setiap jawaban.
- Tombol `Regenerate/Buat ulang`, copy, edit, delete tetap tersedia.
- Tooltip/title dan `aria-label` tombol action dinormalisasi ke Bahasa Indonesia meskipun dibuat dari jalur JS lama.
- Asset cache-bust dinaikkan ke `20261005-phase78`.

## Acceptance Criteria

- Tombol action tidak melebar berlebihan di desktop/mobile.
- Bubble assistant tetap bersih tanpa reasoning leak Phase 77.
- URL/session chat baru tetap `/c/{id}`.
- Tidak ada horizontal overflow.
