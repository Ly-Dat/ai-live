"""Product-aware answers for the harder questions: compare, recommend within a budget, and price/trust/quality doubts.

Everything said comes from the catalog (name, price, highlights, return policy, ...). Nothing is invented: when the
needed fields are missing, or the product is unclear, answer() returns None and the normal LLM path takes over.
No claims such as 'genuine', 'best' or 'guaranteed' are made.
"""
import re
from typing import Dict, List, Optional

from utils.product_catalog import _fold

_COMPARE = ["so sanh", "khac gi", "khac nhau", "cai nao tot hon", "nen chon cai nao", "hon nhau", "nen lay cai nao"]
_RECOMMEND = ["goi y", "tu van", "nen mua gi", "mua gi", "hop voi", "co gi dep", "co gi hay"]
_OBJ = [
    ("price", ["dat qua", "mac qua", "gia cao", "hoi mac", "hoi dat", "mac vay", "dat vay", "giam them"]),
    ("trust", ["co that khong", "hang that", "chinh hang", "lua dao", "co uy tin", "hang fake", "hang gia"]),
    ("quality", ["co tot khong", "chat luong", "co ben khong", "ben khong", "xin khong", "mong khong", "re vay", "sao re", "re qua"]),
    ("hesitate", ["suy nghi", "chua chac", "phan van", "de xem da", "de mai"]),
]
_T = {
    "vi": {
        "compare": "So sánh nhanh nha: {a} giá {pa}{ha}; còn {b} giá {pb}{hb}. Bạn chọn theo nhu cầu của mình nhé.",
        "rec_budget": "Trong tầm {budget} mình gợi ý: {items}.",
        "rec_none": "Hiện chưa có sản phẩm nào trong tầm giá đó, rẻ nhất là {name} giá {price}.",
        "rec_list": "Bạn có thể xem: {items}.",
        "price_off": "Mình hiểu bạn đang cân nhắc giá nha. {name} đang {price}, thấp hơn giá gốc {orig}.",
        "price_plain": "Mình hiểu bạn đang cân nhắc giá nha. {name} đang {price}{hl}; bạn xem kỹ mô tả trong giỏ hàng rồi quyết định nhé.",
        "trust": "Bạn đặt qua giỏ hàng TikTok Shop nha. {ret}",
        "quality": "{name}{hl}. Mình không dám hứa tuyệt đối, bạn xem mô tả và đánh giá thật trong giỏ hàng nha.",
        "hesitate": "Không sao, bạn cứ xem kỹ nha. {ret} {stock}",
        "hl": ", điểm nổi bật: {x}", "cart": "số {n}", "item": "{cart} {name} ({price})",
    },
    "en": {
        "compare": "Quick comparison: {a} is {pa}{ha}; {b} is {pb}{hb}. Pick whichever fits your need.",
        "rec_budget": "Within {budget} I suggest: {items}.",
        "rec_none": "Nothing is in that budget right now; the cheapest is {name} at {price}.",
        "rec_list": "You could look at: {items}.",
        "price_off": "Fair to think about the price. {name} is {price}, below the original {orig}.",
        "price_plain": "Fair to think about the price. {name} is {price}{hl}; check the description in the cart and decide.",
        "trust": "Order through the TikTok Shop cart. {ret}",
        "quality": "{name}{hl}. I cannot promise anything absolute; please read the description and real reviews in the cart.",
        "hesitate": "No rush, take your time. {ret} {stock}",
        "hl": ", highlights: {x}", "cart": "no. {n}", "item": "{cart} {name} ({price})",
    },
}


def money(s) -> Optional[int]:
    """'295.747₫' -> 295747. None when there are no digits."""
    d = re.sub(r"[^0-9]", "", str(s or ""))
    return int(d) if d else None


