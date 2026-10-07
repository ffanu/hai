# Phase 85 — Stop & Regenerate QA

Tanggal: 2026-10-06

## Tujuan

Menutup workflow standar ChatGPT/Claude:

- Stop response tidak boleh membuat state streaming nyangkut.
- Stop cepat tidak boleh menyisakan placeholder “Harmonika AI sedang menyusun jawaban…”.
- Regenerate harus mengganti jawaban terakhir tanpa menggandakan bubble.

## Perubahan

- `scripts/hai_browser_qa.py` mendapat flow:
  - `--flow stop-stream`
  - `--flow regenerate`
- Stop QA sekarang memverifikasi:
  - tombol Stop sempat tampil;
  - `aria-busy=false` setelah stop;
  - tidak ada `.is-streaming`;
  - assistant bubble tidak kosong;
  - assistant bubble tidak masih placeholder waiting;
  - no reasoning leak dan no horizontal overflow.
- Regenerate QA memverifikasi:
  - message id assistant berubah;
  - assistant count tetap satu;
  - action bar tetap empat aksi publik;
  - no reasoning leak dan no horizontal overflow.
- Runtime fix: AbortError outer catch kini mengganti placeholder waiting menjadi `Jawaban dihentikan.` atau `Pembuatan gambar dihentikan.`.
- Asset cache-bust dinaikkan ke `20261006-phase85`.

## Bug yang ditemukan

Sebelum fix, stop sangat cepat bisa meninggalkan bubble:

```text
Harmonika AI sedang menyusun jawaban…
```

tanpa benar-benar berubah menjadi state stop final.

## Acceptance Criteria

- `stop-stream` `ok=true`.
- `regenerate` `ok=true`.
- Stop cepat tidak meninggalkan placeholder waiting.
