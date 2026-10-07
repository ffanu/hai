# Phase 76 — New Chat Link Browser QA

Tanggal: 2026-10-05

## Tujuan

Menutup risiko UX yang pernah dilaporkan: saat user menekan Chat Baru, percakapan baru harus langsung punya link/session ID stabil seperti `/c/{session_id}` dan item sidebar aktif. Ini penting agar user bisa refresh, salin link, dan lanjut riwayat tanpa kehilangan konteks.

## Perubahan

- `scripts/hai_browser_qa.py` mendapat opsi `--flow`.
- Flow default `empty` tetap memverifikasi layout halaman awal.
- Flow baru `new-chat` melakukan klik `#new-chat`, lalu memverifikasi:
  - URL berubah ke `/c/{id}`;
  - ID URL sama dengan item sidebar aktif;
  - minimal satu item riwayat tampil;
  - tidak ada horizontal overflow;
  - `aria-busy` tetap `false` setelah membuat chat kosong.

## Contoh

```bash
python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow new-chat --screenshot /tmp/hai-newchat-desktop.png
python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport mobile --flow new-chat --screenshot /tmp/hai-newchat-mobile.png
```

Exit code `0` berarti flow Chat Baru dan layout lulus. Exit code `1` berarti session link/sidebar/overflow bermasalah.

## Hasil QA lokal 2026-10-05

Desktop:

```json
{
  "ok": true,
  "afterPath": "/c/1791217023413",
  "idFromPath": "1791217023413",
  "activeId": "1791217023413",
  "historyCount": 1,
  "horizontalOverflow": false,
  "ariaBusy": "false"
}
```

Mobile:

```json
{
  "ok": true,
  "afterPath": "/c/1791217026248",
  "idFromPath": "1791217026248",
  "activeId": "1791217026248",
  "historyCount": 1,
  "horizontalOverflow": false,
  "ariaBusy": "false"
}
```

## Acceptance Criteria

- Browser QA berjalan tanpa dependency Python eksternal.
- Desktop dan mobile menghasilkan `ok=true`.
- URL chat baru selalu berbentuk `/c/{id}`.
- Item sidebar aktif memakai ID yang sama dengan URL.
- Tidak ada horizontal overflow di desktop/mobile.
