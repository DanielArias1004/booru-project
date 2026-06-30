# Scans for .jpg, .png, etc. and imports images from folder. Adds to DB if new

import os
import glob # for path navigation
from services.db_handler import add_image

# Supported image extensions
IMAGE_EXTENSIONS = ['*.jpg', '*.jpeg', '*.png', '*.webp', '*.gif', '*.bmp', '*.tiff']

def load_images_from_folder(folder_path: str, base_folder: str) -> list[str]: 
    """
    Scans the given folder (and subfolders) for images, adds each to the DB,
    and returns a list of all absolute image file paths found.
    """
    # take in folder_path (abs path of selected folder within base folder i.e. hncl) and base_folder (abs path of base folder i.e. saved art) so we can find and store relative paths in the DB for portability
    # ^ but base folder is already stored in the config file, so we can just get it from there instead of passing it in. but passing it in makes the function more flexible and testable, so maybe keep it that way.
    all_images = []
    for ext in IMAGE_EXTENSIONS:
        pattern = os.path.join(folder_path, '**', ext)
        found = glob.glob(pattern, recursive=True)
        all_images.extend(found)

    # Add to DB and return unique list
    unique_paths = set(all_images)
    for path in unique_paths:
        rel = os.path.relpath(path, base_folder)
        add_image(rel)  # store relative path in DB for portability

    return sorted(set(all_images)) # or return list(unique_paths)