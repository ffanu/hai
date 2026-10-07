# Phase 93 — Single-sentence regenerate polish

Tujuan fase ini adalah memperbaiki kualitas jawaban final saat user eksplisit meminta satu kalimat.

Sebelumnya QA regenerate masih bisa lulus selama tidak ada exact duplicate first sentence, tetapi model kadang tetap menambahkan kalimat kedua yang mirip. Untuk UI publik bergaya ChatGPT/Claude, instruksi singkat seperti “jawab tepat satu kalimat” harus dihormati.

## Perubahan

Frontend menambahkan finalizer:

- `userExplicitlyAskedSingleSentence(promptText)`
- `trimAssistantToSingleSentenceIfRequested(responseText, promptText)`

Perilaku:

- Hanya aktif jika prompt user eksplisit menyebut “satu kalimat” atau “1 kalimat”.
- Setelah stream selesai, final answer dipotong ke kalimat pertama.
- Hasil yang tersimpan ke history dan dipakai tombol copy/edit/regenerate adalah hasil final yang sudah dirapikan.
- Tidak memengaruhi jawaban normal, dokumen, web sources, atau image artifact.

QA regenerate diperketat:

- `sentenceCount <= 1`
- tetap mengecek no reasoning leak, no overflow, action bar publik, dan satu assistant container.

## Hasil production

Release:

- `/srv/harmonika-chat-webui-release-20261006011556`
- Service: `harmonika-hai-web.service`
- Status: `active`

Regenerate browser QA:

```json
{
  "ok": true,
  "sentenceCount": 1,
  "duplicateFirstSentence": false,
  "hasThinkLeak": false,
  "horizontalOverflow": false
}
```

Core production runner:

```json
{
  "ok": true,
  "passed": 10,
  "total_run": 10
}
```

Extended non-image runner:

```json
{
  "ok": true,
  "mobile": true,
  "multi_attachment": true,
  "web_sources": true,
  "passed": 16,
  "total_run": 16
}
```

Extended coverage:

- desktop empty/chat/history/stop/regenerate/attachment
- mobile empty/history/attachment
- multi-file TXT+CSV desktop/mobile
- web/search source chips desktop

