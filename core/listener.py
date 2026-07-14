"""
listener.py
Handles microphone input and converts speech to text — fully offline.

Pipeline:
  1. Silero VAD watches the microphone stream and decides when the user
     has actually started/stopped speaking (no more fixed-length recordings,
     no clipped first words).
  2. Faster-Whisper transcribes the captured audio locally (no internet,
     no Google Web Speech API).

Implements the WAKE WORD system:
  - wait_for_wake_word() loops, using listen_once() under the hood, until
    the wake word (or one of its aliases) is heard.
  - Runs fine in a background thread — all shared model state is
    protected by locks.

Reusable API:
  - listen_once(timeout, verbose, return_audio)
  - wait_for_wake_word(poll_timeout, verbose)
  - transcribe_audio(audio, sample_rate, verbose)

Requirements (pip install):
  faster-whisper  silero-vad  sounddevice  numpy  torch

DEBUG NOTE:
  Every stage (mic open, speech onset, silence/timeout, transcription
  result) is logged. Set "debug": true/false in config.json to control
  verbosity, or pass verbose=False to any function to silence a single call.
"""

import json
import logging
import os
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd
import torch
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad

# ---------------------------------------------------
# Load configuration
# ---------------------------------------------------
try:
    with open("config.json", "r", encoding="utf-8") as f:
        CONFIG = json.load(f)
except FileNotFoundError as e:
    raise FileNotFoundError(
        "config.json not found. listener.py expects to be run/imported "
        "from the project root, where config.json lives."
    ) from e

WAKE_WORD = CONFIG["wake_word"].lower()
TIMEOUT = CONFIG.get("listen_timeout_seconds", 8)

# ---------------------------------------------------
# Tunables (all overridable from config.json, sensible defaults if absent)
# ---------------------------------------------------
SAMPLE_RATE = CONFIG.get("sample_rate", 16000)
MICROPHONE_INDEX = CONFIG.get("microphone_index", 1)
CHUNK_SAMPLES = 512  # 32ms @ 16kHz — required window size for silero-vad
VAD_THRESHOLD = CONFIG.get("vad_threshold", 0.7)
SILENCE_DURATION_SECONDS = CONFIG.get("silence_duration_seconds", 0.5)
MAX_RECORD_SECONDS = CONFIG.get("max_recording_seconds", 15)
PREROLL_SECONDS = CONFIG.get("preroll_seconds", 0.3)
SPEECH_CONFIRM_CHUNKS = CONFIG.get("speech_confirm_chunks", 2)

WHISPER_MODEL_SIZE = CONFIG.get("whisper_model", "base")
WHISPER_DEVICE = CONFIG.get("whisper_device", "cpu")
WHISPER_COMPUTE_TYPE = CONFIG.get("whisper_compute_type", "int8")

PREROLL_CHUNKS = max(1, int((PREROLL_SECONDS * SAMPLE_RATE) / CHUNK_SAMPLES))
SILENCE_CHUNKS_NEEDED = max(1, int((SILENCE_DURATION_SECONDS * SAMPLE_RATE) / CHUNK_SAMPLES))
MAX_RECORD_CHUNKS = max(1, int((MAX_RECORD_SECONDS * SAMPLE_RATE) / CHUNK_SAMPLES))

# Wake-word aliases (Whisper may mishear "Lily" in various ways)
_DEFAULT_ALIASES = [
    WAKE_WORD,
    f"hey {WAKE_WORD}",
    f"hi {WAKE_WORD}",
    f"{WAKE_WORD} sir",

    "lily",
    "lilly",
    "lilli",
    "lili",
    "lilie",
    "lilie",
    "lilli",
    "lilyy",
    "lilyyy",
    "lilii",
    "liliii",
    "lilee",
    "lilee",
    "lilie",
    "leely",
    "leeli",
    "leelie",
    "leelyy",
    "liliya",
    "lillie",
    "lilly",
    "liley",
    "lilliy",
    "liliey",
    "liley",
    "liliy",
    "lillyy",
    "lilye",
    "liliee",
    "lileeh",
    "leely",
    "leelee",
    "leelee",
    "lilliie",
    "lillii",
    "lilyy",
    "liliy",
    "lileeey",
    "liliyy",
    "lillly",
    "lileee",
    "lile",
    "lileea",
    "lileah",
    "lileeh",
    "lilliiee",
    "lilieee",
    "lilliii",
    "liliiii",
    "lileeey",
    "lillyyy",
]

