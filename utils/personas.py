"""Persona presets: voice + speaking style (+ avatar) in one choice. Compliance rules are always kept."""
import json
from typing import Dict, List, Optional


def load(path: str = "data/personas.json") -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get(data: Dict, persona_id: str) -> Optional[Dict]:
    return next((p for p in data.get("personas", []) if p["id"] == persona_id), None)


def for_mode(data: Dict, mode: str = "seller") -> List[Dict]:
    """Personas for 'seller' (default) or 'creator' (no cart: just-chatting, music, study, gaming lives)."""
    want = "creator" if mode == "creator" else "seller"
    return [p for p in data.get("personas", []) if p.get("mode", "seller") == want]


def build_before_prompt(data: Dict, persona: Dict) -> str:
    rules = data.get("creator_rules") if persona.get("mode") == "creator" and data.get("creator_rules") else data["base_rules"]
    return f"{persona['style']} {rules}"


def apply_to_config(cfg: Dict, data: Dict, persona_id: str) -> List[str]:
    """Mutate a config dict in place; returns a list of human-readable changes."""
    persona = get(data, persona_id)
    if persona is None:
        raise KeyError(f"Unknown persona: {persona_id}")
    changes = []
    cfg["before_prompt"] = build_before_prompt(data, persona)
    changes.append("before_prompt")
    tts = cfg.setdefault("edge-tts", {})
    tts["voice"] = persona["voice"]
    tts["rate"] = persona.get("rate", "+0%")
    changes.append(f"edge-tts voice {persona['voice']} rate {tts['rate']}")
    if persona.get("vieneu_voice"):
        cfg.setdefault("vieneu", {})["voice"] = persona["vieneu_voice"]
        changes.append(f"vieneu voice {persona['vieneu_voice']}")
    if persona.get("live2d") and isinstance(cfg.get("live2d"), dict):
        cfg["live2d"]["name"] = persona["live2d"]
        changes.append(f"live2d model {persona['live2d']}")
    return changes
