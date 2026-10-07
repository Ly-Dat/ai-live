"""Best moments of a live: the busiest minutes, so you can jump to them in TikTok's replay and cut clips.

We do not record video, so this only says WHEN things happened (minutes from the start of the session) and what.
Counts come from the analytics log; no viewer names are kept.
"""
from collections import defaultdict
from typing import Dict, Iterable, List

WEIGHTS = {"comment": 1, "gift": 3, "buy": 2, "shoutout": 2}


def _clock(sec: float) -> str:
    sec = int(max(0, sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def best_moments(events: Iterable[Dict], window: int = 60, top: int = 5, min_score: int = 4) -> List[Dict]:
    """Top busy windows, best first. `window` seconds wide, never overlapping the same window twice."""
    events = [e for e in events if isinstance(e, dict) and "ts" in e]
    if not events:
        return []
    start = events[0]["ts"]
    buckets = defaultdict(lambda: {"comments": 0, "gifts": 0, "buy": 0, "score": 0, "text": ""})
    for e in events:
        k = int((e["ts"] - start) // window)
        b = buckets[k]
        kind = e.get("kind")
        if kind == "comment":
            b["comments"] += 1
            b["score"] += WEIGHTS["comment"]
            if e.get("intent") == "buy":
                b["buy"] += 1
                b["score"] += WEIGHTS["buy"]
                b["text"] = e.get("text") or b["text"]
            elif not b["text"] and e.get("text") and e.get("intent") != "engage":
                b["text"] = e["text"]
        elif kind == "gift":
            b["gifts"] += int(e.get("num") or 1) if str(e.get("num") or 1).isdigit() else 1
            b["score"] += WEIGHTS["gift"]
        elif kind == "shoutout":
            b["score"] += WEIGHTS["shoutout"]
    ranked = sorted(((k, b) for k, b in buckets.items() if b["score"] >= min_score), key=lambda kv: -kv[1]["score"])
    out = []
    for k, b in ranked[:top]:
        out.append({"at": _clock(k * window), "offset_s": k * window, "comments": b["comments"],
                    "gifts": b["gifts"], "buy": b["buy"], "score": b["score"], "sample": (b["text"] or "")[:80]})
    return out


def as_text(moments: List[Dict]) -> str:
    """Copy-paste list for a notes app or a caption."""
    lines = []
    for m in sorted(moments, key=lambda m: m["offset_s"]):
        bits = [f"{m['comments']} comments"]
        if m["buy"]:
            bits.append(f"{m['buy']} buying signals")
        if m["gifts"]:
            bits.append(f"{m['gifts']} gifts")
        lines.append(f"{m['at']}  {', '.join(bits)}" + (f'  "{m["sample"]}"' if m["sample"] else ""))
    return "\n".join(lines)
