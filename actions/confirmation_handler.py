"""
confirmation_handler.py
Sits in front of any destructive action (currently: delete).
Forces a "are you sure?" step before anything irreversible happens.
"""

import json
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

YES_WORDS = [w.lower() for w in CONFIG["confirmation_words_yes"]]
NO_WORDS = [w.lower() for w in CONFIG["confirmation_words_no"]]


def is_confirmation_yes(text: str) -> bool:
    text = text.lower().strip()
    return any(word in text for word in YES_WORDS)


def is_confirmation_no(text: str) -> bool:
    text = text.lower().strip()
    return any(word in text for word in NO_WORDS)


if __name__ == "__main__":
    # Standalone test — type responses manually to check the logic
    tests = ["yes", "yeah sure", "no thanks", "cancel", "do it", "maybe"]
    for t in tests:
        result = "YES" if is_confirmation_yes(t) else ("NO" if is_confirmation_no(t) else "UNCLEAR")
        print(f"Input: '{t}'  ->  Detected as: {result}")

    print("\nCheck above: 'yes','yeah sure','do it' should show YES. "
          "'no thanks','cancel' should show NO. 'maybe' should show UNCLEAR. "
          "If that matches, confirmation_handler.py works.")
