"""What the AI host is saying right now, so the avatar can move its mouth and show a caption in time with the voice.

audio.py calls say() the moment a voice line starts playing; the overlay reads current(). Until now the mouth was timed from
the 'answer' event (about 6 seconds, a guess). With this the mouth runs exactly as long as the audio.
"""
import json
import os
import re
import time
import wave
from typing import Dict, Optional

PATH = os.path.join("data", "avatar", "speaking.json")
TRACKING_S = 120.0      # if nothing was spoken for this long we fall back to the event-based guess
MIN_S, MAX_S = 1.2, 45.0
CPS = 14.0              # Vietnamese speech, normal rate: about 14 characters a second


def duration(audio_path: Optional[str], text: str) -> float:
    """Seconds the line will take: read from a .wav, estimated from the size of an .mp3 (edge-tts ~ 6 KB/s), else from the text."""
    secs = 0.0
    try:
        if audio_path and audio_path.lower().endswith(".wav"):
            with wave.open(audio_path, "rb") as w:
                secs = w.getnframes() / float(w.getframerate() or 1)
        elif audio_path and os.path.isfile(audio_path):
            secs = os.path.getsize(audio_path) / 6000.0
    except (OSError, wave.Error, EOFError):
        secs = 0.0
    if secs <= 0:
        secs = len(text or "") / CPS
    return max(MIN_S, min(MAX_S, secs))


def say(text: str, audio_path: Optional[str] = None, now: Optional[float] = None, path: str = PATH) -> Dict:
    now = time.time() if now is None else now
    text = re.sub(r"\s+", " ", text or "").strip()
    d = {"text": text[:400], "at": now, "dur": round(duration(audio_path, text), 2)}
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass
    return d


def read(path: str = PATH) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {"text": str(d.get("text") or ""), "at": float(d.get("at") or 0), "dur": float(d.get("dur") or 0)}
    except (OSError, ValueError, TypeError):
        return {"text": "", "at": 0.0, "dur": 0.0}


def state(now: float, path: str = PATH) -> Dict:
    """{"tracking": bool, "active": bool, "text": str, "elapsed": s, "dur": s}."""
    d = read(path)
    age = now - d["at"]
    tracking = d["at"] > 0 and 0 <= age <= TRACKING_S + d["dur"]
    active = tracking and age <= d["dur"] + 0.4
    return {"tracking": tracking, "active": active, "text": d["text"], "elapsed": max(0.0, age), "dur": d["dur"]}
