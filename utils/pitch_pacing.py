"""Adaptive pitch pacing for the product tour, pure so it can be tested without a live.

The tour used to give every product a random 5-10 minutes whatever the chat did. Now the time on a product follows the room:
  * viewers are asking to buy this product -> stay longer (up to 1.6x), they are interested;
  * chat is dead for a few minutes -> move on sooner (down to 0.7x), repeating the pitch to nobody helps nobody;
  * busy chat -> add a pause between sentences so comment replies are not drowned by the pitch.
Nothing here invents numbers: it only reads the comment events the analytics already logged."""
from typing import Dict, Iterable, Optional

BUY_INTENTS = {"buy", "price", "stock", "options"}
LONGER, SHORTER = 1.6, 0.7
MIN_MINUTES = 1.0


def signals(events: Iterable[Dict], now: float, product_id: str = "") -> Dict:
    """{"rate": comments per minute over the last 2 min, "quiet_s": seconds since the last comment, "span_s": age of the log, "buy": buying questions about this product in the last 5 min}"""
    rate_n, last, buy, first = 0, 0.0, 0, None
    for e in events:
        if e.get("ts") is not None:
            first = float(e["ts"]) if first is None else min(first, float(e["ts"]))
        if e.get("kind") != "comment":
            continue
        ts = float(e.get("ts") or 0)
        last = max(last, ts)
        if now - ts <= 120:
            rate_n += 1
        if product_id and e.get("product_id") == product_id and e.get("intent") in BUY_INTENTS and now - ts <= 300:
            buy += 1
    return {"rate": rate_n / 2.0, "quiet_s": (now - last) if last else 9999.0, "buy": buy,
            "span_s": (now - first) if first is not None else 0.0}


def adjust_minutes(base: float, sig: Dict, manual: bool = False) -> float:
    """Minutes to stay on a product. A duration the seller typed for the product (`manual`) is never changed."""
    if manual:
        return float(base)
    if sig.get("buy", 0) >= 2:
        return round(float(base) * LONGER, 2)
    if sig.get("span_s", 0) >= 300 and sig.get("quiet_s", 0) >= 180 and sig.get("rate", 0) == 0:   # not in the first minutes of a live
        return round(max(MIN_MINUTES, float(base) * SHORTER), 2)
    return float(base)


def extra_gap(sig: Dict) -> float:
    """Seconds to wait between pitch sentences when chat is busy (0 when it is calm)."""
    r = float(sig.get("rate", 0))
    if r >= 8:
        return 6.0
    if r >= 4:
        return 3.0
    return 0.0
