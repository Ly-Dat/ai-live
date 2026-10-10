import base64
import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from utils import avatar, avatar_gen, host_control, seller_brain
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


def test_expression_follows_events_and_pause_calms_it():
    now = 1000.0
    ev = lambda k, ago: {"kind": k, "ts": now - ago}
    assert avatar.pick_expression([ev("answer", 1)], now) == {"mood": "idle", "talking": True}
    assert avatar.pick_expression([ev("gift", 0.5)], now)["mood"] == "surprised"
    assert avatar.pick_expression([ev("gift", 3)], now)["mood"] == "happy"
    assert avatar.pick_expression([ev("blocked", 1)], now)["mood"] == "confused"
    assert avatar.pick_expression([ev("answer", 30)], now) == {"mood": "idle", "talking": False}
    s = avatar.load_settings("/nonexistent")
    s["enabled"] = True
    files = {"idle": 1.0, "talking": 1.0, "happy": 1.0}
    o = avatar.overlay_avatar(s, files, [ev("answer", 1)], now)
    assert o["talking"] and o["images"]["happy"].startswith("/lv_avatar/pack/happy.png")
    p = avatar.overlay_avatar(s, files, [ev("answer", 1)], now, host_state="paused")
    assert not p["talking"] and p["paused"]
    assert avatar.overlay_avatar(s, {"happy": 1.0}, [], now) is None   # no idle picture -> nothing to show
    s["enabled"] = False
    assert avatar.overlay_avatar(s, files, [], now) is None


def test_settings_are_sanitised(tmp_path):
    p = str(tmp_path / "s.json")
    avatar.save_settings({"enabled": True, "height_vh": 500, "catchphrases": ["  nha  ", "", "x" * 200], "character": {"name": "Rin", "bogus": "x"}}, p)
    s = avatar.load_settings(p)
    assert s["height_vh"] == 90 and s["catchphrases"][0] == "nha" and len(s["catchphrases"][1]) == 60
    assert s["character"]["name"] == "Rin" and "bogus" not in s["character"]


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
