# Phase 231 — Streaming Open Frame

Tanggal: 2026-10-06

Phase ini memperbaiki rasa streaming saat engine atau image bridge lambat memulai jawaban.

## Perubahan

- `/chat` text path mengirim control frame awal `: hai-open\n\n` sebelum membuat koneksi stream ke engine.
- `/chat` image intent path juga mengirim control frame awal sebelum memanggil image bridge/provider, sehingga browser/proxy tidak menunggu kosong ketika gambar sedang disiapkan.
- `/continue_generation` mengirim control frame awal yang sama.
- Frontend menambahkan `normalizeHaiStreamChunk()` untuk membuang control comment `: hai-open`, `: hai-ping`, atau `: hai-heartbeat` sebelum teks dimasukkan ke bubble/history.
- QA baru `scripts/hai_stream_open_qa.py` memastikan text dan image path sama-sama mengirim frame awal.
- `scripts/hai_production_qa.py` kini menjalankan QA stream-open di default suite dan memasukkannya ke `py_compile`.

## Dampak UX

Pengguna tetap melihat placeholder modern seperti "Harmonika AI sedang menyusun jawaban…" atau "sedang mendesain gambar…", tetapi koneksi HTTP sudah aktif lebih cepat. Frame kontrol tidak tampil di UI dan tidak tersimpan ke riwayat.

## Catatan

Ini bukan event replay/WSS penuh. Ini hardening awal untuk TTFB/proxy idle sebelum roadmap realtime resume/WSS dikerjakan.
