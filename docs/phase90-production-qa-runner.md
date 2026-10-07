# Phase 90 — Production QA Runner Baseline

Tanggal: 2026-10-06

## Tujuan

Menyediakan satu command untuk mengecek readiness production inti setelah deploy.

## Perubahan

- Menambahkan `scripts/hai_production_qa.py`.
- Runner menggabungkan:
  - Python compile;
  - JS syntax;
  - History API QA;
  - Attachment API QA;
  - Browser empty desktop;
  - Browser chat text desktop;
  - Browser history desktop;
  - Browser stop desktop;
  - Browser regenerate desktop;
  - Browser attachment desktop.
- Image generation QA dibuat opt-in dengan `--include-image` agar tidak membakar kuota setiap smoke.
- Mobile browser flows dibuat opt-in dengan `--mobile`.

## Command

Core:

```bash
python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id
```

Mobile + image optional:

```bash
python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --mobile --include-image
```

## Hasil production baseline

Core suite lulus:

```json
{
  "ok": true,
  "passed": 10,
  "total_run": 10
}
```

## Acceptance Criteria

- Core runner lulus 10/10.
- `stop-stream` tidak lagi kosong.
- Runner berhenti saat check pertama gagal agar regresi cepat terlihat.
