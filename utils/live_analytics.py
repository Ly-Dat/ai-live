"""
Live-session analytics: what viewers asked, what the AI answered, what the compliance filter blocked.

Design
  * Every interesting thing is one JSON line in log/analytics/session-<timestamp>.jsonl (append-only, crash safe).
  * `summarize(events)` is a pure function; the live app, the web UI dashboard and `report_session.py` all use it.
  * Viewer names are stored as a short salted hash, never in clear text (privacy by default).

Event kinds: comment, answer, blocked, pitch, product_pop, gift, entrance
"""
import hashlib
import json
import os
import re
import threading
import time
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional

from .tiktok_safety import fold

# Intent -> accent-folded trigger phrases. Order matters: the first matching intent wins.
INTENT_RULES = [
    ("buy", ["chot", "len don", "dat hang", "dat luon", "mua", "order", "xin link", "cho minh 1", "cho em 1", "lay 1", "lay cai"]),
    ("price", ["gia", "bao nhieu", "nhieu tien", "bn", "gia ca", "re khong", "sale"]),
    ("shipping", ["ship", "giao hang", "van chuyen", "bao lau", "freeship", "cod"]),
    ("options", ["size", "mau", "kich co", "kich thuoc", "loai nao", "mau gi"]),
    ("stock", ["con hang", "het hang", "con khong", "con size"]),
    ("trust", ["that khong", "co that", "chinh hang", "uy tin", "lua dao", "hang gia", "review"]),
    ("return", ["doi tra", "hoan tien", "bao hanh", "tra hang"]),
    ("usage", ["cach dung", "su dung", "dung sao", "huong dan", "cach giat"]),
]
SALES_INTENTS = {"buy", "price", "shipping", "options", "stock", "trust", "return", "usage"}


def classify_intent(text: str) -> str:
    """Return the viewer's intent ('buy', 'price', ... or 'chat') from an accent-insensitive keyword match."""
    folded = fold(text or "")
    for intent, words in INTENT_RULES:
        for w in words:
            if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", folded):
                return intent
    return "chat"


def _short_hash(name: str, salt: str) -> str:
    return hashlib.sha1((salt + (name or "")).encode("utf-8")).hexdigest()[:8]


class LiveAnalytics:
    """Thread-safe recorder. Disabled instances accept calls and do nothing."""

    def __init__(self, log_dir: str = "log/analytics", enable: bool = True, max_memory_events: int = 5000):
        self.enable = enable
        self.log_dir = log_dir
        self.salt = hashlib.sha1(str(time.time()).encode()).hexdigest()[:6]
        self.events: List[Dict] = []
        self.max_memory_events = max_memory_events
        self._lock = threading.Lock()
        self._path: Optional[str] = None

    @property
    def path(self) -> Optional[str]:
        return self._path

    def record(self, kind: str, **fields) -> None:
        if not self.enable:
            return
        ev = {"ts": round(time.time(), 2), "kind": kind}
        user = fields.pop("user", None)
        if user is not None:
            ev["user"] = _short_hash(user, self.salt)
        if "text" in fields and isinstance(fields["text"], str):
            fields["text"] = fields["text"][:160]
        ev.update(fields)
        with self._lock:
            self.events.append(ev)
            if len(self.events) > self.max_memory_events:
                del self.events[: len(self.events) - self.max_memory_events]
            try:
                if self._path is None:
                    os.makedirs(self.log_dir, exist_ok=True)
                    self._path = os.path.join(self.log_dir, time.strftime("session-%Y%m%d-%H%M%S.jsonl"))
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            except OSError:
                pass  # analytics must never break the live

    def summary(self) -> Dict:
        with self._lock:
            return summarize(list(self.events))


