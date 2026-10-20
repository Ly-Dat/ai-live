"""Release-gate checks from the Next Steps plan: operator control, start guard, no tracked secrets, simulator verdicts."""
import json
import subprocess

from utils import host_control, setup_wizard, simulator, tiktok_safety
from utils.product_catalog import ProductCatalog
from utils.triage import Triage


def test_takeover_edge_stops_speech_once(tmp_path):
    p = str(tmp_path / "hc.json")
    silent, just = host_control.edge(False, p)
    assert (silent, just) == (False, False)                  # live: nothing to stop
    host_control.set_state("takeover", p)
    silent, just = host_control.edge(silent, p)
    assert (silent, just) == (True, True)                    # the moment of takeover: halt queued + playing speech
    silent, just = host_control.edge(silent, p)
    assert (silent, just) == (True, False)                   # stays silent, no repeated halting
    host_control.set_state("live", p)
    assert host_control.edge(silent, p) == (False, False)    # resuming is deliberate and does not replay anything


def test_start_blocked_without_active_products(tmp_path):
    f = tmp_path / "p.json"
    f.write_text(json.dumps({"products": [{"id": "a", "active": False}]}))
    assert "no active products" in setup_wizard.start_blockers({}, str(f))[0]
    assert setup_wizard.start_blockers({"mode": "creator"}, str(f)) == []
    f.write_text(json.dumps({"products": [{"id": "a"}]}))
    assert setup_wizard.start_blockers({}, str(f)) == []
    assert setup_wizard.start_blockers({}, str(tmp_path / "missing.json"))      # unreadable catalog also blocks


def test_no_browser_profile_or_cookies_tracked():
    try:
        out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, timeout=30).stdout.splitlines()
    except Exception:
        return
    if not out:
        return        # not a git checkout
    bad = [f for f in out if f.startswith("data/chrome_profile/") or f.lower().endswith(("/cookies", ".pem", ".p12"))]
    assert not bad, f"private browser data is tracked in git: {bad[:3]}"


def test_simulator_verdicts(tmp_path):
    pp = tmp_path / "p.json"
    pp.write_text(json.dumps({"products": [{"id": "a", "order": 1, "name": "Áo thun", "aliases": ["áo thun"], "price": "100.000₫",
                                           "sizes_colors": "Size M, L", "highlights": [], "faq": []}]}), encoding="utf-8")
    cat = ProductCatalog(str(pp), str(tmp_path / "t.json"))
    safety = tiktok_safety.TikTokSafety("data/tiktok_policy_terms.json")
    tri = Triage()
    v = lambda text, user="u", now=100.0: simulator.evaluate_comment(text, safety, cat, tri, user, now)["verdict"]
    assert v("áo thun giá bao nhiêu", "a", 100) == "quick"
    assert v("áo thun ship mấy ngày", "b", 200) == "cannot_confirm"       # shipping never filled in -> honest, not invented
    assert v("chốt đơn áo thun 1 cái", "c", 300) == "buy_cta"
    assert v("add zalo 0909123456 mình chuyển khoản", "d", 400) == "blocked"
    assert v("aaaaaaaaaaaaaaaaaaa", "e", 500) == "skipped"


def test_streamed_replies_feed_the_breaker():
    from utils import llm_guard
    llm_guard.reset()
    cfg = dict(llm_guard.load(), breaker_fails=2, cooldown_s=60)
    assert llm_guard.stream_allowed("chatgpt", cfg, now=100)
    llm_guard.note("chatgpt", False, settings=cfg, now=100)
    llm_guard.note("chatgpt", False, settings=cfg, now=101)
    assert not llm_guard.stream_allowed("chatgpt", cfg, now=102)        # two empty streams: use the guarded path with fallback
    assert llm_guard.stream_allowed("chatgpt", cfg, now=200)            # breaker closes after the cooldown
    llm_guard.note("chatgpt", True, settings=cfg, now=200)
    llm_guard.reset()


def test_go_nogo_runs_and_reports():
    import go_nogo
    rows = go_nogo.checks()
    assert any(r[0] == go_nogo.MANUAL for r in rows)                  # person-only checks are listed, never faked as PASS
    labels = {r[1]: r[0] for r in rows}
    assert labels["No browser profile / cookies tracked by git"] == go_nogo.PASS
    assert labels["Offline simulation meets its expectations"] == go_nogo.PASS


def test_queue_drops_identical_waiting_lines():
    from utils import speech_queue
    q = [{"content": "Giá 100k nha"}, {"content": "Cảm ơn bạn"}]
    assert speech_queue.is_duplicate(q, {"content": "  giá 100K   nha "})
    assert not speech_queue.is_duplicate(q, {"content": "Giá 200k nha"})
    assert not speech_queue.is_duplicate(q, {"content": ""})


def test_queue_state_file_roundtrip_and_staleness(tmp_path):
    from utils import speech_queue
    p = str(tmp_path / "q.json")
    assert speech_queue.read_state(p) == -1                      # unknown, never faked as 0
    speech_queue.write_state(3, p, now=100)
    assert speech_queue.read_state(p, now=105) == 3
    assert speech_queue.read_state(p, now=200) == -1             # stale: the app stopped writing


def test_open_stream_times_out_and_passes_through():
    import time as _t
    from utils import llm_guard
    cfg = dict(llm_guard.DEFAULTS, timeout_s=1)
    llm_guard.reset()
    t0 = _t.time()
    assert llm_guard.open_stream("chatgpt", lambda: _t.sleep(5), cfg) is None
    assert _t.time() - t0 < 3
    assert llm_guard.open_stream("chatgpt", lambda: "stream-object", cfg) == "stream-object"
    assert llm_guard.open_stream("reread", lambda: "x", cfg) == "x"


def test_guard_iter_passes_through_and_stops_on_stall():
    import time as _t
    from utils import llm_guard
    cfg = dict(llm_guard.DEFAULTS, timeout_s=1)
    llm_guard.reset()
    assert list(llm_guard.guard_iter(iter([1, 2, 3]), "chatgpt", cfg)) == [1, 2, 3]
    assert list(llm_guard.guard_iter("abc", "chatgpt", cfg)) == ["a", "b", "c"]

    def slow():
        yield "a"
        _t.sleep(5)
        yield "b"
    hit = []
    t0 = _t.time()
    assert list(llm_guard.guard_iter(slow(), "chatgpt", cfg, on_stall=lambda: hit.append(1))) == ["a"]
    assert hit and _t.time() - t0 < 3

    def boom():
        yield 1
        raise ValueError("x")
    try:
        list(llm_guard.guard_iter(boom(), "chatgpt", cfg))
        assert False
    except ValueError:
        pass
