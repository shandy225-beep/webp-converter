"""Web UI lokal untuk konversi gambar ke WebP. Jalankan: python app.py"""

import io
import threading
import webbrowser
import zipfile
from pathlib import Path

from PIL import UnidentifiedImageError
from flask import Flask, abort, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from converter import convert_bytes, supported_extensions

BASE = Path(__file__).parent
OUTPUT = BASE / "output"
OUTPUT.mkdir(exist_ok=True)
HOST, PORT = "127.0.0.1", 5000

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB per request

_lock = threading.Lock()


def _unique_name(stem):
    stem = secure_filename(stem) or "image"
    with _lock:
        name, i = f"{stem}.webp", 1
        while (OUTPUT / name).exists():
            name = f"{stem}_{i}.webp"
            i += 1
        (OUTPUT / name).touch()
    return name


@app.get("/")
def index():
    return send_from_directory(BASE / "static", "index.html")


@app.get("/api/formats")
def formats():
    return jsonify(supported_extensions())


@app.post("/api/convert")
def convert():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Tidak ada file."), 400

    quality = max(1, min(100, request.form.get("quality", 85, type=int)))
    lossless = request.form.get("lossless") == "true"
    keep_meta = request.form.get("keep_metadata", "true") == "true"
    max_size = request.form.get("max_size", type=int) or None

    data = f.read()
    try:
        result = convert_bytes(data, f.filename, quality, lossless, max_size, keep_meta)
    except UnidentifiedImageError:
        return jsonify(error="Bukan file gambar atau formatnya tidak didukung."), 422
    except Exception as e:
        return jsonify(error=f"Tidak bisa dikonversi: {e}"), 422

    name = _unique_name(Path(f.filename).stem)
    (OUTPUT / name).write_bytes(result)
    return jsonify(name=name, url=f"/output/{name}", in_size=len(data), out_size=len(result))


@app.get("/output/<path:name>")
def output_file(name):
    return send_from_directory(OUTPUT, name, as_attachment=request.args.get("dl") == "1")


@app.post("/api/zip")
def make_zip():
    names = (request.get_json(silent=True) or {}).get("names", [])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for n in names:
            p = OUTPUT / secure_filename(n)
            if p.is_file():
                z.write(p, p.name)
    if buf.tell() == 0:
        abort(404)
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name="webp_images.zip")


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"WebP Converter berjalan di {url}  (Ctrl+C untuk berhenti)")
    print(f"Hasil konversi juga disimpan di: {OUTPUT}")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host=HOST, port=PORT, debug=False)
