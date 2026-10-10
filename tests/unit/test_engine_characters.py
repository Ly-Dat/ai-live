"""Avatar speed-ups, speaking-aware avatar, regulars' interests, new preflight rows."""
import base64
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

from utils import avatar, avatar_gen, avatar_roster, preflight, returning


def test_reach_matches_the_slow_flood_fill():
    def slow(close):
        bg = np.zeros_like(close)
        bg[0, :], bg[-1, :], bg[:, 0], bg[:, -1] = close[0, :], close[-1, :], close[:, 0], close[:, -1]
        for _ in range(max(close.shape)):
            g = bg.copy()
            g[1:, :] |= bg[:-1, :]
            g[:-1, :] |= bg[1:, :]
            g[:, 1:] |= bg[:, :-1]
            g[:, :-1] |= bg[:, 1:]
            g &= close
            if (g == bg).all():
                break
            bg = g
        return bg
    rng = np.random.default_rng(3)
    for k in range(5):
        close = rng.random((60, 50)) < 0.5 + 0.08 * k
        close = (close.astype(int) + np.roll(close, 1, 0) + np.roll(close, 1, 1) + np.roll(close, -1, 0) + np.roll(close, -1, 1)) >= 3
        edge = np.zeros_like(close)
        edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
        assert (avatar_gen._reach(close, edge) == slow(close)).all()


def test_blink_is_an_expression_that_falls_back_to_idle():
    assert "blink" in avatar_gen.EXPRESSIONS and avatar_gen.resolve("blink", {"idle"}) == "idle"
    assert set(avatar_gen.EXPRESSIONS) == set(avatar_gen._EXPR_TAGS)


class _Fake(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def do_POST(self):
        from tests.unit.test_avatar_seller import _png
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Fake.calls.append((self.path, body))
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


def test_base_picture_is_reused_so_the_face_stays_the_same(server, tmp_path):
    cfg = {"port": server, "steps": 2}
    char = {"hair": "silver hair", "eyes": "green eyes", "outfit": "kimono"}
    avatar_gen.generate_pack(char, cfg, str(tmp_path), seed=5, expressions=["idle", "happy"])
    first = [c[0] for c in _Fake.calls].count("/sdapi/v1/txt2img")
    avatar_gen.generate_pack(char, cfg, str(tmp_path), seed=5, expressions=["wink"])
    assert first == 1 and [c[0] for c in _Fake.calls].count("/sdapi/v1/txt2img") == 1      # no second base
    avatar_gen.generate_pack(char, cfg, str(tmp_path), seed=6, expressions=["blink"])       # new seed -> new face
    assert [c[0] for c in _Fake.calls].count("/sdapi/v1/txt2img") == 2
    assert avatar_roster.drawn is not None and not any(n.startswith("_base") for n in avatar_gen.EXPRESSIONS)


def _stage_char(tmp_path):
    root = str(tmp_path / "chars")
    c = avatar_roster.create_from_preset("mimi", root)
    d = avatar_roster.look_dir(c["id"], c["look"], root)
    os.makedirs(d, exist_ok=True)
    from tests.unit.test_avatar_seller import _png
    for ex in ("idle", "talking", "happy", "blink"):
        with open(os.path.join(d, ex + ".png"), "wb") as f:
            f.write(_png())
    return root, c


def test_overlay_follows_the_voice_when_it_reports_speech(tmp_path):
    root, c = _stage_char(tmp_path)
    s = avatar.load_settings(str(tmp_path / "none.json"))
    s["enabled"], s["active"] = True, c["id"]
    now = 1000.0
    ev = [{"ts": now - 1, "kind": "answer"}]                       # the old guess: talking for ~6 s
    sp_active = {"tracking": True, "active": True, "text": "Xin chào", "elapsed": 1.0, "dur": 3.0}
    o = avatar.overlay_avatar(s, ev, now, root=root, speaking_state=sp_active)
    assert o["talking"] and o["caption"] == {"text": "Xin chào", "elapsed": 1.0, "dur": 3.0} and "blink" in o["images"]
    sp_done = {"tracking": True, "active": False, "text": "Xin chào", "elapsed": 5.0, "dur": 3.0}
    o = avatar.overlay_avatar(s, ev, now, root=root, speaking_state=sp_done)
    assert not o["talking"] and o["caption"] is None             # audio over: mouth closes even though the event is recent
    o = avatar.overlay_avatar(s, ev, now, root=root, speaking_state={"tracking": False})
    assert o["talking"]                                           # no voice reports: the event-based guess still works
    s["stage"]["caption"] = False
    assert avatar.overlay_avatar(s, ev, now, root=root, speaking_state=sp_active)["caption"] is None


def test_viewer_book_remembers_interest_only_for_known_viewers(tmp_path):
    b = returning.ViewerBook(str(tmp_path / "v.json"), gap_hours=1)
    b.note_interest("Lan", "p1")
    assert b.interest("Lan") is None                              # never seen an entrance: nothing stored
    b.visit("Lan", now=0)
    b.note_interest("Lan", "p1")
    assert b.interest("Lan") == "p1"
    again = returning.ViewerBook(str(tmp_path / "v.json"), gap_hours=1)
    assert again.interest("Lan") == "p1" and "Lan" not in open(tmp_path / "v.json", encoding="utf-8").read()


def test_greeting_mentions_the_product_when_known():
    g = returning.greeting("Lan", 2, product_name="Áo thun cotton")
    assert "Lan" in g and "Áo thun cotton" in g
    assert "Áo" not in returning.greeting("Lan", 2)
    assert returning.greeting("Lan", 0, product_name="x") is None


def test_preflight_new_rows_only_when_facts_exist():
    base = {"tiktok_username": "a", "api_ok": True, "bridge_on": True, "mode": "creator"}
    ids = lambda f: [r["id"] for r in preflight.run(dict(base, **f))]
    assert not {"host", "avatar", "ai_speed", "ai_fail"} & set(ids({}))
    assert "host" in ids({"host_state": "paused"})
    assert "avatar" in ids({"avatar_enabled": True, "avatar_ready": False})
    assert "avatar" not in ids({"avatar_enabled": True, "avatar_ready": True})
    rows = {r["id"]: r for r in preflight.run(dict(base, llm_calls=5, llm_p50_ms=6000, llm_fail_rate=0.0))}
    assert rows["ai_speed"]["ok"] is None and rows["ai_speed"]["go"] == "AI engine"
    rows = {r["id"]: r for r in preflight.run(dict(base, llm_calls=5, llm_p50_ms=900, llm_fail_rate=0.5))}
    assert rows["ai_fail"]["ok"] is False
    assert not {"ai_speed", "ai_fail"} & set(ids({"llm_calls": 2, "llm_p50_ms": 9000}))
