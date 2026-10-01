"""Core konversi gambar -> WebP, bisa juga dipakai langsung dari command line.

Contoh:
    python converter.py foto.jpg                     # hasil: foto.webp di folder yang sama
    python converter.py folder_gambar -r -o hasil    # semua gambar di folder (rekursif)
    python converter.py *.png -q 90 --lossless
"""

import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence

# HEIC/HEIF (foto iPhone)
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

# RAW kamera (CR2, NEF, ARW, DNG, ...) — opsional: pip install rawpy
try:
    import rawpy
except ImportError:
    rawpy = None

# SVG — opsional: pip install cairosvg (butuh library Cairo)
try:
    import cairosvg
except (ImportError, OSError):
    cairosvg = None

Image.MAX_IMAGE_PIXELS = None  # izinkan gambar yang sangat besar

WEBP_MAX_DIM = 16383
RAW_EXTS = {".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef", ".srw"}
SVG_EXTS = {".svg", ".svgz"}


def supported_extensions():
    exts = {ext.lower() for ext, fmt in Image.registered_extensions().items() if fmt in Image.OPEN}
    if rawpy:
        exts |= RAW_EXTS
    if cairosvg:
        exts |= SVG_EXTS
    return sorted(exts)


def _open(data, filename):
    ext = Path(filename).suffix.lower()
    if ext in RAW_EXTS and rawpy:
        with rawpy.imread(io.BytesIO(data)) as raw:
            return Image.fromarray(raw.postprocess(use_camera_wb=True))
    if ext in SVG_EXTS and cairosvg:
        return Image.open(io.BytesIO(cairosvg.svg2png(bytestring=data)))
    return Image.open(io.BytesIO(data))


def _normalize(frame):
    """Ubah mode warna apa pun menjadi RGB/RGBA yang didukung WebP."""
    if frame.mode in ("I", "I;16", "I;16B", "I;16L", "I;16N"):
        frame = frame.point(lambda v: v / 256).convert("L")
    elif frame.mode == "F":
        frame = frame.convert("L")

    has_alpha = frame.mode in ("RGBA", "LA", "PA") or (
        frame.mode == "P" and "transparency" in frame.info
    )
    return frame.convert("RGBA" if has_alpha else "RGB")


def _fit(frame, max_size):
    limit = min(max_size or WEBP_MAX_DIM, WEBP_MAX_DIM)
    if max(frame.size) > limit:
        frame = frame.copy()
        frame.thumbnail((limit, limit), Image.LANCZOS)
    return frame


def convert_bytes(data, filename, quality=85, lossless=False, max_size=None, keep_metadata=True):
    """Konversi isi file gambar (bytes) menjadi bytes WebP."""
    img = _open(data, filename)
    animated = getattr(img, "is_animated", False) and img.format in ("GIF", "PNG", "WEBP")

    save_opts = {"format": "WEBP", "quality": quality, "lossless": lossless, "method": 6}
    if keep_metadata:
        if img.info.get("icc_profile"):
            save_opts["icc_profile"] = img.info["icc_profile"]
        exif = Image.Exif()
        exif.load(img.getexif().tobytes())  # salinan, agar orientasi asli tetap terbaca exif_transpose
        if exif:
            exif.pop(0x0112, None)  # orientasi akan diterapkan langsung ke piksel
            save_opts["exif"] = exif.tobytes()

    out = io.BytesIO()
    if animated:
        frames, durations = [], []
        for frame in ImageSequence.Iterator(img):
            durations.append(frame.info.get("duration", img.info.get("duration", 100)))
            frames.append(_fit(_normalize(frame), max_size))
        frames[0].save(
            out,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=img.info.get("loop", 0),
            **save_opts,
        )
    else:
        frame = _fit(_normalize(ImageOps.exif_transpose(img)), max_size)
        frame.save(out, **save_opts)

    return out.getvalue()


def _collect(inputs, recursive):
    exts = set(supported_extensions())
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            pattern = "**/*" if recursive else "*"
            yield from (f for f in sorted(p.glob(pattern)) if f.is_file() and f.suffix.lower() in exts)
        elif p.is_file():
            yield p
        else:
            print(f"[lewati] tidak ditemukan: {item}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Konversi gambar format apa pun menjadi WebP.")
    ap.add_argument("inputs", nargs="+", help="file atau folder gambar")
    ap.add_argument("-o", "--output", help="folder hasil (default: di samping file asli)")
    ap.add_argument("-q", "--quality", type=int, default=85, help="kualitas 1-100 (default 85)")
    ap.add_argument("--lossless", action="store_true", help="kompresi lossless")
    ap.add_argument("--max-size", type=int, help="batasi sisi terpanjang (piksel)")
    ap.add_argument("--strip", action="store_true", help="hapus metadata EXIF/ICC")
    ap.add_argument("-r", "--recursive", action="store_true", help="cari ke subfolder")
    ap.add_argument("--formats", action="store_true", help="tampilkan ekstensi yang didukung")
    args = ap.parse_args()

    if args.formats:
        print(" ".join(supported_extensions()))
        return

    ok = fail = 0
    total_in = total_out = 0
    used = set()
    for src in _collect(args.inputs, args.recursive):
        dest_dir = Path(args.output) if args.output else src.parent
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / (src.stem + ".webp")
        # foto.jpg & foto.png -> foto.webp & foto_png.webp; jangan timpa file sumber
        if dest.resolve() in used or dest.resolve() == src.resolve():
            dest = dest_dir / f"{src.stem}_{src.suffix.lstrip('.').lower() or 'img'}.webp"
        used.add(dest.resolve())
        try:
            data = src.read_bytes()
            result = convert_bytes(data, src.name, args.quality, args.lossless, args.max_size, not args.strip)
            dest.write_bytes(result)
            ok += 1
            total_in += len(data)
            total_out += len(result)
            print(f"[ok] {src} -> {dest} ({len(data) / 1024:.0f} KB -> {len(result) / 1024:.0f} KB)")
        except Exception as e:
            fail += 1
            print(f"[gagal] {src}: {e}", file=sys.stderr)

    if ok:
        saved = (1 - total_out / total_in) * 100 if total_in else 0
        print(f"\nSelesai: {ok} berhasil, {fail} gagal. Hemat {saved:.1f}% ukuran.")
    elif not fail:
        print("Tidak ada gambar yang ditemukan.")


if __name__ == "__main__":
    main()
