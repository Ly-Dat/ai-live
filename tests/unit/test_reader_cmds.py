from utils import reader_cmds as rc


def test_parse():
    assert rc.parse("!tiếp") == "next" and rc.parse("!Lại") == "repeat" and rc.parse("!trước") == "prev" and rc.parse("! next") == "next"
    assert rc.parse("tiếp") is None and rc.parse("!hello") is None and rc.parse("!" + "x" * 40) is None


def test_commands_need_several_distinct_viewers(tmp_path):
    p = str(tmp_path / "c.json")
    assert rc.consume(p, "a", "!tiep", now=100) is False          # reader not running: comments are left alone
    rc.heartbeat(p, True, threshold=3, window=30, now=100)
    assert rc.consume(p, "a", "!tiep", now=101) is True
    assert rc.consume(p, "a", "!tiep", now=102) is True           # same viewer twice does not count twice
    assert rc.pop_pending(p) is None
    rc.consume(p, "b", "!tiếp", now=103)
    assert rc.pop_pending(p) is None
    rc.consume(p, "c", "!next", now=104)
    assert rc.pop_pending(p) == "next" and rc.pop_pending(p) is None


def test_old_votes_expire_and_stale_reader_is_ignored(tmp_path):
    p = str(tmp_path / "c.json")
    rc.heartbeat(p, True, threshold=2, window=30, now=100)
    rc.consume(p, "a", "!lai", now=101)
    rc.consume(p, "b", "!lai", now=140)                           # a's vote is 39 s old
    assert rc.pop_pending(p) is None
    assert rc.consume(p, "c", "!lai", now=100 + rc.ALIVE_S + 50) is False


def test_chapter_vote(tmp_path):
    p = str(tmp_path / "c.json")
    rc.heartbeat(p, True, now=100)
    rc.begin_vote(p, 20, now=100)
    assert rc.consume(p, "a", "1", now=101) and rc.consume(p, "b", "2", now=102) and rc.consume(p, "c", "2", now=103)
    rc.consume(p, "b", "1", now=104)                              # a viewer can change their mind, still one ballot
    assert rc.consume(p, "d", "3", now=105) is False              # not an option -> normal comment
    r = rc.end_vote(p)
    assert r == {"next": 2, "repeat": 1, "winner": "next"}
    rc.begin_vote(p, 20, now=200)
    assert rc.end_vote(p)["winner"] == "next"                      # no votes: continue
    assert rc.consume(p, "a", "1", now=300) is False             # vote closed


def test_digits_are_not_swallowed_without_a_vote(tmp_path):
    p = str(tmp_path / "c.json")
    rc.heartbeat(p, True, now=100)
    assert rc.consume(p, "a", "1", now=101) is False
