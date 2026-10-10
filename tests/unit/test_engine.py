import os
import time

from utils import engine_stats, llm_guard, tts_cache


def setup_function(_):
    engine_stats.SAVE = False
    engine_stats.reset()
    llm_guard.reset()


CFG = {"timeout_s": 0.3, "fallback": "", "breaker_fails": 2, "cooldown_s": 60}


def test_good_answer_passes_through_and_is_timed():
    assert llm_guard.call("a", lambda n: "hi", CFG) == "hi"
    s = engine_stats.summary()["llm"]
    assert s["calls"] == 1 and s["failed"] == 0


def test_hung_provider_times_out_and_returns_none():
    t0 = time.time()
    assert llm_guard.call("a", lambda n: time.sleep(2), CFG) is None
    assert time.time() - t0 < 1.5
    assert engine_stats.summary()["llm"]["timeout"] == 1


def test_fallback_used_when_primary_fails():
    def run(n):
        if n == "a":
            raise RuntimeError("boom")
        return "from b"
    assert llm_guard.call("a", run, {**CFG, "fallback": "b"}) == "from b"
    assert engine_stats.summary()["llm"]["fallback"] == 1


def test_breaker_skips_broken_primary_then_recovers():
    seen = []

    def run(n):
        seen.append(n)
        return None if n == "a" else "ok"
    cfg = {**CFG, "fallback": "b"}
    llm_guard.call("a", run, cfg)
    llm_guard.call("a", run, cfg)           # second failure opens the breaker
    assert llm_guard.is_open("a")
    seen.clear()
    assert llm_guard.call("a", run, cfg) == "ok"
    assert seen == ["b"]                    # primary skipped while open
    assert not llm_guard.is_open("a", now=time.time() + 120)


def test_fallback_same_as_primary_is_ignored_and_local_models_skip_guard():
    calls = []
    assert llm_guard.call("a", lambda n: calls.append(n), {**CFG, "fallback": "a"}) is None
    assert calls == ["a"]
    assert llm_guard.call("reread", lambda n: "x", CFG) == "x"
    assert engine_stats.summary()["llm"]["calls"] == 1


def test_settings_roundtrip_and_clamp(tmp_path):
    p = str(tmp_path / "e.json")
    out = llm_guard.save({"timeout_s": 9999, "fallback": " zhipu ", "cooldown_s": 1}, p)
    assert out["timeout_s"] == 300 and out["fallback"] == "zhipu" and out["cooldown_s"] == 5
    assert llm_guard.load(str(tmp_path / "missing.json")) == llm_guard.DEFAULTS


def test_percentiles():
    for ms in (100, 200, 300, 400, 1000):
        engine_stats.record("llm", ms, save_to=None)
    s = engine_stats.summary()["llm"]
    assert s["p50_ms"] == 300 and s["p95_ms"] == 1000


def test_tts_cache_hit_miss_and_prune(tmp_path):
    d = str(tmp_path / "c")
    src = tmp_path / "a.mp3"
    src.write_bytes(b"x" * 500)
    k = tts_cache.key("edge", "Xin chào  bạn", {"voice": "v"})
    assert k == tts_cache.key("edge", "Xin chào bạn", {"voice": "v"})      # spaces normalised
    assert k != tts_cache.key("edge", "Xin chào bạn", {"voice": "w"})      # settings matter
    dest = str(tmp_path / "out" / "b.mp3")
    assert tts_cache.lookup(k, ".mp3", dest, d) is None
    assert tts_cache.store(k, ".mp3", str(src), d)
    assert tts_cache.lookup(k, ".mp3", dest, d) == dest and os.path.getsize(dest) == 500
    tiny = tmp_path / "t.mp3"
    tiny.write_bytes(b"x")
    assert not tts_cache.store("k2", ".mp3", str(tiny), d)                  # error files are not kept
    assert tts_cache.key("edge", "y" * 400) is None
    for i in range(5):
        tts_cache.store(f"k{i}x", ".mp3", str(src), d, max_bytes=1200)
    assert tts_cache.stats(d)["files"] <= 3


def test_speaking_duration_and_state(tmp_path):
    import wave
    from utils import speaking
    p = str(tmp_path / "s.json")
    w = tmp_path / "a.wav"
    with wave.open(str(w), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000); f.writeframes(b"\0\0" * 8000 * 3)
    assert abs(speaking.duration(str(w), "x") - 3.0) < 0.01
    mp3 = tmp_path / "a.mp3"
    mp3.write_bytes(b"x" * 24000)
    assert abs(speaking.duration(str(mp3), "x") - 4.0) < 0.01
    assert speaking.duration(None, "a" * 70) == 5.0 and speaking.duration(None, "") == speaking.MIN_S
    speaking.say("  Xin   chào ", str(mp3), now=1000.0, path=p)
    s = speaking.state(1002.0, p)
    assert s["tracking"] and s["active"] and s["text"] == "Xin chào" and s["elapsed"] == 2.0
    assert not speaking.state(1006.0, p)["active"] and speaking.state(1006.0, p)["tracking"]
    assert not speaking.state(1000 + 400, p)["tracking"]
    assert speaking.state(5.0, str(tmp_path / "none.json")) == {"tracking": False, "active": False, "text": "", "elapsed": 5.0, "dur": 0.0}


def test_tts_cache_switch_default_on(tmp_path):
    assert llm_guard.load(str(tmp_path / "x.json"))["tts_cache"] is True
    p = str(tmp_path / "e.json")
    assert llm_guard.save({"tts_cache": False}, p)["tts_cache"] is False


def test_stats_are_saved_for_the_web_ui_process(tmp_path):
    p = str(tmp_path / "s.json")
    engine_stats.record("llm", 1500, save_to=None)
    engine_stats.save(p)
    d = engine_stats.load(p)
    assert d["stats"]["llm"]["calls"] == 1 and d["stats"]["llm"]["p50_ms"] == 1500
    assert engine_stats.load(str(tmp_path / "none.json")) == {}
