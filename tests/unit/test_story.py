import re
import io, os, shutil, subprocess, tempfile, zipfile
import pytest
from utils import story, story_video as sv

def png(color=(10, 20, 30)):
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (40, 60), color).save(b, "PNG"); return b.getvalue()

@pytest.fixture
def root():
    d = tempfile.mkdtemp(); yield d; shutil.rmtree(d, ignore_errors=True)

def test_parse_script_paragraphs_and_markers():
    assert story.parse_script("a\n\nb\n\nc\n\nd", 3) == ["a", "b", "c d"]
    assert story.parse_script("only", 3) == ["only", "", ""]
    assert story.parse_script("Panel 2: two\nPanel 1: one", 3) == ["one", "two", ""]

def test_caption_chunks():
    cs = story.caption_chunks("Trời mưa. Cô gái đứng một mình trước cổng trường, tay ôm chiếc ô cũ kỹ và nhìn ra con đường vắng tanh phía xa.", 50)
    assert all(len(c) <= 55 for c in cs) and len(cs) >= 3
    assert story.caption_chunks("   ") == []

def test_add_story_and_licence_gate(root):
    m = story.add_story("Test", "Me", "own", "", [("10.png", png()), ("2.png", png())], "x\n\ny", root)
    assert [p["text"] for p in m["panels"]] == ["x", "y"]
    assert story.can_use(m)[0]
    story.update_license(m["id"], "copyrighted", root)
    assert not story.can_use(story.get_story(m["id"], root))[0]
    m2 = story.add_story("T2", "", "cc-by", "", [("a.png", png())], "", root)
    assert not story.can_use(m2)[0]  # credit needs the artist's name
    assert story.add_story("T3", "", "weird", "", [("a.png", png())], "", root)["license"] == "unknown"

def test_add_story_rejects_non_pictures(root):
    with pytest.raises(ValueError):
        story.add_story("T", "", "own", "", [("a.png", b"not a picture")], "", root)
    with pytest.raises(ValueError):
        story.add_story("T", "", "own", "", [], "", root)

def test_zip_images_ignores_paths_and_other_files():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("../evil.png", png()); z.writestr("ch/10.png", png()); z.writestr("ch/2.png", png()); z.writestr("a.txt", "x")
    names = [n for n, _ in story.zip_images(b.getvalue())]
    assert names == ["2.png", "10.png", "evil.png"]

def test_edit_panels(root):
    m = story.add_story("E", "", "own", "", [("1.png", png()), ("2.png", png()), ("3.png", png())], "a\n\nb\n\nc", root)
    story.move_panel(m["id"], 0, 1, root)
    assert [p["text"] for p in story.get_story(m["id"], root)["panels"]] == ["b", "a", "c"]
    story.delete_panel(m["id"], 0, root)
    assert [p["text"] for p in story.get_story(m["id"], root)["panels"]] == ["a", "c"]
    story.set_texts(m["id"], ["x", "y"], root)
    assert story.get_story(m["id"], root)["panels"][1]["text"] == "y"
    assert story.get_story("../../etc", root) is None

def test_plot_prompt_and_parse():
    assert "exactly 8 picture panels" in story.plot_prompt("horror", "x", 8, "scary", "en")
    ans = "**PANEL 1**\nPICTURE: a door\nNARRATION: It opened.\n\nPANEL 2\nPICTURE: a girl\nNARRATION: She ran.\nShe fell."
    plot = story.parse_plot(ans)
    assert [p["narration"] for p in plot] == ["It opened.", "She ran. She fell."]
    assert story.plot_to_script(plot).startswith("Panel 1: It opened.")
    assert story.parse_plot("nothing useful") == []

def test_post_kit_has_credit_and_follow():
    kit = story.post_kit({"title": "T", "author": "A", "license": "cc-by", "source": ""}, "vi", 1, "Hook?", "fantasy", "Song - X")
    assert "phần 2" in kit and "#fantasy" in kit and "Credit:" in kit and "Music: Song - X" in kit

def test_overlay_story(root):
    import time
    st = {"state": "playing", "story": "s", "panel": 1, "panels": 3, "text": "t", "title": "T", "updated": time.time()}
    o = story.overlay_story(st, {"show_text": True}, time.time())
    assert o["image"] == "/story-img/s/1" and o["index"] == 2
    assert story.overlay_story(st, {"show_text": False}, time.time()) is None
    assert story.overlay_story(dict(st, updated=1), {"show_text": True}, time.time()) is None

