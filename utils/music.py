"""Background music for the stream overlay: only tracks whose licence is safe for a selling live are played.

Honest rules (see docs/MUSIC.md):
  * every track needs a licence tag; "unknown" tracks are never played
  * CC BY tracks need a visible credit -> the overlay shows it whenever such a track plays
  * NC (non-commercial), SA/ND and "YouTube-only" licences are blocked: a shop live is commercial use
Ducking is approximate: the music gets quieter for a few seconds after the host speaks (answer / pitch events).
"""
import json
import os
import random
from typing import Dict, List, Optional

MUSIC_DIR = os.path.join("data", "music")
MANIFEST = "music.json"
SETTINGS_PATH = os.path.join("data", "music_settings.json")
AUDIO_EXT = (".mp3", ".ogg", ".wav", ".m4a")
DUCK_KINDS = {"answer", "pitch", "shoutout", "handoff", "product_pop"}
DUCK_SECONDS = 9.0

# id -> (label, playable on a commercial live?, credit required?, note)
LICENSES: Dict[str, Dict] = {
    "cc0": {"label": "CC0 / public domain", "ok": True, "credit": False, "note": "No conditions. Safest."},
    "own": {"label": "I made it / I bought a licence", "ok": True, "credit": False, "note": "Keep your receipt or licence file."},
    "pixabay": {"label": "Pixabay licence", "ok": True, "credit": False,
                "note": "Free for commercial use, credit optional. Read the track page; do not register it with any copyright-claim system."},
    "mixkit": {"label": "Mixkit free licence", "ok": True, "credit": False, "note": "Free for commercial use, no credit."},
    "cc-by": {"label": "CC BY 4.0 (credit required)", "ok": True, "credit": True, "note": "Credit is shown on the overlay while it plays."},
    "cc-by-sa": {"label": "CC BY-SA", "ok": False, "credit": True, "note": "Share-alike: avoid for a shop."},
    "cc-by-nc": {"label": "CC BY-NC (non-commercial)", "ok": False, "credit": True, "note": "Not allowed on a selling live."},
    "yt-audio": {"label": "YouTube Audio Library", "ok": False, "credit": False, "note": "Licensed for YouTube, not guaranteed on TikTok."},
    "unknown": {"label": "Unknown - not played", "ok": False, "credit": False, "note": "Pick a licence to enable it."},
}
DEFAULT_SETTINGS = {"enable": False, "volume": 25, "shuffle": True, "duck": True, "duck_volume": 8}


def load_settings(path: str = SETTINGS_PATH) -> Dict:
    out = dict(DEFAULT_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k in out:
            if k in data:
                out[k] = data[k]
    except (OSError, ValueError):
        pass
    out["volume"] = max(0, min(100, int(out["volume"] or 0)))
    out["duck_volume"] = max(0, min(out["volume"], int(out["duck_volume"] or 0)))
    return out


def save_settings(settings: Dict, path: str = SETTINGS_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({k: settings.get(k, v) for k, v in DEFAULT_SETTINGS.items()}, f, indent=2)
    os.replace(tmp, path)


def scan(folder: str = MUSIC_DIR) -> List[str]:
    try:
        return sorted(f for f in os.listdir(folder) if f.lower().endswith(AUDIO_EXT))
    except OSError:
        return []


def load_manifest(folder: str = MUSIC_DIR) -> Dict[str, Dict]:
    try:
        with open(os.path.join(folder, MANIFEST), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_manifest(manifest: Dict[str, Dict], folder: str = MUSIC_DIR) -> None:
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, MANIFEST)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def credit_line(t: Dict) -> str:
    """The credit text for a track (CC BY wording: title, author, source, licence)."""
    parts = [f'"{t["title"]}"']
    if t.get("artist"):
        parts.append(f'by {t["artist"]}')
    if t.get("source"):
        parts.append(f'({t["source"]})')
    parts.append("- " + LICENSES.get(t["license"], LICENSES["unknown"])["label"].split(" (")[0])
    return " ".join(parts)


def tracks(folder: str = MUSIC_DIR) -> List[Dict]:
    manifest = load_manifest(folder)
    out = []
    for fn in scan(folder):
        m = manifest.get(fn) or {}
        lic = m.get("license") if m.get("license") in LICENSES else "unknown"
        info = LICENSES[lic]
        t = {"file": fn, "title": (m.get("title") or os.path.splitext(fn)[0]).strip(), "artist": (m.get("artist") or "").strip(),
             "source": (m.get("source") or "").strip(), "license": lic, "ok": info["ok"], "credit_needed": info["credit"]}
        # a credit-required track with no author cannot be credited properly -> not played
        if t["credit_needed"] and not t["artist"]:
            t["ok"] = False
        t["credit"] = credit_line(t) if t["credit_needed"] else ""
        out.append(t)
    return out


def playable(all_tracks: List[Dict]) -> List[Dict]:
    return [t for t in all_tracks if t["ok"]]


def credits_text(all_tracks: List[Dict]) -> str:
    lines = [t["credit"] for t in playable(all_tracks) if t["credit_needed"]]
    return "Music:\n" + "\n".join(lines) if lines else ""


def duck_active(events: List[Dict], now: float, seconds: float = DUCK_SECONDS) -> bool:
    return any(e.get("kind") in DUCK_KINDS and 0 <= now - float(e.get("ts") or 0) <= seconds for e in events[-40:])


def tail_events(path: Optional[str], n: int = 40) -> List[Dict]:
    if not path:
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 16000))
            lines = f.read().decode("utf-8", "replace").splitlines()[-n:]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def overlay_music(settings: Dict, all_tracks: List[Dict], events: List[Dict], now: float, url_prefix: str = "/lv_music/",
                  seed: Optional[int] = None) -> Dict:
    ok = playable(all_tracks)
    if not settings.get("enable") or not ok:
        return {"enabled": False, "tracks": [], "volume": 0.0}
    order = list(ok)
    if settings.get("shuffle"):
        random.Random(seed if seed is not None else 0).shuffle(order)
    ducked = bool(settings.get("duck")) and duck_active(events, now)
    vol = settings["duck_volume"] if ducked else settings["volume"]
    return {"enabled": True, "volume": round(vol / 100.0, 2), "ducked": ducked,
            "tracks": [{"url": url_prefix + t["file"], "title": t["title"], "artist": t["artist"], "credit": t["credit"]} for t in order]}
