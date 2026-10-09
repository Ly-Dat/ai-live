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
    assert "The text is in Chinese: translate it into Vietnamese" in zh and "Do NOT summarise" in zh
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
