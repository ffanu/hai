# Phase 84 — History Controls Browser QA

Tanggal: 2026-10-06

## Tujuan

Menambahkan regression test browser untuk workflow sidebar/history yang penting agar pengalaman web chat terasa seperti ChatGPT/Claude:

- Chat Baru punya session link.
- Rename chat bekerja.
- Search/filter history bekerja.
- Delete chat memakai konfirmasi, menghapus item aktif, dan kembali ke base URL.

## Perubahan

- `scripts/hai_browser_qa.py` mendapat flow `--flow history-controls`.
- Flow ini memakai browser nyata dan profile sementara:
  1. klik `#new-chat`;
  2. ambil ID dari `/c/{id}`;
  3. mock `window.prompt` untuk rename;
  4. verifikasi title sidebar berubah;
  5. isi search history dan verifikasi hasil filter;
  6. mock `window.confirm` untuk delete;
  7. verifikasi item hilang, URL kembali `/`, empty history tampil, dan tidak ada horizontal overflow.

## Hasil QA production awal

Desktop:

```json
{
  "ok": true,
  "initialTitle": "New Chat",
  "searchMatched": true,
  "deletedGone": true,
  "returnedToBase": true,
  "horizontalOverflow": false
}
```

Mobile:

```json
{
  "ok": true,
  "initialTitle": "New Chat",
  "searchMatched": true,
  "deletedGone": true,
  "returnedToBase": true,
  "horizontalOverflow": false
}
```

## Acceptance Criteria

- Desktop dan mobile `history-controls` menghasilkan `ok=true`.
- Delete active chat tidak menyisakan `/c/{id}` stale.
- Search history tidak merusak active state.
