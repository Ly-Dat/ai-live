"""
TikTok LIVE -> AI-Vtuber bridge.

Why: the repo pins TikTokLive 6.0.8, which now fails with "No websocket URL received from TikTok".
This script runs in its OWN venv with TikTokLive 7.x and forwards chat to the app's HTTP API
(POST http://127.0.0.1:8082/send), so the main app's pinned dependencies stay untouched.

Usage (inside the bridge venv):
    python tiktok_bridge.py TIKTOK_USERNAME                 # username WITHOUT @, room must be LIVE
    python tiktok_bridge.py TIKTOK_USERNAME --ignore dat_ly --gifts --joins
    python tiktok_bridge.py TIKTOK_USERNAME --max-per-10s 3 --min-len 4   # busy room: forward less
"""
import argparse
import asyncio
import json
import re
import sys
import time
import urllib.request
from collections import deque

from TikTokLive import TikTokLiveClient
from TikTokLive.client.errors import (
    SignatureRateLimitError,
    UserNotFoundError,
    UserOfflineError,
)
from TikTokLive.events import (
    CommentEvent,
    ConnectEvent,
    DisconnectEvent,
    FollowEvent,
    GiftEvent,
    JoinEvent,
)
from TikTokLive.events import OecLiveShoppingEvent

API_URL = "http://127.0.0.1:8082/send"
IGNORE = set()
MIN_LEN = 3          # drop comments shorter than this (e.g. ".", "ok")
DEBUG_CART = None   # path to dump raw shopping events (--debug-cart)
MAX_PER_10S = 6      # max comments forwarded per 10 seconds (0 = unlimited)
_sent = deque()      # timestamps of forwarded comments


def clean_text(text: str) -> str:
    """Remove TikTok emote codes like [laugh] / [love] so TTS and the word filter don't choke on them."""
    return re.sub(r"\[[A-Za-z_]+\]", "", text or "").strip()


def accept_comment(text: str) -> bool:
    """Drop spam: too short, symbol/emoji-only (TTS can't speak it), or over the rate limit."""
    text = (text or "").strip()
    if len(text) < MIN_LEN or not any(ch.isalnum() for ch in text):
        return False
    if MAX_PER_10S > 0:
        now = time.monotonic()
        while _sent and now - _sent[0] > 10:
            _sent.popleft()
        if len(_sent) >= MAX_PER_10S:
            return False
        _sent.append(now)
    return True


def log(msg: str) -> None:
    print(msg, flush=True)


def post_json(kind: str, data: dict) -> None:
    """POST {"type": kind, "data": {...}} to the app. Blocking; call via asyncio.to_thread."""
    body = json.dumps({"type": kind, "data": {"platform": "tiktok", **data}}).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    if out.get("code") != 200:
        log(f"[app] rejected: {out}")


