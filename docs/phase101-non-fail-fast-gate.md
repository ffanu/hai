# Phase 101 — Non-fail-fast production gate

Tujuan fase ini adalah membuat public release gate memberi bukti lengkap saat ada satu flow gagal/flaky.

## Masalah

Sebelumnya `scripts/hai_production_qa.py` berhenti pada check pertama yang gagal. Saat Phase 99 post-deploy menemukan kegagalan `sources-web`, runner tidak menjalankan mobile sources, visual snapshot, atau release audit sehingga operator kehilangan gambaran penuh.

## Perubahan

- Default runner sekarang mengumpulkan semua check sampai selesai.
- Opsi `--fail-fast` tetap tersedia untuk debugging cepat.
- Summary JSON menambahkan:
  - `total_planned`
  - `failed`
  - `fail_fast`

## Acceptance criteria

- `python3 -m py_compile scripts/hai_production_qa.py` lulus.
- `python3 scripts/hai_production_qa.py --help` menampilkan `--fail-fast`.
- Public release gate tetap lulus 21/21 setelah Phase 100.
