# Phase 102 — Responsive viewport QA

Tujuan fase ini adalah memperluas bukti UI production dari desktop/mobile portrait menjadi empat ukuran utama:

- Desktop: `1365x900`
- Mobile portrait: `390x844`
- Tablet portrait: `820x1180`
- Mobile landscape: `844x390`

## Perubahan

- `scripts/hai_browser_qa.py` menambah viewport:
  - `tablet`
  - `landscape`
- `scripts/hai_visual_qa.py` menangkap screenshot untuk semua viewport secara default.
- `--viewports` ditambahkan agar operator bisa membatasi snapshot saat debugging.
- Public release gate otomatis mendapat artefak visual lebih lengkap karena sudah memakai `--visual-snapshots`.

## Acceptance criteria

- `python3 -m py_compile scripts/hai_browser_qa.py scripts/hai_visual_qa.py scripts/hai_production_qa.py` lulus.
- `python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport tablet --flow empty` lulus tanpa horizontal overflow.
- `python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport landscape --flow empty` lulus tanpa horizontal overflow.
- `python3 scripts/hai_visual_qa.py --base-url https://hai.harmonika.id --include-chat ...` menghasilkan 8 screenshot: 4 empty + 4 chat.
