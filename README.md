# WebP Converter (lokal)

Ubah gambar format apa pun menjadi WebP, sepenuhnya offline di komputer sendiri.

## Cara pakai

**Web UI:** klik dua kali `start.bat`. Browser akan terbuka ke http://127.0.0.1:5000.
Seret file atau folder gambar ke halaman, atur kualitas, lalu unduh satu per satu atau semuanya sebagai ZIP.
Hasil juga tersimpan di folder `output/`.

**Command line:**
```
python converter.py foto.jpg                    # foto.webp di samping file asli
python converter.py D:\Foto -r -o D:\Foto_webp  # satu folder, termasuk subfolder
python converter.py gambar.png --lossless
python converter.py *.heic -q 75 --max-size 1920 --strip
python converter.py --formats                   # daftar format yang didukung
```

## Format yang didukung
JPG, PNG, GIF (animasi tetap beranimasi), APNG, BMP, TIFF, ICO, TGA, PSD, PPM, PCX, DDS, JPEG 2000,
AVIF, HEIC/HEIF (foto iPhone), WebP, dan lain-lain yang bisa dibuka Pillow.

Opsional:
- RAW kamera (CR2, NEF, ARW, DNG, ...): `pip install rawpy`
- SVG: `pip install cairosvg` (perlu library Cairo terpasang)

## Opsi
| Opsi | Keterangan |
|---|---|
| Kualitas (1-100) | Default 85. Makin kecil, makin kecil file. |
| Lossless | Tanpa kehilangan kualitas (cocok untuk logo/screenshot). |
| Sisi terpanjang maks. | Perkecil gambar, misalnya 1920 px. |
| Metadata | Simpan atau hapus EXIF dan profil warna. |

Rotasi dari EXIF otomatis diterapkan, transparansi dipertahankan, dan gambar di atas 16383 px
(batas WebP) otomatis diperkecil.
