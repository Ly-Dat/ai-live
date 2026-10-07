"""
Lifetime milestones across all live sessions. Pure logic, real numbers only (no invented progress).

  lifetime(summaries)      totals: lives, hours, comments, answers, viewers' comments handled
  next_milestone(totals)   the nearest unreached milestone with an honest remaining count
"""
from typing import Dict, Iterable, Optional

LIVES = [1, 3, 5, 10, 25, 50, 100]
ANSWERS = [10, 50, 100, 500, 1000, 5000]


def lifetime(summaries: Iterable[Dict]) -> Dict:
    t = {"lives": 0, "minutes": 0.0, "comments": 0, "answered": 0, "buy_intent": 0}
    for s in summaries:
        t["lives"] += 1
        t["minutes"] += float(s.get("duration_min") or 0)
        t["comments"] += int(s.get("comments") or 0)
        t["answered"] += int(s.get("answered") or 0)
        t["buy_intent"] += int(s.get("buy_intent") or 0)
    t["hours"] = round(t["minutes"] / 60, 1)
    return t


def next_milestone(t: Dict) -> Optional[Dict]:
    """Closest upcoming goal by fraction already done; None when everything listed is reached."""
    best = None
    for key, goals, noun in (("lives", LIVES, "lives"), ("answered", ANSWERS, "viewer answers")):
        have = t.get(key, 0)
        goal = next((g for g in goals if g > have), None)
        if goal is None:
            continue
        frac = have / goal
        if best is None or frac > best["fraction"]:
            best = {"key": key, "goal": goal, "have": have, "left": goal - have, "noun": noun, "fraction": frac}
    return best
