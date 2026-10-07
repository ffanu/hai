# Phase 100 — Intent-gated image artifacts

Tujuan fase ini adalah memastikan artifact gambar hanya muncul ketika server menyatakan intent `image`.

## Masalah

Post-deploy public release gate Phase 99 menemukan regresi di flow `sources-web`:

- Prompt web/search bukan permintaan gambar.
- Namun bubble assistant berisi klaim "Saya sudah buat gambar" dan thumbnail artifact.
- Ini berbahaya karena user pernah melaporkan gambar/link lama bocor ke chat biasa.

## Perubahan

Frontend renderer kini membawa flag `allowImageArtifacts`:

- Nilai `true` hanya jika parent `.assistant-message-container` punya `data-intent="image"`.
- `CodeBlock` hanya mengubah SVG menjadi thumbnail/canvas jika flag ini `true`.
- Legacy Markdown media/download Harmonika hanya diubah menjadi card gambar jika flag ini `true`.
- Untuk intent text/web, Markdown image/media link Harmonika disanitasi dan tidak menjadi artifact.
- Cache-bust CSS/JS dinaikkan ke `20261006-phase100` agar browser pelanggan mengambil renderer baru.
- Release audit default kini melarang marker lama `20261006-phase89` dan `20261006-phase94` di HTML production.

## Acceptance criteria

- `node --check static/js/scripts.js` lulus.
- `python3 scripts/hai_release_audit.py --base-url https://hai.harmonika.id` lulus setelah deploy dan melihat marker `20261006-phase100`.
- Flow `sources-web` menghasilkan:
  - `hasImageArtifact=false`
  - `hasImageClaim=false`
  - source chips tetap tampil
- Flow `image-artifact` tetap menghasilkan:
  - `hasArtifact=true`
  - private preview `/api/files/{file_id}/preview`
  - tanpa URL publik/raw SVG di bubble
