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
