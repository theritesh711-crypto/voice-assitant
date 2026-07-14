"""
intent_parser.py
Takes raw spoken text and figures out WHAT action the user wants
and WHAT the target (file/folder name) is.

Two-stage pipeline:
  1. Fast path: regex/keyword matching (instant, free, no dependencies).
  2. Fallback: if the fast path can't confidently classify the command,
     it's handed to a local Ollama model, which returns the same JSON
     shape. This stays fully offline — Ollama serves the model on
     localhost, nothing leaves the machine.

If Ollama isn't installed/running, or the model call fails/times out
for any reason, we quietly fall back to {"intent": "unknown", ...} —
exactly the old behavior — so a missing Ollama install never breaks
the assistant.
"""

import json
import re

import requests

# ---------------------------------------------------
# Ollama fallback settings
# ---------------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"          # change to whatever model you've pulled
OLLAMA_TIMEOUT_SECONDS = 30      # don't let a slow/offline Ollama hang the assistant

# Keep this in lockstep with the intents handle_command() in main.py knows
# how to act on — the LLM is instructed to only ever pick from this list.
VALID_INTENTS = [
    "open_in_vscode",
    "open_vscode",
    "close_vscode",
    "delete",
    "move",
    "create_file",
    "create_folder",
    "sleep",
    "wake",
    "undo",
    "shutdown",
    "unknown",
]

OLLAMA_SYSTEM_PROMPT = """You are a strict command classifier for a Windows voice assistant.

Given one spoken sentence, output ONLY a single-line JSON object (no markdown
fences, no explanation, no extra text) with this exact shape:

{"intent": "<one of the allowed intents>", "target": <string or null>, "location": <string or null>, "destination": <string or null>}

Allowed intents (pick exactly one):
- open_in_vscode   -> target = file/folder name to open
- open_vscode      -> no target, just opens the VS Code app
- close_vscode     -> no fields
- delete           -> target = file/folder name, location = containing folder name or null
- move             -> target = file/folder name, destination = folder name to move it into
- create_file      -> target = file name, location = containing folder name or null
- create_folder    -> target = folder name, location = containing folder name or null
- sleep            -> no fields (user wants the assistant to stop listening)
- wake             -> no fields (user wants the assistant to resume listening)
- undo             -> no fields
- shutdown         -> no fields (user wants to quit the assistant entirely)
- unknown          -> use this if the sentence genuinely doesn't match any of the above

Rules:
- Only use fields relevant to the chosen intent; set the rest to null.
- Never invent a target/location/destination that wasn't said or clearly implied.
- Output raw JSON only. No ```json fences. No commentary.
"""


def _parse_with_ollama(text: str) -> dict:
    """
    Fallback classifier. Sends the raw text to a local Ollama model and
    parses its JSON reply into the same dict shape parse_command()
    normally returns.

    Returns {"intent": "unknown", "raw_text": text} if Ollama is
    unreachable, times out, or replies with something unparsable —
    callers never need to special-case this function failing.
    """
    prompt = f"{OLLAMA_SYSTEM_PROMPT}\nSentence: \"{text}\"\nJSON:"

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"DEBUG - Ollama fallback unavailable ({e}); treating as unknown.")
        return {"intent": "unknown", "raw_text": text}

    raw_reply = response.json().get("response", "").strip()

    # Models sometimes wrap JSON in ```json ... ``` even when told not to —
    # strip that defensively before parsing.
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_reply, flags=re.MULTILINE).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"DEBUG - Ollama returned unparsable JSON: {raw_reply!r}")
        return {"intent": "unknown", "raw_text": text}

    intent = parsed.get("intent")
    if intent not in VALID_INTENTS:
        print(f"DEBUG - Ollama returned an unrecognized intent: {intent!r}")
        return {"intent": "unknown", "raw_text": text}

    # Trim null/empty fields so the returned dict matches the shape the
    # regex path produces (no stray None-valued keys for simple intents).
    result = {"intent": intent}
    for field in ("target", "location", "destination"):
        value = parsed.get(field)
        if value:
            result[field] = value

    print(f"DEBUG - Ollama fallback classified '{text}' -> {result}")
    return result


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

    Tries fast regex/keyword matching first. Only if that can't classify
    the sentence does it fall back to a local Ollama model (see
    _parse_with_ollama above).
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

    # --- FALLBACK: regex couldn't classify it, try the local LLM ---
    return _parse_with_ollama(text)


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
        # These are phrased naturally enough that the regex fast-path
        # should miss them and fall through to the Ollama fallback:
        "get rid of the notes file",
        "bring up the api folder in the editor",
    ]

    print("Testing intent_parser.py against sample commands:\n")

    for cmd in test_commands:
        result = parse_command(cmd)
        print(f"Input: '{cmd}'")
        print(f"  -> {result}\n")

    print(
        "Check above: every command except 'make me a sandwich' should "
        "show a real intent (not 'unknown'). The last two rely on the "
        "Ollama fallback — if Ollama isn't running, they'll show "
        "'unknown' instead, which is expected/safe."
    )