@pytest.mark.skipif(not (sv.ffmpeg_exe() and sv.find_font()), reason="needs ffmpeg and a font")
def test_video_pipeline_with_fake_tts(root):
    pytest.importorskip("PIL")
    ff = sv.ffmpeg_exe()
    m = story.add_story("V", "", "own", "", [("1.png", png((200, 50, 50))), ("2.png", png((50, 50, 200)))], "Một câu. Hai câu.\n\n", root)
    def tts(t, v, r, o):
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=0.6", "-q:a", "5", o], check=True)
    out = os.path.join(root, "o", "v.mp4")
    res = sv.build(sv.panels_from_story(m, root), out, tts=tts, title="V", part=1, hook="Hook", outro="Bye")
    assert os.path.getsize(out) > 1000 and os.path.exists(res["srt"]) and os.path.exists(res["cover"])
    assert "Hook" in open(res["srt"], encoding="utf-8").read() and res["pieces"] == 4


def test_split_strip_cuts_at_gutters():
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (400, 3000), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for k, (a, b) in enumerate([(0, 900), (960, 1900), (1960, 3000)]):
        for y in range(a, b, 28):   # busy content, gaps (8px) shorter than a gutter
            d.rectangle((20, y, 380, y + 20), fill=(40 * (k + 1), 90, 160 - 30 * k))
    b = io.BytesIO(); im.save(b, "PNG")
    parts = story.split_strip(b.getvalue(), "s")
    assert len(parts) == 3 and parts[0][0] == "s-001.png"
    heights = [Image.open(io.BytesIO(p[1])).height for p in parts]
    assert sum(heights) == 3000 and all(h > 800 for h in heights)
    short = Image.new("RGB", (400, 500), (9, 9, 9)); bb = io.BytesIO(); short.save(bb, "PNG")
    assert len(story.split_strip(bb.getvalue(), "x")) == 1


def test_add_story_splits_strips(root):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (300, 2400), (255, 255, 255)); d = ImageDraw.Draw(im)
    for y in range(0, 1100, 30): d.rectangle((10, y, 290, y + 12), fill=(10, 10, 10))
    for y in range(1200, 2400, 30): d.rectangle((10, y, 290, y + 12), fill=(10, 10, 10))
    b = io.BytesIO(); im.save(b, "PNG")
    m = story.add_story("S", "", "own", "", [("strip.png", b.getvalue())], "", root, split_strips=True)
    assert len(m["panels"]) == 2


# ---------------------------------------------------------------- recap video features
def _tts(ff):
    def tts(t, v, r, o):
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=0.8", "-q:a", "5", o], check=True)
    return tts


def _video_size(ff, path):
    import re
    r = subprocess.run([ff, "-i", path], capture_output=True, text=True)
    m = re.search(r"Video:.*?(\d{3,4})x(\d{3,4})", r.stderr)
    return int(m.group(1)), int(m.group(2))


def test_plan_groups_pieces_by_panel():
    segs = sv.plan([{"image": "a.png", "text": "Một. Hai."}, {"image": "b.png", "text": "Ba."}], "Hook", "Bye")
    assert [s["panel"] for s in segs] == [0, 0, 0, 1, 1][:len(segs)] or segs[0]["panel"] == 0 and segs[-1]["panel"] == 1


def test_motion_modes_and_zoompan():
    assert sv.motion_for("off", 3) == "" and sv.motion_for("zoom", 0) == "zoom_in" and sv.motion_for("zoom", 1) == "zoom_out"
    assert [sv.motion_for("auto", i) for i in range(5)] == ["zoom_in", "pan_right", "zoom_out", "pan_left", "zoom_in"]
    f = sv.zoompan_filter("pan_left", 0.25, 0.5, 50, (1080, 1920), 25)
    assert "d=50" in f and "s=1080x1920" in f and "0.2500" in f
    with pytest.raises(ValueError):
        sv.zoompan_filter("spin", 0, 1, 10, (10, 10), 25)


def test_split_panels_never_cuts_inside_a_panel():
    panels = [{"image": None, "text": "Câu này khá dài để nói. " * 4} for _ in range(6)]
    one = sv.estimate_seconds(panels[:1])
    parts = sv.split_panels(panels, one * 2.5)
    assert sum(len(p) for p in parts) == 6 and len(parts) == 3 and all(len(p) == 2 for p in parts)
    assert sv.split_panels(panels, 0) == [panels]
    assert len(sv.split_panels(panels, 0.1)) == 6


