"""Who is hosting right now: the AI, or you?

You set the hours you will be on camera ("human windows"). Outside them the AI hosts: tour, replies, announcements.
Inside them the AI stays quiet (no tour, no spoken replies) so it never talks over you, and the questions viewers ask
are kept so you can see what came in while you were busy.

Times are the computer's local time. Days: 0 = Monday ... 6 = Sunday. A window may cross midnight (22:00 -> 02:00).
"""
import datetime as dt
import json
import os
import re
from typing import Dict, List, Optional

PATH = os.path.join("data", "coverage.json")
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _minutes(hhmm: str) -> int:
    m = _HHMM.match(hhmm or "")
    if not m:
        raise ValueError(f"Time must look like 19:30, got {hhmm!r}")
    return int(m.group(1)) * 60 + int(m.group(2))


def clean_window(w: Dict) -> Dict:
    days = sorted({int(d) for d in (w.get("days") or []) if 0 <= int(d) <= 6})
    if not days:
        raise ValueError("Pick at least one day.")
    s, e = _minutes(w.get("start")), _minutes(w.get("end"))
    if s == e:
        raise ValueError("Start and end must differ.")
    return {"days": days, "start": f"{s // 60:02d}:{s % 60:02d}", "end": f"{e // 60:02d}:{e % 60:02d}"}


def load(path: str = PATH) -> Dict:
    out = {"enabled": False, "human_windows": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        out["enabled"] = bool(d.get("enabled"))
        for w in d.get("human_windows", []):
            try:
                out["human_windows"].append(clean_window(w))
            except (ValueError, TypeError):
                continue
    except (OSError, ValueError):
        pass
    return out


def save(cfg: Dict, path: str = PATH) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"enabled": bool(cfg.get("enabled")), "human_windows": [clean_window(w) for w in cfg.get("human_windows", [])]},
                  f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _in_window(w: Dict, now: dt.datetime) -> bool:
    t = now.hour * 60 + now.minute
    s, e = _minutes(w["start"]), _minutes(w["end"])
    today, yesterday = now.weekday(), (now.weekday() - 1) % 7
    if s < e:
        return today in w["days"] and s <= t < e
    return (today in w["days"] and t >= s) or (yesterday in w["days"] and t < e)   # crosses midnight


def is_human(cfg: Dict, now: Optional[dt.datetime] = None) -> bool:
    if not cfg.get("enabled"):
        return False
    now = now or dt.datetime.now()
    return any(_in_window(w, now) for w in cfg.get("human_windows", []))


def status(cfg: Dict, now: Optional[dt.datetime] = None) -> Dict:
    """{"who": "ai"|"human", "until": "HH:MM"|None, "day_offset": int} - when the current mode ends."""
    now = (now or dt.datetime.now()).replace(second=0, microsecond=0)
    who = "human" if is_human(cfg, now) else "ai"
    if not cfg.get("enabled") or not cfg.get("human_windows"):
        return {"who": "ai", "until": None, "day_offset": 0}
    t = now
    for _ in range(7 * 24 * 60):
        t += dt.timedelta(minutes=1)
        if ("human" if is_human(cfg, t) else "ai") != who:
            return {"who": who, "until": t.strftime("%H:%M"), "day_offset": (t.date() - now.date()).days}
    return {"who": who, "until": None, "day_offset": 0}


def describe(w: Dict) -> str:
    days = w["days"]
    label = "Every day" if len(days) == 7 else ", ".join(DAY_NAMES[d] for d in days)
    return f"{label} {w['start']}-{w['end']}"


def handoff_questions(events: List[Dict], limit: int = 8) -> List[Dict]:
    """Questions that arrived while you were hosting (kind 'handoff'), newest first."""
    rows = [e for e in events if e.get("kind") == "handoff" and e.get("text")]
    return [{"text": e["text"], "intent": e.get("intent", "chat"), "ts": e["ts"]} for e in reversed(rows)][:limit]
