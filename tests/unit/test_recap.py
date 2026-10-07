import datetime as dt

from utils import recap as r

D = dt.date


def test_streak_and_week():
    files = ["session-20261005-100000.jsonl", "session-20261006-100000.jsonl", "session-20261007-090000.jsonl",
             "session-20260101-000000.jsonl", "junk.txt"]
    dates = r.session_dates(files)
    assert len(dates) == 4
    assert r.streak(dates, D(2026, 10, 7)) == 3
    assert r.streak(dates, D(2026, 10, 8)) == 3   # yesterday still counts
    assert r.streak(dates, D(2026, 10, 9)) == 0
    assert r.week_count(dates, D(2026, 10, 7)) == 3


def test_recap_tips():
    s = {"comments": 20, "unique_viewers": 9, "buy_intent": 5, "duration_min": 30, "blocked": 2,
         "blocked_by_category": {"phone": 2},
         "product_interest": {"a": {"price": 4, "stock": 1}, "b": {"trust": 1}, "c": {"price": 1}}}
    out = r.recap(s, {"a": "Serum"})
    joined = " ".join(out["tips"])
    assert "Serum" in joined and "price" in joined.lower()
    assert len(out["tips"]) <= 4 and "20 comments" in out["headline"]


def test_quiet_session():
    out = r.recap({"comments": 0, "unique_viewers": 0, "buy_intent": 0, "duration_min": 5})
    assert "flash sale" in out["tips"][0].lower()
