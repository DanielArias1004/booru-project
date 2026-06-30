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

    # connect to the database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get current schema version (default 0)
    cur.execute("PRAGMA user_version;")
    current_version = cur.fetchone()[0]

    # create the necessary tables (images, tags, image_tags, etc.)
    # === Version 1: initial schema ===
    if current_version < 1:
        # Create images table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            rotation INTEGER DEFAULT 0,
            last_viewed TEXT,
            favorite INTEGER DEFAULT 0
        );
        """)

        # Create notes table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            content TEXT,
            created_at TEXT,
            FOREIGN KEY (image_id) REFERENCES images(id)
        );
        """)

        # Create tags table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            type TEXT
        );
        """)

        # Create tag_aliases table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tag_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_id INTEGER NOT NULL,
            alias_name TEXT UNIQUE NOT NULL,
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        );
        """)

        # Create image_tags table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS image_tags (
            image_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (image_id, tag_id),
            FOREIGN KEY (image_id) REFERENCES images(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        );
        """)

        # Create pools table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS pools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT
        );
        """)

        # Create pool_images table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS pool_images (
            pool_id INTEGER NOT NULL,
            image_id INTEGER NOT NULL,
            position INTEGER,
            PRIMARY KEY (pool_id, image_id),
            FOREIGN KEY (pool_id) REFERENCES pools(id),
            FOREIGN KEY (image_id) REFERENCES images(id)
        );
        """)


        # Create folders table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL
        );
        """)

        # Set schema version to 1
        cur.execute("PRAGMA user_version = 1;") # schema versioning
        conn.commit()

    # Future migration blocks go here (v2, v3, ...)

    # INDEXES FOR PERFORMANCE

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


def add_folder(relative_path):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO folders (path) VALUES (?);",
        (relative_path,)
    )
    conn.commit()
    conn.close()

def remove_folder(relative_path: str) -> None:
    """Remove a saved folder from the DB by its relative path."""
    with get_db() as conn:
        conn.execute("DELETE FROM folders WHERE path = ?;", (relative_path,))

def get_folders():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT path FROM folders;")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

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

# Additional DB functions (e.g., queries) can be added here