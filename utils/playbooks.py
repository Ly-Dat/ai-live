"""Campaign playbooks: one named preset that sets how the host behaves for the next live (pure, tested).

A playbook only changes settings the seller could change by hand: minutes per product, how pushy the pacing is, and whether
English comments get English answers. The active one is stored in data/active_playbook.json; product_tour.py reads it."""
import json
import os
import time
from typing import Dict, Optional

PATH = os.path.join("data", "active_playbook.json")

PLAYBOOKS: Dict[str, Dict] = {
    "steady": {"label": "Steady day", "about": "Normal pace: 5-10 minutes per product, adapts to chat.",
               "min_minutes": 5.0, "max_minutes": 10.0, "adaptive": True, "english": True},
    "launch": {"label": "New product launch", "about": "Longer on each product (8-14 min) so every question gets time; adapts to chat.",
               "min_minutes": 8.0, "max_minutes": 14.0, "adaptive": True, "english": True},
    "flash": {"label": "Fast flash-sale hour", "about": "Short rounds (2-4 min) so more products get seen; fixed pace, no stretching.",
              "min_minutes": 2.0, "max_minutes": 4.0, "adaptive": False, "english": True},
    "warmup": {"label": "Slow chat warm-up", "about": "Quiet room: 3-6 minutes per product, moves on quickly when nobody replies.",
               "min_minutes": 3.0, "max_minutes": 6.0, "adaptive": True, "english": False},
}
DEFAULT = "steady"


def get(name: str) -> Dict:
    return dict(PLAYBOOKS.get(name) or PLAYBOOKS[DEFAULT], key=name if name in PLAYBOOKS else DEFAULT)


def activate(name: str, path: str = PATH, now: Optional[float] = None) -> Dict:
    pb = get(name)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"key": pb["key"], "at": time.time() if now is None else now}, f)
    return pb


def active(path: str = PATH) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return get(str(json.load(f).get("key")))
    except (OSError, ValueError, AttributeError):
        return get(DEFAULT)
