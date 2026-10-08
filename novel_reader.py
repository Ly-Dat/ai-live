"""AI novel reader: reads a story aloud on the live, chapter after chapter, and steps aside when viewers comment.

Run by the web UI (Novel reader tab -> Start). It is controlled through data/novel_state.json (play / pause / stop /
jump) and reports through data/novel_status.json (shown in the tab and on the overlay).
Do not run it together with the product tour: both would talk at once.
"""
import argparse
import datetime
import json
import os
import sys
import threading
import time
import urllib.request

for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252 and crash on Vietnamese text
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from utils import novel, tiktok_safety  # noqa: E402

LAST_COMMENT = {"t": 0.0}


def watch_comments(log_dir="log"):
    """Mark the time of the last viewer comment (the comment log grows when somebody comments)."""
    def loop():
        pos = {}
        while True:
            d = datetime.date.today()
            path = os.path.join(log_dir, f"comment-{d.year}-{d.month}-{d.day}.txt")
            try:
                size = os.path.getsize(path)
                if path not in pos:
                    pos[path] = size
                elif size > pos[path]:
                    pos[path] = size
                    LAST_COMMENT["t"] = time.time()
            except OSError:
                pass
            time.sleep(0.5)
    threading.Thread(target=loop, daemon=True).start()


def post_reread(api_url, text, voice="", rate=0):
    data = {"type": "reread", "username": "Streamer", "content": text}
    if voice:
        data["voice"] = voice
    if rate:
        data["rate"] = f"{int(rate):+d}%"
    body = json.dumps({"type": "reread", "data": data}).encode("utf-8")
    req = urllib.request.Request(api_url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("code") == 200
    except Exception as e:
        print(f"[novel] cannot reach {api_url}: {type(e).__name__}: {e}", flush=True)
        return False


class Reader:
    def __init__(self, args):
        self.args = args
        self.safety = tiktok_safety.TikTokSafety(args.terms)
        self.started = time.time()
        self.skipped = 0
        self.pos = {"book": "", "chapter": 0, "chunk": 0, "seq": -1}

    # -- helpers
    def control(self):
        return novel.read_control()

    def status(self, state, meta=None, chapter_title="", chunks=None, j=0, role="narrator", **extra):
        chunks = chunks or []
        st = {"state": state, "book": meta["id"] if meta else "", "title": meta["title"] if meta else "",
              "chapter": self.pos["chapter"], "chapter_title": chapter_title, "chunk": j, "chunks": len(chunks), "role": role,
              "text": chunks[j]["text"] if 0 <= j < len(chunks) else "",
              "prev": chunks[j - 1]["text"] if 0 < j <= len(chunks) else "",
              "next": chunks[j + 1]["text"] if 0 <= j + 1 < len(chunks) else "",
              "credit": novel.credit_line(meta) if meta else "", "skipped": self.skipped}
        st.update(extra)
        novel.write_status(st)

    def wait_for_comments(self, s):
        if not s["yield_comments"]:
            return
        need = self.args.reply_wait + self.args.quiet
        while time.time() - LAST_COMMENT["t"] < need:
            c = self.control()
            if c["command"] != "play" or c["seq"] != self.pos["seq"]:
                return
            time.sleep(0.25)

    def sleep_check(self, s):
        return s["sleep_min"] and time.time() - self.started > float(s["sleep_min"]) * 60

    def wait(self, seconds, seq):
        """Sleep `seconds`, but wake early when the seller pauses / stops / jumps. True = keep going."""
        end = time.time() + seconds
        while time.time() < end:
            c = self.control()
            if c["command"] != "play" or c["seq"] != seq:
                return False
            time.sleep(0.2)
        return True

    # -- main loop
    def run(self):
        watch_comments()
        print("[novel] reader ready", flush=True)
        while True:
            ctl = self.control()
            if ctl["command"] == "stop" or not ctl["book"]:
                self.status("idle")
                time.sleep(0.6)
                continue
            if ctl["seq"] != self.pos["seq"]:  # a new start / jump from the tab
                self.pos = {"book": ctl["book"], "chapter": ctl["chapter"], "chunk": ctl["chunk"], "seq": ctl["seq"]}
                self.started = time.time()
            meta = novel.get_book(ctl["book"])
            ok, why = novel.can_read_live(meta)
            if not ok:
                self.status("blocked", meta, message=why)
                time.sleep(1)
                continue
            if ctl["command"] == "pause":
                ch = min(self.pos["chapter"], len(meta["chapters"]) - 1)
                self.status("paused", meta, meta["chapters"][ch]["title"], self.cached(meta, ch), self.pos["chunk"])
                time.sleep(0.5)
                continue
            self.play_chapter(meta, ctl)

    def cached(self, meta, ch):
        names = tuple(sorted(self.control()["settings"].get("characters") or {}))
        key = (meta["id"], ch, names)
        if getattr(self, "_ck", None) != key:
            self._ck = key
            self._chunks = novel.chunks(novel.chapter_body(meta, ch), 180, novel.load_pron(), list(names))
        return self._chunks

    def play_chapter(self, meta, ctl):
        s = ctl["settings"]
        seq = ctl["seq"]
        ci = min(max(self.pos["chapter"], 0), len(meta["chapters"]) - 1)
        title = meta["chapters"][ci]["title"]
        chunks = self.cached(meta, ci)
        j = min(max(self.pos["chunk"], 0), max(len(chunks) - 1, 0))
        if j == 0 and s["announce_chapter"]:
            self.say(f'{meta["title"]}. {title}.', s, seq, meta, title, chunks, 0, "narrator", announce=True)
        while j < len(chunks):
            c = self.control()
            if c["command"] != "play" or c["seq"] != seq:
                return
            s = c["settings"]
            if self.sleep_check(s):
                print("[novel] sleep timer reached, stopping", flush=True)
                novel.write_control(dict(c, command="stop"))
                return
            self.wait_for_comments(s)
            if self.control()["seq"] != seq or self.control()["command"] != "play":
                return
            ch = chunks[j]
            self.pos["chunk"] = j
            novel.save_progress(meta["id"], ci, j)
            if s["safety"] and self.safety.check(ch["text"], "output"):
                self.skipped += 1
                print(f"[novel] skipped one line (TikTok policy filter) in {title}", flush=True)
                j += 1
                continue
            self.say(ch["text"], s, seq, meta, title, chunks, j, ch["role"], speaker=ch.get("speaker", ""))
            if self.control()["seq"] != seq or self.control()["command"] != "play":
                return
            j += 1
        # chapter finished
        if s["auto_next"] and ci + 1 < len(meta["chapters"]):
            self.pos.update(chapter=ci + 1, chunk=0)
            novel.save_progress(meta["id"], ci + 1, 0)
        else:
            self.status("done", meta, title, chunks, len(chunks) - 1)
            novel.write_control(dict(self.control(), command="stop"))
            self.pos["chunk"] = 0

    def say(self, text, s, seq, meta, title, chunks, j, role, announce=False, speaker=""):
        voice = s["voice_dialogue"] if role == "dialogue" and s["voice_dialogue"] else s["voice_narrator"]
        if role == "dialogue" and speaker and (s.get("characters") or {}).get(speaker):
            voice = s["characters"][speaker]
        self.status("playing", meta, title, chunks, j, role)
        if not post_reread(self.args.api, text, voice, s["rate"]):
            self.wait(2.0, seq)
            return
        dur = novel.spoken_seconds(text, self.args.cps, s["rate"]) + float(s["pause_s"])
        # the next line is sent just before this one ends, so there is no dead air between sentences
        self.wait(max(0.2, dur - self.args.lookahead), seq)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AI novel reader")
    ap.add_argument("--api", default="http://127.0.0.1:8082/send")
    ap.add_argument("--terms", default="data/tiktok_policy_terms.json")
    ap.add_argument("--cps", type=float, default=13.0, help="speech speed in characters per second")
    ap.add_argument("--quiet", type=float, default=2.0)
    ap.add_argument("--reply-wait", type=float, default=8.0)
    ap.add_argument("--lookahead", type=float, default=0.8)
    Reader(ap.parse_args()).run()
