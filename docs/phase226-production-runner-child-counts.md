# Phase 226 — Production Runner Child Counts

Tanggal: 2026-10-06

Phase ini memperbaiki keterbacaan report `scripts/hai_production_qa.py` untuk child script yang tidak menulis `passed` dan `total_run` secara eksplisit.

## Masalah

Beberapa child script menghasilkan JSON seperti:

```json
{"ok": true, "results": [{"ok": true}, {"ok": true}]}
```

atau hanya:

```json
{"ok": true}
```

Runner sebelumnya menyimpan `ok=true`, tetapi `passed/total_run` kosong. Contoh yang terlihat di report:

- `attachment_api` punya 4 result, tetapi tidak ada count.
- `history_api` hanya terlihat `{"ok": true}`.

## Perubahan

`summarize_child_json()` sekarang:

- menginfer `passed` dan `total_run` dari `results[]`
- menginfer `passed` dan `total_run` dari `checks[]`
- memakai fallback `1/1` untuk output sederhana `{"ok": true}`
- memakai fallback `0/1` untuk output sederhana `{"ok": false}`

## Acceptance

Ringkasan runner lebih informatif tanpa mengubah kontrak endpoint atau workflow UI.