WAKE_WORD_ALIASES = [a.lower() for a in CONFIG.get("wake_word_aliases", _DEFAULT_ALIASES)]
if WAKE_WORD not in WAKE_WORD_ALIASES:
    WAKE_WORD_ALIASES.append(WAKE_WORD)

# ---------------------------------------------------
# Logging
# ---------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if CONFIG.get("debug", True) else logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [listener] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("listener")

# ---------------------------------------------------
# Load models once (module-level, shared across calls/threads)
# ---------------------------------------------------
logger.debug("Loading Silero VAD model...")
_vad_model = load_silero_vad()
logger.debug("Silero VAD ready.")

logger.debug(
    "Loading Faster-Whisper model '%s' (device=%s, compute=%s)...",
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
    WHISPER_COMPUTE_TYPE,
)

# Free any cached CUDA memory before loading the model
if WHISPER_DEVICE == "cuda" and torch.cuda.is_available():
    torch.cuda.empty_cache()

# Load Whisper model
_whisper_model = WhisperModel(
    WHISPER_MODEL_SIZE,
    device=WHISPER_DEVICE,
    compute_type=WHISPER_COMPUTE_TYPE,
)

logger.debug("Faster-Whisper ready.")

# Runtime information
print("=" * 60)
print("Whisper Runtime Information")
print("=" * 60)

if WHISPER_DEVICE == "cuda" and torch.cuda.is_available():
    print("Backend      : CUDA")
    print("GPU Available:", torch.cuda.is_available())
    print("GPU Name     :", torch.cuda.get_device_name(0))
    print(
        "GPU Memory   : {:.2f} GB".format(
            torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        )
    )
else:
    print("Backend      : CPU")

print("Model        :", WHISPER_MODEL_SIZE)
print("Compute Type :", WHISPER_COMPUTE_TYPE)
print("Microphone   : Device Index", MICROPHONE_INDEX)
print("=" * 60)

# Locks so listen_once()/transcribe_audio() can safely be called from
# multiple threads (e.g. a background wake-word thread + a foreground
# command thread) without two threads hitting the same model at once.
_vad_lock = threading.Lock()
_whisper_lock = threading.Lock()
_mic_lock = threading.Lock()  # only one stream should own the mic at a time


# ---------------------------------------------------
# Internal: VAD-triggered recording
# ---------------------------------------------------
def _record_with_vad(timeout, verbose=True):
    """
    Opens the microphone and records exactly one utterance:
      - Waits (up to `timeout` seconds) for speech to start.
      - Once speech starts, keeps recording until a sustained silence
        (SILENCE_DURATION_SECONDS) or MAX_RECORD_SECONDS is reached.
      - Prepends a small pre-roll buffer so the first word isn't clipped.

    Returns a float32 numpy array (mono, -1..1) or None if nothing was
    captured (timeout with no speech, or a microphone error).
    """
    preroll = deque(maxlen=PREROLL_CHUNKS)
    recorded_chunks = []
    speech_started = False
    consecutive_speech = 0
    consecutive_silence = 0

    start_time = time.time()

    with _mic_lock:
        try:
           with sd.InputStream(
                device=MICROPHONE_INDEX,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=CHUNK_SAMPLES,
            ) as stream:
                

                if verbose:
                    logger.debug(
                        "Microphone open (sr=%d chunk=%d) — waiting for speech...",
                        SAMPLE_RATE, CHUNK_SAMPLES,
                    )

                while True:
                    if not speech_started and (time.time() - start_time) > timeout:
                        if verbose:
                            logger.debug("Timeout — no speech detected in %.1fs", timeout)
                        return None

                    chunk, overflowed = stream.read(CHUNK_SAMPLES)
                    if overflowed and verbose:
                        logger.warning("Audio buffer overflow — some samples dropped")

                    chunk = chunk[:, 0].copy()  # mono, 1D

                    with _vad_lock:
                        speech_prob = float(
                            _vad_model(torch.from_numpy(chunk), SAMPLE_RATE).item()
                        )
                    is_speech = speech_prob >= VAD_THRESHOLD

                    if not speech_started:
                        preroll.append(chunk)
                        if is_speech:
                            consecutive_speech += 1
                            if consecutive_speech >= SPEECH_CONFIRM_CHUNKS:
                                speech_started = True
                                recorded_chunks.extend(preroll)
                                consecutive_silence = 0
                                if verbose:
                                    logger.debug(
                                        "Speech onset (prob=%.2f) — recording started",
                                        speech_prob,
                                    )
                        else:
                            consecutive_speech = 0
                    else:
                        recorded_chunks.append(chunk)
                        if is_speech:
                            consecutive_silence = 0
                        else:
                            consecutive_silence += 1

                        if consecutive_silence >= SILENCE_CHUNKS_NEEDED:
                            if verbose:
                                logger.debug("Sustained silence — recording stopped")
                            break

                        if len(recorded_chunks) >= MAX_RECORD_CHUNKS:
                            if verbose:
                                logger.debug("Max recording length reached — recording stopped")
                            break

        except OSError as e:
            logger.error("Microphone error: %s", e)
            return None

    if not recorded_chunks:
        return None

    audio = np.concatenate(recorded_chunks).astype(np.float32)
    if verbose:
        logger.debug("Captured %.2fs of audio", len(audio) / SAMPLE_RATE)
    return audio


