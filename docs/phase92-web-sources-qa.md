# Phase 92 — Web/source chip browser QA

Tujuan fase ini adalah memastikan fitur referensi web tetap rapi seperti chat modern:

- Full URL tidak tampil di bubble jawaban.
- Referensi tampil kecil sebagai chip/stack favicon.
- Detail sumber hanya menampilkan judul/domain/snippet pendek.
- Tidak ada horizontal overflow.
- Tidak ada leak reasoning.

## Browser flow

Flow baru:

```bash
python3 scripts/hai_browser_qa.py \
  --url https://hai.harmonika.id/ \
  --viewport desktop \
  --flow sources-web \
  --timeout 120
```

Flow mengirim:

```text
@s OpenAI ChatGPT
```

Acceptance checks:

- Assistant selesai streaming (`aria-busy=false`).
- `.hai-source-chips` muncul.
- Untuk tiga sumber atau lebih, stack kecil dan tombol jumlah sumber muncul.
- Detail panel bisa dibuka.
- Source UI tidak mengandung full URL `http://` atau `https://`.
- Assistant bubble tidak mengandung full URL.
- Flow web/search tidak boleh memunculkan artifact/claim gambar.
- `scrollWidth <= innerWidth`.

## Production runner

Flag baru:

```bash
python3 scripts/hai_production_qa.py \
  --base-url https://hai.harmonika.id \
  --web-sources \
  --json-out qa-reports/phase92-production-web-sources-qa.json
```

## Hasil production

Release final:

- `/srv/harmonika-chat-webui-release-20261006011033`
- Guard prompt web/search melarang klaim/preview/download gambar bila user tidak meminta gambar.
- Browser QA `sources-web` kini memeriksa `hasImageArtifact=false` dan `hasImageClaim=false`.

Runner:

```json
{
  "ok": true,
  "base_url": "https://hai.harmonika.id",
  "web_sources": true,
  "passed": 11,
  "total_run": 11
}
```

Hasil source QA:

- `chipsCount`: 4
- `stackLinksCount`: 3
- `detailsOpen`: true
- `assistantHasFullUrl`: false
- `sourceUiHasFullUrl`: false
- `hasImageArtifact`: false
- `hasImageClaim`: false
- `horizontalOverflow`: false
