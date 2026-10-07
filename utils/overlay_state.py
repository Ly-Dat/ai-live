"""What the on-screen overlay shows right now (giveaway, poll, flash sale), built from the same state files the host uses.

Pure function so it is unit tested. Only facts that really are in the state: counts, time left, the seller's own
prize / question / price. Winner names are shown only if they pass the safety check (same rule as the spoken line).
"""
import math
from typing import Callable, Dict, List, Optional


def _left(ends_at, now) -> int:
    return max(0, int(math.ceil(float(ends_at) - now)))


def build(engage: Dict, flash: Optional[Dict], product_name: str = "", now: float = 0.0,
          safe: Callable[[str], bool] = lambda s: True) -> Dict:
    items: List[Dict] = []
    p = (engage or {}).get("poll")
    if p and (p.get("active") or (p.get("ended") and now - p["ends_at"] < 60)):
        counts = [0] * len(p["options"])
        for idx in (p.get("votes") or {}).values():
            if 0 <= idx < len(counts):
                counts[idx] += 1
        total = sum(counts)
        items.append({
            "kind": "poll", "title": p["question"], "total": total,
            "left": _left(p["ends_at"], now) if p.get("active") else 0, "ended": not p.get("active"),
            "options": [{"n": i + 1, "label": o, "count": c, "pct": round(100 * c / total) if total else 0}
                        for i, (o, c) in enumerate(zip(p["options"], counts))],
        })
    g = (engage or {}).get("giveaway")
    if g and (g.get("active") or (g.get("drawn") and now - g["ends_at"] < 90)):
        item = {"kind": "giveaway", "prize": g["prize"], "keyword": g["keyword"], "entries": len(g.get("entrants") or {}),
                "left": _left(g["ends_at"], now) if g.get("active") else 0, "drawn": bool(g.get("drawn"))}
        if g.get("drawn"):
            names = [n for n in (g.get("winners") or []) if n and safe(n)]
            item["winners"] = names
        items.append(item)
    if flash and flash.get("active") and now < float(flash.get("ends_at") or 0):
        items.append({"kind": "flash", "product": product_name, "price": flash.get("sale_price") or "",
                      "stock": flash.get("stock_left"), "left": _left(flash["ends_at"], now)})
    return {"items": items}