# ---------------------------------------------------
# Public API
# ---------------------------------------------------
def transcribe_audio(audio, sample_rate=SAMPLE_RATE, verbose=True):
    """
    Transcribe audio using Faster-Whisper (fully offline).

    `audio` may be:
      - a float32 numpy array, mono, values in -1..1 (what _record_with_vad
        returns), or
      - a path (str) to an audio file on disk.

    Returns lowercase, stripped text, or None if nothing usable was heard.
    """
    if audio is None:
        return None

    try:
        with _whisper_lock:
            segments, info = _whisper_model.transcribe(
                audio,
                language="en",
                beam_size=5,
                vad_filter=False,  # we already did VAD ourselves upstream
            )
            text = " ".join(seg.text.strip() for seg in segments).strip().lower()

        if verbose:
            if text:
                logger.debug(
                    "Transcribed: '%s' (lang=%s, conf=%.2f)",
                    text, info.language, info.language_probability,
                )
            else:
                logger.debug("Whisper returned an empty transcription")

        return text if text else None

    except Exception as e:
        logger.error("Transcription error: %s", e)
        return None


def listen_once(timeout=None, verbose=True, return_audio=False):
    """
    Record one utterance (VAD decides start/stop automatically) and
    transcribe it offline.

    Returns lowercase text, or None if nothing was understood.
    If return_audio=True, returns a (text, audio) tuple instead, where
    `audio` is the raw float32 numpy array that was captured (or None).
    """
    if timeout is None:
        timeout = TIMEOUT

    audio = _record_with_vad(timeout=timeout, verbose=verbose)
    if audio is None:
        return (None, None) if return_audio else None

    text = transcribe_audio(audio, verbose=verbose)
    return (text, audio) if return_audio else text


def wait_for_wake_word(poll_timeout=1.5, verbose=True):
    """
    Blocks (thread-safe — fine to run in a background thread) until the
    wake word or one of its aliases is heard. Returns True once detected.
    """
    logger.info("Listening for wake word: '%s'", WAKE_WORD)
    attempt = 0

    while True:
        attempt += 1
        text = listen_once(timeout=poll_timeout, verbose=verbose)

        if text:
            logger.debug("Heard: '%s'", text)
            if any(alias in text for alias in WAKE_WORD_ALIASES):
                logger.info("Wake word detected!")
                return True

        if attempt % 10 == 0:
            logger.debug("Still waiting for wake word (%d attempts so far)", attempt)


# ---------------------------------------------------
# Manual test
# ---------------------------------------------------
if __name__ == "__main__":
    print("STEP 1 - Testing microphone + VAD + Whisper (say something)")
    result = listen_once(timeout=8)
    print("You said:", result)

    print("\nSTEP 2 - Testing wake word (say 'lily')")
    wait_for_wake_word()

    print("SUCCESS")