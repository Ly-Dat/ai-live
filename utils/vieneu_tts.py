"""
VieNeu-TTS client (free, Apache-2.0, runs locally on CPU or GPU).

VieNeu ships an OpenAI-style server (`python -m apps.openai_speech`, default http://127.0.0.1:8000). We call
POST /v1/audio/speech with response_format "pcm" (48 kHz s16le mono) and wrap it in a proper WAV file so every audio
player can open it. Only the Python standard library is used here, so the main app's dependencies stay untouched; the
model itself runs in its own virtualenv (see voice_server.py).
"""
import json
import os
import urllib.error
import urllib.request
import wave
from typing import List, Optional

DEFAULT_URL = "http://127.0.0.1:8000"


def _headers(api_key: str = "") -> dict:
    h = {"Content-Type": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def pcm_to_wav(pcm: bytes, out_path: str, sample_rate: int = 48000) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return out_path


def synthesize(text: str, cfg: dict, out_path: str) -> Optional[str]:
    """Synthesize `text` to a WAV file. Returns the path, or None if the server is unreachable / errors."""
    text = (text or "").strip()
    if not text:
        return None
    base = (cfg.get("api_url") or DEFAULT_URL).rstrip("/")
    rate = int(cfg.get("sample_rate") or 48000)
    body = {
        "model": cfg.get("model") or "vieneu-v3-turbo",
        "input": text,
        "voice": cfg.get("voice") or None,
        "response_format": "pcm",
        "sample_rate": rate,
    }
    body = {k: v for k, v in body.items() if v is not None}
    req = urllib.request.Request(base + "/v1/audio/speech", data=json.dumps(body).encode("utf-8"),
                                 headers=_headers(cfg.get("api_key", "")), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=float(cfg.get("timeout") or 60)) as r:
            pcm = r.read()
            rate = int(r.headers.get("X-Sample-Rate") or rate)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if len(pcm) < 200:
        return None
    return pcm_to_wav(pcm, out_path, rate)


def _voice_name(item) -> Optional[str]:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for k in ("id", "name", "voice", "label"):
            if item.get(k):
                return str(item[k])
    return None


def list_voices(api_url: str = DEFAULT_URL, api_key: str = "", timeout: float = 5) -> List[str]:
    """Voice names offered by the running server (empty list if it is not reachable)."""
    req = urllib.request.Request(api_url.rstrip("/") + "/v1/voices", headers=_headers(api_key))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return []
    items = data.get("data", data) if isinstance(data, dict) else data
    names = [_voice_name(i) for i in (items if isinstance(items, list) else [])]
    return [n for n in names if n]


def is_up(api_url: str = DEFAULT_URL, timeout: float = 2) -> bool:
    try:
        with urllib.request.urlopen(api_url.rstrip("/") + "/health", timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False
