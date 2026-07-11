"""
intent_parser.py
Takes raw spoken text and figures out WHAT action the user wants
and WHAT the target (file/folder name) is, using pattern matching.

This is intentionally simple (regex/keywords) for v1 — reliable and free.
Can be upgraded later to a local LLM (Ollama) for more natural phrasing.
"""

import re


def parse_command(text: str) -> dict:
    """
    Returns a dict like:
      {"intent": "open_in_vscode", "target": "machine learning"}
      {"intent": "close_vscode"}
      {"intent": "delete", "target": "example.py", "location": "examples"}
      {"intent": "move", "target": "ex.py", "destination": "exp"}
      {"intent": "create_file", "target": "new.py", "location": "examples"}
      {"intent": "create_folder", "target": "new_folder", "location": "examples"}
      {"intent": "sleep"}
      {"intent": "wake"}
      {"intent": "undo"}
      {"intent": "shutdown"}
      {"intent": "unknown"}
    """
    text = text.lower().strip()

    # --- SHUTDOWN ---
    shutdown_phrases = [
        "shut down",
        "shutdown",
        "stop",
        "exit",
        "quit",
        "close",
        "goodbye",
        "bye"
    ]

    if any(phrase in text for phrase in shutdown_phrases):
        return {
            "intent": "shutdown"
        }

    # --- SLEEP / WAKE ---
    if re.search(r"\b(go to sleep|sleep now|stop listening)\b", text):
        return {"intent": "sleep"}

    if re.search(r"\b(wake up|wake now|start listening)\b", text):
        return {"intent": "wake"}

    # --- UNDO ---
    if re.search(r"\bundo\b", text):
        return {"intent": "undo"}

    # --- CLOSE VS CODE ---
    if re.search(r"\bclose (vs ?code|the editor)\b", text):
        return {"intent": "close_vscode"}

    # --- OPEN VS CODE ---
    if re.search(
        r"\b("
        r"open\s+vs\s*code|"
        r"open\s+vscode|"
        r"open\s+code|"
        r"launch\s+vs\s*code|"
        r"launch\s+code|"
        r"start\s+vs\s*code|"
        r"start\s+code|"
        r"run\s+vs\s*code|"
        r"run\s+code|"
        r"open\s+editor|"
        r"start\s+editor|"
        r"launch\s+editor|"
        r"vs\s*code|"
        r"vscode|"
        r"code"
        r")\b",
        text,
    ):
        return {"intent": "open_vscode"}

    # --- OPEN FOLDER/FILE IN VS CODE ---
    match = re.search(r"open (.+?)\s+(folder|file)?\s*in vs ?code", text)
    if match:
        target = match.group(1).strip()
        return {"intent": "open_in_vscode", "target": target}

    match = re.search(r"open (?:the )?(.+?)\s*(file|folder)?$", text)
    if match and "vs code" not in text:
        target = match.group(1).strip()
        return {"intent": "open_in_vscode", "target": target}

    # --- DELETE ---
    match = re.search(
        r"delete (.+?)\s*(file|folder)?\s*from (?:the )?(.+?)\s*(folder)?$",
        text,
    )
    if match:
        target = match.group(1).strip()
        location = match.group(3).strip()
        return {"intent": "delete", "target": target, "location": location}

    match = re.search(r"delete (.+?)\s*(file|folder)?$", text)
    if match:
        target = match.group(1).strip()
        return {"intent": "delete", "target": target, "location": None}

    # --- MOVE ---
    match = re.search(r"move (.+?)\s*(file|folder)?\s*to (.+?)\s*(folder)?$", text)
    if match:
        target = match.group(1).strip()
        destination = match.group(3).strip()
        return {"intent": "move", "target": target, "destination": destination}

    # --- CREATE FOLDER ---
    match = re.search(
        r"create (?:a )?(?:new )?folder(?: called| named)? (.+?)\s*(?:inside|in) (?:this|the )?(.+)?$",
        text,
    )
    if match:
        target = match.group(1).strip()
        location = match.group(2).strip() if match.group(2) else None
        return {"intent": "create_folder", "target": target, "location": location}

    match = re.search(r"create (?:a )?(?:new )?folder(?: called| named)? (.+)$", text)
    if match:
        target = match.group(1).strip()
        return {"intent": "create_folder", "target": target, "location": None}

    # --- CREATE FILE ---
    match = re.search(
        r"create (?:a )?(?:new )?file(?: called| named)? (.+?)\s*(?:inside|in) (?:this|the )?(.+)?$",
        text,
    )
    if match:
        target = match.group(1).strip()
        location = match.group(2).strip() if match.group(2) else None
        return {"intent": "create_file", "target": target, "location": location}

    match = re.search(r"create (?:a )?(?:new )?file(?: called| named)? (.+)$", text)
    if match:
        target = match.group(1).strip()
        return {"intent": "create_file", "target": target, "location": None}

    return {"intent": "unknown", "raw_text": text}


if __name__ == "__main__":
    test_commands = [
        "open machine learning folder in vs code",
        "open the first.txt file",
        "close vs code",
        "delete example.py file from the examples folder",
        "move ex.py file to exp folder",
        "create a new folder called utils inside this examples",
        "create a new file called notes.txt",
        "go to sleep",
        "wake up",
        "undo",
        "shutdown",
        "shut down",
        "stop",
        "exit",
        "quit",
        "close",
        "goodbye",
        "bye",
        "make me a sandwich",
        "open vs code",
        "open vscode",
        "open code",
        "launch vs code",
        "launch code",
        "start vs code",
        "start code",
        "run vs code",
        "run code",
        "open editor",
        "start editor",
        "launch editor",
        "vs code",
        "vscode",
        "code",
    ]

    print("Testing intent_parser.py against sample commands:\n")

    for cmd in test_commands:
        result = parse_command(cmd)
        print(f"Input: '{cmd}'")
        print(f"  -> {result}\n")

    print(
        "Check above: every command except 'make me a sandwich' should "
        "show a real intent (not 'unknown')."
    )