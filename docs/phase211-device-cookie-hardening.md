# Phase 211 — Device Cookie Rate-Limit Hardening

Phase ini menindaklanjuti audit opencode tentang rate-limit yang bisa jatuh ke IP/proxy saat browser belum memiliki cookie device.

## Masalah

Sebelumnya cookie device `__Host-hai_device` terutama dipasang oleh `/api/history`. Jika user baru langsung mengirim chat atau membuka endpoint API lain sebelum history sync, rate-limit akan memakai IP. Di balik reverse proxy/NAT, beberapa user normal bisa berbagi bucket rate-limit yang sama.

## Perubahan

- Halaman `/` dan `/c/{chat_id}` sekarang menanam cookie device jika belum ada.
- Endpoint rate-limited (`/chat`, `/continue_generation`, `/generate-title`, `/api/attachments/parse`, `/api/files/...`) akan mengantrikan cookie device untuk response bila request belum punya cookie.
- Request pertama tanpa cookie tetap memakai bucket IP untuk mencegah bypass rate-limit dengan menolak cookie; request berikutnya dari browser normal akan memakai bucket device.
- `Set-Cookie` tidak diduplikasi jika route sudah memasang cookie lewat helper history.
- `scripts/hai_release_audit.py` sekarang ikut memeriksa first load `/` mengirim cookie device dengan flag `Secure`, `HttpOnly`, `SameSite=Lax`, dan `Path=/`.

## Acceptance

- First load `/` dari browser tanpa cookie mengembalikan `Set-Cookie: __Host-hai_device=...`.
- First `/chat` tanpa cookie juga mengembalikan device cookie pada response SSE/error.
- `/api/history` tetap memakai cookie device yang sama dan tidak rusak.
- Security flags cookie tetap `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`.
