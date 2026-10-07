from utils import moments, preflight


def ev(t, kind="comment", **kw):
    return dict(ts=1000 + t, kind=kind, **kw)


def test_busiest_minute_ranks_first_and_ignores_quiet():
    events = [ev(0, text="hi")]
    events += [ev(125 + i, text=f"c{i}") for i in range(6)]                 # minute 2: busy
    events += [ev(125, "gift", num=2), ev(130, text="chốt đơn", intent="buy")]
    events += [ev(300, text="late")]                                          # quiet
    out = moments.best_moments(events)
    assert out[0]["at"] == "2:00" and out[0]["gifts"] == 2 and out[0]["buy"] == 1
    assert out[0]["sample"] == "chốt đơn"
    assert all(m["at"] != "5:00" for m in out)


def test_empty_and_text_list():
    assert moments.best_moments([]) == []
    t = moments.as_text([{"at": "1:05", "offset_s": 65, "comments": 4, "gifts": 1, "buy": 2, "score": 12, "sample": "ship hn?"}])
    assert t == '1:05  4 comments, 2 buying signals, 1 gifts  "ship hn?"'


def test_clock_hours():
    assert moments._clock(3725) == "1:02:05"


def test_preflight_flags_and_summary():
    rows = preflight.run({"tiktok_username": "", "api_ok": False, "mode": "seller", "product_count": 0,
                          "bridge_on": False, "engine": "vieneu", "voice_ok": False})
    bad = {r["id"] for r in rows if r["ok"] is False}
    assert {"account", "app", "voice", "products", "bridge"} <= bad
    assert all(r["fix"] for r in rows if r["ok"] is False)
    assert "5 things" in preflight.summary(rows)


def test_preflight_creator_skips_products_and_all_clear():
    rows = preflight.run({"tiktok_username": "shop", "api_ok": True, "mode": "creator", "bridge_on": True})
    assert not any(r["id"] == "products" for r in rows)
    assert preflight.summary(rows).startswith("All clear")


def test_price_headsup():
    rows = preflight.run({"tiktok_username": "s", "api_ok": True, "bridge_on": True, "product_count": 2, "no_price": 1})
    assert [r["ok"] for r in rows if r["id"] == "prices"] == [None]
    assert preflight.summary(rows).startswith("Ready.")
