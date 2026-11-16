"""Вынимает из SingleFile-HTML все data:-картинки в отдельные файлы,
а в HTML оставляет короткие метки IMG#N — чтобы разобрать текст страницы.

usage: python3 -I strip_images.py <in.html> <out_dir>
"""
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
img_dir = out / "imgs"
img_dir.mkdir(parents=True, exist_ok=True)

data = src.read_bytes()
print("bytes:", len(data))

EXT = {b"image/jpeg": "jpg", b"image/jpg": "jpg", b"image/png": "png", b"image/webp": "webp",
       b"image/gif": "gif", b"image/svg+xml": "svg", b"image/avif": "avif"}

pat = re.compile(rb'data:(image/[a-z0-9.+-]+)(;[a-z0-9=;-]*)?,([A-Za-z0-9+/=%_-]*)', re.I)
meta = []
seen = {}


def repl(m):
    mime = m.group(1).lower()
    params = (m.group(2) or b"").lower()
    payload = m.group(3)
    n = len(meta)
    try:
        raw = base64.b64decode(payload + b"=" * (-len(payload) % 4)) if b"base64" in params else payload
    except Exception:
        raw = payload
    h = hashlib.sha1(raw).hexdigest()[:16]
    if h in seen:
        ref = seen[h]
    else:
        ext = EXT.get(mime, "bin")
        fn = f"{n:05d}_{h}.{ext}"
        (img_dir / fn).write_bytes(raw)
        seen[h] = fn
        ref = fn
    meta.append({"n": n, "mime": mime.decode(), "bytes": len(raw), "file": ref, "offset": m.start()})
    return b"IMG#%d" % n


stripped = pat.sub(repl, data)
(out / "stripped.html").write_bytes(stripped)
(out / "images.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
by_mime = {}
for x in meta:
    by_mime.setdefault(x["mime"], [0, 0])
    by_mime[x["mime"]][0] += 1
    by_mime[x["mime"]][1] += x["bytes"]
print("data-uris:", len(meta), "unique files:", len(seen))
for k, (c, b) in sorted(by_mime.items(), key=lambda kv: -kv[1][1]):
    print(f"  {k:16} {c:6d} uris  {b/1e6:8.1f} MB")
print("stripped html bytes:", len(stripped))
