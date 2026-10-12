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
