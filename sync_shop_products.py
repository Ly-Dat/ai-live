"""
Pull the seller's products from the TikTok Shop Partner API into data/products.json.

    python sync_shop_products.py                    # activate-status products, merge into data/products.json
    python sync_shop_products.py --details          # also fetch each product's detail (description, options)
    python sync_shop_products.py --refresh-token    # refresh the access token first and save it
    python sync_shop_products.py --dry-run

Credentials: tiktok_shop_credentials.json (git-ignored) or TTS_* env vars - see utils/tiktok_shop_api.py.
Existing catalog entries (matched by id or name) are only filled in where empty / updated for price+active;
anything you wrote by hand (highlights, faq, how_to_use...) is kept.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import product_catalog, tiktok_shop_api as api  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", default="data/products.json")
    ap.add_argument("--credentials", default=api.CREDENTIALS_FILE)
    ap.add_argument("--status", default="ACTIVATE")
    ap.add_argument("--details", action="store_true")
    ap.add_argument("--refresh-token", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    creds = api.load_credentials(a.credentials)
    client = api.TikTokShopClient(creds)
    changed_creds = False
    if a.refresh_token:
        client.refresh_access_token()
        changed_creds = True
    if not creds.get("shop_cipher"):
        client.get_shop_cipher()
        changed_creds = True
    if changed_creds and not a.dry_run and os.path.exists(a.credentials):
        with open(a.credentials, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=2)
        print("credentials file updated (new token / shop cipher)")

    records = []
    for p in client.iter_products(status=a.status):
        if a.details:
            p = {**p, **client.get_product(p["id"])}
        records.append(api.to_catalog_entry(p))
    print(f"fetched {len(records)} products from TikTok Shop")

    catalog = product_catalog.ProductCatalog(a.products, "data/pitch_templates.json")
    added, updated = product_catalog.merge_records(catalog.products, records)
    print(f"{added} added, {updated} updated; catalog now has {len(catalog.products)} products")
    if not a.dry_run:
        catalog.save()
        print("saved", a.products)


if __name__ == "__main__":
    main()
