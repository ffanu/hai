# Phase 86 — Attachment API QA

Tanggal: 2026-10-06

## Tujuan

Menambahkan smoke test repeatable untuk endpoint upload/parser dokumen publik:

`POST /api/attachments/parse`

Fitur lampiran sudah aktif di `/api/capabilities`, sehingga parser perlu QA mandiri selain browser UI.

## Perubahan

- Menambahkan `scripts/hai_attachment_qa.py`.
- Script membuat file kecil di memory tanpa dependency eksternal:
  - TXT
  - CSV
  - DOCX minimal
  - XLSX minimal
- Script melakukan multipart upload ke `/api/attachments/parse` dan memastikan teks unik marker muncul di hasil parse.

## Contoh

```bash
python3 scripts/hai_attachment_qa.py --base-url https://hai.harmonika.id
```

## Hasil production awal

Semua kasus lulus:

- TXT: `200 ok`
- CSV: `200 ok`
- DOCX: `200 ok`
- XLSX: `200 ok`

## Acceptance Criteria

- Script berjalan tanpa dependency eksternal.
- Semua file test mendapat `status=200` dan `payload.ok=true`.
- Teks marker unik muncul di `payload.file.text`.
