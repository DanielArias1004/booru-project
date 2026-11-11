# services/thumb_cache.py
import hashlib
import logging
import os
import threading

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "booru", "thumbs")
CACHE_SIZE = 256  # always cache at 256px; the view scales it down


def get_cache_path(source_path: str) -> str:
    try:
        mtime = str(os.path.getmtime(source_path))
    except OSError:
        mtime = "0"
    digest = hashlib.md5(f"{source_path}:{mtime}".encode()).hexdigest()
    return os.path.join(CACHE_DIR, digest + ".jpg")


def get_or_create_thumbnail(source_path: str, display_size: int | None = None) -> str | None:
    """Return the path of a cached 256px square thumbnail, creating it if needed."""
    cache_path = get_cache_path(source_path)
    if os.path.exists(cache_path):
        return cache_path

    os.makedirs(CACHE_DIR, exist_ok=True)
    # write to a temp file, then rename, so other threads never read a half-written JPEG
    tmp_path = f"{cache_path}.{threading.get_ident()}.tmp"
    try:
        with Image.open(source_path) as img:
            img.draft("RGB", (CACHE_SIZE * 2, CACHE_SIZE * 2))  # JPEG: decode small (fast)
            thumb = ImageOps.fit(img.convert("RGB"), (CACHE_SIZE, CACHE_SIZE), Image.LANCZOS)
        thumb.save(tmp_path, "JPEG", quality=85)
        os.replace(tmp_path, cache_path)
        return cache_path
    except Exception:
        logger.exception("Could not make thumbnail for %s", source_path)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return None