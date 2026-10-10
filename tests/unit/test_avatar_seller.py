import base64
import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import datetime

from utils import avatar, avatar_gen, avatar_roster, bond, host_control, seller_brain
from utils.product_catalog import ProductCatalog


def _png(bg=(255, 255, 255), fg=(200, 30, 90)):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (64, 64), bg)
    ImageDraw.Draw(im).ellipse((16, 16, 48, 48), fill=fg)
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


class _Fake(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Fake.calls.append((self.path, body))
        if body.get("prompt", "").count("surprised") and self.path.endswith("img2img") and os.environ.get("FAKE_FAIL"):
            self.send_response(500)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"images": [base64.b64encode(_png()).decode()]}).encode())


@pytest.fixture
def server():
    _Fake.calls = []
    s = HTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1]
    s.shutdown()


def test_pack_generation_uses_same_seed_and_cuts_out_background(server, tmp_path):
    cfg = {"port": server, "steps": 2}
    char = {"hair": "silver hair", "eyes": "green eyes", "outfit": "kimono"}
    r = avatar_gen.generate_pack(char, cfg, str(tmp_path), seed=77)
    assert sorted(r["made"]) == sorted(avatar_gen.EXPRESSIONS) and not r["failed"]
    paths = [c[0] for c in _Fake.calls]
    assert paths.count("/sdapi/v1/txt2img") == 1 and paths.count("/sdapi/v1/img2img") == len(avatar_gen.EXPRESSIONS) - 1
    assert all(c[1]["seed"] == 77 for c in _Fake.calls)
    assert "silver hair" in _Fake.calls[0][1]["prompt"] and "white background" in _Fake.calls[0][1]["prompt"]
    from PIL import Image
    im = Image.open(tmp_path / "happy.png").convert("RGBA")
    assert im.getpixel((1, 1))[3] == 0 and im.getpixel((32, 32))[3] == 255   # corner clear, body kept


