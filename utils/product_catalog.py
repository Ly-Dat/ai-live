"""
Product catalog for the AI seller.

Loads data/products.json (the items in your TikTok Shop cart / showcase), then provides:
  * all_products()             - ordered list, used by the tour to introduce EVERY item
  * build_pitch(product, n)    - a spoken pitch built only from catalog fields (no invented claims)
  * find_relevant(text)        - products a viewer comment is probably asking about
  * context_for(text)          - a compact knowledge block to prepend to the LLM prompt

products.json format (see data/products.json for a full example):
{
  "shop_name": "...",
  "products": [
    {"id": "P001", "name": "...", "aliases": ["..."], "price": "199.000đ", "original_price": "299.000đ",
     "highlights": ["..."], "description": "...", "how_to_use": "...", "sizes_colors": "...",
     "shipping": "...", "return_policy": "...", "stock_note": "...", "faq": [{"q": "...", "a": "..."}]}
  ]
}
Everything the streamer says about a product comes from these fields, so keep claims honest and
compliant with TikTok rules (no absolute/medical claims, no off-platform contact info).
"""
import json
import os
import random
import re
import unicodedata
from typing import Dict, List, Optional


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", _fold(text))


class ProductCatalog:
    def __init__(self, products_path: str = "data/products.json", templates_path: str = "data/pitch_templates.json"):
        with open(products_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.products_path = products_path
        self.shop_name = data.get("shop_name", "")
        self.products: List[Dict] = data.get("products", [])
        self.templates: Dict = {}
        if os.path.exists(templates_path):
            with open(templates_path, "r", encoding="utf-8") as f:
                self.templates = json.load(f)
        self._index = [(p, self._keywords(p)) for p in self.products]

    # ------------------------------------------------------------ live cart sync
    def find_by_pop(self, pop: Dict) -> Optional[Dict]:
        """Find the catalog entry for a product shown in the live room (match by TikTok product id, then by title)."""
        pid = str(pop.get("product_id") or "")
        title = _fold(pop.get("title") or "").strip()
        for p in self.products:
            if pid and pid in (str(p.get("tiktok_product_id", "")), str(p.get("id", ""))):
                return p
        for p in self.products:
            names = [p.get("name", "")] + list(p.get("aliases", []))
            if title and any(_fold(n).strip() == title for n in names if n):
                return p
        return None

    def upsert_pop(self, pop: Dict, auto_add: bool = True):
        """Match (or add) the product TikTok just pinned/popped up in the live room.

        Returns (product, is_new). New products are marked "auto_imported": true and only carry what TikTok
        sends (title, price, image, id) - fill in highlights/faq in products.json to make pitches richer.
        Existing entries keep everything you wrote; only a missing price/ids are filled in.
        """
        product = self.find_by_pop(pop)
        changed = False
        if product is None:
            if not auto_add or not (pop.get("title") or "").strip():
                return None, False
            product = {
                "id": str(pop.get("product_id") or f"AUTO{len(self.products) + 1:03d}"),
                "order": max([p.get("order", 0) for p in self.products] + [0]) + 1,
                "name": pop["title"].strip(),
                "aliases": [], "price": pop.get("price", ""), "original_price": "",
                "description": "", "highlights": [], "sizes_colors": "", "how_to_use": "",
                "shipping": "", "return_policy": "", "stock_note": "", "faq": [],
                "auto_imported": True,
            }
            self.products.append(product)
            changed = True
            is_new = True
        else:
            is_new = False
            if pop.get("price") and not product.get("price"):
                product["price"] = pop["price"]
                changed = True
        if pop.get("product_id") and not product.get("tiktok_product_id"):
            product["tiktok_product_id"] = str(pop["product_id"])
            changed = True
        if pop.get("image_url") and not product.get("image_url"):
            product["image_url"] = pop["image_url"]
            changed = True
        if changed:
            self._index = [(p, self._keywords(p)) for p in self.products]
            self.save()
        return product, is_new

    def save(self) -> None:
        """Write the catalog back to disk atomically (keeps UTF-8 and Vietnamese accents readable)."""
        data = {"shop_name": self.shop_name, "products": self.products}
        tmp = self.products_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.products_path)

    # ------------------------------------------------------------ listing
    def all_products(self) -> List[Dict]:
        """Products to introduce; items with "active": false (sold out / not for this live) are skipped."""
        return [p for p in self.products if p.get("active", True)]

    @staticmethod
    def _keywords(p: Dict) -> set:
        words = set(_tokens(p.get("name", "")))
        for alias in p.get("aliases", []):
            words |= set(_tokens(alias))
        # drop very common filler tokens so "ao" or "cai" alone doesn't match everything
        return {w for w in words if len(w) > 1}

    # ------------------------------------------------------------ pitches
    def build_pitch(self, product: Dict, round_no: int = 0) -> str:
        """Compose a spoken pitch for one product from templates + catalog fields."""
        t = self.templates
        parts = []
        intro = t.get("intro", ["Next up: {name}."])
        parts.append(intro[round_no % len(intro)].format(name=product["name"], number=product.get("order", "")))
        if product.get("price"):
            if product.get("original_price"):
                parts.append(random.choice(t.get("price_with_original", ["Price {price}, was {original_price}."]))
                             .format(price=product["price"], original_price=product["original_price"]))
            else:
                parts.append(random.choice(t.get("price_only", ["Price {price}."])).format(price=product["price"]))
        if product.get("description"):
            parts.append(product["description"])
        highlights = product.get("highlights", [])
        if highlights:
            take = highlights[(round_no * 2) % len(highlights):][:2] or highlights[:2]
            parts.append(random.choice(t.get("highlights_lead", ["Highlights:"])) + " " + "; ".join(take) + ".")
        if product.get("sizes_colors") and round_no % 2 == 0:
            parts.append(product["sizes_colors"])
        if product.get("how_to_use") and round_no % 2 == 1:
            parts.append(product["how_to_use"])
        if product.get("shipping") and round_no % 3 == 0:
            parts.append(product["shipping"])
        if product.get("return_policy") and round_no % 3 == 1:
            parts.append(product["return_policy"])
        if product.get("stock_note"):
            parts.append(product["stock_note"])
        outro = t.get("call_to_action", ["Tap the cart to see it."])
        parts.append(random.choice(outro))
        return " ".join(s.strip() for s in parts if s and s.strip())

    # ------------------------------------------------------------ retrieval for comments
    def find_relevant(self, text: str, limit: int = 2) -> List[Dict]:
        """Rank products by keyword overlap with the comment (accent-insensitive)."""
        toks = set(_tokens(text))
        if not toks:
            return []
        # number picks: "so 3", "san pham 3", "cai thu 3"
        m = re.search(r"(?:so|sp|san pham|cai|gio hang|item)\s*(?:thu\s*)?(\d{1,3})\b", _fold(text))
        scored = []
        for p, kws in self._index:
            score = len(toks & kws)
            if m and str(p.get("order", "")) == m.group(1):
                score += 3
            if score:
                scored.append((score, p))
        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:limit]]

    def context_for(self, text: str, limit: int = 2) -> str:
        """Compact product knowledge block for the LLM, or '' if nothing matched."""
        found = self.find_relevant(text, limit)
        if not found:
            return ""
        lines = []
        for p in found:
            row = [f"Product: {p['name']}"]
            for key, label in (("price", "Price"), ("original_price", "Original price"), ("description", "Description"),
                               ("sizes_colors", "Options"), ("how_to_use", "How to use"), ("shipping", "Shipping"),
                               ("return_policy", "Returns"), ("stock_note", "Stock")):
                if p.get(key):
                    row.append(f"{label}: {p[key]}")
            if p.get("highlights"):
                row.append("Highlights: " + "; ".join(p["highlights"]))
            for qa in p.get("faq", []):
                row.append(f"FAQ - {qa['q']} -> {qa['a']}")
            lines.append("\n".join(row))
        return "\n---\n".join(lines)


    # ------------------------------------------------------------ quick answers (no LLM)
    _INTENTS = [
        # (field, answer template key, trigger words - accent-folded)
        ("price", "answer_price", ["gia", "bao nhieu", "nhieu tien", "bn", "gia ca"]),
        ("sizes_colors", "answer_options", ["size", "mau", "kich co", "kich thuoc", "mau gi", "loai nao", "co may mau"]),
        ("shipping", "answer_shipping", ["ship", "giao hang", "van chuyen", "bao lau", "mat may ngay", "freeship"]),
        ("return_policy", "answer_return", ["doi tra", "hoan tien", "bao hanh", "doi size", "tra hang"]),
        ("how_to_use", "answer_usage", ["cach dung", "su dung", "dung sao", "dung the nao", "cach giat", "huong dan"]),
        ("stock_note", "answer_stock", ["con hang", "het hang", "con khong", "con size"]),
    ]

    def quick_answer(self, text: str) -> Optional[str]:
        """Answer a simple, factual question straight from the catalog; None means 'let the LLM handle it'.

        Only answers when exactly one product is clearly meant and the needed field exists, so it never
        guesses. FAQ entries are matched first (by word overlap with the question).
        """
        found = self.find_relevant(text, 2)
        if not found:
            return None
        if len(found) > 1 and _scoring_tie(self, text, found):
            return None
        p = found[0]
        folded = _fold(text)
        q_tokens = set(_tokens(text))
        for qa in p.get("faq", []):
            qt = set(_tokens(qa.get("q", "")))
            if qt and len(q_tokens & qt) >= max(3, int(len(qt) * 0.6)):
                return qa["a"]
        for field, key, words in self._INTENTS:
            if any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", folded) for w in words):
                value = p.get(field)
                if not value:
                    return None
                tpl = self.templates.get(key, "{name}: {value}")
                price_extra = ""
                if field == "price" and p.get("original_price"):
                    price_extra = f" (giá gốc {p['original_price']})" if self.templates.get("lang") != "en" else f" (was {p['original_price']})"
                return tpl.format(name=p["name"], value=value) + price_extra
        return None


def _scoring_tie(catalog: "ProductCatalog", text: str, found: List[Dict]) -> bool:
    toks = set(_tokens(text))
    a, b = (len(toks & catalog._keywords(x)) for x in found[:2])
    return a == b


_default: Optional[ProductCatalog] = None


def get_default(products_path: str = "data/products.json", templates_path: str = "data/pitch_templates.json") -> ProductCatalog:
    global _default
    if _default is None:
        _default = ProductCatalog(products_path, templates_path)
    return _default
