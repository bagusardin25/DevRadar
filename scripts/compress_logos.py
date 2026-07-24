"""One-shot logo compression for public assets."""
from pathlib import Path

from PIL import Image

public = Path(__file__).resolve().parents[1] / "public"

for name, max_side in [("logomark.png", 128), ("logomark_text.png", 256)]:
    src = public / name
    if not src.exists():
        print("missing", src)
        continue
    img = Image.open(src)
    before = src.stat().st_size
    print(name, "before", before, "mode", img.mode, "size", img.size)
    w, h = img.size
    scale = min(1.0, max_side / max(w, h))
    if scale < 1.0:
        img = img.resize(
            (max(1, int(w * scale)), max(1, int(h * scale))),
            Image.Resampling.LANCZOS,
        )
    if img.mode not in ("RGBA", "RGB"):
        img = img.convert("RGBA")
    img.save(src, format="PNG", optimize=True)
    webp = public / name.replace(".png", ".webp")
    img.save(webp, format="WEBP", quality=82, method=6)
    print(
        name,
        "after png",
        src.stat().st_size,
        "webp",
        webp.stat().st_size,
        "size",
        img.size,
    )
