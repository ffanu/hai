# Phase 99 — Mobile flow coverage in public release gate

Tujuan fase ini adalah menutup celah QA mobile yang ditemukan audit Claude setelah Phase 96.

## Masalah

Public release gate sudah menguji mobile untuk empty state, history, dan attachment, tetapi flow yang paling rawan di layar kecil masih desktop-only:

- Stop streaming.
- Regenerate.
- Web/search source chips.

## Perubahan

Saat `--mobile` aktif, production runner kini menambahkan:

- `browser_stop_mobile`
- `browser_regenerate_mobile`

Saat `--web-sources` dan `--mobile` sama-sama aktif, runner juga menambahkan:

- `browser_sources_web_mobile`

Karena `--public-release-gate` otomatis mengaktifkan `--mobile` dan `--web-sources`, gate publik sekarang mencakup flow mobile tambahan ini.

## Acceptance criteria

- `python3 -m py_compile scripts/hai_production_qa.py` lulus.
- `python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --mobile --web-sources --json-out ...` menjalankan check mobile tambahan.
- `--public-release-gate` total check bertambah dari 18 menjadi 21 tanpa memasukkan image generation opt-in.
