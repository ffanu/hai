# Phase 203 — Image Picker End-to-End QA

Tanggal: 2026-10-06

## Tujuan

Phase 201 sudah membuktikan vision API membaca gambar lewat payload `/chat`. Phase 203 membuktikan jalur UI browser lengkap:

1. User memilih gambar lewat file input/composer.
2. Chip lampiran gambar muncul.
3. Thumbnail preview siap.
4. Gambar dikirim dari composer.
5. AI membaca isi gambar.
6. Riwayat/bubble user menampilkan nama file tanpa membocorkan base64.

## Perubahan

- Menambahkan flow browser QA `attachment-image-chat`.
- Public release gate kini menjalankan:
  - `browser_attachment_image_desktop`
  - `browser_attachment_image_mobile`
- Flow QA membuat PNG merah valid dari canvas browser, memasukkannya ke file input sebagai `hai-red-vision-qa.png`, lalu meminta AI menjawab warna dominan.

## Hasil QA production target

Command:

```bash
python3 scripts/hai_browser_qa.py \
  --url https://hai.harmonika.id/ \
  --viewport desktop \
  --flow attachment-image-chat \
  --timeout 120

python3 scripts/hai_browser_qa.py \
  --url https://hai.harmonika.id/ \
  --viewport mobile \
  --flow attachment-image-chat \
  --timeout 120
```

Hasil desktop:

- `ok: true`
- Chip: `hai-red-vision-qa.png`
- Status chip: `Gambar siap dianalisis AI`
- Assistant sample: `Merah`
- `base64LeakInText: false`
- `publicMediaLeak: false`
- `horizontalOverflow: false`

Hasil mobile:

- `ok: true`
- Chip: `hai-red-vision-qa.png`
- Status chip: `Gambar siap dianalisis AI`
- Assistant sample: `Merah`
- `base64LeakInText: false`
- `publicMediaLeak: false`
- `horizontalOverflow: false`

## Temuan penting

Percobaan awal memakai PNG hardcoded 97B yang tampil sebagai thumbnail, tetapi engine menjawab “Gambar tidak terbaca.” Setelah QA membuat PNG valid dari canvas browser, jalur UI berhasil. Ini menegaskan bahwa failure awal berasal dari fixture gambar QA yang terlalu kecil/tidak ideal, bukan dari flow composer utama.

## Acceptance Phase 203

Phase 203 lulus bila:

1. Desktop dan mobile `attachment-image-chat` hijau.
2. Chip gambar tampil sebelum kirim.
3. Bubble user menampilkan nama file dan ukuran.
4. Assistant menjawab warna gambar dengan benar.
5. Tidak ada base64/data URL di text bubble.
6. Tidak ada URL publik `/media`/`/download`.

