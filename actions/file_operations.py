"""
file_operations.py
Handles actually creating, deleting, and moving files/folders.
Deletion uses send2trash so files go to Recycle Bin, not permanent delete —
this is a safety net even after you've confirmed "yes".
"""

import os
import shutil
import sys
from send2trash import send2trash

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log_action
from utils.history import add_history


def create_file(path: str):
    try:
        if os.path.exists(path):
            log_action(f"File already exists, skipped: {path}")
            return False
        with open(path, "w", encoding="utf-8") as f:
            f.write("")
        add_history("create_file", {"path": path})
        log_action(f"Created file: {path}")
        return True
    except Exception as e:
        log_action(f"ERROR creating file {path}: {e}")
        return False


def create_folder(path: str):
    try:
        if os.path.exists(path):
            log_action(f"Folder already exists, skipped: {path}")
            return False
        os.makedirs(path)
        add_history("create_folder", {"path": path})
        log_action(f"Created folder: {path}")
        return True
    except Exception as e:
        log_action(f"ERROR creating folder {path}: {e}")
        return False


def delete_path(path: str):
    """
    Sends a file or folder to Recycle Bin (NOT permanent delete).
    Caller (confirmation_handler.py) is responsible for asking "are you sure?" first.
    """
    try:
        if not os.path.exists(path):
            log_action(f"Cannot delete — path does not exist: {path}")
            return False
        send2trash(path)
        add_history("delete", {"path": path})
        log_action(f"Deleted (sent to Recycle Bin): {path}")
        return True
    except Exception as e:
        log_action(f"ERROR deleting {path}: {e}")
        return False


def move_path(source: str, destination_folder: str):
    try:
        if not os.path.exists(source):
            log_action(f"Cannot move — source does not exist: {source}")
            return False
        if not os.path.exists(destination_folder):
            log_action(f"Cannot move — destination folder does not exist: {destination_folder}")
            return False
        new_path = shutil.move(source, destination_folder)
        add_history("move", {"from": source, "to": new_path})
        log_action(f"Moved {source} -> {new_path}")
        return True
    except Exception as e:
        log_action(f"ERROR moving {source} to {destination_folder}: {e}")
        return False


if __name__ == "__main__":
    # Standalone test using a temporary throwaway folder — safe to run, touches nothing real
    test_dir = "test_sandbox"
    os.makedirs(test_dir, exist_ok=True)

    print("1. Creating test file...")
    create_file(os.path.join(test_dir, "sample.txt"))

    print("2. Creating destination folder...")
    create_folder(os.path.join(test_dir, "moved_here"))

    print("3. Moving test file into destination folder...")
    move_path(os.path.join(test_dir, "sample.txt"), os.path.join(test_dir, "moved_here"))

    print("4. Deleting the whole test_sandbox folder (goes to Recycle Bin)...")
    delete_path(test_dir)

    print("\nIf you saw 4 log lines above with no ERROR, file_operations.py works correctly.")
