"""
Product tour: makes the AI streamer introduce EVERY product in the cart, over and over,
while comment replies keep working through the normal pipeline.

Run next to the main app (same machine):
    python product_tour.py                    # uses data/products.json, posts to http://127.0.0.1:8082/send
    python product_tour.py --gap 20 --rounds 0
    python product_tour.py --products data/products.json --once      # one pass, then stop

How it works: each pitch is sent as a "reread" message, which the app speaks directly with the
configured TTS (no LLM involved, so nothing is invented). Every pitch is run through the TikTok
safety filter first; a pitch that trips it is skipped and logged so you can fix the catalog text.
products.json is re-read on every pass, so you can edit it while live.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import product_catalog, tiktok_safety  # noqa: E402

CHARS_PER_SECOND = 13.0  # rough speech rate used to avoid piling up audio (override with --cps)


def post_reread(api_url: str, username: str, text: str) -> bool:
    body = json.dumps({"type": "reread", "data": {"type": "reread", "username": username, "content": text}}).encode("utf-8")
    req = urllib.request.Request(api_url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        return out.get("code") == 200
    except Exception as e:
        print(f"[tour] cannot reach {api_url}: {type(e).__name__}: {e}", flush=True)
        return False


def speak(args, safety, text: str) -> None:
    """Send a non-product line (disclosure, reminder) if it passes the safety filter, then wait for it to be spoken."""
    if not text or safety.check(text, "output"):
        return
    post_reread(args.api, args.name, text)
    time.sleep(len(text) / CHARS_PER_SECOND + args.gap)


def run(args) -> None:
    global CHARS_PER_SECOND
    CHARS_PER_SECOND = args.cps
    safety = tiktok_safety.TikTokSafety(args.terms)
    round_no = 0
    first = True
    while True:
        catalog = product_catalog.ProductCatalog(args.products, args.templates)
        products = sorted(catalog.all_products(), key=lambda p: p.get("order", 0))
        if not products:
            print("[tour] no products in catalog, waiting...", flush=True)
            time.sleep(10)
            continue

        if first and catalog.templates.get("welcome"):
            post_reread(args.api, args.name, catalog.templates["welcome"])
            time.sleep(len(catalog.templates["welcome"]) / CHARS_PER_SECOND + args.gap)
        first = False

        # Say the AI disclosure at the start and every few passes (TikTok asks creators to label AI content)
        if round_no % max(1, args.disclosure_every) == 0:
            speak(args, safety, catalog.templates.get("disclosure"))
        interstitials = catalog.templates.get("interstitial", [])

        for idx, product in enumerate(products):
            # a short reminder (follow / ask questions / open the cart) after every 2 products
            if idx and idx % 2 == 0 and interstitials:
                speak(args, safety, interstitials[(round_no + idx) % len(interstitials)])
            pitch = catalog.build_pitch(product, round_no)
            hits = safety.check(pitch, "output")
            if hits:
                print(f"[tour] SKIPPED '{product['name']}': {[(h.category, h.term) for h in hits]}", flush=True)
                continue
            print(f"[tour] round {round_no} -> {product['name']}", flush=True)
            post_reread(args.api, args.name, pitch)
            time.sleep(len(pitch) / CHARS_PER_SECOND + args.gap)

        end_text = catalog.templates.get("tour_end")
        if end_text and not safety.check(end_text, "output"):
            post_reread(args.api, args.name, end_text)
            time.sleep(len(end_text) / CHARS_PER_SECOND + args.gap)

        round_no += 1
        if args.once or (args.rounds and round_no >= args.rounds):
            return
        time.sleep(args.pause)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AI streamer product tour")
    ap.add_argument("--api", default="http://127.0.0.1:8082/send")
    ap.add_argument("--products", default="data/products.json")
    ap.add_argument("--templates", default="data/pitch_templates.json")
    ap.add_argument("--terms", default="data/tiktok_policy_terms.json")
    ap.add_argument("--name", default="Streamer", help="username shown in logs/captions")
    ap.add_argument("--gap", type=float, default=8.0, help="extra seconds after each pitch, leaves room for comment replies")
    ap.add_argument("--pause", type=float, default=30.0, help="seconds between full passes")
    ap.add_argument("--rounds", type=int, default=0, help="0 = loop forever")
    ap.add_argument("--cps", type=float, default=13.0, help="assumed speech speed in characters per second")
    ap.add_argument("--disclosure-every", type=int, default=4, help="say the AI disclosure every N passes (1 = every pass)")
    ap.add_argument("--once", action="store_true")
    run(ap.parse_args())
