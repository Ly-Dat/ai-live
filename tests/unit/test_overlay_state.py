from utils import overlay_state as ov, engage

NOW = 1000.0


def test_poll_counts_and_percent():
    st = {"giveaway": None, "poll": None}
    engage.start_poll(st, "Mau nao dep hon?", ["Den", "Trang"], 3, now=NOW)
    engage.consume(st, "a", "1", NOW + 1); engage.consume(st, "b", "1", NOW + 2); engage.consume(st, "c", "2", NOW + 3)
    item = ov.build(st, None, now=NOW + 10)["items"][0]
    assert item["total"] == 3 and item["left"] == 170
    assert [(o["count"], o["pct"]) for o in item["options"]] == [(2, 67), (1, 33)]


def test_giveaway_entries_and_unsafe_winner_hidden():
    st = {"giveaway": None, "poll": None}
    engage.start_giveaway(st, "tham gia", "tui", 5, now=NOW)
    engage.consume(st, "An", "tham gia", NOW + 1)
    assert ov.build(st, None, now=NOW + 2)["items"][0]["entries"] == 1
    g = st["giveaway"]; g.update(active=False, drawn=True, winners=["An", "bad word"])
    out = ov.build(st, None, now=g["ends_at"] + 5, safe=lambda s: s != "bad word")["items"][0]
    assert out["winners"] == ["An"] and out["left"] == 0
    assert ov.build(st, None, now=g["ends_at"] + 500)["items"] == []   # fades away


def test_flash_sale_only_while_active():
    fl = {"active": True, "ends_at": NOW + 120, "sale_price": "99k", "stock_left": 5}
    it = ov.build({}, fl, "Ao thun", NOW)["items"][0]
    assert it == {"kind": "flash", "product": "Ao thun", "price": "99k", "stock": 5, "left": 120}
    assert ov.build({}, fl, "x", NOW + 200)["items"] == []
    assert ov.build({}, None, "", NOW)["items"] == []
