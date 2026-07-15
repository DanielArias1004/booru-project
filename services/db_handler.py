# Connects to SQLite, handles all SQLite operations, CRUD for images, tags, notes
    # database initialization -> makes sure db file is created when app first runs
    # functions for images and tags and notes

import sqlite3
import os
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "booru.db")

@contextmanager
def get_db():
    """Yield a connected, auto-committing, auto-closing SQLite connection."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    """initialize the SQLite database if it doesn't exist"""
    # create db folder if it doesnt exist
    # shouldnt this be in the db folder

    # if you want to move the stuff to schema.sql use this code block here instead
    """
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    with get_db() as conn:
        conn.executescript(schema)
    """

    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

    # connect to the database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get current schema version (default 0)
    cur.execute("PRAGMA user_version;")
    current_version = cur.fetchone()[0]

    # create the necessary tables (images, tags, image_tags, etc.)
    # === Version 1: initial schema ===
    if current_version < 1:
        with open(schema_path) as f:
            conn.executescript(f.read())
        cur.execute("PRAGMA user_version = 1;") # Set schema version to 1
        conn.commit()

    # === Version 2: ===
    if current_version < 2:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS folders_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_folder TEXT NOT NULL,
                path TEXT NOT NULL,
                UNIQUE(base_folder, path)
            );
        """)
        cur.execute("""
            INSERT OR IGNORE INTO folders_new (base_folder, path)
            SELECT base_folder, path FROM folders;
        """)
        cur.execute("DROP TABLE IF EXISTS folders;")
        cur.execute("ALTER TABLE folders_new RENAME TO folders;")
        cur.execute("PRAGMA user_version = 2;")
        conn.commit()

    conn.close()

def make_relative_path(full_path, base_path):
    return os.path.relpath(full_path, base_path) # return a relative path to full_path either from curr directory or from an optional start dir (base_path)
    # wont confimr existence or nature of path or start, on windows tou will get a valueerror when path and start are on different drives

def make_absolute_path(relative_path, base_path):
    return os.path.normpath(os.path.join(base_path, relative_path)) # normpath collapses redundant separators and converts clashes
    # use normcase for normalizing case. join will concatenate the two paths

def add_image(file_path: str) -> None:
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO images (file_path) VALUES (?);",
                (file_path,)
            )
    except Exception:
        logger.exception(f"Failed to add image {file_path} to database.")
    # you need to convert the rest of these functions below to use get_db() context manager for consistency and error handling

def add_images_batch(file_paths: list[str]) -> None:
    """Insert many image paths in a single transaction — much faster than one-by-one."""
    if not file_paths:
        return
    try:
        with get_db() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO images (file_path) VALUES (?);",
                [(p,) for p in file_paths]
            )
    except Exception:
        logger.exception("Failed to batch-insert %d images", len(file_paths))

def set_favorite(image_id, is_favorite=True):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "UPDATE images SET favorite = ? WHERE id = ?;",
        (1 if is_favorite else 0, image_id)
    )
    conn.commit()
    conn.close()


def get_favorites():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, file_path FROM images WHERE favorite = 1;"
    )
    results = cur.fetchall()
    conn.close()
    return results


def add_note(image_id, content, created_at):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Remove existing notes for simplicity
    cur.execute("DELETE FROM notes WHERE image_id = ?;", (image_id,))
    cur.execute(
        "INSERT INTO notes (image_id, content, created_at) VALUES (?, ?, ?);",
        (image_id, content, created_at)
    )
    conn.commit()
    conn.close()


def get_latest_note(image_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT content FROM notes WHERE image_id = ? ORDER BY created_at DESC LIMIT 1;",
        (image_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ''


def add_folder(base_folder: str, relative_path: str) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO folders (base_folder, path) VALUES (?, ?);",
            (base_folder, relative_path)
        )

def remove_folder(base_folder: str, relative_path: str) -> None:
    with get_db() as conn:
        conn.execute(
            "DELETE FROM folders WHERE base_folder = ? AND path = ?;",
            (base_folder, relative_path)
        )

def get_folders() -> list[tuple[str, str]]:
    """Returns list of (base_folder, relative_path) tuples."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT base_folder, path FROM folders;"
        ).fetchall()
    return [(r[0], r[1]) for r in rows]

