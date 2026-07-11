"""
listener.py
Handles microphone input and converts speech to text using SpeechRecognition
(free, uses Google's public Web Speech API endpoint — needs internet).

Implements the WAKE WORD system:
- Continuously listens in a lightweight loop for the wake word.
- Only after hearing the wake word does it start actively listening for a command.
- Runs in a background thread.

DEBUG NOTE:
Every listen attempt prints exactly what it heard.
"""

import json
import speech_recognition as sr

# ---------------------------------------------------
# Load configuration
# ---------------------------------------------------
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

WAKE_WORD = CONFIG["wake_word"].lower()
TIMEOUT = CONFIG["listen_timeout_seconds"]

# Wake-word aliases (Google may mishear these)
WAKE_WORD_ALIASES = [
    "hey rakesh",
    "hi rakesh",
    "rakesh",
    "rakeshh",
    "rakish",
    "raki",
    "hey rakesh sir",
]

# ---------------------------------------------------
# Speech recognizer
# ---------------------------------------------------
_recognizer = sr.Recognizer()
_recognizer.energy_threshold = 300
_recognizer.dynamic_energy_threshold = True
_recognizer.pause_threshold = 0.8


def listen_once(timeout=TIMEOUT, verbose=True):
    """
    Listen once and return recognized text in lowercase.
    Returns None if nothing understandable was heard.
    """

    try:
        with sr.Microphone() as source:

    # Calibrate for background noise
            _recognizer.adjust_for_ambient_noise(source, duration=0.5)

            if verbose:
                print(
                    f"[listening... energy_threshold={_recognizer.energy_threshold:.0f}]"
                )

            audio = _recognizer.listen(
                source,
                timeout=timeout,
                phrase_time_limit=8,
             )

    except sr.WaitTimeoutError:
        if verbose:
            print("[heard nothing in time window]")
        return None

    except OSError as e:
        print(f"[MICROPHONE ERROR] {e}")
        return None

    try:
        text = _recognizer.recognize_google(audio).lower()

        if verbose:
            print(f"[recognized: '{text}']")

        return text

    except sr.UnknownValueError:
        if verbose:
            print("[heard sound, but could not understand words]")
        return None

    except sr.RequestError as e:
        print(f"[SPEECH SERVICE ERROR] {e}")
        return None


def wait_for_wake_word():
    """
    Wait until the wake word (or one of its aliases) is spoken.
    """

    print(f"Listening for wake word: '{WAKE_WORD}'...")

    attempt = 0

    while True:

        attempt += 1

        text = listen_once(timeout=3, verbose=True)

        if text:
            print("DEBUG - Recognized:", text)

            for alias in WAKE_WORD_ALIASES:
                if alias in text:
                    print("Wake word detected!")
                    return True

        if attempt % 5 == 0:
            print(
                f"[still waiting for wake word — {attempt} attempts so far]"
            )


if __name__ == "__main__":

    print("STEP 1 - Testing microphone")

    result = listen_once(timeout=6)

    print("You said:", result)

    print("\nSTEP 2 - Testing wake word")

    wait_for_wake_word()

    print("SUCCESS")