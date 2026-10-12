"""Short-lived conversation memory: lets a follow-up such as "còn size nhỏ hơn không?" mean the product just discussed.

Held in memory only, for the current session: no viewer names, nothing written to disk, gone when the app stops.
It never overrides a comment that names a product, and it only fills in for short shopping questions.
"""
import re
import time
from typing import Callable, Dict, List, Optional

from utils.live_analytics import SALES_INTENTS, classify_intent
from utils.tiktok_safety import fold

_REF = ["cai nay", "cai do", "san pham nay", "mon nay", "no", "con nay", "mau nay", "ao nay", "do nay"]


class Convo:
    def __init__(self, ttl_s: float = 150):
        self.ttl_s = ttl_s
        self._pid: Optional[str] = None
        self._at = 0.0

    def remember(self, product_id: Optional[str], now: Optional[float] = None) -> None:
        if product_id:
            self._pid, self._at = str(product_id), time.time() if now is None else now

    def forget(self) -> None:
        self._pid, self._at = None, 0.0

    def resolve(self, text: str, products: List[Dict], current_id: str = "", now: Optional[float] = None) -> Optional[Dict]:
        """The product a product-less follow-up most likely refers to, or None. `current_id` is the tour's active product."""
        now = time.time() if now is None else now
        f = fold(text or "")
        words = f.split()
        if not words or len(words) > 9:
            return None
        ref = any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", f) for w in _REF)
        if not (ref or classify_intent(text) in SALES_INTENTS):
            return None
        pid = self._pid if self._pid and now - self._at <= self.ttl_s else (current_id or None)
        return next((p for p in products if str(p.get("id")) == str(pid)), None) if pid else None
