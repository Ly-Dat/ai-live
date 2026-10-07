import datetime as dt
import pytest
from utils import coverage as cv

CFG = {"enabled": True, "human_windows": [{"days": [0, 1, 2, 3, 4], "start": "19:00", "end": "23:00"}]}
MON = dt.datetime(2026, 10, 5)          # a Monday


def at(day, h, m=0):
    return MON + dt.timedelta(days=day, hours=h, minutes=m)


def test_inside_and_outside_window():
    assert cv.is_human(CFG, at(0, 20)) and not cv.is_human(CFG, at(0, 18, 59))
    assert not cv.is_human(CFG, at(0, 23)) and cv.is_human(CFG, at(0, 22, 59))
    assert not cv.is_human(CFG, at(5, 20))                      # Saturday not selected


def test_disabled_means_ai_always():
    assert not cv.is_human(dict(CFG, enabled=False), at(0, 20))


def test_window_crossing_midnight():
    cfg = {"enabled": True, "human_windows": [{"days": [4], "start": "22:00", "end": "02:00"}]}   # Friday night
    assert cv.is_human(cfg, at(4, 23)) and cv.is_human(cfg, at(5, 1))        # Fri 23:00 and Sat 01:00
    assert not cv.is_human(cfg, at(5, 2)) and not cv.is_human(cfg, at(4, 21))
    assert not cv.is_human(cfg, at(6, 1))                                    # Sunday 01:00: Saturday not selected


def test_status_until():
    s = cv.status(CFG, at(0, 20))
    assert s == {"who": "human", "until": "23:00", "day_offset": 0}
    s = cv.status(CFG, at(0, 23, 30))
    assert s["who"] == "ai" and s["until"] == "19:00" and s["day_offset"] == 1
    assert cv.status({"enabled": False, "human_windows": []}, at(0, 20))["until"] is None


def test_validation_and_roundtrip(tmp_path):
    with pytest.raises(ValueError):
        cv.clean_window({"days": [], "start": "19:00", "end": "20:00"})
    with pytest.raises(ValueError):
        cv.clean_window({"days": [1], "start": "7pm", "end": "20:00"})
    with pytest.raises(ValueError):
        cv.clean_window({"days": [1], "start": "19:00", "end": "19:00"})
    p = str(tmp_path / "c.json")
    cv.save(CFG, p)
    assert cv.load(p) == CFG and cv.load(str(tmp_path / "none.json"))["enabled"] is False
    assert cv.describe(CFG["human_windows"][0]) == "Mon, Tue, Wed, Thu, Fri 19:00-23:00"


def test_handoff_questions_newest_first():
    ev = [{"kind": "handoff", "text": "a", "ts": 1}, {"kind": "comment", "text": "x", "ts": 2}, {"kind": "handoff", "text": "b", "ts": 3}]
    assert [q["text"] for q in cv.handoff_questions(ev)] == ["b", "a"]
