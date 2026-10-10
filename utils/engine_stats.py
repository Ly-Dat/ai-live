"""Rolling speed numbers for the two slow parts of a live: the AI reply (llm) and the voice (tts).

Kept in memory for the current run and saved to data/engine_stats.json now and then, so Home can show them.
"""
import json
import os
import threading
import time
from collections import deque
from typing import Dict, Optional

PATH = os.path.join("data", "engine_stats.json")
KINDS = ("llm", "tts")
_WINDOW = 200
_lock = threading.Lock()
_ms = {k: deque(maxlen=_WINDOW) for k in KINDS}
_count = {k: {"calls": 0, "failed": 0, "cached": 0, "fallback": 0, "timeout": 0} for k in KINDS}
_last_error = {k: "" for k in KINDS}
_since_save = 0
SAVE = True            # tests switch this off
_last_save = 0.0
SAVE_EVERY_S = 3.0     # the web UI runs in another process and reads the saved file


def reset() -> None:
    global _since_save
    with _lock:
        for k in KINDS:
            _ms[k].clear()
            _count[k] = {"calls": 0, "failed": 0, "cached": 0, "fallback": 0, "timeout": 0}
            _last_error[k] = ""
        _since_save = 0


def record(kind: str, ms: float, ok: bool = True, cached: bool = False, fallback: bool = False,
           timeout: bool = False, error: str = "", save_to: Optional[str] = PATH) -> None:
    global _since_save
    if kind not in KINDS:
        return
    with _lock:
        c = _count[kind]
        c["calls"] += 1
        c["failed"] += 0 if ok else 1
        c["cached"] += 1 if cached else 0
        c["fallback"] += 1 if fallback else 0
        c["timeout"] += 1 if timeout else 0
        if ok:
            _ms[kind].append(float(ms))
        if error:
            _last_error[kind] = str(error)[:200]
        _since_save += 1
        due = time.time() - _last_save >= SAVE_EVERY_S
    if due and save_to and SAVE:
        save(save_to)


def _pct(values, q: float) -> int:
    if not values:
        return 0
    v = sorted(values)
    return int(round(v[min(len(v) - 1, int(q * len(v)))]))


def summary() -> Dict:
    with _lock:
        out = {}
        for k in KINDS:
            c = dict(_count[k])
            real = _ms[k]
            n = c["calls"]
            out[k] = {**c, "p50_ms": _pct(real, 0.5), "p95_ms": _pct(real, 0.95),
                      "cache_rate": round(c["cached"] / n, 2) if n else 0.0,
                      "fail_rate": round(c["failed"] / n, 2) if n else 0.0, "last_error": _last_error[k]}
        return out


def save(path: str = PATH) -> None:
    global _since_save, _last_save
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"at": time.time(), "stats": summary()}, f)
        os.replace(tmp, path)
        _since_save = 0
        _last_save = time.time()
    except OSError:
        _last_save = time.time()


def load(path: str = PATH) -> Dict:
    """The saved numbers {"at": time, "stats": summary()}; {} when there are none. The web UI reads this."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
