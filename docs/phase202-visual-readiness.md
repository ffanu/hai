# Phase 202 — Visual Readiness Baseline

Tanggal: 2026-10-06

## Tujuan

Phase ini mengunci baseline visual terbaru `hai.harmonika.id` setelah Phase 200/201. Fokusnya bukan menambah fitur, tetapi memastikan tampilan classic web chat AI sudah layak dipakai publik pada desktop, mobile, tablet, dan landscape.

## Command QA

```bash
python3 scripts/hai_visual_qa.py \
  --base-url https://hai.harmonika.id \
  --out-dir qa-screenshots/phase202 \
  --include-chat \
  --include-rich-content \
  --include-source-states \
  --include-composer-states \
  --include-component-crops \
  --json-out qa-reports/phase202-visual-qa.json
```

## Hasil

- `ok: true`
- `passed: 17/17`
- Desktop/mobile/tablet/landscape screenshots berhasil dibuat.
- Component crops dibuat untuk:
  - Markdown table
  - Code block
  - Source stack/detail
  - Queue pill
  - Composer

## Screenshot kunci

- `qa-screenshots/phase202/desktop-empty.png`
- `qa-screenshots/phase202/mobile-empty.png`
- `qa-screenshots/phase202/desktop-chat-text.png`
- `qa-screenshots/phase202/mobile-chat-text.png`
- `qa-screenshots/phase202/desktop-markdown-rich.png`
- `qa-screenshots/phase202/mobile-markdown-rich.png`
- `qa-screenshots/phase202/desktop-sources-stack.png`
- `qa-screenshots/phase202/mobile-sources-stack.png`
- `qa-screenshots/phase202/desktop-composer-queue-state.png`
- `qa-screenshots/phase202/mobile-composer-queue-state.png`

## Manual visual review

### Desktop empty state

- Sidebar classic gelap terlihat stabil.
- Welcome screen sederhana: logo HAI, headline “Selamat datang di Harmonika AI”, subteks, dan prompt chips.
- Composer berada di bawah, tidak menabrak konten.
- Tidak ada elemen neon/glass berlebihan.

### Mobile empty state

- Header compact.
- Welcome content center dan tidak overflow.
- Prompt chips tersusun 2x2 dan mudah disentuh.
- Composer tetap terlihat di bawah.

### Desktop active chat

- Topbar menampilkan judul chat.
- User bubble biru rapi.
- Assistant response ringan tanpa bubble berat, mirip pola chat modern/classic.
- Sidebar history aktif jelas.

### Mobile active chat

- Bubble user dan assistant readable.
- Action buttons assistant sengaja subtle saat idle agar layar tidak ramai.
- Composer tidak melebar dan tidak memotong teks.

### Rich content & references

- Markdown table dan code block lulus desktop/mobile/compact.
- Source stack tidak menampilkan full URL, memakai chip/logo ringkas.
- Detail panel reference tetap berada dalam viewport.

## Acceptance Phase 202

Phase 202 dianggap lulus karena:

1. Visual QA production lulus 17/17.
2. Tidak ada horizontal overflow pada viewport utama.
3. Empty state dan active chat terlihat konsisten pada desktop/mobile.
4. Composer, queue state, markdown rich, dan source references punya screenshot/crop terverifikasi.
5. Tema tetap classic/AdminLTE seperti arahan owner, bukan kembali ke neon/glass.

## Catatan lanjutan

- Action buttons mobile dibuat sangat samar saat idle. Ini disengaja agar UI bersih, tetapi perlu tetap diawasi bila owner ingin tombol lebih terlihat.
- Phase berikut yang paling bernilai:
  1. UI end-to-end picker gambar dari browser, bukan hanya vision contract API.
  2. Raster image generation private `file_id` dari bridge member AI.
  3. RAG/library permanen.
  4. Realtime resume/replay.

