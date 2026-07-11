"""
vscode_controller.py
Talks to VS Code using its command-line tool ("code").
This is what actually opens folders/files in VS Code, or closes it.
"""

import subprocess
import platform
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils.logger import log_action


def open_in_vscode(path: str):
    """
    Opens a folder or file in VS Code.
    Uses the 'code' CLI command that VS Code installs automatically.
    """
    try:
        subprocess.run(["code", path], shell=True, check=True)
        log_action(f"Opened in VS Code: {path}")
        return True
    except FileNotFoundError:
        log_action("ERROR: 'code' command not found. VS Code CLI is not set up (see Step 4 checkpoint note).")
        return False
    except subprocess.CalledProcessError as e:
        log_action(f"ERROR opening {path} in VS Code: {e}")
        return False


def close_vscode():
    """
    Closes all running VS Code windows.
    Windows only, uses taskkill. (We'll add Mac/Linux support later if needed.)
    """
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["taskkill", "/IM", "Code.exe", "/F"], check=True)
        elif system == "Darwin":
            subprocess.run(["pkill", "-f", "Visual Studio Code"], check=True)
        else:
            subprocess.run(["pkill", "-f", "code"], check=True)
        log_action("Closed VS Code.")
        return True
    except subprocess.CalledProcessError:
        log_action("VS Code was not running, or could not be closed.")
        return False


if __name__ == "__main__":
    # Standalone test — this will actually try to open VS Code with your current folder
    print("Testing: opening current folder in VS Code...")
    result = open_in_vscode(".")
    if result:
        print("\nSUCCESS: VS Code should have opened just now. If it did, vscode_controller.py works.")
    else:
        print("\nFAILED: Check the error above. Most likely fix: open VS Code manually, "
              "press Ctrl+Shift+P, type 'Shell Command: Install code command in PATH', run it, "
              "then restart Command Prompt and try again.")
