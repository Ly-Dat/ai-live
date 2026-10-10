"""The on-stream avatar: settings, the sprite pack on disk, and which expression to show right now.

The overlay page shows one transparent PNG per expression (idle, talking, happy, surprised, confused, thinking). The
expression follows what just happened on the live (read from the analytics event log), and while the host is speaking the
page flaps between the 'talking' picture and the current mood. The flapping is timed from the event, not from the audio
level, so it is an approximation of lip-sync, not true lip-sync.
"""
import json
import os
from typing import Dict, List, Optional

from utils.avatar_gen import EXPRESSIONS

DIR = os.path.join("data", "avatar")
PACK_DIR = os.path.join(DIR, "pack")
SETTINGS_PATH = os.path.join(DIR, "settings.json")
URL_PREFIX = "/lv_avatar/pack/"
SPEAK_SECONDS = 6.0
DEFAULTS = {
    "enabled": False,
    "character": {"name": "Mimi", "gender": "female", "hair": "long pink hair, twin tails", "eyes": "blue eyes",
                  "outfit": "white blouse, red ribbon, small apron", "extra": ""},
    "catchphrases": [],
    "expertise": "",
    "seed": 1234,
    "height_vh": 62,
    "gen": {},
}


def load_settings(path: str = SETTINGS_PATH) -> Dict:
    out = json.loads(json.dumps(DEFAULTS))
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        for k in ("enabled", "expertise", "seed", "height_vh"):
            if k in d:
                out[k] = d[k]
        out["enabled"] = bool(out["enabled"])
        out["character"].update({k: str(v) for k, v in (d.get("character") or {}).items() if k in out["character"]})
        out["catchphrases"] = [str(x).strip()[:60] for x in (d.get("catchphrases") or []) if str(x).strip()][:8]
        out["gen"] = dict(d.get("gen") or {})
        out["height_vh"] = max(25, min(90, int(out["height_vh"])))
        out["seed"] = int(out["seed"])
    except (OSError, ValueError, TypeError):
        pass
    return out


def save_settings(s: Dict, path: str = SETTINGS_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def pack_files(pack_dir: str = PACK_DIR) -> Dict[str, float]:
    """{expression: mtime} for the sprites that exist."""
    out = {}
    for ex in EXPRESSIONS:
        p = os.path.join(pack_dir, ex + ".png")
        if os.path.isfile(p):
            out[ex] = os.path.getmtime(p)
    return out


def pick_expression(events: List[Dict], now: float) -> Dict:
    """{"mood": expression, "talking": bool} from the most recent events (newest wins)."""
    mood, talking = "idle", False
    for e in reversed(events[-40:]):
        age = now - float(e.get("ts") or 0)
        if age < 0:
            continue
        kind = e.get("kind")
        if kind in ("answer", "pitch") and age <= SPEAK_SECONDS:
            return {"mood": "happy" if kind == "pitch" else "idle", "talking": True}
        if kind == "gift" and age <= 5:
            return {"mood": "surprised" if age <= 1.5 else "happy", "talking": False}
        if kind == "blocked" and age <= 4:
            return {"mood": "confused", "talking": False}
        if kind == "comment" and age <= 3:
            return {"mood": "thinking", "talking": False}
        if kind in ("entrance", "product_pop") and age <= 3:
            return {"mood": "happy", "talking": False}
    return {"mood": mood, "talking": talking}


def overlay_avatar(settings: Dict, files: Dict[str, float], events: List[Dict], now: float, host_state: str = "live",
                   url_prefix: str = URL_PREFIX) -> Optional[Dict]:
    if not settings.get("enabled") or "idle" not in files:
        return None
    pick = {"mood": "idle", "talking": False} if host_state != "live" else pick_expression(events, now)
    images = {ex: f"{url_prefix}{ex}.png?v={int(mt)}" for ex, mt in files.items()}
    mood = pick["mood"] if pick["mood"] in images else "idle"
    return {"name": settings["character"].get("name", ""), "images": images, "mood": mood,
            "talking": bool(pick["talking"] and "talking" in images), "height": settings["height_vh"],
            "paused": host_state != "live"}
