"""
Opt-in "welcome back" for returning viewers. Privacy first:
  * OFF by default (data/setup.json: returning_viewers).
  * Only a salted SHA-1 of the viewer name is stored, with a visit count and timestamps; never the name itself.
  * The salt lives in the same file; delete the file ("Forget all viewers") and nobody can be recognised any more.
A "visit" is an entrance at least `gap_hours` after the viewer's previous one, so refreshing the app is not a new visit.
"""
import hashlib
import json
import os
import random
import secrets
import threading
import time
from typing import Optional

GREETINGS = [
    "Chào mừng {name} quay lại nha, vui quá!",
    "Ồ {name} lại ghé live rồi, mừng bạn quay lại nè!",
    "{name} quay lại rồi, cả nhà vỗ tay chào mừng nào!",
]
GREETINGS_MANY = [
    "{name} lại ở đây rồi, fan cứng của live mình đây nè, cảm ơn bạn nhiều!",
    "Bạn {name} ghé live nhiều lần rồi, cảm ơn bạn luôn đồng hành nha!",
]
MAX_VIEWERS = 20000


class ViewerBook:
    def __init__(self, path: str, gap_hours: float = 6.0):
        self.path = path
        self.gap = gap_hours * 3600
        self._lock = threading.Lock()
        self.data = {"salt": secrets.token_hex(8), "viewers": {}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict) and "salt" in loaded:
                self.data = loaded
                self.data.setdefault("viewers", {})
        except (OSError, ValueError):
            pass

    def _key(self, name: str) -> str:
        return hashlib.sha1((self.data["salt"] + (name or "").strip().lower()).encode("utf-8")).hexdigest()[:16]

    def visit(self, name: str, now: Optional[float] = None) -> int:
        """Record an entrance. Returns how many EARLIER visits this viewer had (0 = new, or same visit)."""
        if not (name or "").strip():
            return 0
        now = time.time() if now is None else now
        k = self._key(name)
        with self._lock:
            v = self.data["viewers"].get(k)
            if v is None:
                self.data["viewers"][k] = {"first": now, "last": now, "visits": 1}
                self._trim()
                self._save()
                return 0
            fresh = now - v["last"] >= self.gap
            before = v["visits"] if fresh else v["visits"] - 1
            if fresh:
                v["visits"] += 1
            v["last"] = now
            self._save()
            return before if fresh else 0

    def _trim(self) -> None:
        viewers = self.data["viewers"]
        if len(viewers) > MAX_VIEWERS:
            for k in sorted(viewers, key=lambda x: viewers[x]["last"])[: len(viewers) - MAX_VIEWERS]:
                del viewers[k]

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f)
        except OSError:
            pass

    def count(self) -> int:
        return len(self.data["viewers"])

    def forget_all(self) -> None:
        with self._lock:
            self.data = {"salt": secrets.token_hex(8), "viewers": {}}
            try:
                os.remove(self.path)
            except OSError:
                pass


def greeting(name: str, earlier_visits: int, rng=random) -> Optional[str]:
    """None for a first-time viewer; otherwise a short Vietnamese welcome-back line."""
    if earlier_visits <= 0 or not (name or "").strip():
        return None
    pool = GREETINGS_MANY if earlier_visits >= 3 else GREETINGS
    return rng.choice(pool).format(name=name.strip())
