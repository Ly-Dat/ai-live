"""
Habit helpers for the Home tab. Honest by design: every number comes from the seller's own session logs, nothing is
invented, and a missed day never costs the seller anything (no streak-loss pressure).

  weekly_progress(dates, today, goal)   lives in the last 7 days vs. the seller's own weekly goal
  best_hour(sessions)                   the start hour whose lives drew the most comments per minute (needs >= 3 lives)
  next_live_tasks(tips, done_ids)       the last recap's tips as a checklist for the next live
  load_plan / save_plan                 which tasks are ticked; resets when a new session appears
"""
import datetime
import hashlib
import json
import os
from typing import Dict, Iterable, List, Optional, Set

from . import recap


def weekly_progress(dates: Set[datetime.date], today: datetime.date, goal: int = 3) -> Dict:
    goal = max(1, min(7, int(goal or 3)))
    done = recap.week_count(dates, today)
    return {"done": done, "goal": goal, "left": max(0, goal - done), "hit": done >= goal}


def best_hour(sessions: Iterable[Dict], min_sessions: int = 3) -> Optional[Dict]:
    """sessions: dicts with started_at (epoch), comments, duration_min. Returns {'hour','rate','overall','n'} or None."""
    by_hour: Dict[int, List[float]] = {}
    total_c, total_m, n = 0.0, 0.0, 0
    for s in sessions:
        ts, mins = s.get("started_at"), float(s.get("duration_min") or 0)
        if not ts or mins < 5:  # too short to say anything
            continue
        n += 1
        c = float(s.get("comments") or 0)
        total_c += c
        total_m += mins
        h = datetime.datetime.fromtimestamp(ts).hour
        by_hour.setdefault(h, [0.0, 0.0])
        by_hour[h][0] += c
        by_hour[h][1] += mins
    if n < min_sessions or len(by_hour) < 2 or total_m <= 0:
        return None
    rates = {h: c / m for h, (c, m) in by_hour.items()}
    h = max(rates, key=rates.get)
    overall = total_c / total_m
    if rates[h] <= overall * 1.1:  # no meaningful difference: say nothing rather than invent a pattern
        return None
    return {"hour": h, "rate": round(rates[h], 1), "overall": round(overall, 1), "n": n}


def _tid(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def next_live_tasks(tips: List[str], done_ids: Iterable[str] = ()) -> List[Dict]:
    done = set(done_ids)
    return [{"id": _tid(t), "text": t, "done": _tid(t) in done} for t in tips]


def load_plan(path: str, session_key: str) -> Set[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return set(d.get("done", [])) if d.get("session") == session_key else set()
    except (OSError, ValueError):
        return set()


def save_plan(path: str, session_key: str, done: Iterable[str]) -> None:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"session": session_key, "done": sorted(set(done))}, f)
    except OSError:
        pass
