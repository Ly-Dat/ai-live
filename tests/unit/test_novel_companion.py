import datetime
import os
import tempfile
import time

import pytest

from utils import novel, novel_companion as nc, reader_cmds as rc

CH1 = "Chương 1\n" + "\n".join(["Lan sống ở làng Thủy cùng bà nội. Lan nói: “Con sẽ đi tìm cha.”"] * 6)
CH2 = "Chương 2\n" + "\n".join(["Nam gặp Lan ở bến sông. Nam đáp: “Ta cùng đi.” Họ tìm thấy thanh kiếm cổ."] * 6)
CH3 = "Chương 3\n" + "\n".join(["Kẻ phản bội là thầy Quân, ông giấu chiếc chìa khóa vàng trong hang."] * 6)
CH4 = "Chương 4\n" + "\n".join(["Cuối cùng Lan trở thành vua của Hắc Thành."] * 6)


@pytest.fixture
def book(tmp_path):
    root = str(tmp_path / "novels")
    meta = novel.add_book("Truyen", "A", "own", "", "\n".join([CH1, CH2, CH3, CH4]), root)
    return meta, root, str(tmp_path / "sum.json")


def test_spoiler_shield_never_returns_later_text(book):
    meta, root, _ = book
    assert len(meta["chapters"]) == 4
    ps = nc.book_passages(meta, 1, None, root)
    text = " ".join(p["text"] for p in ps)
    assert "Nam gặp Lan" in text and "thầy Quân" not in text and "vua" not in text
    mid = nc.book_passages(meta, 2, 0, root)                       # only the first line of chapter 3
    assert {p["chapter"] for p in mid} == {0, 1, 2} and "vua" not in " ".join(p["text"] for p in mid)


def test_retrieve_picks_matching_passages():
    ps = [{"chapter": 0, "text": "Trời mưa to ở làng"}, {"chapter": 1, "text": "Thanh kiếm cổ nằm dưới đáy sông"}, {"chapter": 2, "text": "Bà nội nấu cơm"}]
    assert nc.retrieve(ps, "Thanh kiếm ở đâu?", 1)[0]["chapter"] == 1
    assert nc.retrieve(ps, "", 2) == ps[-2:]


def test_ask_uses_only_read_text_and_cleans_answer(book):
    meta, root, sp = book
    seen = []
    ans = nc.ask(meta, "Ai là kẻ phản bội?", 1, None, lambda p: (seen.append(p), "**Chưa** rõ.")[1], "vi", root, sp)
    assert ans == "Chưa rõ." and "thầy Quân" not in seen[0] and "Hắc Thành" not in seen[0] and "spoiler" in seen[0]


def test_viewer_answer_filters(book):
    meta, root, sp = book
    llm = lambda p: "Lan là cô gái ở làng Thủy."
    out = nc.viewer_answer(meta, "An<>", "Lan là ai?", 1, None, llm, None, "vi", root, sp)
    assert out.startswith("An hỏi: Lan là ai?") and "làng Thủy" in out
    assert nc.viewer_answer(meta, "x", "Lan là ai?", 1, None, llm, lambda t, s: s == "output", "vi", root, sp) == ""
    assert nc.viewer_answer(meta, "x", "bad question", 1, None, llm, lambda t, s: s == "input", "vi", root, sp) == ""
    def boom(p): raise RuntimeError("down")
    assert nc.viewer_answer(meta, "x", "Lan là ai?", 1, None, boom, None, "vi", root, sp) == ""


def test_summaries_cached_and_recap(book):
    meta, root, sp = book
    calls = []
    def llm(p):
        calls.append(p)
        return "Recap text." if "previously" in p else "Tóm tắt chương."
    r = nc.previously_on(meta, 3, llm, "vi", root, sp, last=2)
    assert r == "Recap text." and len(calls) == 3                      # 2 summaries + 1 recap
    n = len(calls)
    nc.previously_on(meta, 3, llm, "vi", root, sp, last=2)
    assert len(calls) == n + 1                                         # summaries came from the cache
    assert nc.previously_on(meta, 0, llm, "vi", root, sp) == ""
    assert set(nc.load_summaries(sp)[meta["id"]]) == {"1", "2"}


def test_summary_cancel(book):
    meta, root, sp = book
    with pytest.raises(RuntimeError):
        nc.summarize_chapters(meta, 2, lambda p: "x", "vi", root, sp, cancel=lambda: True)


def test_characters(book):
    meta, root, _ = book
    out = "Lan | nhân vật chính | gan dạ, hiếu thảo | cháu bà nội\nNam | bạn đồng hành | trầm tĩnh | đi cùng Lan\nGhost | x | y | z"
    cards = nc.character_cards(meta, 1, None, lambda p: out, "vi", root, names=["Lan", "Nam"])
    assert [c["name"] for c in cards] == ["Lan", "Nam"] and cards[0]["traits"].startswith("gan")
    assert nc.parse_characters("no pipes here") == []


def test_stats_and_streak(tmp_path):
    p = str(tmp_path / "st.json")
    day = lambda d: time.mktime((datetime.date(2026, 10, 1) + datetime.timedelta(days=d)).timetuple()) + 3600
    for d in (0, 1, 2, 4, 5):
        nc.record_stats(600, 1, p, day(d))
    nc.record_stats(60, 0, p, day(5))
    s = nc.stats_summary(p, day(5))
    assert s["streak"] == 2 and s["best_streak"] == 3 and s["chapters"] == 5 and s["today_min"] == 11.0 and s["total_min"] == 51.0
    assert nc.stats_summary(p, day(7))["streak"] == 0                  # two days off breaks it
    assert nc.stats_summary(p, day(6))["streak"] == 2                  # not yet listened today: yesterday still counts


def test_ask_command_queue_and_limits(tmp_path):
    p = str(tmp_path / "c.json")
    rc.heartbeat(p, True, ask=False, now=100)
    assert rc.consume(p, "a", "!hoi Lan là ai?", now=101) is False       # asking disabled: left to the normal AI reply
    rc.heartbeat(p, True, ask=True, now=100)
    assert rc.consume(p, "a", "!hỏi Lan là ai?", now=101) is True
    assert rc.consume(p, "a", "!hoi câu khác nữa nhé", now=110) is True    # cooldown: swallowed but not queued
    rc.consume(p, "b", "!ask Why did he leave?", now=111)
    rc.consume(p, "c", "!hoi ab", now=112)                                 # too short: swallowed, not queued
    rc.consume(p, "d", "!hoi " + "x" * 200, now=113)                       # too long
    rc.consume(p, "e", "!hoi who is the king?", now=114)
    rc.consume(p, "f", "!hoi fourth question here", now=115)               # queue is full (3)
    got = [rc.pop_ask(p) for _ in range(4)]
    assert [g["q"] for g in got[:3]] == ["Lan là ai?", "Why did he leave?", "who is the king?"] and got[3] is None
    rc.heartbeat(p, True, ask=True, now=199)
    assert rc.consume(p, "a", "!hoi sau 45 giây thì được", now=200) is True and rc.pop_ask(p)["user"] == "a"
    rc.heartbeat(p, True, ask=True, now=299)
    assert rc.consume(p, "a", "hello there", now=300) is False
    assert rc.parse_ask("!hoi") == "" and rc.parse_ask("hello") is None and rc.parse_ask("!tiep") is None
