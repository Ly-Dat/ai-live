"""
Honest flash-sale announcements.

The seller sets: product, how many minutes the offer runs, optional sale price and optional stock number.
The app announces it on a schedule (start, every N minutes, final minute, end). Only facts the seller entered are spoken
(time left, price, stock); the text still passes the TikTok safety output filter before it is said.

State lives in a small JSON file (data/flash_sale.json) so the web UI process and the live app process can share it.
`next_announcement` is a pure function and is unit tested.
"""
import json
import math
import os
import time
from typing import Dict, Optional, Tuple

DEFAULT_PATH = "data/flash_sale.json"

_DEFAULT_TEMPLATES = {
    "flash_start": "Offer on {name}: {minutes} minutes only, price {price}.",
    "flash_remaining": "The offer on {name} has about {minutes} minutes left, price {price}.",
    "flash_stock": " The shop has {stock} left for this live.",
    "flash_final": "The offer on {name} ends in under a minute. Check the cart if you are interested.",
    "flash_end": "The offer on {name} has ended. Thanks for watching!",
}


def load_state(path: str = DEFAULT_PATH) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_state(state: Dict, path: str = DEFAULT_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def start_sale(path: str, product_id: str, minutes: float, sale_price: str = "", stock_left: Optional[int] = None,
               every_min: float = 5, now: Optional[float] = None) -> Dict:
    now = time.time() if now is None else now
    if minutes <= 0:
        raise ValueError("minutes must be > 0")
    state = {
        "active": True,
        "product_id": product_id,
        "started_at": now,
        "ends_at": now + minutes * 60,
        "minutes": minutes,
        "sale_price": sale_price or "",
        "stock_left": stock_left,
        "every_sec": max(60, int(every_min * 60)),
        "last_announce_ts": 0,
        "final_done": False,
    }
    save_state(state, path)
    return state


def stop_sale(path: str = DEFAULT_PATH) -> None:
    state = load_state(path)
    if state:
        state["active"] = False
        save_state(state, path)


def next_announcement(state: Optional[Dict], product: Optional[Dict], templates: Optional[Dict] = None,
                      now: Optional[float] = None) -> Tuple[Optional[str], Optional[Dict]]:
    """Return (text to say or None, updated state). The input state is not modified."""
    if not state or not state.get("active") or not product:
        return None, state
    now = time.time() if now is None else now
    tpl = dict(_DEFAULT_TEMPLATES)
    tpl.update({k: v for k, v in (templates or {}).items() if k.startswith("flash_")})
    st = dict(state)
    remaining = st["ends_at"] - now
    price = st.get("sale_price") or product.get("price") or ""
    fmt = {"name": product.get("name", ""), "price": price, "minutes": max(1, math.ceil(remaining / 60)),
           "stock": st.get("stock_left")}

    if remaining <= 0:
        st["active"] = False
        return tpl["flash_end"].format(**fmt), st

    stock = ""
    if st.get("stock_left"):
        stock = tpl["flash_stock"].format(**fmt)

    if st["last_announce_ts"] == 0:
        st["last_announce_ts"] = now
        return tpl["flash_start"].format(**fmt) + stock, st
    if remaining <= 60 and not st.get("final_done"):
        st["final_done"] = True
        st["last_announce_ts"] = now
        return tpl["flash_final"].format(**fmt), st
    if remaining > 60 and now - st["last_announce_ts"] >= st["every_sec"]:
        st["last_announce_ts"] = now
        return tpl["flash_remaining"].format(**fmt) + stock, st
    return None, st
