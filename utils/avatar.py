"""The on-stream avatar: stage settings, and which picture to show right now.

The overlay page shows one transparent PNG per expression of the active character's active look. The expression follows what just
happened on the live (read from the analytics event log); while the host is speaking the page flaps between the 'talking' picture
and the current mood. The flap is timed from the event, not from the audio level, so it is an approximation of lip-sync.
Missing pictures fall back along avatar_gen.FALLBACK, so a pack with only the six core pictures still works.
"""
import json
import os
import re
from typing import Dict, List, Optional

from utils import avatar_gen, avatar_roster, bond

DIR = os.path.join("data", "avatar")
SETTINGS_PATH = os.path.join(DIR, "settings.json")
PREVIEW_PATH = os.path.join(DIR, "preview.json")
URL_PREFIX = "/lv_avatar/characters/"
SPEAK_SECONDS = 6.0
SLEEP_AFTER = 180.0
SIDES = ("right", "left", "center")
DEFAULTS = {"enabled": False, "active": "", "gen": {},
            "stage": {"side": "right", "height_vh": 62, "motion": "bob", "frame": "none", "nametag": True, "badge": True,
                      "tips": [], "tip_seconds": 9, "caption": True}}

_LOVE = re.compile(r"(yeu|thuong|tym|<3|love|❤|😍)")
_COMPLIMENT = re.compile(r"(xinh|de thuong|cute|kawaii|dep qua|dep ghe|duyen)")
_LAUGH = re.compile(r"(haha|hihi|kkk|=\)\)|lol|😂|🤣)")
_SAD = re.compile(r"(buon|huhu|hic hic|tiec|:\(|😢|😭)")


def _fold(s: str) -> str:
    from utils.product_catalog import _fold as f
    return f(s or "")


def load_settings(path: str = SETTINGS_PATH) -> Dict:
    out = json.loads(json.dumps(DEFAULTS))
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        out["enabled"] = bool(d.get("enabled"))
        out["active"] = str(d.get("active") or "")
        out["gen"] = dict(d.get("gen") or {})
        st = d.get("stage") or {}
        s = out["stage"]
        if st.get("side") in SIDES:
            s["side"] = st["side"]
        try:
            s["height_vh"] = max(25, min(90, int(st.get("height_vh", s["height_vh"]))))
            s["tip_seconds"] = max(4, min(60, int(st.get("tip_seconds", s["tip_seconds"]))))
        except (TypeError, ValueError):
            pass
        s["motion"] = str(st.get("motion") or s["motion"])
        s["frame"] = str(st.get("frame") or s["frame"])
        s["nametag"], s["badge"] = bool(st.get("nametag", True)), bool(st.get("badge", True))
        s["caption"] = bool(st.get("caption", True))
        s["tips"] = [str(x).strip()[:90] for x in (st.get("tips") or []) if str(x).strip()][:6]
    except (OSError, ValueError, TypeError):
        pass
    return out


def save_settings(s: Dict, path: str = SETTINGS_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def active_character(settings: Dict, root: str = avatar_roster.ROOT) -> Optional[Dict]:
    return avatar_roster.load(settings["active"], root) if settings.get("active") else None


def catchphrases(settings: Dict, root: str = avatar_roster.ROOT) -> List[str]:
    c = active_character(settings, root)
    return c["catchphrases"] if c else []


def set_preview(expr: str, now: float, seconds: float = 8.0, path: str = PREVIEW_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"expr": expr, "until": now + seconds}, f)


def read_preview(now: float, path: str = PREVIEW_PATH) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d["expr"] if now < float(d["until"]) and d["expr"] in avatar_gen.EXPRESSIONS else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def mood_for_comment(text: str) -> str:
    f = _fold(text)
    if _COMPLIMENT.search(f):
        return "shy"
    if _LOVE.search(f) or "<3" in (text or ""):
        return "love"
    if _LAUGH.search(f) or any(ch in (text or "") for ch in "😂🤣"):
        return "laughing"
    if _SAD.search(f) or any(ch in (text or "") for ch in "😢😭"):
        return "sad"
    return "thinking"


def pick_expression(events: List[Dict], now: float) -> Dict:
    """{"mood": expression, "talking": bool} from the most recent events (newest wins)."""
    if not events:
        return {"mood": "idle", "talking": False}
    for e in reversed(events[-40:]):
        age = now - float(e.get("ts") or 0)
        if age < 0:
            continue
        kind = e.get("kind")
        if kind in ("answer", "pitch") and age <= SPEAK_SECONDS:
            return {"mood": "proud" if kind == "pitch" else "idle", "talking": True}
        if kind == "gift" and age <= 6:
            return {"mood": "surprised" if age <= 1.5 else ("excited" if age <= 3 else "love"), "talking": False}
        if kind == "blocked" and age <= 4:
            return {"mood": "confused", "talking": False}
        if kind == "comment" and age <= 3:
            return {"mood": mood_for_comment(e.get("text", "")), "talking": False}
        if kind == "entrance" and age <= 3:
            return {"mood": "wink", "talking": False}
        if kind == "product_pop" and age <= 3:
            return {"mood": "excited", "talking": False}
    last = max(float(e.get("ts") or 0) for e in events)
    return {"mood": "sleepy" if now - last > SLEEP_AFTER else "idle", "talking": False}


def overlay_avatar(settings: Dict, events: List[Dict], now: float, host_state: str = "live", cache: Optional[Dict] = None,
                   root: str = avatar_roster.ROOT, preview: Optional[str] = None, speaking_state: Optional[Dict] = None) -> Optional[Dict]:
    if not settings.get("enabled"):
        return None
    char = active_character(settings, root)
    if not char:
        return None
    files = avatar_roster.drawn(char["id"], char["look"], root)
    if "idle" not in files:
        return None
    paused = host_state != "live"
    if preview:
        pick = {"mood": preview, "talking": preview == "talking"}
    elif paused:
        pick = {"mood": "sleepy" if "sleepy" in files else "idle", "talking": False}
    else:
        pick = pick_expression(events, now)
    sp = speaking_state or {}
    caption = None
    if sp.get("tracking") and not preview and not paused:
        # the voice player reports what it is saying: the mouth runs exactly as long as the audio
        pick = {"mood": pick["mood"], "talking": bool(sp.get("active"))}
        if settings["stage"].get("caption", True) and sp.get("active") and sp.get("text"):
            caption = {"text": sp["text"], "elapsed": round(float(sp.get("elapsed") or 0), 2), "dur": round(float(sp.get("dur") or 0), 2)}
    base = f"{URL_PREFIX}{char['id']}/looks/{char['look']}/"
    images = {ex: f"{base}{ex}.png?v={int(mt)}" for ex, mt in files.items()}
    mood = avatar_gen.resolve(pick["mood"], files)
    st = settings["stage"]
    level = int((cache or {}).get("level") or 1)
    frame = st["frame"] if st["frame"] in bond.unlocked(bond.FRAMES, level) else "none"
    motion = st["motion"] if st["motion"] in bond.unlocked(bond.MOTIONS, level) else "bob"
    badge = ""
    if st["badge"] and cache:
        badge = f"Lv {level}" + (f" · {cache['streak']}-day streak" if cache.get("streak", 0) >= 2 else "")
    return {"name": char["name"] if st["nametag"] else "", "badge": badge, "images": images, "mood": mood,
            "talking": bool(pick["talking"] and "talking" in files), "height": st["height_vh"], "side": st["side"],
            "frame": frame, "motion": motion, "tips": st["tips"], "tip_seconds": st["tip_seconds"], "paused": paused,
            "caption": caption}