@pytest.mark.skipif(not (sv.ffmpeg_exe() and sv.find_font()), reason="needs ffmpeg and a font")
@pytest.mark.parametrize("fmt,motion", [("vertical", "auto"), ("wide", "zoom"), ("vertical", "off")])
def test_video_with_motion_formats_and_marks(root, fmt, motion):
    pytest.importorskip("PIL")
    ff = sv.ffmpeg_exe()
    m = story.add_story("M", "", "own", "", [("1.png", png((200, 50, 50))), ("2.png", png((50, 50, 200))), ("3.png", png((50, 200, 50)))],
                        "Một câu. Hai câu.\n\nBa câu.\n\nBốn câu.", root)
    out = os.path.join(root, "o", "m.mp4")
    res = sv.build(sv.panels_from_story(m, root), out, tts=_tts(ff), title="M", part=2, hook="Hook", outro="Bye", size=sv.FORMATS[fmt],
                   fps=10, motion=motion, fade=True)
    assert _video_size(ff, out) == sv.FORMATS[fmt]
    assert len(res["marks"]) == 3 and res["marks"][0]["t"] == 0
    assert sv.audio_seconds(ff, out) > res["seconds"] - 1


@pytest.mark.skipif(not (sv.ffmpeg_exe() and sv.find_font()), reason="needs ffmpeg and a font")
def test_build_parts_end_on_cliffhanger(root):
    ff = sv.ffmpeg_exe()
    m = story.add_story("P", "", "own", "", [(f"{i}.png", png((40 * i, 50, 90))) for i in range(1, 5)], "a a a.\n\nb b b.\n\nc c c.\n\nd d d.", root)
    panels = sv.panels_from_story(m, root)
    one = sv.estimate_seconds(panels[:1])
    res = sv.build_parts(panels, os.path.join(root, "o", "p"), one * 2.2, 1, "Hook", "Final", "vi", tts=_tts(ff), title="P", fps=10)
    assert [r["part"] for r in res] == [1, 2] and all(os.path.exists(r["video"]) for r in res)
    srt1 = open(res[0]["srt"], encoding="utf-8").read()
    srt2 = open(res[1]["srt"], encoding="utf-8").read()
    assert "Hook" in srt1 and "phần 2" in srt1 and "Hook" not in srt2 and "Final" in srt2


def test_thumbnail(root):
    pytest.importorskip("PIL")
    from PIL import Image
    img = os.path.join(root, "a.png"); open(img, "wb").write(png())
    out = sv.make_thumbnail(img, "cô gái và cánh cửa lúc nửa đêm", os.path.join(root, "t", "x.jpg"), badge="Part 1")
    assert Image.open(out).size == (1280, 720)
    out2 = sv.make_thumbnail(None, "", os.path.join(root, "t", "y.jpg"))
    assert os.path.exists(out2)


def test_recap_prompt_stats_chapters_and_kit():
    p = story.recap_prompt("Cô gái mở cửa.", 2, "vi", "review", 5)
    assert "about 312 words" in p and "exactly 5 numbered scenes" in p and "Cô gái mở cửa." in p and "YOUR TAKE" in p
    assert story.parse_recap("SCENE 1\nNARRATION: A.\nSCENE 2\nNARRATION: B.") == ["A.", "B."]
    assert story.parse_recap("one\n\ntwo") == ["one", "two"]
    st = story.script_stats("Câu " * 40 + "đây.")
    assert st["words"] == 41 and any("25 words" in w for w in st["warnings"]) and any("follow" in w.lower() for w in st["warnings"])
    assert story.script_stats("Bạn tin không? Theo dõi nhé.")["warnings"] == []
    marks = [{"t": 0, "label": "Hook"}, {"t": 4, "label": "too close"}, {"t": 15, "label": "B"}, {"t": 3700, "label": "C"}]
    assert story.chapters_text(marks).splitlines() == ["0:00 Hook", "0:15 B", "1:01:40 C"]
    assert story.chapters_text(marks[:2]) == ""
    kit = story.youtube_kit({"title": "T", "author": "A", "license": "cc-by", "source": ""}, "vi", 2, "Hook?", "fantasy", marks, "Song")
    assert "TITLE IDEAS" in kit and "Phần 2" in kit and "0:15 B" in kit and "Credit:" in kit and "PINNED COMMENT" in kit
    assert all(len(l) <= 72 for l in kit.splitlines() if l.startswith("- "))


# ---- story_tools
def _strip(heights=(300, 300, 300), gap=40):
    from PIL import Image, ImageDraw
    w = 200
    H = sum(heights) + gap * (len(heights) + 1)
    im = Image.new("RGB", (w, H), "white")
    d = ImageDraw.Draw(im)
    y = gap
    for k, h in enumerate(heights):
        for r in range(0, h, 6):  # noisy content so rows are not flat
            d.line([(0, y + r), (w, y + r)], fill=(30 + (r * 7 + k * 50) % 200, 80, 120 + r % 100), width=3)
        y += h + gap
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()

