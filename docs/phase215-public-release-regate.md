# Phase 215 — Public Release Re-Gate After Hardening

Phase ini menjalankan ulang full public release gate setelah rangkaian hardening Phase 209–214:

- `/api/readiness`
- file artifact 404/rate-limit
- device cookie rate-limit hardening
- public URL SSRF guard
- image generation quota enforcement
- source header budget guard

## Command

```bash
.venv/bin/python scripts/hai_production_qa.py \
  --base-url https://hai.harmonika.id \
  --public-release-gate \
  --json-out qa-reports/phase215-public-release-gate.json \
  --visual-out-dir qa-screenshots/phase215-public-release-gate
```

## Result

- `ok=true`
- `passed=56`
- `total_run=56`
- `failed=[]`

## Coverage

Gate ini mencakup:

- Python compile dan JavaScript syntax.
- URL safety local QA.
- Source header budget local QA.
- Backend contract API.
- Readiness API.
- Image contract API.
- Vision image input contract.
- History API.
- Attachment parser API.
- Desktop browser flows:
  - empty state
  - sidebar collapse
  - chat text
  - history controls
  - stop
  - regenerate
  - error retry/history/edit/continue
  - document/image attachment
  - multi attachment
  - web sources
  - sources stack
  - a11y
  - streaming states
  - queue composer
  - layout metrics
  - composer keyboard
  - image modal
  - export localization
  - attachment preview a11y
  - rich Markdown
- Mobile browser flows:
  - empty/history
  - stop/regenerate
  - error retry/history/edit/continue
  - document/image/multi attachment
  - web sources
  - source stack
  - a11y
  - streaming states
  - queue composer
  - layout metrics
  - composer keyboard
  - image modal
  - rich Markdown
- Visual snapshots `17/17`:
  - desktop/mobile/tablet/landscape empty
  - desktop/mobile/tablet/landscape chat text
  - desktop/mobile/compact rich Markdown
  - desktop/mobile sources stack
  - desktop/mobile/tablet/landscape composer queue state
- Release audit:
  - HTML/metadata
  - security headers
  - device cookie
  - CSS/JS/icon assets
  - `/healthz`
  - `/api/capabilities`

## Interpretation

`hai.harmonika.id` remains public-MVP ready after hardening. The roadmap gaps from `/api/readiness` still remain intentionally not claimed as complete:

- raster image provider production
- RAG/library/vector database
- realtime replay/WSS
- voice/video
- calendar/automation/admin analytics
