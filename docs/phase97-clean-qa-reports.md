# Phase 97 — Clean production QA reports

Tujuan fase ini adalah membuat JSON hasil `scripts/hai_production_qa.py` lebih mudah dibaca oleh operator.

## Masalah

Saat `--public-release-gate` menjalankan sub-runner seperti visual snapshot atau release audit, stdout child script berisi JSON panjang. Karena production runner menyimpan tail stdout mentah, report menjadi noisy dan sulit dibaca.

## Perubahan

Production runner kini mengekstrak JSON child script dan menambahkan `child_summary` ringkas pada tiap check yang relevan.

Contoh ringkasan visual:

```json
{
  "name": "visual_snapshots",
  "ok": true,
  "child_summary": {
    "ok": true,
    "passed": 4,
    "total_run": 4,
    "out_dir": "qa-screenshots/public-release-gate",
    "children": [
      {
        "name": "desktop_empty",
        "ok": true,
        "screenshot": "qa-screenshots/public-release-gate/desktop-empty.png"
      }
    ]
  }
}
```

Untuk check sukses, `stdout` mentah juga dipotong lebih pendek. Jika check gagal, runner tetap menyimpan stdout/stderr lebih panjang agar debugging tidak kehilangan konteks.

## Acceptance criteria

- `py_compile` production runner lulus.
- `--help` tetap menampilkan semua flag Phase 96.
- `--public-release-gate` tetap kompatibel dengan report lama karena field lama tidak dihapus; hanya menambah `child_summary` dan merapikan stdout sukses.
