from utils import avatar_gestures as ag, lang_policy as lp, pitch_pacing as pp, playbooks as pb, replay


def _c(ts, pid="P1", intent="chat"):
    return {"kind": "comment", "ts": ts, "product_id": pid, "intent": intent}


def test_pacing_extends_on_buy_signals_and_never_touches_manual():
    ev = [_c(900, intent="price"), _c(950, intent="buy"), _c(990)]
    s = pp.signals(ev, 1000, "P1")
    assert s["buy"] == 2 and pp.adjust_minutes(6, s) == 9.6
    assert pp.adjust_minutes(6, s, manual=True) == 6.0
    assert pp.signals(ev, 1000, "P2")["buy"] == 0


def test_pacing_shortens_when_dead_and_pauses_when_busy():
    s = pp.signals([_c(100)], 1000, "P1")
    assert s["rate"] == 0 and pp.adjust_minutes(5, s) == 3.5
    assert pp.adjust_minutes(1.2, s) == 1.0          # never below the floor
    assert pp.adjust_minutes(5, pp.signals([], 1000)) == 5.0     # a live that has just started is never "dead"
    busy = pp.signals([_c(1000 - i) for i in range(20)], 1000)
    assert pp.extra_gap(busy) == 6.0 and pp.extra_gap({"rate": 1}) == 0.0


def test_language_detection():
    assert lp.detect("áo này giá bao nhiêu vậy shop") == "vi"
    assert lp.detect("ao nay gia bao nhieu") == "vi"
    assert lp.detect("how much is this and does it ship") == "en"
    assert lp.detect("这个多少钱") == "cjk" and lp.detect("ราคาเท่าไหร่") == "th"
    assert lp.detect("ok") == "vi" and lp.detect("") == "vi"


def test_language_note_and_settings(tmp_path):
    assert "English" in lp.note("how much is this one", True)
    assert "tiếng Việt" in lp.note("how much is this one", False)
    assert lp.note("giá bao nhiêu", True) == ""
    assert "tiếng Việt" in lp.note("这个多少钱")
    p = str(tmp_path / "l.json")
    assert lp.settings(p)["english"] is True
    lp.save(False, p)
    assert lp.settings(p)["english"] is False


def test_gestures():
    ev = [{"kind": "answer", "ts": 98}, {"kind": "gift", "ts": 99}]
    assert ag.pick(ev, 100) == {"name": "cheer", "id": 99}
    assert ag.pick(ev, 110)["name"] == "" and ag.pick([], 5)["name"] == ""
    assert ag.pick([{"kind": "entrance", "ts": 100}], 100)["name"] == "wave"


def test_playbooks(tmp_path):
    p = str(tmp_path / "a.json")
    assert pb.active(p)["key"] == "steady"
    assert pb.activate("flash", p)["max_minutes"] == 4.0 and pb.active(p)["key"] == "flash"
    assert pb.get("nope")["key"] == "steady"
    assert all(v["min_minutes"] < v["max_minutes"] for v in pb.PLAYBOOKS.values())


def test_replay_timeline():
    ev = [{"kind": "comment", "ts": 0, "intent": "price"}, {"kind": "comment", "ts": 5, "intent": "chat"},
          {"kind": "gift", "ts": 70}, {"kind": "comment", "ts": 600}]
    tl = replay.build(ev)
    assert len(tl["rows"]) == 11 and tl["rows"][0]["comments"] == 2 and tl["rows"][0]["questions"] == 1
    assert tl["peak"]["min"] == 0.0 or tl["peak"]["gifts"] == 1
    assert tl["quiet"] and tl["quiet"][0]["from"] == 2.0
    assert "Busiest minute" in replay.markdown(tl)
    assert replay.build([])["rows"] == [] and "No events" in replay.markdown(replay.build([]))


def test_product_card():
    from utils import overlay_state as ov
    p = {"name": "Cardigan nữ", "price": "295.000₫", "original_price": "350.000₫", "highlights": ["", "Chất len mềm"]}
    c = ov.product_card(p)
    assert c["kind"] == "product" and c["was"] == "350.000₫" and c["note"] == "Chất len mềm"
    assert ov.product_card(dict(p, original_price="276.000₫"))["was"] == ""      # no fake discount
    assert ov.product_card(p, safe=lambda s: False) is None and ov.product_card({}) is None
