import random

import pytest

from utils import engage


def _g(now=1000, **kw):
    s = {"giveaway": None, "poll": None}
    return engage.start_giveaway(s, kw.get("keyword", "tham gia"), "áo thun", 10, kw.get("winners", 1), now=now)


def test_entry_rules():
    s = _g()
    assert engage.consume(s, "Lan", "Tham gia ạ!", now=1001) == "giveaway"
    assert engage.consume(s, "lan", "tham gia", now=1002) == "giveaway"     # same viewer, still one entry
    assert engage.consume(s, "Minh", "tham gia", now=1003) == "giveaway"
    assert engage.consume(s, "Hoa", "không tham gia đâu", now=1004) == "giveaway"   # whole phrase present
    assert engage.consume(s, "Tú", "áo đẹp quá", now=1005) is None
    assert len(s["giveaway"]["entrants"]) == 3
    assert engage.consume(s, "Late", "tham gia", now=1000 + 11 * 60) is None   # after the end


def test_announcement_flow_and_fair_draw():
    s = _g(winners=2)
    for i, n in enumerate(["A", "B", "C", "D"]):
        engage.consume(s, n, "tham gia", now=1001 + i)
    t, s = engage.next_announcement(s, now=1010)
    assert "tham gia" in t and "áo thun" in t and "10 phút" in t
    assert engage.next_announcement(s, now=1011)[0] is None                    # nothing twice
    t, s = engage.next_announcement(s, now=1010 + 200)
    assert "4 bạn" in t                                                          # reminder says how many entered
    t, s = engage.next_announcement(s, now=1000 + 570)
    assert "một phút" in t
    t, s = engage.next_announcement(s, now=1000 + 601, rng=random.Random(3))
    g = s["giveaway"]
    assert g["drawn"] and not g["active"] and len(g["winners"]) == 2 and set(g["winners"]) <= {"A", "B", "C", "D"}
    assert "4 bạn" in t and all(w in t for w in g["winners"])
    assert engage.next_announcement(s, now=1000 + 700)[0] is None              # drawn once only


def test_no_entrants_no_winner():
    s = _g()
    engage.next_announcement(s, now=1001)
    t, s = engage.next_announcement(s, now=1000 + 601)
    assert "Chưa có bạn nào" in t and s["giveaway"]["winners"] == []


def test_draw_is_uniform_enough():
    wins = {n: 0 for n in "ABCD"}
    for seed in range(400):
        s = _g()
        for n in "ABCD":
            engage.consume(s, n, "tham gia", now=1001)
        engage.next_announcement(s, now=1001)
        engage.next_announcement(s, now=1000 + 601, rng=random.Random(seed))
        wins[s["giveaway"]["winners"][0]] += 1
    assert all(60 < c < 140 for c in wins.values())


def test_poll_votes_tally_and_result():
    s = {"giveaway": None, "poll": None}
    engage.start_poll(s, "Áo màu nào?", ["Đen", "Trắng"], 5, now=1000)
    assert engage.consume(s, "A", "1", now=1001) == "poll"
    assert engage.consume(s, "A", "2", now=1002) == "poll"                       # a second vote does not change it
    assert engage.consume(s, "B", "chọn 2", now=1003) == "poll"
    assert engage.consume(s, "C", "2", now=1004) == "poll"
    assert engage.consume(s, "D", "3", now=1005) is None                          # no option 3
    assert engage.consume(s, "E", "mình thích 2 hơn", now=1006) is None           # only a bare number counts
    assert engage.tally(s["poll"]) == [1, 2]
    t, s = engage.next_announcement(s, now=1010)
    assert "1 là Đen" in t and "2 là Trắng" in t
    t, s = engage.next_announcement(s, now=1000 + 301)
    assert "Trắng 2 phiếu" in t and "nhiều nhất là Trắng" in t


def test_poll_tie_and_empty():
    s = {"giveaway": None, "poll": None}
    engage.start_poll(s, "Q?", ["X", "Y"], 1, now=0)
    engage.next_announcement(s, now=1)
    t, s = engage.next_announcement(s, now=61)
    assert "Chưa có bạn nào bình chọn" in t
    s2 = {"giveaway": None, "poll": None}
    engage.start_poll(s2, "Q?", ["X", "Y"], 1, now=0)
    engage.consume(s2, "a", "1", now=1); engage.consume(s2, "b", "2", now=1)
    engage.next_announcement(s2, now=1)
    assert "bằng nhau" in engage.next_announcement(s2, now=61)[0]


def test_validation_and_file(tmp_path):
    s = {"giveaway": None, "poll": None}
    with pytest.raises(ValueError):
        engage.start_giveaway(s, "", "prize", 5)
    with pytest.raises(ValueError):
        engage.start_poll(s, "Q", ["only one"], 5)
    p = str(tmp_path / "e.json")
    engage.start_giveaway(s, "1", "mũ", 5, now=0)
    engage.save_state(s, p)
    assert engage.load_state(p)["giveaway"]["prize"] == "mũ"
    assert engage.load_state(str(tmp_path / "none.json")) == {"giveaway": None, "poll": None}
    engage.stop(s, "giveaway")
    assert not s["giveaway"]["active"]