def budget_from(text: str) -> Optional[int]:
    """'duoi 300k', 'tam 200 nghin', 'khoang 1 trieu' -> VND."""
    m = re.search(r"(?:duoi|toi da|khoang|tam|under|<)\s*(\d+(?:[.,]\d+)?)\s*(k|nghin|ngan|tr|trieu|m)?\b", _fold(text))
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    u = m.group(2) or ""
    if u in ("k", "nghin", "ngan"):
        return int(v * 1000)
    if u in ("tr", "trieu", "m"):
        return int(v * 1_000_000)
    return int(v) if v >= 10000 else None   # a bare small number ("tam 3 cai") is not a budget


def _has(folded: str, words: List[str]) -> bool:
    return any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", folded) for w in words)


def _short(name: str, n: int = 38) -> str:
    name = (name or "").strip()
    if len(name) <= n:
        return name
    cut = name[:n].rsplit(" ", 1)[0]
    return (cut or name[:n]).rstrip(",:;- ")


def _hl(p: Dict, t: Dict) -> str:
    h = [x for x in (p.get("highlights") or []) if x]
    return t["hl"].format(x="; ".join(h[:2])) if h else ""


def answer(catalog, text: str) -> Optional[str]:
    t = _T["en" if catalog.templates.get("lang") == "en" else "vi"]
    f = _fold(text)
    prods = [p for p in catalog.all_products() if p.get("price")]
    if _has(f, _COMPARE):
        found = catalog.find_relevant(text, 2)
        if len(found) == 2 and found[0].get("price") and found[1].get("price"):
            a, b = found
            return t["compare"].format(a=_short(a["name"]), pa=a["price"], ha=_hl(a, t), b=_short(b["name"]), pb=b["price"], hb=_hl(b, t))
        return None
    if _has(f, _RECOMMEND) or budget_from(text):
        if not prods:
            return None
        cap = budget_from(text)
        if cap:
            ok = sorted([p for p in prods if (money(p["price"]) or 10**12) <= cap], key=lambda p: -(money(p["price"]) or 0))[:2]
            if not ok:
                cheapest = min(prods, key=lambda p: money(p["price"]) or 10**12)
                return t["rec_none"].format(name=_short(cheapest["name"]), price=cheapest["price"])
            items = "; ".join(t["item"].format(cart=t["cart"].format(n=p.get("order", "")), name=_short(p["name"]), price=p["price"]) for p in ok)
            return t["rec_budget"].format(budget=f"{cap:,}".replace(",", "."), items=items)
        if _has(f, _RECOMMEND):
            top = sorted(prods, key=lambda p: p.get("order") or 999)[:3]
            return t["rec_list"].format(items="; ".join(t["item"].format(cart=t["cart"].format(n=p.get("order", "")), name=_short(p["name"]), price=p["price"]) for p in top))
        return None
    for kind, words in _OBJ:
        if _has(f, words):
            found = catalog.find_relevant(text, 1)
            if not found:
                return None
            p = found[0]
            name = _short(p["name"])
            if kind == "price" and p.get("price"):
                po, pp = money(p.get("original_price")), money(p["price"])
                if po and pp and po > pp:
                    return t["price_off"].format(name=name, price=p["price"], orig=p["original_price"])
                return t["price_plain"].format(name=name, price=p["price"], hl=_hl(p, t))
            if kind == "trust" and p.get("return_policy"):
                return t["trust"].format(ret=p["return_policy"])
            if kind == "quality":
                hl = _hl(p, t)
                if not hl:
                    return None
                return t["quality"].format(name=name, hl=hl)
            if kind == "hesitate" and (p.get("return_policy") or p.get("stock_note")):
                return t["hesitate"].format(ret=p.get("return_policy", ""), stock=p.get("stock_note", "")).strip()
            return None
    return None


_counter = {"n": 0}


def add_catchphrase(reply: str, phrases: List[str], every: int = 3) -> str:
    """Append one of the character's catchphrases to roughly every third spoken reply (never to long ones)."""
    if not reply or not phrases:
        return reply
    _counter["n"] += 1
    if _counter["n"] % every or len(reply) > 220:
        return reply
    ph = phrases[(_counter["n"] // every) % len(phrases)]
    return reply if ph.lower() in reply.lower() else f"{reply.rstrip()} {ph}"