def test_split_strip_cuts_at_gutters():
    from utils import story_tools as st
    from PIL import Image
    parts = st.split_strip(_strip())
    assert len(parts) == 3
    assert all(abs(Image.open(io.BytesIO(p)).size[1] - 300) <= 12 for p in parts)

def test_split_strip_no_gutter_only_cut_by_height():
    from utils import story_tools as st
    from PIL import Image
    from PIL import ImageDraw
    im = Image.new("RGB", (100, 1000), "white"); d = ImageDraw.Draw(im)
    for r in range(0, 1000, 4):
        d.line([(0, r), (100, r)], fill=(r % 255, 10, 200), width=2)
    b = io.BytesIO(); im.save(b, "PNG")
    parts = st.split_strip(b.getvalue())
    assert len(parts) >= 5 and sum(Image.open(io.BytesIO(p)).size[1] for p in parts) == 1000

def test_split_many_names_keep_order():
    from utils import story_tools as st
    out = st.split_many([("10.png", _strip((300, 300))), ("2.png", _strip((300,)))])
    assert [n for n, _ in out] == ["001-001.png", "002-001.png", "002-002.png"]

def test_recap_prompt_and_roundtrip():
    from utils import story_tools as st
    p = st.recap_prompt(["Hello", ""], "My story", "en")
    assert "Panel 1: Hello" in p and "Panel 2: (no text" in p and "Be faithful" in p and "cliffhanger" not in p
    r = st.recap_prompt(["Hello", ""], "My story", "en", mode="recap")
    assert "cliffhanger" in r and "Be faithful" not in r
    zh = st.recap_prompt(["你看这样", "好的"], "", "vi")
    assert "Panel 1: 你看这样" in zh and "tiếng Việt" in zh
    assert "in Chinese" not in st.recap_prompt(["xin chào"], "", "vi")
    assert story.parse_script("Panel 1: a\nPanel 2: b", 2) == ["a", "b"]

def test_ocr_clean_and_missing_engine_message():
    from utils import story_tools as st
    assert st.clean_ocr("a   b\n\n\nc ") == "a b\nc"
    if not st.ocr_engine():
        with pytest.raises(RuntimeError):
            st.ocr_image(png())


def test_ask_llm_talks_to_the_app_endpoint():
    import json, threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from utils import story_tools as st
    seen = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = {"code": 200, "message": "Success", "data": {"content": "Panel 1: Xin chào"}} if "ok" in seen["body"]["content"] else {"code": -1, "message": "boom"}
            b = json.dumps(out).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def log_message(self, *a): pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/llm"
    assert st.ask_llm(url, "chatgpt", "ok please") == "Panel 1: Xin chào"
    assert seen["body"]["type"] == "chatgpt" and seen["body"]["content"] == "ok please"
    with pytest.raises(RuntimeError, match="boom"):
        st.ask_llm(url, "chatgpt", "bad")
    srv.shutdown()
    with pytest.raises(RuntimeError, match="Could not reach"):
        st.ask_llm("http://127.0.0.1:1/llm", "chatgpt", "x", timeout=2)


def test_write_narration_batches_context_retry_and_dash():
    import re
    from utils import story_tools as st
    calls = []

    def fake(prompt):
        calls.append(prompt)
        nums = [int(x) for x in re.findall(r"(?m)^Panel (\d+): ", prompt.split("--- PANEL TEXT ---")[1])]
        if len(calls) == 2:
            nums = nums[:-1]                      # the AI forgets the last panel of batch 2
        return "\n".join(f"**Panel {n}:** nói {n}" if n != 4 else f"- Panel {n} - -" for n in nums)
    out, miss = st.write_narration([f"t{i}" for i in range(10)], fake, "T", "vi", "dramatic", "faithful", "A = B", batch=4)
    assert out == ["nói 1", "nói 2", "nói 3", "", "nói 5", "nói 6", "nói 7", "nói 8", "nói 9", "nói 10"] and miss == []
    assert len(calls) == 4 and "A = B" in calls[0] and "Story so far" not in calls[0]
    assert "Panel 3: nói 3" in calls[1] and "Panel 5: t4" in calls[1].split("--- PANEL TEXT ---")[1]
    out2, miss2 = st.write_narration(["a", "b"], lambda p: "nothing useful", batch=8)
    assert out2 == ["", ""] and miss2 == [1, 2]


