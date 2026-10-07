import datetime

from utils import habit


def _ts(h, day=1):
    return datetime.datetime(2026, 10, day, h, 0).timestamp()


def test_weekly_progress():
    today = datetime.date(2026, 10, 8)
    dates = {today, today - datetime.timedelta(days=2), today - datetime.timedelta(days=30)}
    p = habit.weekly_progress(dates, today, 3)
    assert p["done"] == 2 and p["left"] == 1 and not p["hit"]
    assert habit.weekly_progress(dates, today, 2)["hit"]
    assert habit.weekly_progress(dates, today, 99)["goal"] == 7


def test_best_hour_needs_data_and_a_real_difference():
    few = [{"started_at": _ts(20), "comments": 100, "duration_min": 30}] * 2
    assert habit.best_hour(few) is None
    flat = [{"started_at": _ts(h, d), "comments": 30, "duration_min": 30} for d, h in [(1, 10), (2, 20), (3, 10)]]
    assert habit.best_hour(flat) is None
    real = [{"started_at": _ts(20, 1), "comments": 120, "duration_min": 30},
            {"started_at": _ts(20, 2), "comments": 100, "duration_min": 30},
            {"started_at": _ts(9, 3), "comments": 20, "duration_min": 30}]
    b = habit.best_hour(real)
    assert b["hour"] == 20 and b["rate"] > b["overall"] and b["n"] == 3


def test_tasks_and_plan_reset(tmp_path):
    p = str(tmp_path / "plan.json")
    tasks = habit.next_live_tasks(["Say the price first.", "Add shipping."])
    habit.save_plan(p, "session-A", [tasks[0]["id"]])
    done = habit.load_plan(p, "session-A")
    t2 = habit.next_live_tasks(["Say the price first.", "Add shipping."], done)
    assert [t["done"] for t in t2] == [True, False]
    assert habit.load_plan(p, "session-B") == set()   # a new session starts a fresh list


def test_recap_actions_exclude_info_only_tips():
    from utils import recap
    r = recap.recap({"comments": 10, "blocked": 4, "blocked_by_category": {"off_platform_contact": 4}, "product_interest": {}})
    assert any("Nothing to do" in t for t in r["tips"])
    assert all("Nothing to do" not in t for t in r["actions"])
