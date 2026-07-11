"""
file_locator.py
Given a spoken name like "machine learning folder", searches your configured
root directories and finds the best matching real folder/file on disk.
Uses fuzzy matching so slightly wrong pronunciation still works.
If multiple good matches exist, returns all of them so the caller can ask
"did you mean X or Y?" instead of guessing wrong.
"""

import os
import json
import sys
from fuzzywuzzy import fuzz

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log_action

with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

ROOT_DIRS = CONFIG["root_directories"]
THRESHOLD = CONFIG["fuzzy_match_threshold"]


def _walk_all_entries():
    """Yields every file and folder path under all configured root directories."""
    for root_dir in ROOT_DIRS:
        if not os.path.exists(root_dir):
            continue
        for current_root, dirs, files in os.walk(root_dir):
            for d in dirs:
                yield os.path.join(current_root, d)
            for f in files:
                yield os.path.join(current_root, f)


def find_matches(spoken_name: str, only_folders: bool = False, only_files: bool = False):
    """
    Returns a list of (path, score) tuples sorted by best match first.
    Only returns matches at or above the configured fuzzy threshold.
    """
    spoken_name = spoken_name.lower().strip()
    results = []

    for path in _walk_all_entries():
        name = os.path.basename(path).lower()
        # strip extension for comparison so "example" matches "example.py"
        name_no_ext = os.path.splitext(name)[0]

        if only_folders and not os.path.isdir(path):
            continue
        if only_files and not os.path.isfile(path):
            continue

        score = max(fuzz.ratio(spoken_name, name), fuzz.ratio(spoken_name, name_no_ext))
        if score >= THRESHOLD:
            results.append((path, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def resolve_target(spoken_name: str, only_folders: bool = False, only_files: bool = False):
    """
    High-level function the rest of the app should call.
    Returns one of three outcomes as a dict:
      {"status": "found", "path": "..."}                -> exactly one clear match
      {"status": "ambiguous", "options": [paths...]}      -> multiple good matches, need to ask user
      {"status": "not_found"}                             -> nothing matched
    """
    matches = find_matches(spoken_name, only_folders, only_files)

    if not matches:
        log_action(f"No match found for: '{spoken_name}'")
        return {"status": "not_found"}

    # If the top match is clearly better than the next one, treat it as certain
    if len(matches) == 1 or (matches[0][1] - matches[1][1] >= 15):
        log_action(f"Resolved '{spoken_name}' -> {matches[0][0]} (score {matches[0][1]})")
        return {"status": "found", "path": matches[0][0]}

    # Otherwise there's real ambiguity — return top options for clarification
    top_options = [m[0] for m in matches[:3]]
    log_action(f"Ambiguous match for '{spoken_name}': {top_options}")
    return {"status": "ambiguous", "options": top_options}


if __name__ == "__main__":
    print("NOTE: This test will only find real results if your config.json 'root_directories' "
          "point to real folders on YOUR laptop with actual files/folders inside them.\n")

    test_query = input("Type a folder/file name to search for (e.g. 'machine learning'): ")
    result = resolve_target(test_query)
    print("\nResult:", result)
    print("\nIf status is 'found' with a real path, or 'ambiguous' with multiple real paths, "
          "file_locator.py works correctly. 'not_found' just means no match existed — "
          "try a name you know exists in your root_directories.")