def test_polish_keeps_old_text_when_ai_skips_a_panel():
    from utils import story_tools as st
    out, kept = st.polish_narration(["một", "", "ba"], lambda p: "Panel 1: MỘT", st.POLISH["shorter"])
    assert out == ["MỘT", "", "ba"] and kept == [3]
    assert "Panel 1: một" in st.polish_prompt(["một"], "x") and "Panel 7: -" in st.polish_prompt(["-"], "x", start=7)
    assert st.parse_numbered("Panel 1: a\nb\n\nPanel 2. c\n- panel 3 - -") == {1: "a b", 2: "c", 3: ""}


# ---------------------------------------------------------------- direct AI + story writer
def _fake_openai(models=("qwen2.5:7b",), reply=lambda body: "Panel 1: ok"):
    import json, threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    seen = []

    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            b = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def do_GET(self):
            seen.append(("GET", self.path, self.headers.get("Authorization")))
            self._send(200, {"data": [{"id": m} for m in models]})
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append(("POST", self.path, body))
            if body["model"] == "missing":
                return self._send(404, {"error": "model not found"})
            self._send(200, {"choices": [{"message": {"content": reply(body)}}]})
        def log_message(self, *a): pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


def test_story_llm_direct_without_start_run():
    from utils import story_llm as L
    srv, seen = _fake_openai(reply=lambda b: "<think>plan</think>\n```\nPanel 1: Xin chào\n```")
    cfg = {"chat_type": "chatgpt", "openai": {"api": f"http://127.0.0.1:{srv.server_port}/v1", "api_key": ["k"]}, "chatgpt": {"model": "qwen2.5:7b"}}
    assert L.list_models(cfg) == ["qwen2.5:7b"] and seen[0][2] == "Bearer k"
    assert L.make_llm(cfg, temperature=0.3)("hi") == "Panel 1: Xin chào"
    assert seen[-1][2]["temperature"] == 0.3 and seen[-1][2]["model"] == "qwen2.5:7b" and seen[-1][2]["stream"] is False
    assert L.make_llm(cfg, model="other")("x") and seen[-1][2]["model"] == "other"
    with pytest.raises(RuntimeError, match="404"):
        L.chat(cfg, "x", model="missing")
    # another provider goes through the running app
    cfg2 = dict(cfg, chat_type="gemini")
    assert L.make_llm(cfg2, app_llm=lambda p: "<think>x</think>via app")("p") == "via app"
    srv.shutdown()
    with pytest.raises(RuntimeError, match="Cannot reach"):
        L.list_models({"openai": {"api": "http://127.0.0.1:1/v1"}}, timeout=2)


def test_parse_numbered_single_line_and_credit_cards():
    from utils import story_tools as st
    assert st.parse_numbered("Panel 1: Một. Panel 2: Hai. Panel 3: - Panel 4: Bốn") == {1: "Một.", 2: "Hai.", 3: "", 4: "Bốn"}
    assert st.looks_like_credits("Pháp Sư Mo DKKT: Chủ bút: Bốn Trực Thần Chi Assistant: Yusheng")
    assert st.looks_like_credits("出品 主笔 编剧") and not st.looks_like_credits("Cô ấy là writer giỏi nhất thành phố, ai cũng biết.")
    calls = []
    out, miss = st.write_narration(["Chủ bút: A Assistant: B", "Xin chào"], lambda p: calls.append(p) or "Panel 2: Hello", batch=8)
    assert out == ["", "Hello"] and miss == [] and "Chủ bút" not in calls[0].split("--- PANEL TEXT ---")[1]


def _line(k):
    """A panel text with unique words (no repeated openers / phrases) that names the hero."""
    return " ".join(f"tu{k}x{j}" if j != 5 else "Minh" for j in range(11))


