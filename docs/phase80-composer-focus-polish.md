# Phase 80 — Composer Focus Polish

Tanggal: 2026-10-06

## Tujuan

Merapikan focus state composer. Screenshot mobile Phase 79 menunjukkan textarea masih memakai outline browser default yang terlalu tebal/double-blue sehingga terasa kurang halus untuk UI publik.

## Perubahan

- Focus ring utama dipindahkan ke container composer/form.
- `#user-input` menghapus outline/box-shadow default saat fokus.
- Tombol upload/kirim tetap punya `focus-visible` ring agar aksesibilitas keyboard tidak hilang.
- Prompt QA `chat-text` dibersihkan agar screenshot tidak lagi menampilkan label phase lama.
- Asset cache-bust dinaikkan ke `20261006-phase80`.

## Acceptance Criteria

- Composer fokus tetap terlihat jelas tapi tidak double-outline.
- Browser QA `chat-text` desktop/mobile tetap `ok=true`.
- Visible assistant actions tetap hanya 4 aksi publik.
