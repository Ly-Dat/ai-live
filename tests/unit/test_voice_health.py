from utils import voice_health as vh


def test_stale_by_type():
    assert vh.is_stale("entrance", 100, now=125) is True
    assert vh.is_stale("entrance", 100, now=110) is False
    assert vh.is_stale("comment", 100, now=140) is False and vh.is_stale("comment", 100, now=150) is True
    assert vh.is_stale("abnormal_alarm", 1, now=9999) is False      # alerts are never dropped
    assert vh.is_stale("comment", None, now=9999) is False          # unknown age: keep
    assert vh.is_stale("unknown_type", 0.5, now=100) is False and vh.is_stale("unknown_type", 1, now=200) is True


def test_level_transitions(tmp_path):
    p = str(tmp_path / "v.json")
    assert vh.level(p, now=10)["level"] == "unknown"
    vh.record(True, path=p, now=10)
    assert vh.level(p, now=11)["level"] == "ok"
    vh.record(True, used_backup=True, path=p, now=20)
    assert vh.level(p, now=30)["level"] == "backup"
    assert vh.level(p, now=20 + vh.RECENT_S + 1)["level"] == "ok"
    vh.record(False, path=p, now=40)
    assert vh.level(p, now=41)["level"] == "backup"      # one failure is not "down"; the earlier backup use is still recent
    vh.record(False, path=p, now=42)
    assert vh.level(p, now=43)["level"] == "down"
    vh.record(True, path=p, now=44)
    assert vh.level(p, now=45)["fails"] == 0


def test_stale_counter_and_backup(tmp_path):
    p = str(tmp_path / "v.json")
    vh.record_stale(p, now=5)
    vh.record_stale(p, now=6)
    assert vh.level(p, now=7)["stale_dropped"] == 2
    assert vh.backup_type("edge-tts") is None and vh.backup_type("vieneu") == "edge-tts"