def _scripted_writer(outline_answer="OK", audit_answer="OK"):
    """A fake writers' room that answers each stage in the format the prompts ask for."""
    import re
    log = []

    def llm(prompt):
        log.append(prompt)
        if prompt.startswith("You are a story editor at a hit"):
            return ("CONCEPT 1: Một thợ khóa muốn tìm em gái | TWIST: anh đã khóa em lại\nCONCEPT 2: Một cô lao công nghe tiếng gõ | TWIST: là chính cô\n"
                    "CONCEPT 3: Một đứa trẻ giữ chìa khóa của tòa nhà | TWIST: tòa nhà là một con tàu")
        if prompt.startswith("You are the editorial director"):
            return "Số 2 là mạnh nhất."
        if prompt.startswith("You are the head writer"):
            return ("TITLE: Cánh cửa lúc nửa đêm\nLOGLINE: Một thợ sửa khóa muốn tìm em gái nhưng cánh cửa đòi một ký ức.\n"
                    "HERO: Minh | 29 | gầy, áo khoác xanh, sẹo ở mày | hay nói dối | tìm em gái\nOTHER: Lan | chủ tiệm | tóc bạc | giữ chìa khóa\n"
                    "WORLD: Sài Gòn, mùa mưa.\nSTAKES: Em gái biến mất vĩnh viễn trước bình minh.\nSECRET: Minh mới là người đã khóa em gái lại.\n"
                    "CLUES: chìa khóa ấm; tiếng gõ ba nhịp; vết sơn mới\nMOTIF: tiếng gõ ba nhịp\nVOICE: Minh nhìn lại, khàn và thành thật\n"
                    "THEME: nỗi sợ quên đi lỗi lầm")
        if "Plan the story panel by panel" in prompt:
            return "\n".join(f"BEAT {n}: chuyện {n} xảy ra [clue 1]" for n in re.findall(r"(?m)^BEAT (.+?) \(panels", prompt))
        if prompt.startswith("You are a continuity editor. Read the story bible and the outline"):
            return outline_answer
        if prompt.startswith("You are a continuity editor. Read the finished narration"):
            return audit_answer
        if prompt.startswith("You are writing panels"):
            first, last = map(int, re.search(r"panels (\d+)-(\d+) of", prompt).groups())
            return "\n\n".join(f"PANEL {k}\nPICTURE: Minh áo xanh cảnh {k}\nNARRATION: nháp {k}." for k in range(first, last + 1))
        if "Edit like a sharp story editor" in prompt:
            return "\n".join(f"Panel {k}: {_line(k)}" for k in range(1, 40) if f"Panel {k}:" in prompt)
        if prompt.startswith("Rewrite ONE panel"):
            return "Panel 9: Minh đẩy cánh cửa, ngửi mùi sơn còn ướt và nhận ra mình đã đứng đúng chỗ này một lần."
        if "opening hook lines" in prompt:
            return "1. Cánh cửa mở lúc nửa đêm, và tôi nghe tiếng mình gọi.\n2. Tôi đã khóa em gái mình lại.\n3. Bạn sẽ đổi gì để quên một lỗi lầm?"
        if prompt.startswith("Story bible:") and "Pitch part 2" in prompt:
            return "Tiếng gõ không dừng. Minh phải mở cánh cửa cuối. Và Lan không phải người giữ chìa."
        if "Rewrite the whole outline" in prompt:
            return "\n".join(f"BEAT {n}: chuyện {n} đã sửa" for n in re.findall(r"(?m)^BEAT (.+?):", prompt.split("nothing else:")[1]))
        raise AssertionError(prompt[:80])
    return llm, log


def test_story_writer_pipeline():
    from utils import story_writer as w
    llm, log = _scripted_writer()
    steps = []
    temps = []
    res = w.write_story("thợ khóa tìm em gái", llm, "mystery", "scary", "vi", 10, progress=lambda a, b, m: steps.append((a, b, m)),
                        llm_for=lambda t: (temps.append(t), llm)[1])
    assert res["title"] == "Cánh cửa lúc nửa đêm" and len(res["plot"]) == 10 and res["missing"] == [] and res["polished"]
    assert res["chosen"].startswith("Một cô lao công") and len(res["concepts"]) == 3 and res["problems"] == [] and res["fixed"] == []
    assert all(p["picture"] and p["narration"] == _line(i) for i, p in enumerate(res["plot"], 1))
    assert len(res["hooks"]) == 3 and res["part2"].startswith("Tiếng gõ") and steps[0][2].startswith("Pitching") and steps[-1][2] == "Done"
    assert all(a <= b for a, b, _ in steps) and max(a for a, _, _ in steps[:-1]) < steps[0][1]
    assert min(temps) <= 0.2 and max(temps) >= 1.0                       # careful editing, wild idea stages
    writes = [p for p in log if p.startswith("You are writing panels")]
    assert len(writes) == 7 and "HOOK" in writes[0] and "no 'once upon a time'" in writes[0]
    assert "cliffhanger" in writes[-1] and "STORY BIBLE" in writes[1] and "nháp 1." in writes[1]               # continuity
    assert "Minh | 29" in writes[3] and "continue directly from the last panel" in writes[1] and "Keep the narrator's voice" in writes[1]
    assert "MOTIF: tiếng gõ ba nhịp" in writes[2] and "recurring" not in writes[1]
    bible_p = next(p for p in log if p.startswith("You are the head writer"))
    assert "lao công" in bible_p                                          # the picked concept feeds the bible


