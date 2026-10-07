"""
Giveaways and polls for the live. Pure state functions (unit tested) + a small JSON file shared by the web UI process
(which starts and stops them) and the live app (which counts entries and speaks the announcements).

Fairness and honesty:
  * One entry per viewer, whole-word keyword match, no weighting: the draw is uniform random among entrants.
  * The announcement always says how many viewers entered; with no entrants nothing is "won".
  * Only the prize / question the seller typed is spoken. Every line still passes the TikTok output filter.
  * Entrant display names live in the state file only until the next giveaway starts (they are needed to announce winners).
"""
import json
import math
import os
import random
import re
import time
import unicodedata
from typing import Dict, List, Optional, Tuple

DEFAULT_PATH = "data/engage.json"

TEMPLATES = {
    "giveaway_start": "Mini game nè cả nhà! Comment \"{keyword}\" để tham gia nhận {prize}. Còn {minutes} phút, mình quay số ngẫu nhiên nha.",
    "giveaway_remind": "Còn khoảng {minutes} phút nữa là quay số nhận {prize}. Comment \"{keyword}\" để tham gia nha, hiện có {n} bạn tham gia.",
    "giveaway_final": "Sắp quay số rồi, dưới một phút nữa thôi! Comment \"{keyword}\" thật nhanh nha.",
    "giveaway_winner": "Quay số xong rồi! Trong {n} bạn tham gia, người may mắn nhận {prize} là {winners}. Chúc mừng nha!",
    "giveaway_none": "Chưa có bạn nào tham gia nên mình chưa quay số được. Lần sau nha!",
    "poll_start": "Bình chọn nè cả nhà: {question} {options}. Comment số để chọn nha.",
    "poll_remind": "Đang bình chọn: {question} Hiện tại {tally}. Comment số để chọn nha.",
    "poll_end": "Kết quả bình chọn: {tally}. {winner}",
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _ukey(name: str) -> str:
    return _fold(name).strip()


# ------------------------------------------------------------------ file
def load_state(path: str = DEFAULT_PATH) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {"giveaway": d.get("giveaway"), "poll": d.get("poll")}
    except (OSError, ValueError):
        return {"giveaway": None, "poll": None}


def save_state(state: Dict, path: str = DEFAULT_PATH) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ------------------------------------------------------------------ giveaway
def start_giveaway(state: Dict, keyword: str, prize: str, minutes: float, winners: int = 1,
                   remind_min: float = 3, now: Optional[float] = None) -> Dict:
    keyword, prize = (keyword or "").strip(), (prize or "").strip()
    if not keyword or not prize:
        raise ValueError("Enter the keyword viewers type and what the prize is.")
    if minutes <= 0:
        raise ValueError("minutes must be > 0")
    now = time.time() if now is None else now
    state["giveaway"] = {
        "active": True, "keyword": keyword, "prize": prize, "started_at": now, "ends_at": now + minutes * 60,
        "winners_wanted": max(1, int(winners)), "remind_sec": max(60, int(remind_min * 60)),
        "entrants": {}, "announced_start": False, "last_announce": 0, "final_done": False, "drawn": False, "winners": [],
    }
    return state


def _keyword_hit(keyword: str, text: str) -> bool:
    k = _fold(keyword).strip()
    return bool(k) and re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", _fold(text)) is not None


def _enter(g: Dict, username: str, text: str, now: float) -> bool:
    if not g or not g.get("active") or now >= g["ends_at"] or not _ukey(username):
        return False
    if not _keyword_hit(g["keyword"], text):
        return False
    g["entrants"].setdefault(_ukey(username), username.strip())
    return True


# ------------------------------------------------------------------ poll
def start_poll(state: Dict, question: str, options: List[str], minutes: float, remind_min: float = 2,
               now: Optional[float] = None) -> Dict:
    options = [o.strip() for o in options if o and o.strip()]
    if not (question or "").strip() or not 2 <= len(options) <= 4:
        raise ValueError("A poll needs a question and 2 to 4 options.")
    if minutes <= 0:
        raise ValueError("minutes must be > 0")
    now = time.time() if now is None else now
    state["poll"] = {
        "active": True, "question": question.strip(), "options": options, "started_at": now, "ends_at": now + minutes * 60,
        "remind_sec": max(60, int(remind_min * 60)), "votes": {}, "announced_start": False, "last_announce": 0, "ended": False,
    }
    return state


_VOTE = re.compile(r"^(?:chon|vote|bau)?\s*([1-4])\s*$")


def _vote(p: Dict, username: str, text: str, now: float) -> bool:
    if not p or not p.get("active") or now >= p["ends_at"] or not _ukey(username):
        return False
    m = _VOTE.match(_fold(text).strip())
    if not m:
        return False
    idx = int(m.group(1)) - 1
    if idx >= len(p["options"]):
        return False
    p["votes"].setdefault(_ukey(username), idx)  # first vote counts
    return True


def tally(p: Dict) -> List[int]:
    counts = [0] * len(p["options"])
    for idx in p["votes"].values():
        counts[idx] += 1
    return counts


def consume(state: Dict, username: str, text: str, now: Optional[float] = None) -> Optional[str]:
    """Count a comment as a giveaway entry or a poll vote. Returns 'giveaway', 'poll' or None (state mutated in place)."""
    now = time.time() if now is None else now
    hit = None
    if _enter(state.get("giveaway"), username, text, now):
        hit = "giveaway"
    if _vote(state.get("poll"), username, text, now):
        hit = hit or "poll"
    return hit


# ------------------------------------------------------------------ announcements
def _tpl(templates: Optional[Dict], key: str) -> str:
    return (templates or {}).get(key) or TEMPLATES[key]


def _poll_tally_text(p: Dict) -> str:
    return ", ".join(f"{o} {c} phiếu" for o, c in zip(p["options"], tally(p)))


def next_announcement(state: Dict, now: Optional[float] = None, templates: Optional[Dict] = None,
                      rng=None) -> Tuple[Optional[str], Dict]:
    """The next thing the host should say (or None), and the updated state. One announcement per call."""
    now = time.time() if now is None else now
    rng = rng or random.SystemRandom()
    g, p = state.get("giveaway"), state.get("poll")
    if g and g.get("active"):
        left = g["ends_at"] - now
        mins = max(1, math.ceil(left / 60))
        if not g["announced_start"]:
            g.update(announced_start=True, last_announce=now)
            return _tpl(templates, "giveaway_start").format(keyword=g["keyword"], prize=g["prize"], minutes=mins), state
        if left <= 0 and not g["drawn"]:
            names = list(g["entrants"].values())
            g.update(active=False, drawn=True)
            if not names:
                return _tpl(templates, "giveaway_none"), state
            g["winners"] = rng.sample(names, min(g["winners_wanted"], len(names)))
            return _tpl(templates, "giveaway_winner").format(n=len(names), prize=g["prize"], winners=", ".join(g["winners"])), state
        if 0 < left <= 60 and not g["final_done"]:
            g.update(final_done=True, last_announce=now)
            return _tpl(templates, "giveaway_final").format(keyword=g["keyword"]), state
        if left > 90 and now - g["last_announce"] >= g["remind_sec"]:
            g["last_announce"] = now
            return _tpl(templates, "giveaway_remind").format(minutes=mins, prize=g["prize"], keyword=g["keyword"], n=len(g["entrants"])), state
    if p and p.get("active"):
        left = p["ends_at"] - now
        if not p["announced_start"]:
            p.update(announced_start=True, last_announce=now)
            opts = ", ".join(f"{i + 1} là {o}" for i, o in enumerate(p["options"]))
            return _tpl(templates, "poll_start").format(question=p["question"], options=opts), state
        if left <= 0 and not p["ended"]:
            p.update(active=False, ended=True)
            counts = tally(p)
            if sum(counts) == 0:
                winner = "Chưa có bạn nào bình chọn."
            else:
                top = max(counts)
                leaders = [o for o, c in zip(p["options"], counts) if c == top]
                winner = f"Lựa chọn nhiều nhất là {leaders[0]}." if len(leaders) == 1 else "Các lựa chọn đang bằng nhau!"
            return _tpl(templates, "poll_end").format(tally=_poll_tally_text(p), winner=winner), state
        if left > 60 and now - p["last_announce"] >= p["remind_sec"]:
            p["last_announce"] = now
            return _tpl(templates, "poll_remind").format(question=p["question"], tally=_poll_tally_text(p)), state
    return None, state


def stop(state: Dict, which: str) -> Dict:
    if state.get(which):
        state[which]["active"] = False
    return state
