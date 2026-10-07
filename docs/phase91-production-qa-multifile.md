# Phase 91 — Production QA multi-file + anti-duplicate response guard

Tujuan fase ini adalah memperkuat gate production tanpa mengubah kontrak publik chat:

- Menambahkan browser QA `attachment-multi-chat`.
- Menambahkan opsi runner `--multi-attachment`.
- Menambahkan opsi `--json-out` agar hasil QA bisa disimpan sebagai artefak rilis.
- Memperkuat prompt backend agar jawaban tidak menggandakan kalimat/paragraf yang sama.
- Menambahkan assertion ringan di QA regenerate untuk menangkap exact duplicate first sentence.

## Perubahan

### Browser QA

Flow baru:

```bash
python3 scripts/hai_browser_qa.py \
  --url https://hai.harmonika.id/ \
  --viewport desktop \
  --flow attachment-multi-chat \
  --timeout 120
```

Yang diuji:

- TXT dan CSV dipilih dalam satu message.
- Tray menampilkan dua chip dan counter `2/3`.
- Bubble user menampilkan dua nama file.
- Assistant membaca dua marker unik dari isi lampiran.
- Tray kosong setelah kirim.
- Tidak ada horizontal overflow.
- Tidak ada leak reasoning.

### Production runner

Flag baru:

```bash
python3 scripts/hai_production_qa.py \
  --base-url https://hai.harmonika.id \
  --mobile \
  --multi-attachment \
  --json-out qa-reports/phase91-production-qa-after-deploy.json
```

`--multi-attachment` menambahkan:

- `browser_attachment_multi_desktop`
- `browser_attachment_multi_mobile` bila `--mobile` aktif

`--json-out` menyimpan full summary JSON untuk audit rilis.

### Backend quality guard

Default system prompt sekarang menambahkan aturan:

- Jangan menggandakan jawaban.
- Jangan mengulang kalimat/paragraf yang sama.
- Jika user meminta singkat, jawab langsung dan padat.

Aturan ini juga disisipkan ke jalur system prompt hasil search/link/continue agar mode khusus tidak melepas guard kualitas.

## Hasil production

Release production:

- `/srv/harmonika-chat-webui-release-20261006005312`
- Service: `harmonika-hai-web.service`
- Status service: `active`

Runner pasca-deploy:

```json
{
  "ok": true,
  "base_url": "https://hai.harmonika.id",
  "include_image": false,
  "mobile": true,
  "multi_attachment": true,
  "passed": 15,
  "total_run": 15
}
```

## Acceptance criteria

- Core runner tetap hijau.
- Mobile runner hijau.
- Multi-file TXT+CSV desktop/mobile hijau.
- Regenerate tetap hanya satu assistant container, action bar maksimal empat aksi publik, dan exact duplicate first sentence tidak lolos.
- JSON report tersimpan untuk audit.

