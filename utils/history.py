"""
history.py
Keeps a record of recent actions so we can support "undo last action" later.
Stores things as a simple JSON list on disk so it survives restarts.
"""

import json
import os

HISTORY_FILE = "logs/history.json"


def _load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_history(history):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def add_history(action_type: str, details: dict):
    """
    Records an action so it can potentially be undone later.
    action_type examples: 'create_file', 'delete_file', 'move_file'
    details example: {'path': 'D:/Projects/example.py', 'moved_to': 'D:/Projects/exp'}
    """
    history = _load_history()
    history.append({"action_type": action_type, "details": details})
    # keep only the last 20 actions so the file doesn't grow forever
    history = history[-20:]
    _save_history(history)


def get_last_action():
    """Returns the most recent action, or None if there isn't one."""
    history = _load_history()
    if not history:
        return None
    return history[-1]


def pop_last_action():
    """Removes and returns the most recent action (used right after undoing it)."""
    history = _load_history()
    if not history:
        return None
    last = history.pop()
    _save_history(history)
    return last


if __name__ == "__main__":
    # Standalone test
    add_history("create_file", {"path": "D:/Projects/test_undo.txt"})
    last = get_last_action()
    print("Last recorded action:", last)
    print("\nIf you see a dictionary printed above with action_type 'create_file', history.py works.")
