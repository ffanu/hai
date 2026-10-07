# Phase 103 — Deterministic source QA

Tujuan fase ini adalah menghilangkan flake pada flow `sources-web`.

## Masalah

Public release gate Phase 102 membuktikan visual responsive 8/8, tetapi `sources-web` desktop/mobile gagal karena query `@s OpenAI ChatGPT` kadang tidak menghasilkan source metadata dari provider search eksternal. UI sebenarnya sehat, tetapi QA bergantung pada hasil DuckDuckGo yang tidak deterministik.

## Perubahan

Flow `sources-web` di `scripts/hai_browser_qa.py` kini memakai URL deterministic yang tidak memuat copy onboarding gambar:

```text
@s https://hai.harmonika.id/healthz jelaskan singkat status service ini
```

Dengan ini browser QA tetap membuktikan hal yang penting:

- source chip muncul;
- full URL tidak bocor di bubble/source UI;
- tidak ada artifact/klaim gambar;
- tidak ada horizontal overflow.

Namun test tidak lagi bergantung pada search engine eksternal yang bisa kosong/rate-limit.

## Acceptance criteria

- `python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport desktop --flow sources-web` lulus.
- `python3 scripts/hai_browser_qa.py --url https://hai.harmonika.id/ --viewport mobile --flow sources-web` lulus.
- Public release gate kembali hijau dengan visual responsive 8/8.
