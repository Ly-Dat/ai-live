"""Sold-count shoutouts.

TikTok's live feed never says WHO bought something. The only purchase signal it sends is an anonymous per-product
"sold" counter (the little "Đã bán 120" tag). So we thank the room, never a person, and only when that counter
really went up: no invented numbers, no made-up buyers.
"""
import json
import os
import re
import tempfile

DEFAULT_PATH = os.path.join("data", "sales_shoutout.json")
DEFAULTS = {"enable": False, "step": 5, "cooldown": 120}
_SOLD = re.compile(r"(sold|đã bán|da ban)", re.I)

TEMPLATES = [
    "{product} vừa bán thêm {n} cái rồi, cảm ơn cả nhà đã tin tưởng nha!",
    "Cảm ơn cả nhà, {product} đã có thêm {n} bạn chốt rồi nè!",
    "Wow, thêm {n} cái {product} vừa được chốt, cảm ơn mọi người nhiều nha!",
]


def load_settings(path=DEFAULT_PATH):
    out = dict(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            out["enable"] = bool(data.get("enable", False))
            out["step"] = max(1, int(data.get("step", out["step"])))
            out["cooldown"] = max(30, int(data.get("cooldown", out["cooldown"])))
    except Exception:
        pass
    return out


def save_settings(settings, path=DEFAULT_PATH):
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def is_sold_tag(desc):
    return bool(_SOLD.search(desc or ""))


class SalesWatcher:
    """Remembers the last sold count per product and says when enough new sales have happened."""

    def __init__(self):
        self.base = {}
        self.last_say = float("-inf")

    def update(self, product_id, desc, count, now, step=5, cooldown=120):
        """Return how many new sales to announce (int) or None."""
        try:
            count = int(count)
        except (TypeError, ValueError):
            return None
        if not product_id or count <= 0 or not is_sold_tag(desc):
            return None
        prev = self.base.get(product_id)
        if prev is None or count < prev:  # first sight, or the counter reset
            self.base[product_id] = count
            return None
        gained = count - prev
        if gained < step or now - self.last_say < cooldown:
            return None  # keep accumulating; the base stays so the gain is not lost
        self.base[product_id] = count
        self.last_say = now
        return gained
