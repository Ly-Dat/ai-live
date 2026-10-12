"""Small helpers for the speech queue, kept pure so they can be tested without audio hardware."""
import re
from typing import Dict, Iterable


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def is_duplicate(queue: Iterable[Dict], item: Dict) -> bool:
    """True when the same line is already waiting to be spoken (so a burst of identical questions or a repeated pitch
    cannot make the host say it twice in a row). Empty lines are never duplicates."""
    c = _norm(item.get("content"))
    return bool(c) and any(_norm(m.get("content")) == c for m in queue)


STATE_PATH = "data/queue_state.json"


def write_state(queued: int, path: str = STATE_PATH, now: float = 0.0) -> None:
    """The audio side (main.py process) tells the control panel how many lines are waiting."""
    import json, os, time
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"queued": int(queued), "ts": now or time.time()}, f)
    os.replace(tmp, path)


def read_state(path: str = STATE_PATH, now: float = 0.0, max_age: float = 15.0) -> int:
    """Lines waiting, or -1 when unknown (file missing or stale: the app is not running)."""
    import json, time
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        if (now or time.time()) - float(d.get("ts") or 0) > max_age:
            return -1
        return int(d.get("queued", -1))
    except (OSError, ValueError, TypeError):
        return -1
