"""Turn a recorded live session into a post-live report.

  python report_session.py                      # latest session -> stdout
  python report_session.py --file log/analytics/session-XXXX.jsonl --out report.md
  python report_session.py --json               # raw summary
"""
import argparse
import json
import os
import sys

from utils import live_analytics, product_catalog


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", help="session .jsonl (default: latest)")
    ap.add_argument("--dir", default="log/analytics")
    ap.add_argument("--products", default="data/products.json")
    ap.add_argument("--out", help="write markdown here instead of stdout")
    ap.add_argument("--json", action="store_true", help="print the raw summary as JSON")
    a = ap.parse_args()
    path = a.file or live_analytics.latest_session_file(a.dir)
    if not path or not os.path.exists(path):
        sys.exit("No session file found. Run a live first (analytics.enable must be true).")
    summary = live_analytics.summarize(live_analytics.load_events(path))
    if a.json:
        text = json.dumps(summary, ensure_ascii=False, indent=2)
    else:
        names, shop = {}, ""
        if os.path.exists(a.products):
            data = json.load(open(a.products, encoding="utf-8"))
            names = {p["id"]: p["name"] for p in data.get("products", [])}
            shop = data.get("shop_name", "")
        text = live_analytics.report_markdown(summary, names, shop)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"Wrote {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
