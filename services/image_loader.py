# Scans for .jpg, .png, etc. and imports images from folder. Adds to DB if new

import os
import glob
from services.db_handler import add_image

# Supported image extensions
IMAGE_EXTENSIONS = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.gif', '*.tiff']

def load_images_from_folder(folder_path):
    """
    Scans the given folder (and subfolders) for images, adds each to the DB,
    and returns a list of all image file paths found.
    """
    all_images = []
    for ext in IMAGE_EXTENSIONS:
        pattern = os.path.join(folder_path, '**', ext)
        found = glob.glob(pattern, recursive=True)
        all_images.extend(found)

    # Add to DB and return unique list
    unique_paths = set(all_images)
    for path in unique_paths:
        add_image(path)

    return list(unique_paths)