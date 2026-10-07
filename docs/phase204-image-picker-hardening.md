# Phase 204 — Image Picker Hardening

Tanggal: 2026-10-06

## Tujuan

Phase ini menutup temuan audit Claude/opencode setelah Phase 203. Public gate sudah hijau, tetapi audit menemukan beberapa celah coverage dan risiko payload gambar terlalu besar saat foto HP dikirim inline sebagai base64 JSON.

## Perubahan

- Gambar browser kini dikompresi ke target aman `HAI_INLINE_IMAGE_TARGET_BYTES` sebelum dikonversi ke base64 untuk request `/chat`.
- Metadata attachment image memakai MIME dari file hasil kompresi, bukan MIME file awal, supaya tidak mismatch saat browser mengubah PNG/WebP besar menjadi JPEG.
- Browser QA `attachment-image-chat` diperketat:
  - memastikan `accept` file input mencakup `image/png`, `image/jpeg`, dan `image/webp`;
  - memastikan chip composer dan bubble user menampilkan nama + ukuran file;
  - jawaban vision harus benar-benar satu kata `Merah`/`Red`, bukan sekadar mengandung kata merah di pesan error;
  - deteksi bocor URL publik diperluas ke atribut HTML relatif/absolut `/media`, `/download`, dan `/files`.
- Production QA runner kini menangkap `subprocess.TimeoutExpired` sebagai check gagal terstruktur, bukan crash yang menghilangkan JSON report.

## QA

Targeted QA lokal setelah patch:

```bash
python3 -m py_compile app.py scripts/hai_browser_qa.py scripts/hai_production_qa.py
node --check static/js/scripts.js
python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow attachment-image-chat --timeout 120
python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport mobile --flow attachment-image-chat --timeout 120
```

Hasil targeted sebelum deploy:

- Syntax Python/JS: lulus.
- Desktop `attachment-image-chat`: lulus.
- Mobile `attachment-image-chat`: lulus.

## Catatan lanjutan

- History multi-turn setelah gambar tetap sengaja tidak menyimpan raw/base64 image. Jika owner ingin follow-up vision seperti “gambar tadi ada apa lagi?”, perlu desain eksplisit: resend image terakhir secara aman atau simpan file privat server-side.
- Raster image generation private `file_id` masih gap terpisah dari image input/vision.
