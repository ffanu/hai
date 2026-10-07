# Phase 94 — Visual snapshot QA + mobile action bar polish

Tujuan fase ini adalah membuat audit visual production lebih repeatable dan merapikan tampilan chat mobile.

## Perubahan

### Visual QA harness

Ditambahkan:

```bash
python3 scripts/hai_visual_qa.py \
  --base-url https://hai.harmonika.id \
  --out-dir qa-screenshots/phase94-final \
  --include-chat \
  --json-out qa-reports/phase94-visual-final.json
```

Yang diuji:

- Screenshot desktop empty `1365x900`.
- Screenshot mobile empty `390x844`.
- Screenshot desktop chat-text `1365x900`.
- Screenshot mobile chat-text `390x844`.
- PNG valid dan ukuran sesuai viewport.
- Tidak ada horizontal overflow.
- Chat flow tetap selesai, no reasoning leak, dan action assistant tetap ada.

### Production runner

`scripts/hai_production_qa.py` kini punya:

```bash
--visual-snapshots --visual-out-dir qa-screenshots/production
```

### Mobile action bar polish

Action bar mobile dibuat lebih tenang:

- background lebih subtle;
- shadow dihapus;
- opacity default lebih rendah;
- ikon tetap touch-friendly.

### Cache bust

Asset marker dinaikkan:

- `styles.css?v=20261006-phase94`
- `scripts.js?v=20261006-phase94`

Ini memastikan browser pelanggan tidak tertahan cache `phase89`.

## Hasil production

Release:

- `/srv/harmonika-chat-webui-release-20261006012657` untuk patch awal Phase 94.
- `/srv/harmonika-chat-webui-release-20261006012949` untuk release final dengan cache-bust `phase94`.

Visual QA final:

```json
{
  "ok": true,
  "passed": 4,
  "total_run": 4
}
```

Production runner with visual snapshots:

```json
{
  "ok": true,
  "visual_snapshots": true,
  "passed": 11,
  "total_run": 11
}
```

Screenshot final:

- `qa-screenshots/phase94-final/desktop-empty.png`
- `qa-screenshots/phase94-final/mobile-empty.png`
- `qa-screenshots/phase94-final/desktop-chat-text.png`
- `qa-screenshots/phase94-final/mobile-chat-text.png`

Cache-bust final verified:

- CSS URL: `https://hai.harmonika.id/static/css/styles.css?v=20261006-phase94`
