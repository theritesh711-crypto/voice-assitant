"""
utils/config.py
Loads settings from config.json at the project root, so you can tweak
the wake word, timeouts, and TTS voice settings WITHOUT touching code.

If config.json is missing, this creates one with sensible defaults
automatically the first time you run the assistant.
"""

import json
import os

DEFAULT_CONFIG = {
    "wake_word": "rakesh",
    "listen_timeout": 8,
    "confirm_timeout": 6,
    "tts_rate": 175,
    "tts_volume": 1.0,
}

# utils/config.py -> go up one folder to reach the project root
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config.json",
)


def _load():
    if not os.path.exists(CONFIG_PATH):
        _save(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print("Warning: config.json is malformed, using defaults.")
            data = {}

    # Merge with defaults so a missing key never crashes the app —
    # e.g. if you add a new setting later but forget to update old configs.
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    return merged


def _save(data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# Loaded once at import time and shared everywhere via `from utils.config import config`
config = _load()


if __name__ == "__main__":
    print("Loaded config:")
    print(json.dumps(config, indent=2))
    print(f"\nReading from: {CONFIG_PATH}")