"""AI story reader for picture stories (manhua / webtoon style): shows one panel at a time on the overlay and the AI host
narrates it, stepping aside when viewers comment.

Run by the web UI (Story studio -> Read it on my live). Controlled through data/story_state.json, reports through
data/story_status.json (shown in the tab and on the overlay). Do not run it together with the Novel reader or the product tour.
"""
import argparse
import sys
import time

for _stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252 and crash on Vietnamese text
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from novel_reader import CMD_PATH, LAST_COMMENT, post_reread, watch_comments  # noqa: E402
from utils import novel, reader_cmds, story, tiktok_safety  # noqa: E402
import threading  # noqa: E402


class StoryReader:
    def __init__(self, args):
        self.args = args
        self.safety = tiktok_safety.TikTokSafety(args.terms)
        self.started = time.time()
        self.skipped = 0
        self.pos = {"story": "", "panel": 0, "seq": -1}
        self.npanels = 1

    def control(self):
        return story.read_control()

    def status(self, state, meta=None, panel=0, text="", **extra):
        st = {"state": state, "story": meta["id"] if meta else "", "title": meta["title"] if meta else "", "panel": panel,
              "panels": len(meta["panels"]) if meta else 0, "text": text, "credit": story.credit_line(meta) if meta else "",
              "skipped": self.skipped,
              "hint": reader_cmds.hint(int(self.control()["settings"].get("cmd_votes") or 3)) if self.control()["settings"].get("viewer_commands") else ""}
        st.update(extra)
        story.write_status(st)

    def alive(self, seq):
        c = self.control()
        return c["command"] == "play" and c["seq"] == seq

    def beat_loop(self):
        while True:
            try:
                c = self.control()
                on = c["command"] in ("play", "pause") and bool(c["story"]) and c["settings"].get("viewer_commands")
                reader_cmds.heartbeat(CMD_PATH, bool(on), int(c["settings"].get("cmd_votes") or 3))
            except Exception as e:
                print(f"[story] heartbeat: {e}", flush=True)
            time.sleep(3)

    def poll_cmd(self, c):
        if not c["settings"].get("viewer_commands"):
            return False
        cmd = reader_cmds.pop_pending(CMD_PATH)
        if not cmd:
            return False
        i = self.pos["panel"]
        i = min(i + 1, self.npanels - 1) if cmd == "next" else max(i - 1, 0) if cmd == "prev" else i
        story.write_control(dict(c, panel=i, seq=c["seq"] + 1, command="play"))
        print(f"[story] viewers asked: {cmd}", flush=True)
        post_reread(self.args.api, reader_cmds.ACK_VI[cmd], c["settings"].get("voice", ""), c["settings"].get("rate", 0))
        return True

    def wait(self, seconds, seq):
        end = time.time() + seconds
        while time.time() < end:
            c = self.control()
            if c["command"] != "play" or c["seq"] != seq:
                return False
            if self.poll_cmd(c):
                return False
            time.sleep(0.2)
        return True

    def wait_for_comments(self, s, seq):
        if not s["yield_comments"]:
            return
        need = self.args.reply_wait + self.args.quiet
        while time.time() - LAST_COMMENT["t"] < need and self.alive(seq):
            time.sleep(0.25)

    def run(self):
        watch_comments()
        threading.Thread(target=self.beat_loop, daemon=True).start()
        print("[story] reader ready", flush=True)
        while True:
            ctl = self.control()
            if ctl["command"] == "stop" or not ctl["story"]:
                self.status("idle")
                time.sleep(0.6)
                continue
            if ctl["seq"] != self.pos["seq"]:
                self.pos = {"story": ctl["story"], "panel": ctl["panel"], "seq": ctl["seq"]}
                self.started = time.time()
            meta = story.get_story(ctl["story"])
            ok, why = story.can_use(meta)
            if not ok:
                self.status("blocked", meta, message=why)
                time.sleep(1)
                continue
            i = min(max(self.pos["panel"], 0), len(meta["panels"]) - 1)
            self.npanels = len(meta["panels"])
            self.pos["panel"] = i
            if ctl["command"] == "pause":
                self.status("paused", meta, i, meta["panels"][i]["text"])
                time.sleep(0.5)
                continue
            self.play_panel(meta, i, ctl)

    def play_panel(self, meta, i, ctl):
        s, seq = ctl["settings"], ctl["seq"]
        t0 = time.time()
        pieces = story.caption_chunks(meta["panels"][i].get("text", ""), 180)
        pron = novel.load_pron()
        if not pieces:
            self.status("playing", meta, i, "")
        for text in pieces:
            c = self.control()
            if c["command"] != "play" or c["seq"] != seq:
                return
            s = c["settings"]
            if s["sleep_min"] and time.time() - self.started > float(s["sleep_min"]) * 60:
                print("[story] sleep timer reached, stopping", flush=True)
                story.write_control(dict(c, command="stop"))
                return
            self.wait_for_comments(s, seq)
            if not self.alive(seq):
                return
            if s["safety"] and self.safety.check(text, "output"):
                self.skipped += 1
                print(f"[story] skipped one line (TikTok policy filter) on panel {i + 1}", flush=True)
                continue
            self.status("playing", meta, i, text)
            spoken = novel.clean_for_speech(text, pron)
            if not post_reread(self.args.api, spoken, s["voice"], s["rate"]):
                self.wait(2.0, seq)
                continue
            dur = novel.spoken_seconds(spoken, self.args.cps, s["rate"]) + float(s["pause_s"])
            if not self.wait(max(0.2, dur - self.args.lookahead), seq):
                return
        # every picture stays on screen long enough to look at
        if not self.wait(max(0.0, float(s["min_panel_s"]) - (time.time() - t0)), seq):
            return
        if not self.alive(seq):
            return
        if i + 1 < len(meta["panels"]):
            self.pos["panel"] = i + 1
        elif s["loop"]:
            self.pos["panel"] = 0
        else:
            self.status("done", meta, i, "")
            story.write_control(dict(self.control(), command="stop"))
            self.pos["panel"] = 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AI picture-story reader")
    ap.add_argument("--api", default="http://127.0.0.1:8082/send")
    ap.add_argument("--terms", default="data/tiktok_policy_terms.json")
    ap.add_argument("--cps", type=float, default=13.0)
    ap.add_argument("--quiet", type=float, default=2.0)
    ap.add_argument("--reply-wait", type=float, default=8.0)
    ap.add_argument("--lookahead", type=float, default=0.8)
    StoryReader(ap.parse_args()).run()
