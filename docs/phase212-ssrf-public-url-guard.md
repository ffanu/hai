# Phase 212 — Public URL Fetch Guard

Phase ini menutup risiko SSRF pada jalur `@s` webpage/search fetch.

## Masalah

Perintah `@s https://...` dan fetch hasil search dapat mengambil halaman web untuk diringkas. Sebelum phase ini, URL arbitrary dapat diarahkan ke IP internal/private bila user memasukkan URL seperti localhost, private network, atau metadata link-local.

## Perubahan

- Menambahkan validasi URL publik sebelum HTTP fetch:
  - hanya `http` dan `https`
  - blok `localhost`
  - blok IP loopback, private, link-local, multicast, reserved, dan unspecified
  - DNS host di-resolve dan semua hasil IP diperiksa
- Redirect tidak lagi di-follow otomatis. Redirect diproses manual maksimal `HAI_PUBLIC_FETCH_MAX_REDIRECTS` default `3`, dan setiap `Location` divalidasi ulang.
- Guard diterapkan ke:
  - `handle_webpage_command`
  - arXiv fetch
  - fetch teks dari hasil DuckDuckGo/search
- Ditambahkan `scripts/hai_url_safety_qa.py` untuk local QA guard URL.

## Acceptance

- URL publik seperti `https://hai.harmonika.id/healthz` tetap valid.
- `127.0.0.1`, `localhost`, `::1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, dan `169.254.169.254` ditolak.
- Redirect menuju URL internal juga ditolak karena setiap redirect divalidasi ulang.
