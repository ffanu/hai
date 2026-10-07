# Phase 96 — Public release gate

Tujuan fase ini adalah menyatukan smoke production penting menjadi satu command standar sebelum rilis publik `hai.harmonika.id`.

## Perubahan

`scripts/hai_production_qa.py` kini punya flag:

```bash
python3 scripts/hai_production_qa.py \
  --base-url https://hai.harmonika.id \
  --public-release-gate \
  --json-out qa-reports/phase96-public-release-gate.json
```

Flag ini otomatis mengaktifkan:

- Core syntax/API/browser QA.
- Mobile browser flows.
- Multi-file attachment desktop/mobile.
- Web/search source chip QA.
- Visual snapshots desktop/mobile.
- HTTP release audit.

Image generation tidak otomatis ikut karena bisa memakai kuota/provider production. Untuk smoke gambar, jalankan eksplisit:

```bash
python3 scripts/hai_production_qa.py \
  --base-url https://hai.harmonika.id \
  --public-release-gate \
  --include-image \
  --json-out qa-reports/phase96-public-release-gate-with-image.json
```

## Hasil production awal

Run awal terhadap production:

```json
{
  "ok": true,
  "public_release_gate": true,
  "include_image": false,
  "mobile": true,
  "multi_attachment": true,
  "web_sources": true,
  "visual_snapshots": true,
  "visual_out_dir": "qa-screenshots/public-release-gate",
  "release_audit": true,
  "expected_asset_marker": "20261006-phase94",
  "passed": 18,
  "total_run": 18
}
```

Checklist yang lulus:

- `py_compile`
- `js_syntax`
- `history_api`
- `attachment_api`
- `browser_empty_desktop`
- `browser_chat_text_desktop`
- `browser_history_desktop`
- `browser_stop_desktop`
- `browser_regenerate_desktop`
- `browser_attachment_desktop`
- `browser_empty_mobile`
- `browser_history_mobile`
- `browser_attachment_mobile`
- `browser_attachment_multi_desktop`
- `browser_attachment_multi_mobile`
- `browser_sources_web_desktop`
- `visual_snapshots`
- `release_audit`

## Acceptance criteria

- Satu command gate bisa dijalankan ulang oleh Codex/ops sebelum publish.
- Browser QA menutup desktop dan mobile.
- Source/reference UI tetap rapi tanpa menampilkan full URL di bubble.
- Attachment tetap maksimal 3 file per pesan dan parser sehat.
- Visual snapshots tersimpan sebagai artefak rilis.
- Release audit memastikan asset marker, security headers, `/healthz`, dan `/api/capabilities` sehat.
