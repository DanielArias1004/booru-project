# services/image_loader.py
import os
from services.db_handler import add_images_batch

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff'}


def _is_image(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS


def load_images_from_folder(folder_path: str, recursive: bool = False) -> list[str]:
    """List images in folder_path (optionally including subfolders), register them in the DB,
    and return sorted absolute paths."""
    found = []
    if recursive:
        for dirpath, _dirs, files in os.walk(folder_path):
            found.extend(os.path.normpath(os.path.join(dirpath, f)) for f in files if _is_image(f))
    else:
        with os.scandir(folder_path) as it:
            found.extend(os.path.normpath(e.path) for e in it if e.is_file() and _is_image(e.name))
    found.sort()
    add_images_batch(found)
    return found