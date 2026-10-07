# Phase 89 — Stop Hidden Reasoning Guard

Tanggal: 2026-10-06

## Tujuan

Menutup kasus Stop cepat yang masih bisa menghasilkan bubble kosong walau Phase 88 sudah membuat render stop sinkron.

## Penyebab

Saat Stop ditekan sangat cepat, upstream kadang sudah mengirim potongan raw reasoning seperti `<think>...`. Nilai `fullResponse.trim()` menjadi tidak kosong, sehingga fallback `Jawaban dihentikan.` tidak dipasang. Namun renderer publik memang menyembunyikan reasoning, akibatnya bubble terlihat kosong.

## Perubahan

- Jalur AbortError utama kini mengecek `stripPublicReasoningBlocks(fullResponse).trim()`.
- Jika teks publik yang terlihat kosong, `fullResponse` diganti menjadi `Jawaban dihentikan.` sebelum action buttons dan history disimpan.
- Asset cache-bust dinaikkan ke `20261006-phase89`.

## Acceptance Criteria

- `stop-stream` tidak boleh menghasilkan bubble kosong.
- Stop cepat dengan raw reasoning tersembunyi tetap tampil sebagai `Jawaban dihentikan.`.
- Production QA runner core harus lulus sampai selesai.