def test_story_writer_fixes_plot_holes_and_weak_panels():
    from utils import story_writer as w
    llm, log = _scripted_writer(outline_answer="PROBLEM: BEAT RISING - Minh biết chìa khóa ở đâu mà chưa ai nói.",
                                audit_answer="Panel 4: Lan xuất hiện mà chưa được giới thiệu\nPanel 99: bỏ qua")
    res = w.write_story("x", llm, "mystery", "scary", "vi", 8, polish=False)
    assert res["problems"] and "Minh biết chìa khóa" in res["problems"][0]
    assert any("Rewrite the whole outline" in p for p in log) and all("đã sửa" in o for o in res["outline"])
    # draft panels are 3 words -> flagged 'too short' by the local checks, the audit adds panel 4; each is rewritten once
    assert 4 in res["fixed"] and all(1 <= k <= 8 for k in res["fixed"])
    assert res["plot"][3]["narration"].startswith("Minh đẩy cánh cửa")
    assert sum(1 for p in log if p.startswith("Rewrite ONE panel")) == len(res["fixed"])
    llm2, log2 = _scripted_writer()
    res2 = w.write_story("x", llm2, panels=8, polish=True, check=False, concepts=False, hooks=False)
    assert not any(p.startswith(("You are a continuity", "Rewrite ONE", "You are a story editor")) for p in log2) and res2["fixed"] == []


def test_story_writer_retries_short_answers_and_survives_polish_failure():
    from utils import story_writer as w
    llm, log = _scripted_writer()

    def flaky(prompt):
        if prompt.startswith("You are writing panels") and "panels 4-6" in prompt and not any("panels 6-6" in p or "panels 5-6" in p for p in log):
            log.append(prompt)
            return "PANEL 4\nPICTURE: a\nNARRATION: chỉ một panel"
        if "Edit like a sharp story editor" in prompt:
            raise RuntimeError("model crashed")
        return llm(prompt)
    res = w.write_story("x", flaky, "fantasy", "dramatic", "vi", 12, check=False)
    assert len(res["plot"]) == 12 and res["missing"] == [] and not res["polished"]
    assert w.allocate(12) == w.allocate(12) and sum(c for *_, c in w.allocate(33)) == 33 and sum(c for *_, c in w.allocate(3)) == 7
    with pytest.raises(RuntimeError, match="story bible"):
        w.write_story("x", lambda p: "nonsense", panels=8)


def test_quality_report_flags_weak_panels_without_an_ai():
    from utils import story_writer as w
    bible = {"HERO": "Minh | 29 | gầy | nói dối | tìm em"}
    plot = [{"narration": n} for n in [
        "Minh mở cánh cửa gỗ cũ kỹ và nghe tiếng bản lề rít lên giữa căn nhà vắng lặng như tờ lúc nửa đêm.",
        "Minh bỗng nhiên nhớ ra định mệnh của mình đã được viết sẵn từ rất lâu trước khi anh biết đọc chữ.",
        "Ngắn quá.",
        "Minh " + " ".join(f"từ{j}" for j in range(80)),
        "Ánh đèn pin quét qua tường lộ ra vết sơn mới màu xanh rêu ở góc phòng phía sau tủ sách cũ kỹ ấy.",
        "Ánh trăng đổ xuống sân gạch rêu phong còn Minh thì đứng yên nghe nhịp tim mình đập từng hồi chậm rãi.",
        "Cô chủ tiệm gõ ba nhịp lên mặt bàn và nghe tiếng gõ ba nhịp lên mặt bàn vọng lại từ tầng hầm sâu.",
        "Tiếng gõ ba nhịp lên mặt bàn lại vang lên, lần này nhanh hơn, như thể ai đó dưới kia đang rất sốt ruột.",
        "Anh gõ ba nhịp lên mặt bàn để đáp lại, và cánh cửa tầng hầm hé ra một khe hẹp lạnh toát hơi nước.",
    ]]
    rep = w.quality_report(plot, bible, "vi")
    why = {(i["panel"], i["reason"].split(" ")[0]) for i in rep["issues"]}
    assert (3, "too") in why and (4, "too") in why and (6, "starts") in why          # short, long, repeated opener (Ánh / Ánh)
    assert any(i["panel"] == 2 and "cliche" in i["reason"] for i in rep["issues"])
    assert any(i["panel"] in (8, 9) and "repeats the phrase" in i["reason"] for i in rep["issues"])
    assert rep["stats"]["panels"] == 9
    few = [{"narration": "Cô ấy mở cửa bước vào căn phòng tối " + str(i) + " và đứng yên thật lâu nghe tiếng mưa."} for i in range(8)]
    assert any("hero Minh is hardly named" in i["reason"] for i in w.quality_report(few, bible, "vi")["issues"])
    assert not w.quality_report([{"narration": _line(i)} for i in range(1, 9)], bible)["issues"]


