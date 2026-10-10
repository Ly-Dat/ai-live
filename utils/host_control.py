"""Manual control over the AI host: pause it, or take over yourself, with one click.

States: "live" (the AI hosts), "paused" (the AI says nothing; comments are still collected), "takeover" (you are
hosting; same silence, but shown differently so you remember why). Questions that arrive while silent are kept in the
analytics log as hand-offs, exactly like the 'I am hosting' hours in coverage.py.
"""
import json
import os
import time
from typing import Dict

PATH = os.path.join("data", "host_control.json")
STATES = ("live", "paused", "takeover")


def load(path: str = PATH) -> Dict:
    out = {"state": "live", "since": 0.0}
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        if d.get("state") in STATES:
            out = {"state": d["state"], "since": float(d.get("since") or 0)}
    except (OSError, ValueError, TypeError):
        pass
    return out


def set_state(state: str, path: str = PATH, now: float = 0.0) -> Dict:
    if state not in STATES:
        raise ValueError(f"State must be one of {', '.join(STATES)}.")
    d = {"state": state, "since": now or time.time()}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, path)
    return d


def is_silent(path: str = PATH) -> bool:
    return load(path)["state"] != "live"
