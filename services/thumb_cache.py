# services/thumb_cache.py
import hashlib
import logging
import os
import threading
from contextlib import nullcontext

from PIL import Image, ImageOps

# These are your own files, so disable Pillow's "decompression bomb" guard.
Image.MAX_IMAGE_PIXELS = None

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "booru", "thumbs")
CACHE_SIZE = 256

# Huge non-JPEG images can't be decoded at reduced size, so they use lots of RAM.
# Only let ONE of them decode at a time across all threads.
BIG_IMAGE_PIXELS = 30_000_000
_BIG_IMAGE_LOCK = threading.Lock()


def get_cache_path(source_path: str) -> str:
    try:
        mtime = str(os.path.getmtime(source_path))
    except OSError:
        mtime = "0"
    digest = hashlib.md5(f"{source_path}:{mtime}".encode()).hexdigest()
    return os.path.join(CACHE_DIR, digest + ".jpg")


def _to_rgb(img: Image.Image) -> Image.Image:
    """Convert to RGB. Transparent images get a dark background instead of black."""
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info
    )
    if has_alpha:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (26, 26, 26))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def get_or_create_thumbnail(source_path: str, display_size: int | None = None) -> str | None:
    """Return the path of a cached 256px square thumbnail, creating it if needed."""
    cache_path = get_cache_path(source_path)
    if os.path.exists(cache_path):
        return cache_path

    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp_path = f"{cache_path}.{threading.get_ident()}.tmp"
    try:
        with Image.open(source_path) as img:       # open() only reads the header
            is_huge = img.format != "JPEG" and img.width * img.height > BIG_IMAGE_PIXELS
            with (_BIG_IMAGE_LOCK if is_huge else nullcontext()):
                img.draft("RGB", (CACHE_SIZE * 2, CACHE_SIZE * 2))   # JPEG only: decode small
                thumb = ImageOps.fit(_to_rgb(img), (CACHE_SIZE, CACHE_SIZE), Image.LANCZOS)
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