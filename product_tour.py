"""
Product tour v2: AI streamer introduces products top -> bottom.

- Each product is presented for 5-10 minutes (random, or product["duration_min"]).
  If the pitch runs out before the time is up, it is repeated (different template
  variant each cycle) until the time is over, then the tour moves to the next product.
- The pitch is sent sentence by sentence. Between sentences the tour checks for viewer
  comments. If a comment arrived, the tour STOPS talking and lets the normal pipeline
  (main.py: safety filter -> quick answer from products.json / LLM -> TTS) reply first.
- After the reply, if nobody comments for ~2s, the tour continues from the sentence it
  was in the middle of (same product, no restart).

How the tour learns about comments
----------------------------------
The tour runs a tiny HTTP listener (default :8091). Make tiktok_bridge.py ALSO post each
comment to it (see README snippet at the bottom of this file).

Run:
    python product_tour.py                       # 5-10 min per product, loop forever
    python product_tour.py --min-minutes 5 --max-minutes 10 --quiet 2
    python product_tour.py --once                # one pass, then stop
"""

import argparse
import json
import os
import random
import re
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import product_catalog, tiktok_safety  # noqa: E402

import datetime

# ------------------------------------------------------------------ comment state
class CommentState:
    """Thread-safe record of the last comment time."""

    def __init__(self):
        self._lock = threading.Lock()
        self.last_comment = 0.0   # time of last comment
        self.count = 0

    def mark(self):
        with self._lock:
            self.last_comment = time.time()
            self.count += 1

    def since(self) -> float:
        with self._lock:
            return time.time() - self.last_comment if self.last_comment else 1e9


STATE = CommentState()


def start_listener(port: int):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            # any POST (/comment) = "a viewer just commented"
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n:
                self.rfile.read(n)
            STATE.mark()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"code":200}')

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[tour] listening for comment pings on http://127.0.0.1:{port}/comment", flush=True)

def start_log_watcher(log_dir="log"):
    def loop():
        last = {}
        while True:
            d = datetime.date.today()
            path = os.path.join(log_dir, f"comment-{d.year}-{d.month}-{d.day}.txt")
            try:
                size = os.path.getsize(path)
                if path in last and size > last[path]:
                    print("[tour] new line in comment log", flush=True)
                    STATE.mark()
                last[path] = size
            except OSError:
                pass
            time.sleep(0.3)
    threading.Thread(target=loop, daemon=True).start()

# ------------------------------------------------------------------ helpers
def post_reread(api_url: str, username: str, text: str) -> bool:
    body = json.dumps({"type": "reread", "data": {"type": "reread", "username": username, "content": text}}).encode("utf-8")
    req = urllib.request.Request(api_url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("code") == 200
    except Exception as e:
        print(f"[tour] cannot reach {api_url}: {type(e).__name__}: {e}", flush=True)
        return False


def split_sentences(text: str):
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p and p.strip()]


def wait_until_free(args) -> None:
    """Block while viewers are commenting / the AI is replying.
    Returns once: (reply window has passed) AND (no new comment for `quiet` seconds)."""
    if STATE.since() > args.reply_wait + args.quiet:
        return
    print("[tour] comment detected -> yielding to reply pipeline", flush=True)
    while True:
        s = STATE.since()
        # reply_wait = estimated time for filter + LLM + TTS to finish speaking the answer
        if s >= args.reply_wait + args.quiet:
            return
        time.sleep(0.25)


def say(args, text: str) -> None:
    """Send one sentence and wait for it to be spoken (interruptible only between sentences)."""
    post_reread(args.api, args.name, text)
    end = time.time() + len(text) / args.cps
    while time.time() < end:
        time.sleep(0.2)


