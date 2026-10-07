"""Live-room templates: one click sets mode, host persona and tour pace for a kind of live.

A template only changes settings the seller can already change in Setup. Anything that needs the seller's own input
(a real prize, a real discount) is listed as an 'idea', never started automatically.
"""
import json
import os
from typing import Dict, List, Tuple

PATH = os.path.join("data", "live_templates.json")
FIELDS = [("mode", "Mode"), ("persona_id", "Host"), ("auto_tour", "Product tour"), ("tour_min_minutes", "Tour min (min)"),
          ("tour_max_minutes", "Tour max (min)"), ("tour_quiet", "Quiet seconds"), ("gifts", "Thank gifts and follows"),
          ("joins", "Greet new viewers"), ("returning_viewers", "Welcome back returning viewers")]


def load(path: str = PATH) -> List[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return list(json.load(f).get("templates", []))
    except (OSError, ValueError):
        return []


def for_mode(templates: List[Dict], mode: str) -> List[Dict]:
    want = "creator" if mode == "creator" else "seller"
    return [t for t in templates if t.get("mode", "seller") == want]


def apply(setup: Dict, template: Dict) -> Tuple[Dict, List[Tuple[str, object, object]]]:
    """Return (new_setup, [(label, old, new) for each setting that really changes])."""
    new = dict(setup)
    changes = []
    for key, label in FIELDS:
        if key in template and template[key] != setup.get(key):
            changes.append((label, setup.get(key), template[key]))
            new[key] = template[key]
    new["template_id"] = template["id"]
    return new, changes


def show(value) -> str:
    if value is True:
        return "on"
    if value is False:
        return "off"
    return str(value)
