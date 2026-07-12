"""
config.py

Loads settings from config.json at the project root and exposes them
through a shared dictionary named `config`.

Features:
- Automatically creates config.json with sensible defaults if missing.
- Handles malformed JSON gracefully.
- Merges missing keys with defaults so older config files still work.
- Uses an absolute path, so it works no matter where Python is launched from.

Usage:
    from config import config

Example:
    wake_word = config["wake_word"]
"""

import json
import os

# -------------------------------------------------------------------
# Default configuration
# -------------------------------------------------------------------
DEFAULT_CONFIG = {
    "wake_word": "rakesh",
    "listen_timeout": 8,
    "confirm_timeout": 6,

    "tts_engine": "pyttsx3",
    "piper_model_path": "models/en_GB-alan-medium.onnx",

    "tts_rate": 175,
    "tts_volume": 1.0,
}

# -------------------------------------------------------------------
# Path to config.json (project root)
# -------------------------------------------------------------------

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "config.json",
)

# -------------------------------------------------------------------
# Save configuration
# -------------------------------------------------------------------


def _save(data):
    """Write configuration to config.json."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# -------------------------------------------------------------------
# Load configuration
# -------------------------------------------------------------------


def _load():
    """
    Load config.json.

    If the file doesn't exist, create it using DEFAULT_CONFIG.
    Missing keys are automatically filled from DEFAULT_CONFIG.
    """

    if not os.path.exists(CONFIG_PATH):
        _save(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

    except json.JSONDecodeError:
        print("Warning: config.json is malformed. Using default configuration.")
        data = {}

    except Exception as e:
        print(f"Error reading config.json: {e}")
        data = {}

    # Merge existing config with defaults
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)

    # Save merged config back if new keys were added
    if merged != data:
        _save(merged)

    return merged


# -------------------------------------------------------------------
# Shared configuration dictionary
# -------------------------------------------------------------------

config = _load()

# -------------------------------------------------------------------
# Debug
# -------------------------------------------------------------------

if __name__ == "__main__":
    print("Configuration loaded successfully.\n")
    print(json.dumps(config, indent=2))
    print(f"\nConfig file location:\n{CONFIG_PATH}")