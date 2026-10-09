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

from utils import novel, novel_companion, reader_cmds, story_llm, tiktok_safety  # noqa: E402

LAST_COMMENT = {"t": 0.0}
CMD_PATH = reader_cmds.DEFAULT_PATH


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


def load_config(path="config.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


class Reader:
    def __init__(self, args):
        self.args = args
        self.safety = tiktok_safety.TikTokSafety(args.terms)
        self.started = time.time()
        self.skipped = 0
        self.pos = {"book": "", "chapter": 0, "chunk": 0, "seq": -1}
        self.nchap = 1
        self.vote_hint = ""
        self.config = load_config()
        self.recap_cache = {}

    # -- AI companion
    def llm(self, temperature=0.3):
        """Direct call to the OpenAI-compatible server from config.json (no Start Run needed); other providers: no AI here."""
        if str(self.config.get("chat_type", "chatgpt")) != "chatgpt":
            raise RuntimeError("companion AI needs the OpenAI-compatible setting")
        model = self.control()["settings"].get("ai_model") or ""
        return story_llm.make_llm(self.config, model, "", temperature)

    def ask_loop(self):
        """Answers viewers' !hoi questions from the text read so far (never from later chapters)."""
        while True:
            time.sleep(1.5)
            try:
                c = self.control()
                s = c["settings"]
                if not (s.get("ask_viewers") and c["command"] in ("play", "pause") and c["book"]):
                    continue
                q = reader_cmds.pop_ask(CMD_PATH)
                if not q:
                    continue
                meta = novel.get_book(c["book"])
                text = novel_companion.viewer_answer(meta, q["user"], q["q"], self.pos["chapter"], self.pos["chunk"], self.llm(0.3),
                                                     self.safety.check if s.get("safety") else None)
                print(f"[novel] viewer question from {q['user']}: {'answered' if text else 'skipped'}", flush=True)
                if text:
                    post_reread(self.args.api, text, s.get("voice_narrator", ""), s.get("rate", 0))
            except Exception as e:
                print(f"[novel] viewer question failed: {e}", flush=True)

    def ai_recap(self, meta, ci):
        """AI 'previously on ...' for chapter ci (cached per chapter); falls back to the plain recap if the AI is unreachable."""
        key = (meta["id"], ci)
        if key not in self.recap_cache:
            try:
                self.recap_cache[key] = novel_companion.previously_on(meta, ci, self.llm(0.5))
            except Exception as e:
                print(f"[novel] AI recap failed ({e}); using the plain recap", flush=True)
                self.recap_cache[key] = ""
        return self.recap_cache[key] or novel.recap_text(meta, ci)

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
              "credit": novel.credit_line(meta) if meta else "", "skipped": self.skipped, "hint": self.hint_text()}
        st.update(extra)
        novel.write_status(st)

    def hint_text(self):
        if self.vote_hint:
            return self.vote_hint
        s = self.control()["settings"]
        return reader_cmds.hint(int(s.get("cmd_votes") or 3)) if s.get("viewer_commands") else ""

    def beat_loop(self):
        """Tells the live app that viewer commands / votes are on (comments are only swallowed while this beats)."""
        while True:
            try:
                c = self.control()
                s = c["settings"]
                on = c["command"] in ("play", "pause") and bool(c["book"]) and (s.get("viewer_commands") or s.get("chapter_vote") or s.get("ask_viewers"))
                reader_cmds.heartbeat(CMD_PATH, bool(on), int(s.get("cmd_votes") or 3), ask=bool(s.get("ask_viewers")))
            except Exception as e:
                print(f"[novel] heartbeat: {e}", flush=True)
            time.sleep(3)

    def poll_cmd(self, c):
        """Apply a viewer command (next / back / again). True = the position changed, stop waiting."""
        if not c["settings"].get("viewer_commands"):
            return False
        cmd = reader_cmds.pop_pending(CMD_PATH)
        if not cmd:
            return False
        ci, j = self.pos["chapter"], self.pos["chunk"]
        if cmd == "next":
            ci, j = min(ci + 1, self.nchap - 1), 0
        elif cmd == "prev":
            ci, j = max(ci - 1, 0), 0
        else:
            j = max(0, j - 3)
        novel.write_control(dict(c, chapter=ci, chunk=j, seq=c["seq"] + 1, command="play"))
        print(f"[novel] viewers asked: {cmd}", flush=True)
        post_reread(self.args.api, reader_cmds.ACK_VI[cmd], c["settings"].get("voice_narrator", ""), c["settings"].get("rate", 0))
        return True

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
            if self.poll_cmd(c):
                return False
            time.sleep(0.2)
        return True

    # -- main loop
    def run(self):
        watch_comments()
        threading.Thread(target=self.beat_loop, daemon=True).start()
        threading.Thread(target=self.ask_loop, daemon=True).start()
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
        self.nchap = len(meta["chapters"])
        ci = min(max(self.pos["chapter"], 0), len(meta["chapters"]) - 1)
        title = meta["chapters"][ci]["title"]
        chunks = self.cached(meta, ci)
        j = min(max(self.pos["chunk"], 0), max(len(chunks) - 1, 0))
        if j == 0 and s.get("recap") and ci > 0 and not self.pos.get("recapped"):
            self.pos["recapped"] = True
            rc = self.ai_recap(meta, ci) if s.get("ai_recap") else novel.recap_text(meta, ci)
            if rc:
                self.say(rc, s, seq, meta, title, chunks, 0, "narrator", announce=True)
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
        self.stat(0, 1)
        if s.get("chapter_vote") and ci + 1 < len(meta["chapters"]):
            res = self.run_vote(meta, ci, s, seq, title, chunks)
            if res == "interrupted":
                return
            if res == "repeat":
                c = self.control()
                novel.write_control(dict(c, chapter=ci, chunk=0, seq=c["seq"] + 1, command="play"))
                return
            s = dict(s, auto_next=True)
        if s["auto_next"] and ci + 1 < len(meta["chapters"]):
            self.pos.update(chapter=ci + 1, chunk=0)
            novel.save_progress(meta["id"], ci + 1, 0)
        else:
            self.status("done", meta, title, chunks, len(chunks) - 1)
            novel.write_control(dict(self.control(), command="stop"))
            self.pos["chunk"] = 0

    def run_vote(self, meta, ci, s, seq, title, chunks):
        """End-of-chapter vote: 1 = next chapter, 2 = read it again. Returns 'next', 'repeat' or 'interrupted'."""
        secs = max(8, int(s.get("vote_s") or 20))
        ask = (f"Hết chương rồi cả nhà ơi! Comment 1 để nghe chương tiếp theo, comment 2 để nghe lại chương này. "
               f"Mình chờ {secs} giây nha.")
        self.vote_hint = "Bình chọn: comment 1 = nghe tiếp · 2 = nghe lại"
        try:
            reader_cmds.begin_vote(CMD_PATH, secs + novel.spoken_seconds(ask, self.args.cps, s["rate"]))
            self.say(ask, s, seq, meta, title, chunks, len(chunks) - 1, "narrator", announce=True)
            if not self.wait(secs, seq):
                return "interrupted"
            r = reader_cmds.end_vote(CMD_PATH)
            if r["winner"] == "repeat":
                msg = f'Kết quả: {r["repeat"]} bạn muốn nghe lại, {r["next"]} bạn muốn nghe tiếp. Mình đọc lại chương này nha.'
            elif r["next"] + r["repeat"]:
                msg = f'Kết quả: {r["next"]} bạn muốn nghe tiếp, {r["repeat"]} bạn muốn nghe lại. Mình đọc tiếp nha.'
            else:
                msg = "Chưa có bạn nào bình chọn, mình đọc tiếp nha."
            self.say(msg, s, seq, meta, title, chunks, len(chunks) - 1, "narrator", announce=True)
            return r["winner"]
        finally:
            self.vote_hint = ""

    def stat(self, seconds, chapters):
        try:
            novel_companion.record_stats(seconds, chapters)
        except Exception:
            pass

    def say(self, text, s, seq, meta, title, chunks, j, role, announce=False, speaker=""):
        voice = novel.voice_for({"role": role, "speaker": speaker}, s)
        self.status("playing", meta, title, chunks, j, role)
        if not post_reread(self.args.api, text, voice, s["rate"]):
            self.wait(2.0, seq)
            return
        dur = novel.spoken_seconds(text, self.args.cps, s["rate"]) + float(s["pause_s"])
        if not announce:
            self.stat(dur, 0)
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
