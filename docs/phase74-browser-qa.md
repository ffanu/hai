# Phase 74 — Browser QA Harness

Tanggal: 2026-10-05

## Tujuan

Menambahkan verifikasi browser yang lebih akurat untuk UI `hai.harmonika.id`, terutama setelah ditemukan bahwa screenshot Chrome headless biasa bisa misleading: `--window-size=390` dapat menghasilkan runtime viewport 500px lalu screenshot ter-crop.

## Perubahan

- Menambahkan `scripts/hai_browser_qa.py`.
- Script memakai Chrome DevTools Protocol langsung tanpa dependency pihak ketiga.
- Script memaksa device metrics mobile/desktop, lalu mengukur:
  - `innerWidth` / `innerHeight`;
  - `documentElement.scrollWidth` dan `body.scrollWidth`;
  - status horizontal overflow;
  - class body/theme;
  - URL CSS aktif;
  - bounding box empty state dan composer;
  - `aria-busy` chat log;
  - optional screenshot.

## Contoh

```bash
python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport mobile --screenshot /tmp/hai-mobile.png
python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --screenshot /tmp/hai-desktop.png
```

Exit code `0` berarti tidak ada horizontal overflow. Exit code `1` berarti ada overflow dan perlu diperbaiki.

## Acceptance Criteria

- Script berjalan tanpa package Python tambahan.
- Mobile viewport 390px melaporkan `horizontalOverflow: false`.
- Desktop viewport 1365px melaporkan `horizontalOverflow: false`.
- Screenshot opsional berhasil dibuat.

## Hasil QA 2026-10-05

Mobile:

```json
{
  "innerWidth": 390,
  "documentScrollWidth": 390,
  "bodyScrollWidth": 390,
  "horizontalOverflow": false,
  "emptyState": { "left": 12, "right": 378, "width": 366 },
  "composer": { "left": 12, "right": 378, "width": 366 },
  "ariaBusy": "false"
}
```

Desktop:

```json
{
  "innerWidth": 1365,
  "documentScrollWidth": 1365,
  "bodyScrollWidth": 1365,
  "horizontalOverflow": false,
  "emptyState": { "left": 353, "right": 1275, "width": 922 },
  "composer": { "left": 353, "right": 1273, "width": 920 },
  "ariaBusy": "false"
}
```

Screenshot QA lokal:

- `/tmp/hai_phase74_mobile.png`
- `/tmp/hai_phase74_desktop.png`
