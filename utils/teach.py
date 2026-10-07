"""
Teach your host: questions the AI was not sure about, and answers the seller teaches once.

  is_unsure(reply)                    does an AI reply admit it does not know? (matches the "I am not sure" rule in the prompt)
  pending(events, book)               distinct unanswered questions from the session logs, most asked first
  TaughtBook(path)                    data/taught.json: taught Q&A + ignored questions; answer(text) is used before the LLM

A taught answer is only ever what the seller typed, so the host stays honest; it still goes through the output filter.
"""
import json
import math
import os
import re
import threading
import time
import unicodedata
from typing import Dict, Iterable, List, Optional

_UNSURE = [
    "khong chac", "chua chac", "chua ro", "khong biet", "chua co thong tin", "khong co thong tin",
    "xem them o trang san pham", "xem trang san pham", "kiem tra lai",
    "not sure", "i don't know", "i do not know", "no information",
]
_STOP = set("a ad oi shop ban cho minh em anh chi co khong ko k la va nay kia nha nhe the nao vay di voi cua duoc moi "
            "ah ha da roi a ơ the thi minh ben dang can muon hoi".split())


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", _fold(text)) if len(t) > 1 and t not in _STOP]


def question_key(text: str) -> str:
    return " ".join(sorted(set(tokens(text))))


def is_unsure(reply: str) -> bool:
    f = _fold(reply)
    return any(m in f for m in _UNSURE)


class TaughtBook:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._mtime = None
        self._data: Dict = {"taught": [], "ignored": []}
        self._reload()

    def _reload(self) -> None:
        try:
            mt = os.path.getmtime(self.path)
        except OSError:
            if self._mtime is not None:  # file was deleted
                self._data, self._mtime = {"taught": [], "ignored": []}, None
            return
        if mt == self._mtime:
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self._data = {"taught": list(d.get("taught", [])), "ignored": list(d.get("ignored", []))}
            self._mtime = mt
        except (OSError, ValueError):
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
        self._mtime = os.path.getmtime(self.path)

    # ---- reading
    def entries(self) -> List[Dict]:
        with self._lock:
            self._reload()
            return list(self._data["taught"])

    def ignored(self) -> List[str]:
        with self._lock:
            self._reload()
            return list(self._data["ignored"])

    def find(self, text: str, product_id: Optional[str] = None) -> Optional[Dict]:
        """Best taught entry for a viewer comment, or None. Needs most of the taught question's words to appear."""
        tt = set(tokens(text))
        best, best_score = None, 0.0
        for e in self.entries():
            qt = set(tokens(e.get("q", "")))
            if not qt:
                continue
            pid = e.get("product_id")
            if pid and product_id and pid != product_id:
                continue
            overlap = len(qt & tt)
            if overlap < max(2, math.ceil(0.6 * len(qt))) and not (len(qt) == 1 and overlap == 1):
                continue
            score = overlap / len(qt) + 0.01 * len(qt)
            if score > best_score:
                best, best_score = e, score
        return best

    def answer(self, text: str, product_id: Optional[str] = None) -> Optional[str]:
        e = self.find(text, product_id)
        return e["a"] if e else None

    # ---- writing
    def add(self, q: str, a: str, product_id: Optional[str] = None) -> Dict:
        q, a = (q or "").strip(), (a or "").strip()
        if not q or not a:
            raise ValueError("A question and an answer are both needed.")
        with self._lock:
            self._reload()
            entry = {"q": q, "a": a, "product_id": product_id or None, "ts": int(time.time())}
            key = question_key(q)
            self._data["taught"] = [t for t in self._data["taught"] if question_key(t.get("q", "")) != key] + [entry]
            self._save()
            return entry

    def remove(self, q: str) -> None:
        with self._lock:
            self._reload()
            key = question_key(q)
            self._data["taught"] = [t for t in self._data["taught"] if question_key(t.get("q", "")) != key]
            self._save()

    def ignore(self, q: str) -> None:
        with self._lock:
            self._reload()
            key = question_key(q)
            if key and key not in self._data["ignored"]:
                self._data["ignored"].append(key)
                self._save()


def pending(events: Iterable[Dict], book: TaughtBook, limit: int = 30) -> List[Dict]:
    """Distinct questions the host was unsure about that nobody has taught or ignored yet."""
    ignored = set(book.ignored())
    groups: List[Dict] = []
    for e in sorted((x for x in events if x.get("kind") == "unsure"), key=lambda x: x.get("ts", 0)):
        text = (e.get("text") or "").strip()
        toks = set(tokens(text))
        key = question_key(text)
        if not toks or key in ignored:
            continue
        # the same question worded differently ("ship Đà Nẵng bao lâu" / "shop có ship đi Đà Nẵng không") is one group
        g = next((x for x in groups if x["product_id"] == (e.get("product_id") or x["product_id"])
                  and len(toks & x["toks"]) >= 2 and len(toks & x["toks"]) / min(len(toks), len(x["toks"])) >= 0.6), None)
        if g is None:
            g = {"key": key, "q": text, "count": 0, "product_id": e.get("product_id"), "last": 0, "toks": toks}
            groups.append(g)
        g["count"] += 1
        g["toks"] |= toks
        g["last"], g["q"] = e.get("ts", 0), text
        g["product_id"] = e.get("product_id") or g["product_id"]
    out = [g for g in groups if book.find(g["q"], g["product_id"]) is None]
    for g in out:
        g.pop("toks", None)
    out.sort(key=lambda g: (-g["count"], -g["last"]))
    return out[:limit]
