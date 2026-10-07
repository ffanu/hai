# Phase 225 — Production Runner Child Summary

Tanggal: 2026-10-06

Phase ini memperbaiki ringkasan child JSON di `scripts/hai_production_qa.py`.

## Masalah

Output `scripts/hai_readiness_qa.py` berisi nested object `production.gate_result` dengan field `passed=56` dan `total=56`. Parser runner lama mencari object JSON terakhir yang memiliki key seperti `passed`, sehingga pada beberapa output ia memilih nested `gate_result`, bukan JSON top-level QA.

Akibatnya, child summary untuk check `readiness_api` bisa terlihat seperti:

```json
{"passed": 56}
```

Padahal ringkasan yang benar adalah `ok=true`, `passed=6`, `total_run=6`.

## Perubahan

`extract_json()` sekarang memprioritaskan kandidat JSON top-level yang punya:

- `ok` boolean
- `total_run`

Baru setelah itu fallback ke heuristik lama.

## Acceptance

Runner utama harus menampilkan child summary readiness sebagai `passed=6`, `total_run=6`, bukan `passed=56`.
