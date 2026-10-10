"""Your character's journey: a level, a streak, achievements and cosmetic unlocks built from your real live sessions.

Nothing is invented: every number comes from the analytics logs (log/analytics/session-YYYYMMDD*.jsonl). Unlocks are cosmetic only
(overlay frames, idle motions, extra outfits); they never change what the AI says or what viewers are told.

XP = 50 per live + 2 per viewer question answered + 5 per gift + 10 per hour on air. Level n starts at 50*n*(n-1) XP.
"""
import datetime
import json
import os
from typing import Dict, Iterable, List

from utils import live_analytics, milestones, recap

PATH = os.path.join("data", "avatar", "bond.json")
FRAMES = [("none", 1), ("glow", 2), ("neon", 3), ("sakura", 4), ("gold", 6)]
MOTIONS = [("bob", 1), ("still", 1), ("breathe", 2), ("sway", 3), ("float", 5)]
DAILY_GOAL = 10   # viewer questions answered in a day


def level_for(xp: int) -> int:
    lv = 1
    while 50 * (lv + 1) * lv <= xp:
        lv += 1
    return lv


def max_looks(level: int) -> int:
    return min(8, 1 + level // 2)


def unlocked(options, level: int) -> List[str]:
    return [name for name, need in options if level >= need]


def next_unlock(level: int) -> str:
    cands = [(need, f"{name} frame") for name, need in FRAMES if need > level] + \
            [(need, f"{name} motion") for name, need in MOTIONS if need > level]
    lk = next((lv for lv in range(level + 1, 20) if max_looks(lv) > max_looks(level)), None)
    if lk and max_looks(lk) <= 8:
        cands.append((lk, "one more outfit slot"))
    if not cands:
        return ""
    need = min(c[0] for c in cands)
    return f"Level {need}: " + ", ".join(sorted(n for lv, n in cands if lv == need))


ACHIEVEMENTS = [
    ("first_live", "First live", "Go live once", lambda t: t["lives"] >= 1, lambda t: (t["lives"], 1)),
    ("lives_5", "Regular", "Go live 5 times", lambda t: t["lives"] >= 5, lambda t: (t["lives"], 5)),
    ("lives_25", "Veteran", "Go live 25 times", lambda t: t["lives"] >= 25, lambda t: (t["lives"], 25)),
    ("answers_10", "Helpful", "Answer 10 viewer questions", lambda t: t["answered"] >= 10, lambda t: (t["answered"], 10)),
    ("answers_100", "Go-to seller", "Answer 100 viewer questions", lambda t: t["answered"] >= 100, lambda t: (t["answered"], 100)),
    ("answers_1000", "Never sleeps", "Answer 1000 viewer questions", lambda t: t["answered"] >= 1000, lambda t: (t["answered"], 1000)),
    ("gift_1", "First gift", "Receive a gift", lambda t: t["gifts"] >= 1, lambda t: (t["gifts"], 1)),
    ("gift_25", "Loved", "Receive 25 gifts", lambda t: t["gifts"] >= 25, lambda t: (t["gifts"], 25)),
    ("streak_3", "On a roll", "Live 3 days in a row", lambda t: t["streak"] >= 3, lambda t: (t["streak"], 3)),
    ("streak_7", "Weekly habit", "Live 7 days in a row", lambda t: t["streak"] >= 7, lambda t: (t["streak"], 7)),
    ("hours_10", "Ten hours", "Spend 10 hours on air", lambda t: t["hours"] >= 10, lambda t: (t["hours"], 10)),
    ("showcase", "Showcase", "Present 10 products in one live", lambda t: t["best_products"] >= 10, lambda t: (t["best_products"], 10)),
]


def compute(summaries: Iterable[Dict], dates, today: datetime.date, answered_today: int = 0) -> Dict:
    sums = list(summaries)
    t = milestones.lifetime(sums)
    t["gifts"] = sum(int(s.get("gifts") or 0) for s in sums)
    t["best_products"] = max([int(s.get("products_pitched") or 0) for s in sums] or [0])
    t["streak"] = recap.streak(dates, today)
    xp = t["lives"] * 50 + t["answered"] * 2 + t["gifts"] * 5 + int(t["hours"] * 10)
    lv = level_for(xp)
    floor_xp, ceil_xp = 50 * lv * (lv - 1), 50 * (lv + 1) * lv
    ach = []
    for aid, title, desc, test, prog in ACHIEVEMENTS:
        have, goal = prog(t)
        ach.append({"id": aid, "title": title, "desc": desc, "done": bool(test(t)), "have": have, "goal": goal})
    return {"xp": xp, "level": lv, "into": xp - floor_xp, "span": ceil_xp - floor_xp, "streak": t["streak"], "lives": t["lives"],
            "answered": t["answered"], "hours": t["hours"], "week": recap.week_count(dates, today), "achievements": ach,
            "goal": DAILY_GOAL, "answered_today": answered_today, "next_unlock": next_unlock(lv)}


def refresh(log_dir: str = "log/analytics", today: datetime.date = None, path: str = PATH) -> Dict:
    """Recompute from the logs, save a small cache for the overlay, and return the full picture."""
    today = today or datetime.date.today()
    sums, files = [], []
    try:
        files = sorted(f for f in os.listdir(log_dir) if f.startswith("session-") and f.endswith(".jsonl"))
    except OSError:
        pass
    answered_today = 0
    stamp = today.strftime("%Y%m%d")
    for f in files:
        try:
            s = live_analytics.summarize(live_analytics.load_events(os.path.join(log_dir, f)))
        except Exception:
            continue
        sums.append(s)
        if stamp in f:
            answered_today += int(s.get("answered") or 0)
    b = compute(sums, recap.session_dates(files), today, answered_today)
    old = load_cache(path)
    cache = {"level": b["level"], "streak": b["streak"], "xp": b["xp"], "done": [a["id"] for a in b["achievements"] if a["done"]],
             "seen": old.get("seen", None)}
    if cache["seen"] is None:   # first run: do not announce what was already earned before this feature existed
        cache["seen"] = list(cache["done"])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(cache, f)
    os.replace(path + ".tmp", path)
    b["new"] = [a for a in b["achievements"] if a["done"] and a["id"] not in cache["seen"]]
    return b


def load_cache(path: str = PATH) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def mark_seen(path: str = PATH) -> None:
    c = load_cache(path)
    c["seen"] = list(c.get("done", []))
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(c, f)
    os.replace(path + ".tmp", path)
