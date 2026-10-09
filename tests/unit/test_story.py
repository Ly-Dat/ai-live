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
    assert "Panel 1: Hello" in p and "Panel 2: (no text" in p and "cliffhanger" in p
    assert story.parse_script("Panel 1: a\nPanel 2: b", 2) == ["a", "b"]

def test_ocr_clean_and_missing_engine_message():
    from utils import story_tools as st
    assert st.clean_ocr("a   b\n\n\nc ") == "a b\nc"
    if not st.ocr_engine():
        with pytest.raises(RuntimeError):
            st.ocr_image(png())
