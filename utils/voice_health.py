"""Stale-line dropping and TTS failure bookkeeping, pure so it can be tested without audio hardware.

A line that waited too long in the queue (the host was busy, the voice was slow) is dropped instead of being spoken late and
sounding out of touch ("welcome!" two minutes after the viewer left). Voice failures are counted so the header can say the
voice is on its backup or down, instead of the host silently going quiet."""
import json
import os
import time
from typing import Dict, Optional

# seconds a line may wait (from the moment it was queued) before it is no longer worth saying
MAX_AGE = {"entrance": 20, "follow": 30, "comment": 45, "read_comment": 45, "talk": 60, "reply": 60, "gift": 60,
           "schedule": 120, "idle_time_task": 120, "trends_copywriting": 120}
DEFAULT_AGE = 180
NEVER_STALE = {"reread_top_priority", "abnormal_alarm"}
STATE_PATH = os.path.join("data", "voice_state.json")
DOWN_AFTER = 2          # consecutive lines that failed on every voice -> "down"
RECENT_S = 600


def is_stale(msg_type: str, queued_at: Optional[float], now: Optional[float] = None) -> bool:
    if not queued_at or msg_type in NEVER_STALE:
        return False
    now = time.time() if now is None else now
    return now - float(queued_at) > MAX_AGE.get(msg_type, DEFAULT_AGE)


def _load(path: str) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(d: Dict, path: str) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, path)
    except OSError:
        pass


def record(ok: bool, used_backup: bool = False, path: str = STATE_PATH, now: Optional[float] = None) -> Dict:
    """One line finished synthesis: ok = got audio (maybe from the backup voice)."""
    now = time.time() if now is None else now
    d = _load(path)
    d["fails"] = 0 if ok else int(d.get("fails", 0)) + 1
    if used_backup and ok:
        d["backup_at"] = now
    d["ts"] = now
    _save(d, path)
    return d


def record_stale(path: str = STATE_PATH, now: Optional[float] = None) -> None:
    d = _load(path)
    d["stale_dropped"] = int(d.get("stale_dropped", 0)) + 1
    d["ts"] = time.time() if now is None else now
    _save(d, path)


def level(path: str = STATE_PATH, now: Optional[float] = None) -> Dict:
    """{"level": ok|backup|down|unknown, "fails": n, "stale_dropped": n} for the header pill."""
    now = time.time() if now is None else now
    d = _load(path)
    if not d or now - float(d.get("ts") or 0) > 3600:
        return {"level": "unknown", "fails": 0, "stale_dropped": int(d.get("stale_dropped", 0))}
    fails = int(d.get("fails", 0))
    if fails >= DOWN_AFTER:
        lv = "down"
    elif d.get("backup_at") and now - float(d["backup_at"]) < RECENT_S:
        lv = "backup"
    else:
        lv = "ok"
    return {"level": lv, "fails": fails, "stale_dropped": int(d.get("stale_dropped", 0))}


def backup_type(current: str) -> Optional[str]:
    """The free voice to fall back to, or None when the current one already is it."""
    return None if current in ("edge-tts", "none") else "edge-tts"
