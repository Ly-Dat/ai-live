"""'Sound like me': clone the host's OWN voice from a short clip.

Rules baked in: nothing is sent anywhere until the person ticks the own-voice statement; every enrollment is written
to data/voice_consent.json (name, time, statement) so there is a record; clips are only for the local VieNeu server.
"""
import json
import os
import time
import wave

from . import vieneu_tts

CONSENT_PATH = os.path.join("data", "voice_consent.json")
STATEMENT = "This is my own voice, or the speaker has given me permission to clone it."
MIN_S, MAX_S = 3.0, 12.0


def clip_seconds(path):
    """Length of a .wav clip in seconds; None for other formats (we cannot check them without extra libraries)."""
    if not path.lower().endswith(".wav"):
        return None
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except (wave.Error, OSError, EOFError):
        return -1.0


def check_clip(path):
    """Return an error string, or '' when the clip is fine."""
    secs = clip_seconds(path)
    if secs == -1.0:
        return "This does not look like a valid WAV file."
    if secs is not None and secs < MIN_S:
        return f"The clip is {secs:.1f}s; use 3 to 8 seconds of clear speech."
    if secs is not None and secs > MAX_S:
        return f"The clip is {secs:.0f}s; trim it to 3 to 8 seconds."
    return ""


def records(path=CONSENT_PATH):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def record_consent(name, path=CONSENT_PATH, now=None):
    items = records(path)
    items.append({"name": name, "at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now or time.time())),
                  "statement": STATEMENT})
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def enroll_own_voice(name, clip_path, consent, cfg, consent_path=CONSENT_PATH):
    """Returns (ok, message). Refuses without the consent tick."""
    if not consent:
        return False, "Tick the box confirming this is your own voice (or you have permission)."
    if not vieneu_tts.valid_voice_name(name):
        return False, "Voice name: 1-64 letters, digits, spaces, '.', '-' or '_'."
    problem = check_clip(clip_path)
    if problem:
        return False, problem
    ok, msg = vieneu_tts.enroll_voice(name, clip_path, cfg.get("api_url") or vieneu_tts.DEFAULT_URL,
                                      cfg.get("api_key", ""))
    if ok:
        record_consent(name, consent_path)
    return ok, msg
