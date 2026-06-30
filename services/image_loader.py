# Scans for .jpg, .png, etc. and imports images from folder. Adds to DB if new

import os
import glob # for path navigation
from services.db_handler import add_images_batch

# Supported image extensions
IMAGE_EXTENSIONS = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.gif', '*.bmp', '*.tiff']

def load_images_from_folder(folder_path: str, base_folder: str) -> list[str]: 
    """
    Scans the given folder (and subfolders) for image paths only (no decoding).
    Batches the new paths into the DB in a signle transaction, and returns absolute paths.
    """
    # take in folder_path (abs path of selected folder within base folder i.e. hncl) and base_folder (abs path of base folder i.e. saved art) so we can find and store relative paths in the DB for portability
    # ^ but base folder is already stored in the config file, so we can just get it from there instead of passing it in. but passing it in makes the function more flexible and testable, so maybe keep it that way.
    all_images = []
    for ext in IMAGE_EXTENSIONS:
        pattern = os.path.join(folder_path, '**', ext)
        found = glob.glob(pattern, recursive=True)
        all_images.extend(found)

    # Add to DB and return unique list
    unique_paths = sorted(set(all_images))
    rel_paths = [os.path.relpath(p, base_folder) for p in unique_paths] # list comprehension here is faster than using a for loop, and more pythonic. stores relative paths into a list.
    add_images_batch(rel_paths)  # store list in DB, one transaction for all new images (instead of a new transaction for every iteration of a for loop). we use relative paths for portability.

    return unique_paths  # return absolute paths for display in the UI