def ping_tour(username: str = "", content: str = "") -> None:
    """Tell product_tour.py (if running) a viewer commented: it yields to the reply and shows the comment on the overlay."""
    try:
        req = urllib.request.Request("http://127.0.0.1:8091/comment",
                                     data=json.dumps({"username": username, "content": content}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=1).read()
    except Exception:
        pass


async def send(kind: str, data: dict) -> None:
    try:
        if kind == "comment":
            await asyncio.to_thread(ping_tour, str(data.get("username", "")), str(data.get("content", "")))
        await asyncio.to_thread(post_json, kind, data)
    except Exception as e:  # app not running / wrong port
        log(f"[app] cannot reach {API_URL}: {type(e).__name__}: {e}")


def make_client(user: str, gifts: bool, joins: bool, state: dict) -> TikTokLiveClient:
    client = TikTokLiveClient(unique_id=f"@{user}")

    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent):
        state["connected"] = True
        log(f"[OK] Connected to @{user} (room {client.room_id})")

    @client.on(DisconnectEvent)
    async def on_disconnect(event: DisconnectEvent):
        log("[disconnected]")

    @client.on(CommentEvent)
    async def on_comment(event: CommentEvent):
        nick = event.user.nickname if event.user else "?"
        text = clean_text(event.comment)
        if not text or nick in IGNORE:
            return
        if not accept_comment(text):
            return
        log(f"[chat] {nick}: {text}")
        await send("comment", {"username": nick, "content": text})

    @client.on(OecLiveShoppingEvent)
    async def on_product(event: OecLiveShoppingEvent):
        """The seller pinned / popped up a product. TikTok does not push the whole cart over the websocket,
        only the product being shown plus the total count, so the app builds its catalog from these events."""
        if DEBUG_CART:
            # Raw dump for investigating richer cart data (the V2 message may carry the full product list)
            with open(DEBUG_CART, "a", encoding="utf-8") as f:
                f.write(repr(event) + "\n")
        # Anonymous "sold N" counters (TikTok never says who bought); the app turns rises into a thank-you
        try:
            info = event.atmosphere_tag_info
            tags = [{"product_id": str(t.product_id), "desc": t.tag_desc, "count": int(t.count)}
                    for t in (info.atmosphere_tags if info else [])]
            if tags:
                await send("sales", {"tags": tags})
        except Exception as e:
            if DEBUG_CART:
                log(f"[sales] could not read tags: {e}")
        pop = event.pop_product
        if pop is None or not (pop.title or "").strip():
            return
        log(f"[product] {pop.title} - {pop.price} (cart size: {event.live_product_number})")
        await send("product", {
            "product_id": pop.product_id,
            "title": pop.title,
            "price": pop.price,
            "image_url": pop.image_url,
            "open_url": pop.open_url,
            "live_product_number": event.live_product_number,
        })

    if joins:
        @client.on(JoinEvent)
        async def on_join(event: JoinEvent):
            nick = event.user.nickname if event.user else "?"
            if nick in IGNORE:
                return
            log(f"[join] {nick}")
            await send("entrance", {"username": nick, "content": "entered the live room"})

    if gifts:
        @client.on(FollowEvent)
        async def on_follow(event: FollowEvent):
            nick = event.user.nickname if event.user else "?"
            if nick in IGNORE:
                return
            log(f"[follow] {nick}")
            await send("follow", {"username": nick, "content": "followed the channel"})

        @client.on(GiftEvent)
        async def on_gift(event: GiftEvent):
            # streakable gifts: only report when the streak has ended
            if event.gift.streakable and event.streaking:
                return
            nick = event.user.nickname if event.user else "?"
            num = event.repeat_count if event.gift.streakable else 1
            unit = event.gift.diamond_count or 1
            log(f"[gift] {nick} sent {num} x {event.gift.name}")
            await send("gift", {
                "gift_name": event.gift.name,
                "username": nick,
                "num": num,
                "unit_price": unit / 10,
                "total_price": unit * num / 10,
            })

    return client


async def main(user: str, gifts: bool, joins: bool) -> None:
    delay = 5
    while True:
        state = {"connected": False}
        client = make_client(user, gifts, joins, state)
        try:
            log(f"Connecting to @{user} ...")
            await client.connect()  # returns when the connection ends
            log("Connection ended.")
        except UserOfflineError:
            log(f"@{user} is not LIVE right now. Retrying in 30s.")
            await asyncio.sleep(30)
            continue
        except UserNotFoundError:
            raise SystemExit(f"User @{user} not found. Check the username (no @).")
        except SignatureRateLimitError as e:
            log(f"[rate limit] {e}. Waiting 90s.")
            await asyncio.sleep(90)
            continue
        except Exception as e:
            log(f"[ERROR] {type(e).__name__}: {e}")
        # reconnect with backoff; reset after a successful connection
        if state["connected"]:
            delay = 5
        log(f"Reconnecting in {delay}s ...")
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("username", help="TikTok username without @")
    p.add_argument("--api", default=API_URL, help="AI-Vtuber /send endpoint")
    p.add_argument("--ignore", nargs="*", default=[], help="nicknames to ignore (e.g. your own account)")
    p.add_argument("--gifts", action="store_true", help="forward gifts")
    p.add_argument("--joins", action="store_true", help="forward viewer joins (can be noisy)")
    p.add_argument("--min-len", type=int, default=MIN_LEN, help="drop comments shorter than N chars (default 3)")
    p.add_argument("--max-per-10s", type=int, default=MAX_PER_10S, help="max comments forwarded per 10s, 0 = unlimited (default 6)")
    p.add_argument("--debug-cart", default=None, help="append raw shopping/cart events to this file")
    a = p.parse_args()
    DEBUG_CART = a.debug_cart
    API_URL = a.api
    IGNORE = set(a.ignore)
    MIN_LEN = a.min_len
    MAX_PER_10S = a.max_per_10s
    try:
        asyncio.run(main(a.username.lstrip("@"), a.gifts, a.joins))
    except KeyboardInterrupt:
        log("Stopped.")