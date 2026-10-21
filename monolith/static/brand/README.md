# Logo Hy+ Clinic

Upload file logo ke folder ini. Nama file yang disarankan:

| File | Isi | Ukuran |
|---|---|---|
| `logo.svg` atau `logo.png` | Logo lengkap (ikon + tulisan "Hy+ Clinic") | PNG minimal 1000 px lebar, latar transparan |
| `mark.svg` atau `mark.png` | Ikon saja (untuk favicon, ikon aplikasi di HP, kiosk) | PNG minimal 512 × 512 px, persegi |
| `logo-white.svg` / `logo-white.png` | (Opsional) versi putih untuk latar gelap | sama seperti logo |

Format terbaik: **SVG**. Kalau hanya ada PNG/JPG, tidak apa-apa.

Aset web (logo header, ikon aplikasi, favicon) dibuat dari file di sini dengan
`python3 scripts/brand_assets.py static/brand static/img static/icons`, lalu deploy ulang.
