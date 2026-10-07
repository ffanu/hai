# Phase 62 Production Verification

Tanggal: 2026-10-05
Domain: `https://hai.harmonika.id`
Release sebelum verifikasi: `/srv/harmonika-chat-webui-release-20261005153436`
Asset aktif saat verifikasi: `20261005-phase61`

## Ringkasan

Phase 62 adalah checkpoint verifikasi production untuk state yang belum tercakup penuh oleh smoke CSS sebelumnya:

- upload parser dokumen;
- history reload/sync;
- source stack/citations;
- chat SSE normal.

Tidak ada perubahan kontrak API atau backend pada checkpoint ini.

## Hasil

### 1. Upload parser

Endpoint: `POST /api/attachments/parse`

| File | MIME | Hasil |
| --- | --- | --- |
| `phase62.txt` | `text/plain` | `ok=true`, teks berisi `HAI-TXT-6262` |
| `phase62.csv` | `text/csv` | `ok=true`, teks berisi `HAI-CSV-6262` |
| `phase62.pdf` | `application/pdf` | `ok=true`, teks berisi `HAI-PDF-6262` |

Catatan: pengecekan CSV pertama sempat false karena string pembanding menyertakan newline; respons detail membuktikan teks CSV diekstrak normal.

### 2. History reload

Endpoint: `GET /api/history`, `PUT /api/history`

Uji memakai cookie jar terisolasi:

- `GET /api/history` awal: `200`, `chats=[]`.
- `PUT /api/history` dengan chat `phase62-smoke`: `200`, `ok=true`.
- `GET /api/history` ulang: `200`, chat `phase62-smoke` ditemukan, pesan berisi `HAI-HIST-6262`.

### 3. Source stack / citations

Endpoint: `POST /chat`

Prompt smoke:

```text
@s berita teknologi AI terbaru ringkas 3 sumber
```

Hasil:

- status `200`;
- header `X-HAI-Intent: text`;
- header `X-HAI-Sources` tersedia;
- jumlah source terdecode: `3`;
- contoh sumber: `berita.ai`, `detik.com`, `teknopulse.id`.

Ini cukup untuk memicu tampilan source stack/citation di UI.

### 4. Chat SSE

Endpoint: `POST /chat`

Prompt smoke:

```text
Jawab singkat satu kalimat: apa itu router?
```

Hasil:

- status `200`;
- header `X-HAI-Intent: text`;
- stream berisi jawaban normal tentang router.

## Catatan risiko

- Smoke ini tidak menguji perangkat mobile sungguhan atau virtual keyboard.
- Smoke upload dilakukan langsung ke endpoint parser; flow browser picker visual tetap perlu uji manual jika diperlukan.
- Source stack diverifikasi dari header dan jumlah metadata; screenshot Chrome headless di mesin lokal sempat timeout sehingga tidak menjadi gate.
