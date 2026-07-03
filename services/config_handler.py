import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r") as f:
        content = f.read().strip()
    if not content:
        # file exists but is empty — treat it as a fresh config
        return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # file is corrupt — log a warning and start fresh rather than crashing
        import logging
        logging.getLogger(__name__).warning(
            "config.json could not be parsed, starting with empty config"
        )
        return {}

def save_config(config) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def get_base_folders() -> list[str]:
    """Return all saved base folders."""
    config = load_config()
    return config.get("base_folders", [])

def add_base_folder(path: str) -> None:
    config = load_config()
    folders = config.get("base_folders", [])
    if path not in folders:
        folders.append(path)
    config["base_folders"] = folders
    save_config(config)

def remove_base_folder(path: str) -> None:
    config = load_config()
    folders = config.get("base_folders", [])
    if path in folders:
        folders.remove(path)
    config["base_folders"] = folders
    save_config(config)