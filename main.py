"""
main.py
The control loop that ties everything together:
  wake word -> listen for command -> parse intent -> resolve file target
  -> confirm if destructive -> execute -> speak result

Mic listening runs in a background thread so long actions (VS Code opening,
large file moves) never freeze voice input. The tray icon runs on the
MAIN thread and gives the user a way to see status / pause / quit.
"""

import threading
import os
import sys

sys.path.append(os.path.dirname(__file__))

from core.listener import listen_once, wait_for_wake_word
from core.speaker import speak, repeat_heard_text
from core.intent_parser import parse_command
from core.file_locator import resolve_target
from core.tray import run_tray, state as tray_state
from actions.vscode_controller import open_in_vscode, close_vscode
from actions.file_operations import create_file, create_folder, delete_path, move_path
from actions.confirmation_handler import is_confirmation_yes, is_confirmation_no
from utils.logger import log_action
from utils.history import get_last_action, pop_last_action, add_history
from utils.config import config


def resolve_or_clarify(target_name: str, only_folders=False, only_files=False):
    """
    Resolves a spoken target name to a real path.
    If ambiguous, asks the user to pick between options out loud.
    Returns a real path string, or None if it couldn't be resolved.
    """
    result = resolve_target(target_name, only_folders, only_files)

    if result["status"] == "found":
        return result["path"]

    if result["status"] == "not_found":
        speak(f"I couldn't find anything matching {target_name}.")
        return None

    if result["status"] == "ambiguous":
        options = result["options"]
        names = [os.path.basename(o) for o in options]
        speak(f"I found multiple matches: {', '.join(names)}. Which one did you mean?")
        choice_text = listen_once(timeout=8)
        if not choice_text:
            speak("I didn't catch that, cancelling.")
            return None
        for path, name in zip(options, names):
            if name.lower() in choice_text:
                return path
        speak("That didn't match any of the options, cancelling.")
        return None


def perform_undo(last_action: dict) -> bool:
    """
    Attempts to reverse the given history entry.
    Returns True if the undo actually succeeded, False otherwise.

    Supported: create_file, create_folder, move
    Not supported yet: delete (see note below)
    """
    action_type = last_action["action_type"]
    details = last_action["details"]

    if action_type in ("create_file", "create_folder"):
        target_path = details.get("path")
        if not target_path or not os.path.exists(target_path):
            return False
        try:
            if os.path.isdir(target_path):
                os.rmdir(target_path)  # only removes if EMPTY — safe default,
                                        # won't nuke a folder you've since filled
            else:
                os.remove(target_path)
            return True
        except Exception as e:
            log_action(f"Undo failed for {action_type} at {target_path}: {e}")
            return False

    if action_type == "move":
        moved_to = details.get("destination")
        original_source = details.get("source")
        if not moved_to or not original_source or not os.path.exists(moved_to):
            return False
        try:
            move_path(moved_to, os.path.dirname(original_source))
            return True
        except Exception as e:
            log_action(f"Undo failed for move: {e}")
            return False

    if action_type == "delete":
        # Deletes go through send2trash, so the file is in the Recycle
        # Bin, not gone. Auto-restoring it needs extra Windows APIs
        # (winshell / pywin32 shell operations) we haven't wired up —
        # for now, point the user at the Recycle Bin instead of
        # pretending we restored it.
        speak("Deleted items go to your Recycle Bin, not gone forever — "
              "you can restore that one manually from there.")
        log_action(f"Undo requested for delete of {details.get('path')} "
                    "— pointed user to Recycle Bin (not auto-restorable yet).")
        return False

    log_action(f"Undo requested for unsupported action type: {action_type}")
    return False


