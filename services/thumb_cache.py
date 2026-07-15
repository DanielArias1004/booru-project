# services/thumb_cache.py
import os
import hashlib
from PIL import Image

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "booru", "thumbs")
CACHE_SIZE = 256  # always cache at 256px regardless of display size


def get_cache_path(source_path: str) -> str:
    try:
        mtime = str(os.path.getmtime(source_path))
    except OSError:
        mtime = "0"
    key = f"{source_path}:{mtime}"
    digest = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, digest + ".jpg")


def get_or_create_thumbnail(source_path: str, display_size: int) -> str | None:
    """
    Returns path to a cached square thumbnail, creating it if missing.
    Always generates at CACHE_SIZE (256px) for quality.
    Safe to call from background threads — Pillow releases the GIL.
    """
    cache_path = get_cache_path(source_path)
    if os.path.exists(cache_path):
        return cache_path

    os.makedirs(CACHE_DIR, exist_ok=True)

    try:
        with Image.open(source_path) as img:
            # handle palette/RGBA modes
            img = img.convert("RGB")
            w, h = img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            img = img.crop((left, top, left + side, top + side))
            img = img.resize((CACHE_SIZE, CACHE_SIZE), Image.LANCZOS)
            img.save(cache_path, "JPEG", quality=85, optimize=True)
        return cache_path
    except Exception:
        return None