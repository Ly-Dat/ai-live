import os, shutil, tempfile
import pytest
from utils import novel

TEXT = ("Chương 1\nLan nói: “Mình đi thôi.” Nam đáp: “Ừ, đi.”\n\n— Trời mưa rồi — Lan nói.\n— Ừ — Nam đáp.\n\nLan nói khẽ về chuyện hôm qua. Nam hỏi lại: “Thật sao?”\n"
        "Chương 2\nMark said, “We should go.” Anna replied, “Not yet.” The wind rose. said Mark again. " * 3)

def test_detect_characters():
    names = novel.detect_characters(TEXT)
    assert "Lan" in names and "Nam" in names
    assert "Anh" not in novel.detect_characters("Anh nói gì. Anh nói nữa. Anh hỏi.")

def test_find_speaker_and_chunks_carry_speaker():
    cs = novel.chunks("Lan nói: “Mình đi thôi.” Nam đáp: “Ừ, đi.”", 180, None, ["Lan", "Nam"])
    d = [(c["speaker"], c["text"]) for c in cs if c["role"] == "dialogue"]
    assert ("Lan", "Mình đi thôi.") in d
    assert novel.find_speaker("Nam đáp khẽ", ["Lan", "Nam"]) == "Nam"
    assert novel.find_speaker("không ai cả", ["Lan"]) == ""

def test_chunks_without_characters_still_work():
    cs = novel.chunks("Trời mưa. “Anh đi đâu?” cô hỏi.", 180)
    assert all("speaker" in c for c in cs) and {c["role"] for c in cs} == {"narrator", "dialogue"}

def test_minutes_format():
    assert novel.fmt_minutes(0.2) == "1 min" and novel.fmt_minutes(135) == "2 h 15 min"

@pytest.fixture
def book():
    root = tempfile.mkdtemp()
    m = novel.add_book("S", "A", "own", "", TEXT * 2, root)
    yield m, root
    shutil.rmtree(root, ignore_errors=True)

def test_search_and_minutes(book):
    m, root = book
    r = novel.search(m, "trời mưa", root=root)
    assert r and r[0]["chapter"] >= 0 and "mưa" in r[0]["text"].lower()
    assert novel.search(m, "z", root=root) == []
    assert novel.book_minutes(m) > 0

def test_bookmarks(tmp_path):
    p = str(tmp_path / "b.json")
    novel.add_bookmark("x", 2, 5, "đoạn hay", p)
    novel.add_bookmark("x", 3, 0, "", p)
    assert [b["chapter"] for b in novel.list_bookmarks("x", p)] == [2, 3]
    novel.delete_bookmark("x", 0, p)
    assert novel.list_bookmarks("x", p)[0]["chapter"] == 3
    assert novel.list_bookmarks("nope", p) == []


def test_two_speakers_in_one_paragraph():
    cs = novel.chunks("Lan nói: “Mình đi thôi.” Nam đáp: “Ừ, đi.”", 180, None, ["Lan", "Nam"])
    assert [(c["speaker"], c["text"]) for c in cs if c["role"] == "dialogue"] == [("Lan", "Mình đi thôi."), ("Nam", "Ừ, đi.")]
    cs = novel.chunks("“Go,” Anna said. “No,” said Mark.", 180, None, ["Anna", "Mark"])
    assert [c["speaker"] for c in cs if c["role"] == "dialogue"] == ["Anna", "Mark"]
    cs = novel.chunks("— Trời mưa rồi — Lan nói.", 180, None, ["Lan"])
    assert [c["speaker"] for c in cs if c["role"] == "dialogue"] == ["Lan"]


def test_voice_for_and_recap(book):
    s = {"voice_narrator": "N", "voice_dialogue": "D", "characters": {"Lan": "L"}}
    assert novel.voice_for({"role": "narrator"}, s) == "N"
    assert novel.voice_for({"role": "dialogue", "speaker": "Lan"}, s) == "L"
    assert novel.voice_for({"role": "dialogue", "speaker": "Zed"}, s) == "D"
    assert novel.voice_for({"role": "dialogue"}, {"voice_narrator": "N"}) == "N"
    m, root = book
    assert novel.recap_text(m, 0, root) == ""
    if len(m["chapters"]) > 1:
        assert novel.recap_text(m, 1, root).startswith("Ở chương trước: ")


def test_overlay_novel_style():
    import time
    st = {"state": "playing", "updated": time.time(), "text": "x"}
    o = novel.overlay_novel(st, {"show_text": True, "overlay_size": "l", "overlay_theme": "sepia"}, time.time())
    assert o["size"] == "l" and o["theme"] == "sepia"
    o = novel.overlay_novel(st, {"show_text": True, "overlay_size": "huge", "overlay_theme": "x"}, time.time())
    assert o["size"] == "m" and o["theme"] == "dark"


def test_audiobook_with_fake_tts(book, tmp_path):
    import subprocess
    from utils import novel_audio, story_video
    ff = story_video.ffmpeg_exe()
    if not ff:
        pytest.skip("no ffmpeg")
    m, root = book
    used = []
    def tts(t, v, r, o):
        used.append(v)
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=0.3", "-c:a", "libmp3lame", o], check=True)
    out = str(tmp_path / "a.mp3")
    res = novel_audio.build(m, [0], out, {"voice_narrator": "N", "voice_dialogue": "D", "characters": {"Lan": "L", "Nam": "M"}, "rate": 0},
                            tts=tts, root=root)
    assert os.path.getsize(out) > 500 and res["pieces"] == len(used) and res["timestamps"].startswith("0:00 ")
    assert "L" in used and "M" in used and "N" in used
