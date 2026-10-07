"""
Post-live recap and streak, pure logic (no UI, no I/O besides parsing file names).

  recap(summary, names)      headline + concrete "do this next live" tips from one session summary
  session_dates(filenames)   dates of sessions from 'session-YYYYMMDD-HHMMSS.jsonl'
  streak(dates, today)       consecutive days with a live, counting back from today (or yesterday)
  week_count(dates, today)   lives in the last 7 days
"""
import datetime
import re
from typing import Dict, Iterable, List, Optional, Set

_ADVICE = {
    "price": "Say the price in the first sentence of the pitch; viewers kept asking.",
    "shipping": "Add a shipping line (time, fee, free-ship threshold) to the product facts.",
    "stock": "Put stock or colour/size availability in the facts, and say it out loud.",
    "options": "List the options (size, colour, variants) in the product facts.",
    "trust": "Add proof: reviews, warranty or a real-use line to the facts. Trust questions mean hesitation.",
    "return": "State the return policy in the pitch; it removes the last objection.",
    "usage": "Add a short how-to-use line to the facts.",
    "buy": "Viewers are ready to buy: repeat how to order, and run a flash sale on it.",
}
_DATE = re.compile(r"session-(\d{8})-\d{6}\.jsonl$")


def recap(s: Dict, names: Optional[Dict[str, str]] = None) -> Dict:
    names = names or {}
    tips: List[str] = []
    interest = s.get("product_interest") or {}
    ranked = sorted(interest.items(), key=lambda kv: -sum(kv[1].values()))
    if ranked:
        pid, intents = ranked[0]
        n = sum(intents.values())
        nm = names.get(pid, pid)
        tips.append(f"{nm} drew the most questions ({n}). Introduce it earlier next live.")
        top_intent = max(intents, key=intents.get)
        if top_intent in _ADVICE:
            tips.append(f"For {nm}: {_ADVICE[top_intent]}")
    if len(ranked) > 1:
        pid, intents = ranked[-1]
        if sum(intents.values()) <= 1 and len(ranked) >= 3:
            tips.append(f"{names.get(pid, pid)} got almost no interest. Reword its pitch or move it later.")
    un = s.get("sales_unmatched", 0)
    if un >= 3:
        tips.append(f"{un} buying questions were not about a specific product. Pin the product on screen so viewers say which one.")
    blocked = s.get("blocked", 0)
    if blocked:
        cats = s.get("blocked_by_category") or {}
        top = max(cats, key=cats.get) if cats else "policy"
        label = str(top).replace("_", " ")
        tips.append(f"{blocked} comment(s) were filtered, mostly '{label}'. Nothing to do; the host did not repeat them.")
    comments = s.get("comments", 0)
    buy = s.get("buy_intent", 0)
    if comments and buy / comments >= 0.15:
        tips.append(_ADVICE["buy"])
    if not tips:
        tips.append("Quiet session. Try a flash sale announcement to give viewers a reason to comment.")
    mins = s.get("duration_min", 0)
    headline = f"{comments} comments from {s.get('unique_viewers', 0)} viewers in {mins} min, {buy} buying signals."
    tips = tips[:4]
    # "actions" are the tips a seller can act on; the filtered-comments note is information only.
    actions = [t for t in tips if "Nothing to do" not in t]
    return {"headline": headline, "tips": tips, "actions": actions}


def session_dates(filenames: Iterable[str]) -> Set[datetime.date]:
    out = set()
    for f in filenames:
        m = _DATE.search(f)
        if m:
            try:
                out.add(datetime.datetime.strptime(m.group(1), "%Y%m%d").date())
            except ValueError:
                pass
    return out


def streak(dates: Set[datetime.date], today: datetime.date) -> int:
    day = today if today in dates else today - datetime.timedelta(days=1)
    n = 0
    while day in dates:
        n += 1
        day -= datetime.timedelta(days=1)
    return n


def week_count(dates: Set[datetime.date], today: datetime.date) -> int:
    return sum(1 for d in dates if 0 <= (today - d).days < 7)
