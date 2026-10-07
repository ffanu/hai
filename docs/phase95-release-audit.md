# Phase 95 — HTTP release audit

Tujuan fase ini adalah membuat gate production yang memeriksa keadaan publik `hai.harmonika.id`, bukan hanya file lokal atau browser flow.

## Perubahan

Ditambahkan:

```bash
python3 scripts/hai_release_audit.py \
  --base-url https://hai.harmonika.id \
  --expected-asset-marker 20261006-phase94 \
  --json-out qa-reports/phase95-release-audit.json
```

Audit memeriksa:

- `/` merespons 200.
- HTML memakai asset marker `20261006-phase94`.
- HTML tidak lagi memakai marker lama `20261006-phase89`.
- CSS dan JS asset dengan marker phase94 load 200 dan ukurannya masuk akal.
- Header keamanan dasar ada:
  - `X-Content-Type-Options`
  - `X-Frame-Options`
  - `Referrer-Policy`
  - `Permissions-Policy`
  - `Strict-Transport-Security`
- `/healthz` ok dan secret production configured.
- `/api/capabilities` mengekspos fitur publik utama.
- Limit upload/multi-attachment sesuai kontrak.

## Production runner

`scripts/hai_production_qa.py` kini punya:

```bash
--release-audit --expected-asset-marker 20261006-phase94
```

## Hasil production

Standalone release audit:

```json
{
  "ok": true,
  "passed": 4,
  "total_run": 4
}
```

Production runner dengan release audit:

```json
{
  "ok": true,
  "release_audit": true,
  "expected_asset_marker": "20261006-phase94",
  "passed": 11,
  "total_run": 11
}
```

Evidence penting:

- CSS asset: `https://hai.harmonika.id/static/css/styles.css?v=20261006-phase94`
- JS asset: `https://hai.harmonika.id/static/js/scripts.js?v=20261006-phase94`
- `flask_secret_configured=true`
- `device_secret_configured=true`
- `attachments_per_message=3`
- `max_upload_bytes=10485760`

