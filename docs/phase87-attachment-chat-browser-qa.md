# Phase 87 — Attachment Chat Browser QA

Tanggal: 2026-10-06

## Tujuan

Menambahkan regression test end-to-end untuk lampiran dari UI browser, bukan hanya endpoint parser.

## Perubahan

- `scripts/hai_browser_qa.py` mendapat flow `--flow attachment-chat`.
- Flow ini mensimulasikan pemilihan file TXT melalui file input:
  1. membuat `File` di browser dengan marker unik;
  2. mengisi `input[type=file]` memakai `DataTransfer`;
  3. menunggu chip lampiran tampil di tray;
  4. mengirim prompt;
  5. memastikan bubble user menampilkan nama file;
  6. memastikan assistant membaca marker dari isi file;
  7. memastikan tray lampiran kosong setelah send;
  8. memastikan no reasoning leak dan no horizontal overflow.

## Hasil production awal

Desktop dan mobile lulus:

```json
{
  "ok": true,
  "chipText": "hai-ui-attachment.txt ... 1/3",
  "assistantSample": "HAI-UI-ATTACH-...",
  "trayAfterSend": "",
  "horizontalOverflow": false
}
```

## Acceptance Criteria

- Desktop dan mobile `attachment-chat` menghasilkan `ok=true`.
- AI menyebut marker unik dari isi file.
- User bubble menampilkan metadata lampiran.
- Tray composer bersih setelah pesan terkirim.
