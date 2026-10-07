from utils import sales


def test_first_sight_is_baseline_not_a_shoutout():
    w = sales.SalesWatcher()
    assert w.update("p1", "Đã bán 120", 120, 1000) is None


def test_announces_real_gain_only():
    w = sales.SalesWatcher()
    w.update("p1", "Sold 100", 100, 1000)
    assert w.update("p1", "Sold 103", 103, 1010, step=5) is None
    assert w.update("p1", "Sold 108", 108, 1020, step=5, cooldown=60) == 8


def test_cooldown_keeps_gain_for_later():
    w = sales.SalesWatcher()
    w.update("p1", "Sold 10", 10, 0)
    assert w.update("p1", "Sold 20", 20, 10, step=5, cooldown=120) == 10
    assert w.update("p1", "Sold 30", 30, 20, step=5, cooldown=120) is None
    assert w.update("p1", "Sold 31", 31, 200, step=5, cooldown=120) == 11


def test_ignores_non_sold_tags_and_resets():
    w = sales.SalesWatcher()
    assert w.update("p1", "Free ship", 50, 0) is None
    w.update("p1", "Sold 50", 50, 0)
    assert w.update("p1", "Sold 2", 2, 500) is None
    assert w.update("p1", "Sold 9", 9, 900, step=5) == 7


def test_settings_roundtrip_and_defaults(tmp_path):
    p = str(tmp_path / "s.json")
    assert sales.load_settings(p)["enable"] is False
    sales.save_settings({"enable": True, "step": 3, "cooldown": 90}, p)
    s = sales.load_settings(p)
    assert s == {"enable": True, "step": 3, "cooldown": 90}