def build_segments(catalog, product, cycle: int, safety):
    """One cycle of the product's script as a list of sentences (all safety-checked)."""
    text = catalog.build_pitch(product, cycle)
    segs = split_sentences(text)

    # rotate one highlight per cycle so repeated cycles are not identical
    hl = product.get("highlights") or []
    if isinstance(hl, list) and hl:
        segs.append(str(hl[cycle % len(hl)]))

    clean = []
    for s in segs:
        hits = safety.check(s, "output")
        if hits:
            print(f"[tour] dropped sentence in '{product.get('name')}': {[(h.category, h.term) for h in hits]}", flush=True)
            continue
        clean.append(s)
    return clean


def present_product(args, catalog, safety, product, round_no: int) -> None:
    minutes = product.get("duration_min") or random.uniform(args.min_minutes, args.max_minutes)
    deadline = time.time() + float(minutes) * 60
    print(f"[tour] round {round_no} -> {product['name']} ({minutes:.1f} min)", flush=True)

    cycle = round_no
    pending = []                       # sentences left in the current cycle
    while time.time() < deadline:
        if not pending:
            pending = build_segments(catalog, product, cycle, safety)
            cycle += 1
            if not pending:
                print(f"[tour] nothing safe to say for '{product['name']}', skipping", flush=True)
                return
        # 1) comments have priority
        wait_until_free(args)
        if time.time() >= deadline:
            break
        # 2) continue with the next unspoken sentence (resume where we stopped)
        say(args, pending.pop(0))


# ------------------------------------------------------------------ main loop
def run(args) -> None:
    safety = tiktok_safety.TikTokSafety(args.terms)
    start_listener(args.listen_port)
    start_log_watcher()
    round_no = 0
    first = True

    while True:
        catalog = product_catalog.ProductCatalog(args.products, args.templates)  # re-read -> hot edit
        products = [p for p in sorted(catalog.all_products(), key=lambda p: p.get("order", 0)) if p.get("active", True)]
        if not products:
            print("[tour] no products, waiting...", flush=True)
            time.sleep(10)
            continue

        if first:
            for key in ("welcome", "disclosure"):
                t = catalog.templates.get(key)
                if t and not safety.check(t, "output"):
                    wait_until_free(args)
                    say(args, t)
            first = False

        for product in products:
            present_product(args, catalog, safety, product, round_no)

        end_text = catalog.templates.get("tour_end")
        if end_text and not safety.check(end_text, "output"):
            wait_until_free(args)
            say(args, end_text)

        round_no += 1
        if args.once or (args.rounds and round_no >= args.rounds):
            return


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AI streamer product tour (timed, comment-priority)")
    ap.add_argument("--api", default="http://127.0.0.1:8082/send")
    ap.add_argument("--products", default="data/products.json")
    ap.add_argument("--templates", default="data/pitch_templates.json")
    ap.add_argument("--terms", default="data/tiktok_policy_terms.json")
    ap.add_argument("--name", default="Streamer")
    ap.add_argument("--min-minutes", type=float, default=5.0)
    ap.add_argument("--max-minutes", type=float, default=10.0)
    ap.add_argument("--quiet", type=float, default=2.0, help="seconds without comments before resuming the pitch")
    ap.add_argument("--reply-wait", type=float, default=8.0,
                    help="estimated seconds the AI needs to speak a comment reply (tour stays silent this long)")
    ap.add_argument("--listen-port", type=int, default=8091, help="port that receives comment pings from tiktok_bridge.py")
    ap.add_argument("--cps", type=float, default=13.0, help="speech speed in characters per second")
    ap.add_argument("--rounds", type=int, default=0, help="0 = loop forever")
    ap.add_argument("--once", action="store_true")
    run(ap.parse_args())

# ----------------------------------------------------------------------------
# README snippet - in tiktok_bridge.py, right where it POSTs a comment to :8082/send,
# add this so the tour knows somebody commented:
#
#     try:
#         urllib.request.urlopen(
#             urllib.request.Request("http://127.0.0.1:8091/comment", data=b"{}", method="POST"),
#             timeout=1)
#     except Exception:
#         pass
# ----------------------------------------------------------------------------