def load_events(path: str) -> List[Dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


def latest_session_file(log_dir: str = "log/analytics") -> Optional[str]:
    if not os.path.isdir(log_dir):
        return None
    files = sorted(f for f in os.listdir(log_dir) if f.startswith("session-") and f.endswith(".jsonl"))
    return os.path.join(log_dir, files[-1]) if files else None


def summarize(events: Iterable[Dict], hot_window_sec: int = 300) -> Dict:
    """Aggregate events into the numbers a seller cares about."""
    events = list(events)
    comments = [e for e in events if e["kind"] == "comment"]
    answers = [e for e in events if e["kind"] == "answer"]
    blocked = [e for e in events if e["kind"] == "blocked"]
    pitches = [e for e in events if e["kind"] == "pitch"]
    intents = Counter(e.get("intent", "chat") for e in comments)
    sales_comments = [e for e in comments if e.get("intent") in SALES_INTENTS]
    by_product: Dict[str, Counter] = defaultdict(Counter)
    for e in sales_comments:
        if e.get("product_id"):
            by_product[e["product_id"]][e["intent"]] += 1
    now = events[-1]["ts"] if events else time.time()
    hot = Counter(
        e["product_id"] for e in sales_comments if e.get("product_id") and now - e["ts"] <= hot_window_sec
    )
    blocked_cat = Counter(c for e in blocked for c in (e.get("categories") or ["unknown"]))
    answer_src = Counter(e.get("source", "llm") for e in answers)
    answered = len(answers)
    start = events[0]["ts"] if events else None
    return {
        "started_at": start,
        "duration_min": round((now - start) / 60, 1) if start else 0,
        "comments": len(comments),
        "unique_viewers": len({e.get("user") for e in comments if e.get("user")}),
        "sales_comments": len(sales_comments),
        "buy_intent": intents.get("buy", 0),
        "intents": dict(intents.most_common()),
        "answered": answered,
        "answer_sources": dict(answer_src),
        "blocked": len(blocked),
        "blocked_by_category": dict(blocked_cat.most_common()),
        "blocked_input": sum(1 for e in blocked if e.get("scope") == "input"),
        "blocked_output": sum(1 for e in blocked if e.get("scope") == "output"),
        "pitches": len(pitches),
        "products_pitched": len({e.get("product_id") for e in pitches if e.get("product_id")}),
        "gifts": sum(1 for e in events if e["kind"] == "gift"),
        "entrances": sum(1 for e in events if e["kind"] == "entrance"),
        "product_interest": {pid: dict(c) for pid, c in sorted(by_product.items(), key=lambda kv: -sum(kv[1].values()))},
        "hot_products": [pid for pid, _ in hot.most_common(3)],
    }


def report_markdown(summary: Dict, names: Optional[Dict[str, str]] = None, shop_name: str = "") -> str:
    """Human-readable post-live report. `names` maps product_id -> display name."""
    names = names or {}
    s = summary
    title = f"# Live session report{' - ' + shop_name if shop_name else ''}"
    lines = [
        title, "",
        f"- Duration: **{s['duration_min']} min**",
        f"- Comments: **{s['comments']}** from **{s['unique_viewers']}** viewers; **{s['sales_comments']}** were shopping questions "
        f"(**{s['buy_intent']}** buying signals)",
        f"- AI answers: **{s['answered']}** ({', '.join(f'{k}: {v}' for k, v in s['answer_sources'].items()) or 'none'})",
        f"- Products pitched: **{s['products_pitched']}** ({s['pitches']} pitches)",
        f"- Compliance: **{s['blocked']}** messages blocked or masked "
        f"({s['blocked_input']} viewer comments, {s['blocked_output']} AI lines caught before speaking)",
        "",
        "## What viewers wanted", "",
    ]
    if s["intents"]:
        lines += ["| Intent | Count |", "|---|---|"] + [f"| {k} | {v} |" for k, v in s["intents"].items()]
    else:
        lines.append("No comments recorded.")
    lines += ["", "## Product interest", ""]
    if s["product_interest"]:
        lines += ["| Product | Questions | Breakdown |", "|---|---|---|"]
        for pid, c in s["product_interest"].items():
            lines.append(f"| {names.get(pid, pid)} | {sum(c.values())} | {', '.join(f'{k}: {v}' for k, v in c.items())} |")
    else:
        lines.append("No product-specific questions.")
    if s["blocked_by_category"]:
        lines += ["", "## Compliance log (by category)", "", "| Category | Hits |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in s["blocked_by_category"].items()]
    lines += ["", "## Suggested follow-ups", ""]
    base = len(lines)
    top = next(iter(s["product_interest"]), None)
    if top:
        lines.append(f"- Pitch **{names.get(top, top)}** earlier next time: it drew the most questions.")
    if s["intents"].get("trust"):
        lines.append("- Several viewers asked whether the products are genuine: add proof (origin, certificates) to the catalog FAQ.")
    if s["intents"].get("shipping") or s["intents"].get("return"):
        lines.append("- Fill the `shipping` / `return_policy` fields so the AI can answer instantly.")
    if s["blocked_output"]:
        lines.append("- Review the pitch templates: the output filter caught lines the AI was about to say.")
    if len(lines) == base:
        lines.append("- Nothing to flag.")
    return "\n".join(lines) + "\n"
