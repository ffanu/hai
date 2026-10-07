# Phase 98 — Dynamic asset marker audit

Tujuan fase ini adalah menutup risiko deploy stale karena cache-bust marker CSS/JS hardcoded di QA script.

## Masalah

Sebelumnya `scripts/hai_release_audit.py` dan `scripts/hai_production_qa.py` punya default:

```text
20261006-phase94
```

Jika rilis berikutnya mengubah CSS/JS tetapi lupa menaikkan marker, atau menaikkan marker di template tetapi lupa mengubah QA script, audit bisa memberi sinyal yang menyesatkan.

## Perubahan

Kedua script kini mendeteksi marker lokal dari `templates/index.html`:

- `styles.css?...`
- `scripts.js?...`

Audit hanya lanjut jika kedua marker lokal konsisten. Marker lokal itu lalu dipakai sebagai `expected_asset_marker` ketika memeriksa HTML production.

Override manual tetap tersedia:

```bash
python3 scripts/hai_release_audit.py \
  --base-url https://hai.harmonika.id \
  --expected-asset-marker 20261006-phase94
```

## Acceptance criteria

- `python3 -m py_compile scripts/hai_release_audit.py scripts/hai_production_qa.py` lulus.
- `python3 scripts/hai_release_audit.py --base-url https://hai.harmonika.id` lulus tanpa perlu arg marker eksplisit.
- `python3 scripts/hai_production_qa.py --base-url https://hai.harmonika.id --release-audit` tetap melaporkan `expected_asset_marker` sesuai template lokal.