def test_story_writer_new_parsers():
    from utils import story_writer as w
    cs = w.parse_concepts("**CONCEPT 1:** Một thợ khóa muốn tìm em gái | TWIST: x\nconcept 2 - Một cô lao công nghe tiếng gõ | TWIST: y\nrác")
    assert len(cs) == 2 and cs[0].startswith("Một thợ khóa") and w.parse_pick("Số 2 là mạnh nhất", 3) == 1 and w.parse_pick("9", 3) == 0
    assert w.parse_problems("OK") == [] and w.parse_problems("ok.") == []
    assert w.parse_problems("PROBLEM: BEAT RISING - Minh biết chìa khóa ở đâu mà chưa ai nói.\nPROBLEM 2: stakes biến mất ở beat 5") != []
    assert w.parse_audit("OK", 5) == [] and w.parse_audit("Panel 2: tên đổi từ Lan sang Lam\nPanel 8: x", 5) == [
        {"panel": 2, "reason": "tên đổi từ Lan sang Lam"}]
    bible = w.parse_bible("TITLE: A\nHERO: Minh | 29\nCLUES: a; b; c\nMOTIF: m\nVOICE: v\nSTAKES: s")
    assert w.bible_text(bible).splitlines() == ["TITLE: A", "HERO: Minh | 29", "STAKES: s", "CLUES: a; b; c", "MOTIF: m", "VOICE: v"]
    assert w.hero_name(bible) == "Minh"


def test_story_writer_parsers():
    from utils import story_writer as w
    b = w.parse_bible("**TITLE:** A\n- LOGLINE: x\ny continues\nHERO: Minh | 29")
    assert b["TITLE"] == "A" and b["LOGLINE"] == "x y continues" and b["HERO"].startswith("Minh")
    plan = w.allocate(8)
    out = w.parse_outline("BEAT HOOK: một\nBEAT TWIST + CLIFFHANGER (panels 7-8): hai", plan)
    assert out[0] == "một" and out[-1] == "hai" and out[1] == plan[1][1]
    assert w.parse_hooks("1. Câu hook đầu tiên khá dài.\n2) Câu thứ hai cũng ổn.\nrác\n3: ngắn") == ["Câu hook đầu tiên khá dài.", "Câu thứ hai cũng ổn."]


def test_best_model_prefers_settings_then_biggest_chat_model():
    from utils.story_llm import best_model
    names = ["nomic-embed-text:latest", "llama3.2:3b", "qwen2.5:14b-instruct", "qwen2.5:7b", "llama3.1:70b"]
    assert best_model(names, "qwen2.5:7b") == "qwen2.5:7b"
    assert best_model(names, "gpt-3.5-turbo") == "qwen2.5:14b-instruct"
    assert best_model(["nomic-embed-text"], "") == "nomic-embed-text" and best_model([], "") == ""


@pytest.mark.skipif(not (sv.ffmpeg_exe() and sv.find_font()), reason="needs ffmpeg and a font")
def test_video_and_voice_stay_in_sync_over_many_pieces(root):
    """Many pieces with awkward lengths: the picture track and the voice track must end together (no drift) and match the planned length."""
    pytest.importorskip("PIL")
    ff = sv.ffmpeg_exe()
    text = "\n\n".join(f"Câu số {k} nói về một chuyện." for k in range(40))
    m = story.add_story("Sync", "", "own", "", [("1.png", png((200, 50, 50)))], text, root)
    lengths = [0.37, 0.61, 0.43, 0.88, 0.53]
    counter = {"n": 0}
    def tts(t, v, r, o):
        d = lengths[counter["n"] % len(lengths)]
        counter["n"] += 1
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=300:duration={d}", "-q:a", "5", o], check=True)
    out = os.path.join(root, "o", "sync.mp4")
    res = sv.build(sv.panels_from_story(m, root), out, tts=tts, title="S", size=(270, 480), tts_workers=3)

    def track_seconds(sel):
        p = subprocess.run([ff, "-i", out, "-map", sel, "-f", "null", "-"], capture_output=True, text=True)
        t = re.findall(r"time=(\d+):(\d+):([\d.]+)", p.stderr)[-1]
        return int(t[0]) * 3600 + int(t[1]) * 60 + float(t[2])
    v, a = track_seconds("0:v"), track_seconds("0:a")
    assert res["pieces"] >= 30
    assert abs(v - a) < 0.08, (v, a)
    assert abs(v - res["seconds"]) < 0.15, (v, res["seconds"])
