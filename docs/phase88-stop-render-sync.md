# Phase 88 — Stop Render Sync

Tanggal: 2026-10-06

## Tujuan

Menutup regresi yang ditemukan oleh production QA runner: flow `stop-stream` kadang menghasilkan bubble assistant kosong setelah Stop cepat, walau state sudah idle.

## Penyebab

`setAssistantError()` memakai React root render. Pada React 18, render root dapat terschedule async sehingga QA/user bisa melihat state sudah selesai tetapi isi bubble belum ter-render.

## Perubahan

- `setAssistantError()` kini memasang `textContent` fallback langsung sebelum render React.
- Jika `ReactDOM.flushSync` tersedia, render error/stop dilakukan sinkron.
- Asset cache-bust dinaikkan ke `20261006-phase88`.

## Acceptance Criteria

- `stop-stream` menghasilkan bubble non-kosong.
- Bubble stop berisi `Jawaban dihentikan.` atau pesan stop/error yang aman.
- Tidak ada placeholder `Harmonika AI sedang menyusun jawaban…` setelah stop.
