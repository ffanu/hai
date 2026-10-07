# Phase 77 — Public Reasoning Guard

Tanggal: 2026-10-05

## Tujuan

Menutup kebocoran tampilan reasoning internal pada bubble assistant. Sebelum phase ini, browser QA chat-text membuktikan jawaban final masih menampilkan panel gelap:

- `Thought Process (...)`
- `Sedang menyusun jawaban…`

Untuk UI publik seperti ChatGPT/Claude, teks tersebut tidak boleh tampil sebagai bagian jawaban.

## Perubahan

- Menambahkan `stripPublicReasoningBlocks()` di renderer Markdown.
- `preprocessMarkdown()` kini menghapus blok `<think>...</think>` dan end-tag reasoning sebelum Markdown dirender.
- Raw content tetap tidak dipaksa migrasi agar riwayat lama tetap kompatibel, tetapi tampilan publik hanya menampilkan jawaban akhir.
- `scripts/hai_browser_qa.py` mendapat flow `--flow chat-text` untuk mengirim prompt dari browser nyata dan memverifikasi:
  - user bubble muncul;
  - assistant bubble muncul;
  - URL chat tetap `/c/{id}`;
  - sidebar aktif sesuai ID URL;
  - `aria-busy=false` setelah final;
  - tidak ada teks `Thought Process`, `<think>`, atau `Sedang menyusun jawaban` di tampilan.
- Asset cache-bust dinaikkan ke `20261005-phase77`.

## Contoh QA

```bash
python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow chat-text --timeout 60
```

## Acceptance Criteria

- `node --check static/js/scripts.js` lulus.
- `python -m py_compile app.py scripts/hai_browser_qa.py scripts/hai_history_qa.py` lulus.
- Flow browser `chat-text` menghasilkan `ok=true`.
- Screenshot bubble assistant tidak menampilkan panel/teks reasoning internal.