def add_tag(name, tag_type=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO tags (name, type) VALUES (?, ?);",
        (name, tag_type)
    )
    conn.commit()
    conn.close()

def get_all_tags():
    """
    Returns a dictionary of tags grouped by tag type.
    {
        'artist': ['tag1', 'tag2'],
        'character': ['tag3'],
        ...
    }
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT type, name FROM tags")
    rows = cur.fetchall()
    conn.close()

    tag_dict = {}
    for tag_type, name in rows:
        tag_dict.setdefault(tag_type, []).append(name)
    return tag_dict


def add_alias(tag_id, alias_name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO tag_aliases (tag_id, alias_name) VALUES (?, ?);",
        (tag_id, alias_name)
    )
    conn.commit()
    conn.close()


def add_tag_to_image(image_id, tag_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?);",
        (image_id, tag_id)
    )
    conn.commit()
    conn.close()


def get_image_id_by_path(file_path: str) -> int | None:
    """Return the DB id for an image by its file path, or None if not found."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM images WHERE file_path = ?;", (file_path,)
        ).fetchone()
    return row[0] if row else None

# --- Tag functions ---

def get_tags_for_image(image_id: int) -> list[dict]:
    """Return all tags for an image as list of {id, name, type}."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t.id, t.name, t.type
            FROM tags t
            JOIN image_tags it ON it.tag_id = t.id
            WHERE it.image_id = ?
            ORDER BY t.type, t.name
        """, (image_id,)).fetchall()
    return [{"id": r[0], "name": r[1], "type": r[2]} for r in rows]


def get_or_create_tag(name: str, tag_type: str) -> int:
    """Get existing tag id or create it. Returns tag id."""
    name = name.strip().lower()
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM tags WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row[0]
        cur = conn.execute(
            "INSERT INTO tags (name, type) VALUES (?, ?)", (name, tag_type)
        )
        return cur.lastrowid


def add_tag_to_image(image_id: int, tag_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
            (image_id, tag_id)
        )


def remove_tag_from_image(image_id: int, tag_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "DELETE FROM image_tags WHERE image_id = ? AND tag_id = ?",
            (image_id, tag_id)
        )


def get_all_tags_with_counts() -> list[dict]:
    """Return all tags with how many images use each one."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT t.id, t.name, t.type, COUNT(it.image_id) as count
            FROM tags t
            LEFT JOIN image_tags it ON it.tag_id = t.id
            GROUP BY t.id
            ORDER BY count DESC, t.name
        """).fetchall()
    return [{"id": r[0], "name": r[1], "type": r[2], "count": r[3]} for r in rows]


def search_images_by_tags(tag_names: list[str]) -> list[str]:
    """Return file paths of images that have ALL the given tags."""
    if not tag_names:
        return []
    tag_names = [t.strip().lower() for t in tag_names]
    placeholders = ",".join("?" * len(tag_names))
    with get_db() as conn:
        rows = conn.execute(f"""
            SELECT i.file_path
            FROM images i
            JOIN image_tags it ON it.image_id = i.id
            JOIN tags t ON t.id = it.tag_id
            WHERE t.name IN ({placeholders})
            GROUP BY i.id
            HAVING COUNT(DISTINCT t.name) = ?
            ORDER BY i.file_path
        """, (*tag_names, len(tag_names))).fetchall()
    return [r[0] for r in rows]


def set_favorite(image_id: int, is_favorite: bool) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE images SET favorite = ? WHERE id = ?",
            (1 if is_favorite else 0, image_id)
        )


def get_favorite(image_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT favorite FROM images WHERE id = ?", (image_id,)
        ).fetchone()
    return bool(row[0]) if row else False


def get_image_tags_autocomplete(prefix: str) -> list[str]:
    """Return tag names starting with prefix for autocomplete."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name FROM tags WHERE name LIKE ? ORDER BY name LIMIT 20",
            (prefix + "%",)
        ).fetchall()
    return [r[0] for r in rows]

# Additional DB functions (e.g., queries) can be added here