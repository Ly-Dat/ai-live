"""Let viewers steer the Novel reader / Story reader with comments - safely.

  * Commands ("!tiep" next chapter / panel, "!lai" read again, "!truoc" back) only happen when `threshold` DIFFERENT viewers
    send the same command within `window` seconds, so one troll cannot skip the story.
  * Chapter vote: at the end of a chapter the host asks "1 = next chapter, 2 = read it again"; one vote per viewer, the
    option with more votes wins, a tie or no votes means "next".
The live app (my_handle) calls consume() for every comment and swallows the ones that are commands / votes (no AI reply);
the reader process calls heartbeat() and pop_pending() / end_vote(). They share one small JSON file. Pure functions, unit tested.
"""
import json
import os
import time
import unicodedata
from typing import Dict, List, Optional

DEFAULT_PATH = os.path.join("data", "reader_cmds.json")
ALIVE_S = 15.0   # the reader must have sent a heartbeat this recently, otherwise comments are left alone

ALIASES = {
    "next": ("next", "tiep", "tieptheo", "chuongtiep", "chuongsau", "sau"),
    "prev": ("back", "prev", "truoc", "chuongtruoc"),
    "repeat": ("repeat", "again", "lai", "doclai"),
}
ACK_VI = {
    "next": "Cả nhà muốn nghe tiếp, mình đọc tiếp nha.",
    "prev": "Cả nhà muốn quay lại, mình đọc lại phần trước nha.",
    "repeat": "Mình đọc lại đoạn này nha.",
}
VOTE_OPTIONS = ("next", "repeat")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def parse(text: str) -> Optional[str]:
    """'!tiếp' -> 'next', '!Lại' -> 'repeat', anything else -> None."""
    t = _fold(text).strip()
    if not t.startswith("!") or len(t) > 24:
        return None
    word = t[1:].replace(" ", "")
    for cmd, names in ALIASES.items():
        if word in names:
            return cmd
    return None


def hint(threshold: int) -> str:
    return f"{threshold}+ bạn comment: !tiep = tiếp · !lai = đọc lại · !truoc = quay lại"


def _read(path: str) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(path: str, st: Dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(tmp, path)


def _alive(st: Dict, now: float) -> bool:
    return bool(st.get("enabled")) and now - float(st.get("beat") or 0) <= ALIVE_S


# ------------------------------------------------------------------ reader side
def heartbeat(path: str, enabled: bool, threshold: int = 3, window: float = 30.0, now: Optional[float] = None) -> None:
    """Called every few seconds by the reader: its settings and "I am alive". Separate file, so it never races with the vote counting."""
    now = time.time() if now is None else now
    _write(path + ".beat", {"enabled": bool(enabled), "threshold": max(1, int(threshold)), "window": float(window), "beat": now})


def pop_pending(path: str) -> Optional[str]:
    """The oldest command viewers asked for (and clears the queue), or None."""
    st = _read(path)
    pend: List[str] = st.get("pending") or []
    if not pend:
        return None
    st["pending"] = []
    _write(path, st)
    return pend[0]


def begin_vote(path: str, seconds: float, now: Optional[float] = None) -> None:
    now = time.time() if now is None else now
    st = _read(path)
    st["vote"] = {"ends": now + seconds, "ballots": {}}
    _write(path, st)


def end_vote(path: str) -> Dict:
    """Closes the vote. {'winner': 'next'|'repeat', 'next': n, 'repeat': n}; no votes / tie -> 'next'."""
    st = _read(path)
    v = st.pop("vote", None) or {"ballots": {}}
    _write(path, st)
    counts = {o: sum(1 for x in v["ballots"].values() if x == o) for o in VOTE_OPTIONS}
    winner = "repeat" if counts["repeat"] > counts["next"] else "next"
    return dict(counts, winner=winner)


# ------------------------------------------------------------------ live app side
def consume(path: str, username: str, text: str, now: Optional[float] = None) -> bool:
    """True when the comment was a reader command or a vote (counted; the caller must not answer it)."""
    now = time.time() if now is None else now
    cfg = _read(path + ".beat")
    if not _alive(cfg, now):
        return False
    st = _read(path)
    who = _fold(username).strip() or "?"
    v = st.get("vote")
    t = _fold(text).strip()
    if v and now <= float(v.get("ends") or 0) and t in ("1", "2"):
        v["ballots"][who] = VOTE_OPTIONS[int(t) - 1]
        _write(path, st)
        return True
    cmd = parse(text)
    if not cmd:
        return False
    votes = st.setdefault("votes", {})
    window = float(cfg.get("window") or 30.0)
    bucket = {u: ts for u, ts in (votes.get(cmd) or {}).items() if now - ts <= window}
    bucket[who] = now
    if len(bucket) >= int(cfg.get("threshold") or 3):
        st.setdefault("pending", []).append(cmd)
        bucket = {}
    votes[cmd] = bucket
    _write(path, st)
    return True