def handle_command(text: str):
    print("=" * 50)
    print("DEBUG - Spoken text:", text)

    parsed = parse_command(text)
    print("DEBUG - Parsed command:", parsed)

    intent = parsed.get("intent")
    print("DEBUG - Intent:", intent)

    # --- Sleep / wake are checked BEFORE the pause gate below, since
    # they're the only commands that should still work while paused. ---
    if intent == "sleep":
        tray_state.paused = True
        speak("Going to sleep. Say the wake word, then wake up, to resume.")
        return

    if intent == "wake":
        tray_state.paused = False
        speak("I'm back and listening.")
        return

    if tray_state.paused:
        speak("I'm paused right now. Say wake up to resume.")
        return
    elif intent == "shutdown":
        speak("Byeee.")

        log_action("Assistant shutdown requested by voice.")

        # Stop the background listening loop
        tray_state.running = False

        # Close the tray icon
        try:
            tray_state.icon.stop()
        except Exception:
            pass

        return

    if intent == "open_in_vscode":
        path = resolve_or_clarify(parsed["target"])
        if path:
            open_in_vscode(path)
            speak(f"Opened {os.path.basename(path)} in VS Code.")

    elif intent == "close_vscode":
        close_vscode()
        speak("Closed VS Code.")

    elif intent == "delete":
        target_name = parsed["target"]
        path = resolve_or_clarify(target_name)
        if not path:
            return
        speak(f"Are you sure you want to delete {os.path.basename(path)}? Say yes to confirm.")
        response = listen_once(timeout=config["confirm_timeout"])
        if response and is_confirmation_yes(response):
            delete_path(path)
            add_history("delete", {"path": path})
            speak(f"Deleted {os.path.basename(path)}.")
        else:
            speak("Cancelled. Nothing was deleted.")
            log_action(f"Delete cancelled by user for: {path}")

    elif intent == "move":
        source_path = resolve_or_clarify(parsed["target"])
        if not source_path:
            return
        dest_path = resolve_or_clarify(parsed["destination"], only_folders=True)
        if not dest_path:
            return

        # NEW: confirmation step, same pattern as delete — a misheard
        # move command used to execute instantly with no safety net.
        speak(f"Move {os.path.basename(source_path)} to {os.path.basename(dest_path)}? Say yes to confirm.")
        response = listen_once(timeout=config["confirm_timeout"])
        if response and is_confirmation_yes(response):
            final_path = os.path.join(dest_path, os.path.basename(source_path))
            move_path(source_path, dest_path)
            add_history("move", {"source": source_path, "destination": final_path})
            speak(f"Moved {os.path.basename(source_path)} to {os.path.basename(dest_path)}.")
        else:
            speak("Cancelled. Nothing was moved.")
            log_action(f"Move cancelled by user for: {source_path}")

    elif intent == "create_file":
        location = parsed.get("location")
        base_dir = resolve_or_clarify(location, only_folders=True) if location else "."
        if base_dir:
            new_path = os.path.join(base_dir, parsed["target"])
            create_file(new_path)
            add_history("create_file", {"path": new_path})
            speak(f"Created file {parsed['target']}.")

    elif intent == "create_folder":
        location = parsed.get("location")
        base_dir = resolve_or_clarify(location, only_folders=True) if location else "."
        if base_dir:
            new_path = os.path.join(base_dir, parsed["target"])
            create_folder(new_path)
            add_history("create_folder", {"path": new_path})
            speak(f"Created folder {parsed['target']}.")

    elif intent == "undo":
        last = get_last_action()
        if not last:
            speak("There's nothing to undo.")
        else:
            if perform_undo(last):
                pop_last_action()
                speak(f"Undid the last action: {last['action_type'].replace('_', ' ')}.")
            elif last["action_type"] != "delete":
                # delete's failure path already spoke its own message above
                speak("I couldn't undo that automatically. It may have already changed.")

    else:
        speak("Sorry, I didn't understand that command.")


def assistant_loop():
    print("STEP 1")
    speak("Voice assistant started.")
    print("STEP 2")

    while tray_state.running:
        print("STEP 3")
        wait_for_wake_word()

        if not tray_state.running:
            break

        print("STEP 4")
        speak("I'm listening.")

        command = listen_once(timeout=config["listen_timeout"])
        print("Command:", command)

        repeat_heard_text(command)

        if not command:
            speak("I didn't catch that.")
            continue

        # Any bug inside handle_command used to kill this ENTIRE background
        # thread silently (that's what happened with the earlier NameError).
        # Now it's caught, logged, spoken, and the loop keeps running.
        try:
            handle_command(command)
        except Exception as e:
            print("ERROR in handle_command:", e)
            log_action(f"Error handling command '{command}': {e}")
            speak("Something went wrong with that command.")


if __name__ == "__main__":
    listener_thread = threading.Thread(
        target=assistant_loop,
        daemon=True
    )
    listener_thread.start()

    print("Assistant is running. Tray icon starting...")

    # run_tray() blocks the main thread and owns the tray icon's event
    # loop. Clicking "Quit" in the tray menu sets tray_state.running =
    # False and returns, letting us exit cleanly below.
    run_tray()

    print("\nTray closed. Shutting down assistant.")