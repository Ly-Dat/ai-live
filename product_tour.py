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

import mimetypes

import ast

from collections import deque

PENDING = deque()            
SAID = deque(maxlen=30)     
META = {"reply_at": 0.0}
BOX_LOCK = threading.Lock()
HOLD = 12      
PAIR_GAP = 6     
PENDING_TTL = 40 

CURRENT = {"name": "", "images": []}   # product being presented (overlay reads this)
BOX = {"user": "", "comment": "", "reply": ""}   # chat box on the overlay

IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "product_images")

OVERLAY_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;background:transparent;overflow:hidden;font-family:Segoe UI,Arial,sans-serif}
#chat{position:absolute;top:2%;left:4%;right:4%;max-height:24%;padding:14px 18px;border-radius:16px;
  background:rgba(0,0,0,.55);color:#fff;font-size:3.2vh;line-height:1.35;display:none;overflow:hidden}
#chat .u{color:#ffd166;font-weight:600}
#chat .a{color:#7ee0ff;font-weight:600}
#chat div+div{margin-top:8px}
#imgs{position:absolute;left:0;right:0;bottom:2%;height:40%}
#imgs img{position:absolute;inset:0;margin:auto;max-width:100%;max-height:100%;border-radius:12px;
  opacity:0;transition:opacity .6s}
#imgs img.on{opacity:1}
</style></head><body>
<div id="chat"><div id="c"></div><div id="r"></div></div>
<div id="imgs"><img id="a"></div>
<script>
const SECONDS = 5;
let key = "", list = [], i = 0;
const el = document.getElementById("a");
const esc = s => s.replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function show() {
  if (!list.length) { el.classList.remove("on"); return; }
  el.src = "/img/" + encodeURIComponent(list[i % list.length]);
  el.classList.add("on");
}
function chat(b) {
  const c = document.getElementById("c"), r = document.getElementById("r");
  c.innerHTML = b.comment ? '<span class="u">' + esc(b.user || "Viewer") + ':</span> ' + esc(b.comment) : "";
  r.innerHTML = b.reply ? '<span class="a">AI:</span> ' + esc(b.reply) : "";
  document.getElementById("chat").style.display = (b.comment || b.reply) ? "block" : "none";
}
async function poll() {
  try {
    const d = await (await fetch("/current", {cache: "no-store"})).json();
    const k = d.name + "|" + d.images.join(",");
    if (k !== key) { key = k; list = d.images; i = 0; show(); }
    chat(d.chat);
  } catch (e) {}
}
setInterval(poll, 700);
setInterval(() => { if (list.length) { i++; show(); } }, SECONDS * 1000);
poll();
</script></body></html>"""

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

def is_own(reply: str) -> bool:
    r = reply.strip().lower()
    return any(r in s or s in r for s in SAID)


def show_answer(reply: str):
    now = time.time()
    with BOX_LOCK:
        while PENDING and now - PENDING[0][0] > PENDING_TTL:
            PENDING.popleft()
        if now - META["reply_at"] > PAIR_GAP:         
            if PENDING:
                _, u, c = PENDING.popleft()
                BOX.update(user=u, comment=c)
            else:
                BOX.update(user="", comment="")   
        BOX["reply"] = reply     
        META["reply_at"] = now


def start_listener(port: int):
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(n) if n else b""
            try:
                d = json.loads(raw.decode("utf-8")) if raw else {}
            except Exception:
                d = {}
            if self.path.startswith("/reply"):
                show_answer(str(d.get("content", "")))
            else:
                if d.get("content"):
                    with BOX_LOCK:
                        PENDING.append((time.time(), str(d.get("username", "")), str(d["content"])))
                STATE.mark()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"code":200}')
            
        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.startswith("/overlay"):
                self._send(200, "text/html; charset=utf-8", OVERLAY_HTML.encode("utf-8"))
            elif self.path.startswith("/current"):
                self._send(200, "application/json", json.dumps({**CURRENT, "chat": BOX}).encode("utf-8"))
            elif self.path.startswith("/img/"):
                name = os.path.basename(self.path[5:].split("?")[0])
                from urllib.parse import unquote
                fp = os.path.join(IMG_DIR, unquote(name))
                if os.path.isfile(fp):
                    with open(fp, "rb") as fh:
                        self._send(200, mimetypes.guess_type(fp)[0] or "image/jpeg", fh.read())
                else:
                    self._send(404, "text/plain", b"")
            else:
                self._send(404, "text/plain", b"")
        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"[tour] listening for comment pings on http://127.0.0.1:{port}/comment", flush=True)

def start_log_watcher(log_dir="log"):
    def loop():
        pos = {}
        while True:
            d = datetime.date.today()
            for kind in ("comment", "log"):
                path = os.path.join(log_dir, f"{kind}-{d.year}-{d.month}-{d.day}.txt")
                try:
                    size = os.path.getsize(path)
                except OSError:
                    continue
                if path not in pos:
                    pos[path] = size          
                    continue
                if size <= pos[path]:
                    continue
                with open(path, "rb") as fh:
                    fh.seek(pos[path])
                    chunk = fh.read()
                cut = chunk.rfind(b"\n") + 1  
                pos[path] += cut
                text = chunk[:cut].decode("utf-8", "ignore")
                if kind == "comment":
                    STATE.mark()
                    continue
                for line in text.splitlines():
                    if "received data:" not in line or "'content_type': 'answer'" not in line:
                        continue
                    try:
                        obj = ast.literal_eval(line.split("received data:", 1)[1].strip())
                        reply = str(obj["data"]["content"]).strip()
                    except Exception:
                        continue
                    if reply:
                        if is_own(reply):          
                            continue
                        show_answer(reply)
                        STATE.mark()
                        print(f"[tour] AI reply -> overlay: {reply[:60]}", flush=True)
            with BOX_LOCK:
                if (BOX["reply"] or BOX["comment"]) and time.time() - META["reply_at"] > HOLD:
                    BOX.update(user="", comment="", reply="")
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
    SAID.append(text.strip().lower())
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
    
    CURRENT.update(name=product.get("name", ""),
        images=[os.path.basename(x) for x in (product.get("images") or [])])
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
            
        CURRENT.update(name="", images=[])
        
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