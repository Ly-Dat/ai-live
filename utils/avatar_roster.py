"""Characters you can pick from: ready-made original archetypes, or your own. Each character has looks (outfits), and each look
has its own set of expression pictures on disk:

  data/avatar/characters/<id>/character.json
  data/avatar/characters/<id>/looks/<look>/<expression>.png
"""
import json
import os
import shutil
from typing import Dict, List, Optional

from utils.avatar_gen import EXPRESSIONS, safe_name

ROOT = os.path.join("data", "avatar", "characters")

# Original designs (no existing characters). 'persona' names a voice persona from data/personas.json to pair it with in the Voice tab.
PRESETS = [
    {"id": "mimi", "name": "Mimi", "tagline": "Warm shop girl", "gender": "female", "hair": "long pink hair, twin tails", "eyes": "blue eyes",
     "outfit": "white blouse, red ribbon, small apron", "persona": "friendly_girl", "catchphrases": ["nha", "nè"]},
    {"id": "kuro", "name": "Kuro", "tagline": "Calm product expert", "gender": "male", "hair": "short black hair, glasses", "eyes": "amber eyes",
     "outfit": "navy vest, white shirt, tie", "persona": "calm_expert", "catchphrases": ["để mình nói rõ nhé"]},
    {"id": "yuki", "name": "Yuki", "tagline": "Cool idol host", "gender": "female", "hair": "long silver hair, hair ribbon", "eyes": "red eyes",
     "outfit": "black idol dress, white gloves", "persona": "cheerful_host", "catchphrases": ["cùng chốt đơn nào"]},
    {"id": "nana", "name": "Nana", "tagline": "Cat-ear cafe chatter", "gender": "female", "hair": "short brown bob, cat ears", "eyes": "green eyes",
     "outfit": "cafe apron over a pastel dress, bell choker", "persona": "chat_buddy", "catchphrases": ["meo meo", "nè cả nhà"]},
    {"id": "haru", "name": "Haru", "tagline": "Fox-ear hype boy", "gender": "male", "hair": "short orange hair, fox ears, fox tail", "eyes": "golden eyes",
     "outfit": "cream hoodie, red scarf", "persona": "cheerful_host", "catchphrases": ["hot hot hot"]},
    {"id": "sora", "name": "Sora", "tagline": "Bright student type", "gender": "female", "hair": "light blue ponytail", "eyes": "blue eyes",
     "outfit": "sailor school uniform, yellow ribbon", "persona": "friendly_girl", "catchphrases": ["nhanh tay nha"]},
    {"id": "mei", "name": "Mei", "tagline": "Gentle kimono host", "gender": "female", "hair": "black hair in a bun, hair stick", "eyes": "brown eyes",
     "outfit": "pastel floral kimono, obi", "persona": "friendly_girl", "catchphrases": ["từ từ xem nha"]},
    {"id": "leo", "name": "Leo", "tagline": "Streetwear buddy", "gender": "male", "hair": "messy green hair, headphones around neck", "eyes": "grey eyes",
     "outfit": "oversized yellow hoodie, cargo pants", "persona": "chat_buddy", "catchphrases": ["chill thôi nha"]},
]
_FIELDS = ("name", "gender", "hair", "eyes", "outfit", "extra")


def _dir(cid: str, root: str = ROOT) -> str:
    return os.path.join(root, safe_name(cid))


def look_dir(cid: str, look: str, root: str = ROOT) -> str:
    return os.path.join(_dir(cid, root), "looks", safe_name(look))


def _clean(d: Dict, cid: str) -> Dict:
    out = {"id": safe_name(cid), "name": "Character", "gender": "female", "hair": "", "eyes": "", "outfit": "", "extra": "",
           "persona": "", "tagline": "", "seed": 1234, "catchphrases": [], "looks": {}, "look": "default"}
    out.update({k: str(d[k]) for k in _FIELDS + ("persona", "tagline") if k in d})
    out["gender"] = "male" if out["gender"] == "male" else "female"
    out["catchphrases"] = [str(x).strip()[:60] for x in (d.get("catchphrases") or []) if str(x).strip()][:8]
    try:
        out["seed"] = int(d.get("seed", 1234))
    except (TypeError, ValueError):
        pass
    looks = {safe_name(k): str(v) for k, v in (d.get("looks") or {}).items()}
    looks.setdefault("default", out["outfit"])
    out["looks"] = dict(list(looks.items())[:8])
    out["look"] = safe_name(d.get("look") or "default")
    if out["look"] not in out["looks"]:
        out["look"] = "default"
    return out


def load(cid: str, root: str = ROOT) -> Optional[Dict]:
    try:
        with open(os.path.join(_dir(cid, root), "character.json"), "r", encoding="utf-8") as f:
            return _clean(json.load(f), cid)
    except (OSError, ValueError):
        return None


def save(c: Dict, root: str = ROOT) -> Dict:
    c = _clean(c, c.get("id") or c.get("name") or "character")
    os.makedirs(_dir(c["id"], root), exist_ok=True)
    p = os.path.join(_dir(c["id"], root), "character.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    os.replace(p + ".tmp", p)
    return c


def list_all(root: str = ROOT) -> List[Dict]:
    out = []
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            c = load(name, root)
            if c:
                out.append(c)
    return out


def create_from_preset(preset_id: str, root: str = ROOT) -> Dict:
    p = next((x for x in PRESETS if x["id"] == preset_id), None)
    if not p:
        raise ValueError("Unknown preset.")
    cid, n = p["id"], 2
    while load(cid, root):
        cid = f"{p['id']}-{n}"
        n += 1
    return save({**p, "id": cid}, root)


def create_custom(name: str, root: str = ROOT) -> Dict:
    base = safe_name(name)
    cid, n = base, 2
    while load(cid, root):
        cid = f"{base}-{n}"
        n += 1
    return save({"id": cid, "name": name.strip() or "Character", "hair": "long brown hair", "eyes": "brown eyes", "outfit": "white shirt, blue skirt"}, root)


def delete(cid: str, root: str = ROOT) -> None:
    d = _dir(cid, root)
    if os.path.abspath(d).startswith(os.path.abspath(root) + os.sep) and os.path.isdir(d):
        shutil.rmtree(d)


def add_look(c: Dict, name: str, outfit: str, max_looks: int) -> Dict:
    key = safe_name(name)
    if key not in c["looks"] and len(c["looks"]) >= max_looks:
        raise ValueError(f"You can keep {max_looks} look(s) at your level. Level up to unlock more.")
    c = dict(c)
    c["looks"] = {**c["looks"], key: outfit}
    c["look"] = key
    return c


def drawn(cid: str, look: str, root: str = ROOT) -> Dict[str, float]:
    """{expression: mtime} of the pictures that exist for this look."""
    out = {}
    d = look_dir(cid, look, root)
    for ex in EXPRESSIONS:
        p = os.path.join(d, ex + ".png")
        if os.path.isfile(p):
            out[ex] = os.path.getmtime(p)
    return out
