"""Reuse a recent AI answer when the same question comes again (same product, same product data).

Why: viewers ask "ship bao lâu?" or "có size L không?" again and again. Re-asking the model costs money and 2-4 s each
time. The cache only returns a reply that already passed every safety filter once (it goes through them again on use),
is dropped when product data / the flash sale changes, and never keeps a reply that admits it is unsure or names a viewer.
"""
import re
import time
import unicodedata
from collections import OrderedDict
from typing import Optional

TTL_S = 600
MAX_ITEMS = 300
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", (text or "").lower())
    t = _PUNCT.sub(" ", t)
    t = re.sub(r"(.)\1{2,}", r"\1\1", t)  # "đẹpppp" -> "đẹpp"
    return re.sub(r"\s+", " ", t).strip()


def make_key(question: str, product_id: Optional[str], version: str = "") -> Optional[str]:
    q = normalize(question)
    if len(q) < 4:
        return None
    return f"{product_id or '-'}|{version}|{q}"


def cacheable(reply: Optional[str], username: str = "", unsure: bool = False) -> bool:
    if not reply or unsure:
        return False
    r = reply.strip()
    if not 3 <= len(r) <= 400:
        return False
    if username and len(username) >= 3 and username.lower() in r.lower():
        return False
    return True


class AnswerCache:
    def __init__(self, ttl: float = TTL_S, max_items: int = MAX_ITEMS):
        self.ttl, self.max_items = ttl, max_items
        self._d: "OrderedDict[str, tuple]" = OrderedDict()

    def get(self, key: Optional[str], now: Optional[float] = None) -> Optional[str]:
        if not key or key not in self._d:
            return None
        now = time.time() if now is None else now
        ts, reply = self._d[key]
        if now - ts > self.ttl:
            del self._d[key]
            return None
        self._d.move_to_end(key)
        return reply

    def put(self, key: Optional[str], reply: str, now: Optional[float] = None) -> None:
        if not key:
            return
        self._d[key] = (time.time() if now is None else now, reply.strip())
        self._d.move_to_end(key)
        while len(self._d) > self.max_items:
            self._d.popitem(last=False)

    def __len__(self) -> int:
        return len(self._d)
