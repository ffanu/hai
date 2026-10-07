# Phase 201 — Vision Input Contract QA

Tanggal: 2026-10-06

## Tujuan

Membuktikan bahwa `image_input=true` di `https://hai.harmonika.id/api/capabilities` bukan sekadar menerima MIME gambar, tetapi benar-benar membuat engine membaca isi gambar.

## Perubahan

- Menambahkan `scripts/hai_vision_contract_qa.py`.
- Public release gate kini menjalankan `vision_contract_api`.
- QA membuat PNG merah kecil secara programatik, mengirimnya ke `/chat` sebagai payload multimodal `image_url` data URL, lalu meminta Harmonika AI menjawab warna dominan.

## Hasil QA production

Command:

```bash
python3 scripts/hai_vision_contract_qa.py \
  --base-url https://hai.harmonika.id \
  --json-out qa-reports/phase201-vision-contract-production.json
```

Hasil:

- `ok: true`
- `passed: 2/2`
- `features.image_input: true`
- Accepted MIME image: `image/png`, `image/jpeg`, `image/webp`
- `/chat` multimodal menjawab: `Merah`
- Durasi smoke: sekitar 6,1 detik
- Tidak ada base64/data URL bocor di jawaban
- Tidak ada terminal/file-manager leak
- Tidak ada URL publik `/media`/`/download`
- Tidak ada pesan `vision_unavailable`

## Acceptance Phase 201

Phase ini dianggap lulus karena:

1. Capabilities dan MIME image konsisten.
2. Engine membaca gambar merah dan menjawab warna dengan benar.
3. Jawaban tetap customer-safe dan tidak mengekspos payload internal.

## Catatan berikutnya

Vision image input untuk web publik sudah terbukti berfungsi pada smoke dasar. Pengujian yang masih dapat ditambahkan nanti:

- Gambar dengan teks/OCR sederhana.
- Foto objek nyata.
- Error path untuk corrupt image dan file terlalu besar.
- UI browser end-to-end dari file picker gambar, bukan hanya kontrak API `/chat`.

