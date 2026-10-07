# Phase 221 — Release Audit Failure Report

Tanggal: 2026-10-06

Phase ini membuat `scripts/hai_release_audit.py` lebih aman untuk pipeline otomatis.

## Perubahan

Jika target audit tidak bisa dihubungi, helper `fetch()` sekarang mengembalikan hasil terstruktur:

```json
{
  "status": 0,
  "body": {"error": "request_failed", "detail": "..."},
  "headers": {}
}
```

Audit tetap menyelesaikan seluruh daftar check, menulis `json-out`, dan keluar dengan status gagal. Sebelumnya kondisi unreachable bisa membuat script crash sebelum artefak audit terbentuk.

## Alasan

Release readiness butuh bukti negatif yang bisa dibaca manusia/agent. JSON gagal terstruktur lebih berguna daripada traceback mentah ketika network/DNS/proxy sedang bermasalah.

## Acceptance

- Target production sehat tetap menghasilkan release audit OK.
- Target unreachable menghasilkan `ok=false`, `status=0`, dan file JSON tetap dibuat.
