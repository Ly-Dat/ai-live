"""
Import products from a spreadsheet (CSV or XLSX) into data/products.json.

Typical source: TikTok Shop Seller Center -> Products -> export, or your own sheet.
Column headers are matched loosely (English or Vietnamese, accents ignored):

    name        : product name | ten san pham | title
    price       : price | gia | gia ban
    original    : original price | gia goc | gia niem yet
    description : description | mo ta
    highlights  : highlights | diem noi bat | features   (separate items with ; or |)
    options     : sizes | colors | size/mau | phan loai
    sku / id    : sku | id | ma san pham
    active      : active | status   (0/false/no/het hang = skip in the tour)

Existing products are matched by id or by name and UPDATED only where the sheet has a value, so the
details you wrote by hand (faq, how_to_use, ...) are kept. New rows are appended in sheet order.

    python import_products.py seller_export.xlsx
    python import_products.py products.csv --products data/products.json --dry-run
"""
import argparse
import csv
import json
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ALIASES = {
    "name": ["name", "product name", "ten san pham", "ten", "title", "san pham"],
    "price": ["price", "gia", "gia ban", "selling price", "sale price"],
    "original_price": ["original price", "gia goc", "gia niem yet", "list price", "original"],
    "description": ["description", "mo ta", "mo ta san pham"],
    "highlights": ["highlights", "diem noi bat", "features", "tinh nang"],
    "sizes_colors": ["sizes", "colors", "size/mau", "phan loai", "options", "variations", "mau sac"],
    "id": ["sku", "id", "ma san pham", "product id", "seller sku"],
    "active": ["active", "status", "trang thai"],
}
FALSE_WORDS = {"0", "false", "no", "n", "off", "inactive", "het hang", "ngung ban", "deactivated"}


def fold(text) -> str:
    text = unicodedata.normalize("NFKC", str(text or "")).lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").strip()


def read_rows(path: str):
    if path.lower().endswith((".xlsx", ".xlsm")):
        try:
            import openpyxl
        except ImportError:
            sys.exit("Reading .xlsx needs openpyxl: pip install openpyxl (or export the sheet as CSV)")
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).active
        it = ws.iter_rows(values_only=True)
        headers = [str(h or "") for h in next(it)]
        for row in it:
            yield {headers[i]: ("" if v is None else v) for i, v in enumerate(row) if i < len(headers)}
    else:
        with open(path, encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f)


def map_columns(headers):
    mapping = {}
    for h in headers:
        fh = fold(h)
        for field, names in ALIASES.items():
            if field not in mapping.values() and fh in names:
                mapping[h] = field
                break
    return mapping


def split_items(value):
    return [x.strip() for x in str(value).replace("|", ";").split(";") if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("--products", default="data/products.json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    data = {"shop_name": "", "products": []}
    if os.path.exists(a.products):
        with open(a.products, encoding="utf-8") as f:
            data = json.load(f)
    products = data["products"]
    by_id = {str(p.get("id")): p for p in products if p.get("id")}
    by_name = {fold(p.get("name")): p for p in products}

    added = updated = skipped = 0
    mapping = None
    for row in read_rows(a.sheet):
        if mapping is None:
            mapping = map_columns(row.keys())
            if "name" not in mapping.values():
                sys.exit(f"No product-name column found. Headers seen: {list(row.keys())}")
            print("Column mapping:", {k: v for k, v in mapping.items()})
        rec = {mapping[k]: v for k, v in row.items() if k in mapping and str(v).strip() != ""}
        name = str(rec.get("name", "")).strip()
        if not name:
            skipped += 1
            continue
        if "highlights" in rec:
            rec["highlights"] = split_items(rec["highlights"])
        if "active" in rec:
            rec["active"] = fold(rec["active"]) not in FALSE_WORDS
        for k in ("price", "original_price"):
            if k in rec:
                rec[k] = str(rec[k]).strip()
        existing = by_id.get(str(rec.get("id"))) or by_name.get(fold(name))
        if existing:
            existing.update({k: v for k, v in rec.items() if k != "id" or not existing.get("id")})
            updated += 1
        else:
            new = {"id": str(rec.get("id") or f"IMP{len(products) + 1:03d}"), "order": len(products) + 1,
                   "aliases": [], "description": "", "highlights": [], "sizes_colors": "", "how_to_use": "",
                   "shipping": "", "return_policy": "", "stock_note": "", "faq": [], "price": "",
                   "original_price": ""}
            new.update(rec)
            new["name"] = name
            products.append(new)
            by_id[new["id"]] = new
            by_name[fold(name)] = new
            added += 1

    print(f"{added} added, {updated} updated, {skipped} rows skipped; catalog now has {len(products)} products")
    if a.dry_run:
        return
    tmp = a.products + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, a.products)
    print("saved", a.products)


if __name__ == "__main__":
    main()
