"""
utils/logger.py
Records every command and action the assistant takes, with a timestamp.

UPGRADE FROM v1: now uses Python's built-in RotatingFileHandler instead
of manually opening/writing the file each time. This means:
  - the log file auto-splits once it hits 1MB (activity_log.txt,
    activity_log.txt.1, activity_log.txt.2, ...)
  - it keeps the last 5 rotated files and deletes older ones automatically
  - so a background assistant running for weeks won't quietly grow one
    giant unreadable file, and you won't run out of disk space.

The public function signature (log_action) is UNCHANGED, so nothing
else in the project needs to change.
"""

import logging
from logging.handlers import RotatingFileHandler
import os

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "activity_log.txt")

os.makedirs(LOG_DIR, exist_ok=True)

_logger = logging.getLogger("voice_assistant")
_logger.setLevel(logging.INFO)

# Guard against adding duplicate handlers if this module gets imported
# more than once (can happen with certain thread/reload setups).
if not _logger.handlers:
    _formatter = logging.Formatter(
        fmt="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    _file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,   # 1 MB per file
        backupCount=5,        # keep 5 old files, then delete the oldest
        encoding="utf-8",
    )
    _file_handler.setFormatter(_formatter)
    _logger.addHandler(_file_handler)

    _console_handler = logging.StreamHandler()
    _console_handler.setFormatter(_formatter)
    _logger.addHandler(_console_handler)


def log_action(message: str):
    """Writes a timestamped line to the log file AND prints it to console."""
    _logger.info(message)


if __name__ == "__main__":
    log_action("Logger test: this line should appear in logs/activity_log.txt")
    print("\nIf you see the line above AND it also appears inside logs/activity_log.txt, logger.py works.")