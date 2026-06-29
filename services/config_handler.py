import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def get_base_folder():
    config = load_config()
    return config.get("base_folder", "")

def set_base_folder(path):
    config = load_config()
    config["base_folder"] = path
    save_config(config)