def test_one_failed_expression_does_not_stop_the_rest(server, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_FAIL", "1")
    r = avatar_gen.generate_pack({}, {"port": server}, str(tmp_path))
    assert "surprised" in r["failed"] and "idle" in r["made"] and "thinking" in r["made"]


def test_missing_server_gives_instructions_not_a_crash(tmp_path):
    r = avatar_gen.generate_pack({}, {"port": 1, "timeout": 1}, str(tmp_path))
    assert r["made"] == [] and "--api" in r["failed"]["all"]


def test_host_control_roundtrip(tmp_path):
    p = str(tmp_path / "h.json")
    assert not host_control.is_silent(p)
    host_control.set_state("paused", p)
    assert host_control.is_silent(p)
    host_control.set_state("live", p)
    assert not host_control.is_silent(p)
    with pytest.raises(ValueError):
        host_control.set_state("loud", p)
    open(p, "w").write("garbage")
    assert host_control.load(p)["state"] == "live"


def test_fourteen_expressions_and_fallback_chain():
    assert len(avatar_gen.EXPRESSIONS) == 14 and avatar_gen.EXPRESSIONS[:6] == avatar_gen.CORE
    assert set(avatar_gen.EXPRESSIONS) == set(avatar_gen._EXPR_TAGS)
    assert avatar_gen.resolve("love", {"idle", "happy"}) == "happy"
    assert avatar_gen.resolve("sad", {"idle", "confused"}) == "confused"
    assert avatar_gen.resolve("shy", {"idle"}) == "idle"
    assert avatar_gen.resolve("wink", {"wink", "idle"}) == "wink"


def test_expression_follows_events():
    now = 1000.0
    ev = lambda k, ago, **kw: {"kind": k, "ts": now - ago, **kw}
    assert avatar.pick_expression([ev("answer", 1)], now) == {"mood": "idle", "talking": True}
    assert avatar.pick_expression([ev("pitch", 1)], now) == {"mood": "proud", "talking": True}
    assert avatar.pick_expression([ev("gift", 0.5)], now)["mood"] == "surprised"
    assert avatar.pick_expression([ev("gift", 2)], now)["mood"] == "excited"
    assert avatar.pick_expression([ev("gift", 5)], now)["mood"] == "love"
    assert avatar.pick_expression([ev("blocked", 1)], now)["mood"] == "confused"
    assert avatar.pick_expression([ev("entrance", 1)], now)["mood"] == "wink"
    for text, mood in (("chị xinh quá", "shy"), ("yêu shop <3", "love"), ("haha buồn cười", "laughing"), ("buồn quá huhu", "sad"), ("size nào vậy", "thinking")):
        assert avatar.pick_expression([ev("comment", 1, text=text)], now)["mood"] == mood, text
    assert avatar.pick_expression([ev("answer", 30)], now)["mood"] == "idle"
    assert avatar.pick_expression([ev("comment", 400)], now)["mood"] == "sleepy"   # quiet for a while
    assert avatar.pick_expression([], now)["mood"] == "idle"                        # nothing yet: not asleep


def _stage_char(tmp_path, exprs=("idle", "talking", "happy")):
    root = str(tmp_path / "chars")
    c = avatar_roster.create_from_preset("mimi", root)
    d = avatar_roster.look_dir(c["id"], c["look"], root)
    os.makedirs(d)
    for ex in exprs:
        open(os.path.join(d, ex + ".png"), "wb").write(_png())
    s = avatar.load_settings("/nonexistent")
    s.update(enabled=True, active=c["id"])
    return root, s


def test_overlay_uses_active_character_and_fallbacks(tmp_path):
    root, s = _stage_char(tmp_path)
    now = 1000.0
    ev = lambda k, ago, **kw: {"kind": k, "ts": now - ago, **kw}
    o = avatar.overlay_avatar(s, [ev("answer", 1)], now, root=root)
    assert o["talking"] and o["name"] == "Mimi" and "/characters/mimi/looks/default/talking.png" in o["images"]["talking"]
    assert avatar.overlay_avatar(s, [ev("comment", 1, text="yêu quá")], now, root=root)["mood"] == "happy"   # love not drawn -> happy
    p = avatar.overlay_avatar(s, [ev("answer", 1)], now, host_state="paused", root=root)
    assert not p["talking"] and p["paused"]
    assert avatar.overlay_avatar(s, [], now, root=root, preview="happy")["mood"] == "happy"
    s["enabled"] = False
    assert avatar.overlay_avatar(s, [], now, root=root) is None
    root2, s2 = _stage_char(tmp_path / "x", exprs=("happy",))
    assert avatar.overlay_avatar(s2, [], now, root=root2) is None   # no idle picture -> nothing to show


def test_locked_cosmetics_are_not_shown_before_they_are_earned(tmp_path):
    root, s = _stage_char(tmp_path)
    s["stage"].update(frame="gold", motion="float", badge=True)
    o = avatar.overlay_avatar(s, [], 1000.0, root=root, cache={"level": 1, "streak": 0})
    assert o["frame"] == "none" and o["motion"] == "bob" and o["badge"] == "Lv 1"
    o = avatar.overlay_avatar(s, [], 1000.0, root=root, cache={"level": 6, "streak": 4})
    assert o["frame"] == "gold" and o["motion"] == "float" and o["badge"] == "Lv 6 · 4-day streak"


def test_settings_are_sanitised(tmp_path):
    p = str(tmp_path / "s.json")
    avatar.save_settings({"enabled": True, "active": "mimi", "stage": {"height_vh": 500, "side": "up", "tips": ["  hi  ", "", "x" * 200]}}, p)
    s = avatar.load_settings(p)
    assert s["stage"]["height_vh"] == 90 and s["stage"]["side"] == "right" and s["stage"]["tips"][0] == "hi" and len(s["stage"]["tips"][1]) == 90
    open(p, "w").write("junk")
    assert avatar.load_settings(p)["enabled"] is False


def test_preview_override_expires(tmp_path):
    p = str(tmp_path / "pv.json")
    avatar.set_preview("wink", 100.0, 8, p)
    assert avatar.read_preview(105.0, p) == "wink" and avatar.read_preview(109.0, p) is None


def test_roster_presets_looks_and_delete(tmp_path):
    root = str(tmp_path / "r")
    assert len(avatar_roster.PRESETS) >= 8
    a = avatar_roster.create_from_preset("kuro", root)
    b = avatar_roster.create_from_preset("kuro", root)
    assert a["id"] == "kuro" and b["id"] == "kuro-2" and a["gender"] == "male"
    assert {c["id"] for c in avatar_roster.list_all(root)} == {"kuro", "kuro-2"}
    c2 = avatar_roster.add_look(a, "Summer", "yukata", max_looks=2)
    assert c2["look"] == "summer" and c2["looks"]["summer"] == "yukata"
    with pytest.raises(ValueError):
        avatar_roster.add_look(c2, "Winter", "coat", max_looks=2)
    avatar_roster.save(c2, root)
    assert avatar_roster.load("kuro", root)["look"] == "summer"
    avatar_roster.delete("kuro", root)
    assert avatar_roster.load("kuro", root) is None and avatar_roster.load("kuro-2", root)
    avatar_roster.delete("../../etc", root)   # path tricks do nothing


def test_every_preset_prompts_cleanly():
    for p in avatar_roster.PRESETS:
        pr = avatar_gen.character_prompt(p)
        assert p["hair"] in pr and ("1boy" if p["gender"] == "male" else "1girl") in pr


def test_levels_unlocks_and_honest_achievements():
    assert [bond.level_for(x) for x in (0, 99, 100, 299, 300, 600)] == [1, 1, 2, 2, 3, 4]
    assert bond.max_looks(1) == 1 and bond.max_looks(2) == 2 and bond.max_looks(20) == 8
    assert "neon" in bond.unlocked(bond.FRAMES, 3) and "gold" not in bond.unlocked(bond.FRAMES, 3)
    assert bond.next_unlock(1).startswith("Level 2")
    today = datetime.date(2026, 10, 10)
    dates = {today - datetime.timedelta(days=i) for i in range(3)}
    sums = [{"duration_min": 60, "comments": 40, "answered": 30, "gifts": 2, "products_pitched": 12}] * 3
    b = bond.compute(sums, dates, today, answered_today=4)
    assert b["streak"] == 3 and b["answered"] == 90 and b["xp"] == 3 * 50 + 90 * 2 + 6 * 5 + 30
    done = {a["id"] for a in b["achievements"] if a["done"]}
    assert {"first_live", "answers_10", "gift_1", "streak_3", "showcase"} <= done and "streak_7" not in done and "answers_100" not in done
    empty = bond.compute([], set(), today)
    assert empty["level"] == 1 and not any(a["done"] for a in empty["achievements"])


def test_refresh_reads_logs_and_announces_new_achievements_once(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    today = datetime.date(2026, 10, 10)
    ev = [{"kind": "comment", "ts": 1.0, "user": "u"}, {"kind": "answer", "ts": 2.0}, {"kind": "gift", "ts": 3.0}]
    (logs / "session-20261010-0900.jsonl").write_text("\n".join(json.dumps(e) for e in ev), encoding="utf-8")
    path = str(tmp_path / "bond.json")
    first = bond.refresh(str(logs), today, path)
    assert first["new"] == [] and first["lives"] == 1 and first["answered_today"] == 1   # earned before the feature: not announced
    (logs / "session-20261011-0900.jsonl").write_text("\n".join(json.dumps(e) for e in ev * 10), encoding="utf-8")
    second = bond.refresh(str(logs), today + datetime.timedelta(days=1), path)
    assert [a["id"] for a in second["new"]] == ["answers_10"]
    bond.mark_seen(path)
    assert bond.refresh(str(logs), today + datetime.timedelta(days=1), path)["new"] == []
    assert bond.load_cache(path)["level"] >= 1


@pytest.fixture
def cat(tmp_path):
    prods = {"shop_name": "s", "products": [
        {"id": "A", "order": 1, "name": "Áo cardigan nữ tay dài", "price": "295.000₫", "original_price": "350.000₫", "highlights": ["dáng rộng", "dễ phối"],
         "return_policy": "Được đổi trả theo chính sách của TikTok Shop.", "stock_note": "Số lượng có hạn.", "active": True},
        {"id": "B", "order": 2, "name": "Quần jean ống rộng", "price": "450.000₫", "highlights": ["co giãn nhẹ"], "active": True},
        {"id": "C", "order": 3, "name": "Túi tote vải", "price": "99.000₫", "active": True}]}
    pp = tmp_path / "p.json"
    pp.write_text(json.dumps(prods), encoding="utf-8")
    return ProductCatalog(str(pp), str(tmp_path / "none.json"))


def test_budget_parsing():
    b = seller_brain.budget_from
    assert b("có cái nào dưới 300k không") == 300000 and b("tầm 1 triệu") == 1000000
    assert b("tầm 3 cái") is None and b("hello") is None


def test_recommend_by_budget_uses_only_catalog(cat):
    r = seller_brain.answer(cat, "cho mình hỏi có cái nào dưới 300k không")
    assert "Túi tote vải" in r and "Áo cardigan" in r and "Quần jean" not in r
    r = seller_brain.answer(cat, "có gì dưới 50k không")
    assert "rẻ nhất là Túi tote vải" in r


def test_compare_two_products(cat):
    r = seller_brain.answer(cat, "so sánh áo cardigan với quần jean đi")
    assert r and "295.000₫" in r and "450.000₫" in r and "dáng rộng" in r
    assert seller_brain.answer(cat, "so sánh đi") is None


def test_objections_stay_factual_and_never_overclaim(cat):
    r = seller_brain.answer(cat, "áo cardigan đắt quá")
    assert "350.000₫" in r and "295.000₫" in r
    assert "đổi trả" in seller_brain.answer(cat, "áo cardigan có thật không shop")
    q = seller_brain.answer(cat, "áo cardigan có tốt không")
    assert "dáng rộng" in q and "không dám hứa" in q
    assert seller_brain.answer(cat, "túi tote có tốt không") is None   # no highlights -> no invented praise
    bad = " ".join(filter(None, [r, q, seller_brain.answer(cat, "áo cardigan có thật không")])).lower()
    assert "chính hãng" not in bad and "100%" not in bad and "tốt nhất" not in bad


def test_catchphrase_only_sometimes_and_never_on_long_replies():
    seller_brain._counter["n"] = 0
    out = [seller_brain.add_catchphrase("Giá 100k nha", ["nè"]) for _ in range(6)]
    assert sum(o.endswith("nè") for o in out) == 2
    assert seller_brain.add_catchphrase("x" * 300, ["nè"], every=1) == "x" * 300
    assert seller_brain.add_catchphrase("hi", []) == "hi"
