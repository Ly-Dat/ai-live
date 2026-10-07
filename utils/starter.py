"""
Starter shop: three generic sample products so a new seller can hear the host pitch something in one click,
before typing anything. Pure data; the caller decides whether to write it (only when the catalog is empty).
"""
from typing import Dict, List

STARTER_SHOP = "Shop của tôi"


def starter_products() -> List[Dict]:
    base = [
        ("S001", "Áo thun cotton basic", "Áo thun cotton mềm, thoáng, dễ phối đồ.", "Màu: Trắng, Đen; Size: S, M, L", "149.000₫", "199.000₫"),
        ("S002", "Túi tote canvas", "Túi tote canvas dày dặn, đựng vừa laptop và sách.", "Màu: Be, Đen", "99.000₫", ""),
        ("S003", "Bình giữ nhiệt 500ml", "Bình giữ nhiệt inox, giữ nóng và lạnh nhiều giờ.", "Màu: Xanh, Hồng, Trắng", "179.000₫", ""),
    ]
    out = []
    for i, (pid, name, desc, opts, price, orig) in enumerate(base, 1):
        out.append({
            "id": pid, "order": i, "name": name, "description": desc, "sizes_colors": opts,
            "price": price, "original_price": orig, "images": [], "how_to_use": "", "shipping": "",
            "return_policy": "", "stock_note": "", "active": True, "aliases": [], "highlights": [], "faq": [],
            "intro": "", "sample": True,
        })
    return out


def starter_catalog() -> Dict:
    return {"shop_name": STARTER_SHOP, "products": starter_products()}
