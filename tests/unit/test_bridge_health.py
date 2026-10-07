from utils import bridge_health as bh

NOW = 10_000.0


def st(**kw):
    base = {"state": "connected", "failures": 0, "last_event_ts": NOW - 5, "last_error": "", "lib": "7.1", "updated": NOW - 3}
    base.update(kw)
    return base


def test_ok_and_not_started():
    assert bh.assess(st(), NOW)["level"] == "ok"
    assert bh.assess(None, NOW)["level"] == "off"


def test_stale_heartbeat_means_not_running():
    r = bh.assess(st(updated=NOW - 200), NOW)
    assert r["level"] == "off" and "not running" in r["message"]


def test_repeated_errors_are_down_and_offer_fallback():
    r = bh.assess(st(state="error", failures=3, last_error="WebcastBlocked: x"), NOW)
    assert r["level"] == "down" and r["fallback"] and "WebcastBlocked" in r["message"] and "7.1" in r["message"]
    assert bh.assess(st(state="error", failures=1), NOW)["level"] == "warn"


def test_waiting_for_live_is_not_a_failure():
    r = bh.assess(st(state="waiting_live"), NOW)
    assert r["level"] == "warn" and not r["fallback"]


def test_silent_connection_flagged():
    r = bh.assess(st(last_event_ts=NOW - 900), NOW)
    assert r["level"] == "warn" and r["fallback"] and "15 min" in r["message"]


def test_read_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"state": "connected"}')
    assert bh.read(str(p))["state"] == "connected"
    assert bh.read(str(tmp_path / "nope.json")) is None
