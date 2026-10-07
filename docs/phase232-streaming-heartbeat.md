# Phase 232 — Streaming Heartbeat

Tanggal: 2026-10-06

Phase ini melanjutkan Phase 231. Jika Phase 231 hanya mengirim frame awal, Phase 232 menjaga koneksi tetap hidup selama upstream AI/image bridge lambat.

## Perubahan

- Ditambahkan `_stream_with_heartbeat()` di backend:
  - producer blocking berjalan di worker thread daemon;
  - response tetap bisa mengirim `: hai-open` segera;
  - saat belum ada output baru, backend mengirim `: hai-ping` berkala.
- `/chat` text path memakai wrapper heartbeat.
- `/chat` image intent path memakai wrapper heartbeat, sehingga pembuatan gambar yang lambat tidak membuat HTTP stream kosong.
- `/continue_generation` memakai wrapper heartbeat.
- Frontend sudah menyaring `: hai-open`, `: hai-ping`, dan `: hai-heartbeat`, jadi frame kontrol tidak tampil dan tidak masuk riwayat.
- `scripts/hai_stream_open_qa.py` kini mengecek:
  - text stream punya open frame;
  - image stream punya open frame;
  - image stream lambat mengirim heartbeat sebelum hasil akhir.

## Dampak

UI tetap terlihat seperti ChatGPT/Claude: placeholder/typing state muncul, tombol Stop tetap tersedia, dan koneksi lebih tahan terhadap idle timeout proxy ketika engine lambat.

## Batasan

Ini belum realtime replay/WSS. Heartbeat hanya menjaga koneksi SSE aktif. Resume/replay event tetap masuk roadmap lanjutan.
