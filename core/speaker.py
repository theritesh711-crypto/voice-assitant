"""
core/speaker.py
Offline text-to-speech using pyttsx3.

IMPORTANT (Windows): pyttsx3 talks to SAPI5 via COM, and COM objects are
bound to the thread that created them. Since this assistant's main loop
runs in a background thread (see main.py), we must:
  1. Call pythoncom.CoInitialize() at the start of that thread
  2. Create the pyttsx3 engine INSIDE that thread (lazy init), not at
     module import time (which happens on the main thread)
Skipping either step causes runAndWait() to hang forever.

TTS rate/volume now come from config.json instead of being hardcoded —
edit that file to change how fast/loud the assistant speaks.
"""

import threading
import pyttsx3

try:
    import pythoncom
    _HAS_PYTHONCOM = True
except ImportError:
    _HAS_PYTHONCOM = False
    print("Warning: pywin32 not found. Run: pip install pywin32")

from utils.config import config

# -------------------------------
# Thread-local engine storage
# -------------------------------
_local = threading.local()


def _get_engine():
    """
    Returns a pyttsx3 engine that belongs to the CURRENT thread.
    Creates one (and initializes COM) the first time this thread speaks.
    """
    engine = getattr(_local, "engine", None)
    if engine is not None:
        return engine

    if _HAS_PYTHONCOM:
        pythoncom.CoInitialize()

    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", config["tts_rate"])
        engine.setProperty("volume", config["tts_volume"])
        _local.engine = engine
        return engine
    except Exception as e:
        print("Failed to initialize speaker:", e)
        _local.engine = None
        return None


def speak(text: str):
    """
    Speak the given text. Safe to call from any thread — each thread
    gets its own engine instance.
    """
    print(f"ASSISTANT: {text}")

    engine = _get_engine()
    if engine is None:
        print("Speaker Error: Engine not initialized.")
        return

    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print("Speaker Error:", e)


def repeat_heard_text(text: str):
    """
    Repeat back whatever the speech recognizer heard.
    Useful for debugging recognition accuracy.
    """
    if not text:
        return

    print(f"HEARD: {text}")

    engine = _get_engine()
    if engine is None:
        print("Speaker Error: Engine not initialized.")
        return

    try:
        engine.say(f"I heard {text}")
        engine.runAndWait()
    except Exception as e:
        print("Speaker Error:", e)


def stop_speaking():
    """
    Stop any speech currently in progress on the CURRENT thread's engine.
    """
    engine = getattr(_local, "engine", None)
    if engine is not None:
        engine.stop()


if __name__ == "__main__":
    print("Testing speaker...\n")

    speak("Hello. Speaker is working correctly.")
    repeat_heard_text("open machine learning folder")

    print("\nSpeaker test completed.")