"""
core/speaker.py
Offline text-to-speech with TWO selectable engines, switched via config.json's
"tts_engine" key:

  "pyttsx3" (default) — Windows SAPI5 voices. Instant, robotic-ish, zero setup.
  "piper"             — Neural TTS, much more natural, needs a downloaded voice
                         model (see Step 4 checkpoint instructions).

IMPORTANT (Windows, pyttsx3 only): pyttsx3 talks to SAPI5 via COM, and COM
objects are bound to the thread that created them. Since this assistant's
main loop runs in a background thread (see main.py), we must:
  1. Call pythoncom.CoInitialize() at the start of that thread
  2. Create the pyttsx3 engine INSIDE that thread (lazy init), not at
     module import time (which happens on the main thread)
Skipping either step causes runAndWait() to hang forever.
"""

import threading
import subprocess
import os
import wave
import pyttsx3

try:
    import pythoncom
    _HAS_PYTHONCOM = True
except ImportError:
    _HAS_PYTHONCOM = False
    print("Warning: pywin32 not found. Run: pip install pywin32")

from utils.config import config

_local = threading.local()
_ENGINE_CHOICE = config.get("tts_engine", "pyttsx3")

# Piper is loaded lazily (only if selected) since it's a heavier import
_piper_voice = None


def _get_pyttsx3_engine():
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
        print("Failed to initialize pyttsx3 speaker:", e)
        _local.engine = None
        return None


def _get_piper_voice():
    """
    Loads the Piper model once and reuses it. Piper models are a pair of
    files: a .onnx model and a matching .onnx.json config, both must sit
    next to each other at the path given in config.json's "piper_model_path".
    """
    global _piper_voice
    if _piper_voice is not None:
        return _piper_voice

    model_path = config["piper_model_path"]
    if not os.path.exists(model_path):
        print(f"Piper model not found at: {model_path}")
        print("Download instructions are in the Step 4 checkpoint notes.")
        return None

    try:
        from piper import PiperVoice
        _piper_voice = PiperVoice.load(model_path)
        return _piper_voice
    except Exception as e:
        print("Failed to load Piper voice:", e)
        return None


def _speak_pyttsx3(text: str):
    engine = _get_pyttsx3_engine()
    if engine is None:
        print("Speaker Error: pyttsx3 engine not initialized.")
        return
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print("Speaker Error:", e)

def _speak_piper(text: str):
    """
    Speak using Piper v1.4.x.
    """

    voice = _get_piper_voice()

    if voice is None:
        print("Falling back to pyttsx3 for this message.")
        _speak_pyttsx3(text)
        return

    try:
        import numpy as np
        import sounddevice as sd

        # Piper returns one AudioChunk per sentence
        for chunk in voice.synthesize(text):

            audio = chunk.audio_float_array

            sd.play(audio, samplerate=chunk.sample_rate)

            sd.wait()

    except Exception as e:
        print("Piper playback error:", e)
        print("Falling back to pyttsx3 for this message.")
        _speak_pyttsx3(text)

def speak(text: str):
    """Speak the given text using whichever engine is set in config.json."""
    print(f"ASSISTANT: {text}")
    if _ENGINE_CHOICE == "piper":
        _speak_piper(text)
    else:
        _speak_pyttsx3(text)


def repeat_heard_text(text: str):
    """Repeat back whatever the speech recognizer heard — useful for debugging."""
    if not text:
        return
    print(f"HEARD: {text}")
    speak(f"I heard {text}")


def stop_speaking():
    """Stop any speech currently in progress on the CURRENT thread's pyttsx3 engine."""
    engine = getattr(_local, "engine", None)
    if engine is not None:
        engine.stop()


if __name__ == "__main__":
    print(f"Testing speaker with engine: '{_ENGINE_CHOICE}'\n")
    speak("Hello. Speaker is working correctly.")
    repeat_heard_text("open machine learning folder")
    print("\nSpeaker test completed. If you heard both sentences, this engine works.")