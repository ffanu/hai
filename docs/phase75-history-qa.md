# Phase 75 — History API QA

Tanggal: 2026-10-05

## Tujuan

Menambahkan verifikasi repeatable untuk `/api/history` sebelum refactor sidebar/history lebih jauh.

## Perubahan

- Menambahkan `scripts/hai_history_qa.py`.
- Script memakai cookie jar terisolasi sehingga tidak menyentuh riwayat browser/user nyata.
- Alur QA:
  1. `GET /api/history` dengan device baru.
  2. `PUT /api/history` untuk menyimpan chat test unik.
  3. `GET /api/history` untuk memastikan chat test tersimpan dan active benar.
  4. `PUT /api/history` dengan tombstone delete untuk chat test.
  5. `GET /api/history` untuk memastikan chat hilang dan tombstone tersimpan.

## Contoh

```bash
python3 scripts/hai_history_qa.py --base-url https://hai.harmonika.id
```

## Acceptance Criteria

- Script berjalan tanpa dependency eksternal.
- Save/reload chat test berhasil.
- Tombstone delete menghapus chat test dari list aktif.
- Riwayat user lain tidak tersentuh karena cookie jar terisolasi.

## Hasil QA 2026-10-05

```json
{
  "ok": true,
  "base_url": "https://hai.harmonika.id",
  "device": "a85996a5",
  "chat_id": "qa-history-1791216796590",
  "initial_chats": 0,
  "saved_count": 1,
  "after_delete_chats": 0,
  "tombstone_saved": true
}
```
