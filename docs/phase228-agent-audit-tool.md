# Phase 228 — Agent Audit Tool

Tanggal: 2026-10-06

Phase ini menambahkan tooling koordinasi agent yang lebih stabil untuk audit non-edit Claude/opencode.

## Masalah

Percobaan audit agent sebelumnya memakai wrapper shell/background dan sempat gagal karena command `timeout` tidak tersedia di macOS atau proses background tidak menulis output. Akibatnya tidak ada temuan agent yang bisa dipakai sebagai evidence.

## Perubahan

Script baru: `scripts/hai_agent_audit.py`

Fitur:

- menjalankan Claude, opencode, atau keduanya
- mode non-edit lewat prompt standar
- timeout berbasis Python `subprocess.run(..., timeout=...)`
- output JSON terstruktur dengan `passed/total_run`
- stdout dipotong aman agar report tidak terlalu besar
- output ANSI/color dibersihkan agar JSON report mudah dibaca
- jika binary tidak ada, hasil `skipped=true`, bukan crash tidak jelas

## Command

```bash
.venv/bin/python scripts/hai_agent_audit.py --agent claude --timeout 120 --json-out qa-reports/agent-claude.json
.venv/bin/python scripts/hai_agent_audit.py --agent opencode --timeout 120 --json-out qa-reports/agent-opencode.json
.venv/bin/python scripts/hai_agent_audit.py --agent both --timeout 120 --json-out qa-reports/agent-audit.json
```

## Acceptance

- Script bisa di-compile.
- `--agent claude` dan `--agent opencode` punya command path eksplisit.
- Kegagalan/hang agent tetap menghasilkan JSON artifact yang bisa diaudit.
