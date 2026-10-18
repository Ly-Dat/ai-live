"""Small body gestures for the avatar, chosen from the latest events (pure, tested).

wave on a new viewer, cheer on a gift, nod after an answer, lean towards the camera while pitching. The overlay plays each
for under a second. `id` changes with every new gesture so the page restarts the animation exactly once per event."""
from typing import Dict, List

GESTURES = ("wave", "cheer", "nod", "lean")
WINDOW_S = 2.5


def pick(events: List[Dict], now: float) -> Dict:
    """{"name": gesture or "", "id": event time} for the newest event young enough to deserve one."""
    for e in reversed(events[-40:] if events else []):
        ts = float(e.get("ts") or 0)
        age = now - ts
        if age < 0 or age > WINDOW_S:
            continue
        kind = e.get("kind")
        name = {"entrance": "wave", "gift": "cheer", "answer": "nod", "pitch": "lean"}.get(kind, "")
        if name:
            return {"name": name, "id": ts}
    return {"name": "", "id": 0}
