"""
Simulated TikTok LIVE room: try the whole pipeline without going live.

  python simulate_live.py --offline              # no server needed: shows what the bot would do with each viewer comment
  python simulate_live.py                        # replay the scenario into the running app (POST /send), the avatar speaks
  python simulate_live.py --speed 3 --loop       # faster / repeat forever
  python simulate_live.py --scenario my.json     # your own script

Scenario file: {"steps": [{"after": 3, "type": "comment", "data": {"username": "A", "content": "..."}, "expect": "quick"}]}
`expect` (optional, used by --offline and the unit tests): blocked | quick | buy_cta | llm.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

from utils import product_catalog, simulator, tiktok_safety


def load_scenario(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["steps"]


def run_offline(steps, products, templates, terms):
    safety = tiktok_safety.TikTokSafety(terms)
    catalog = product_catalog.ProductCatalog(products, templates)
    bad = 0
    for s in steps:
        if s["type"] != "comment":
            print(f"  [{s['type']:<8}] {json.dumps(s['data'], ensure_ascii=False)}")
            continue
        r = simulator.evaluate_comment(s["data"]["content"], safety, catalog)
        flag = ""
        if s.get("expect") and s["expect"] != r["verdict"]:
            flag, bad = f"   <-- expected {s['expect']}", bad + 1
        extra = f" {r['categories']}" if r["categories"] else ""
        print(f"  [{r['verdict']:<8}] ({r['intent']}) {r['text']}{extra}{flag}")
        if r["reply"]:
            print(f"             -> {r['reply']}")
    print("\nAll expectations met." if not bad else f"\n{bad} unexpected result(s).")
    return bad


def run_online(steps, api, speed, loop):
    while True:
        for s in steps:
            time.sleep(max(0, s.get("after", 2)) / speed)
            body = json.dumps({"type": s["type"], "data": s["data"]}).encode("utf-8")
            req = urllib.request.Request(api, data=body, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    print(f"[{s['type']}] {json.dumps(s['data'], ensure_ascii=False)} -> {r.status}")
            except Exception as e:
                sys.exit(f"Cannot reach the app at {api}: {e}\nStart it first (python main.py) or use --offline.")
        if not loop:
            return


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", default=os.path.join(here, "data", "sim_scenario.json"))
    ap.add_argument("--api", default="http://127.0.0.1:8082/send")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--products", default="data/products.json")
    ap.add_argument("--templates", default="data/pitch_templates.json")
    ap.add_argument("--terms", default="data/tiktok_policy_terms.json")
    a = ap.parse_args()
    steps = load_scenario(a.scenario)
    if a.offline:
        sys.exit(1 if run_offline(steps, a.products, a.templates, a.terms) else 0)
    run_online(steps, a.api, max(a.speed, 0.1), a.loop)


if __name__ == "__main__":
    main()
