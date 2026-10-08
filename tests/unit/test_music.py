import json
import os
import tempfile
import unittest
from utils import music


def _dir(files, manifest):
    d = tempfile.mkdtemp()
    for f in files:
        open(os.path.join(d, f), "wb").close()
    music.save_manifest(manifest, d)
    return d


class Music(unittest.TestCase):
    def test_unknown_and_nc_blocked(self):
        d = _dir(["a.mp3", "b.mp3", "c.mp3", "d.txt"], {"b.mp3": {"license": "cc-by-nc", "artist": "x"}, "c.mp3": {"license": "cc0"}})
        t = {x["file"]: x for x in music.tracks(d)}
        self.assertEqual(set(t), {"a.mp3", "b.mp3", "c.mp3"})
        self.assertFalse(t["a.mp3"]["ok"])
        self.assertFalse(t["b.mp3"]["ok"])
        self.assertTrue(t["c.mp3"]["ok"])

    def test_cc_by_needs_artist_and_gets_credit(self):
        d = _dir(["a.mp3", "b.mp3"], {"a.mp3": {"license": "cc-by", "title": "Sunny", "artist": "Kevin MacLeod", "source": "incompetech.com"},
                                      "b.mp3": {"license": "cc-by"}})
        t = {x["file"]: x for x in music.tracks(d)}
        self.assertTrue(t["a.mp3"]["ok"])
        self.assertIn("Kevin MacLeod", t["a.mp3"]["credit"])
        self.assertIn("incompetech.com", t["a.mp3"]["credit"])
        self.assertFalse(t["b.mp3"]["ok"])
        self.assertIn("Sunny", music.credits_text(list(t.values())))

    def test_overlay_disabled_or_empty(self):
        s = dict(music.DEFAULT_SETTINGS)
        self.assertFalse(music.overlay_music(s, [], [], 0)["enabled"])
        s["enable"] = True
        self.assertFalse(music.overlay_music(s, [], [], 0)["enabled"])

    def test_duck_window(self):
        ev = [{"kind": "answer", "ts": 100.0}]
        self.assertTrue(music.duck_active(ev, 105))
        self.assertFalse(music.duck_active(ev, 120))
        self.assertFalse(music.duck_active([{"kind": "comment", "ts": 100.0}], 101))

    def test_overlay_volume_ducks(self):
        tr = [{"file": "a.mp3", "title": "A", "artist": "", "credit": "", "ok": True, "credit_needed": False}]
        s = dict(music.DEFAULT_SETTINGS, enable=True, volume=30, duck_volume=10)
        self.assertEqual(music.overlay_music(s, tr, [], 100)["volume"], 0.3)
        o = music.overlay_music(s, tr, [{"kind": "answer", "ts": 99.0}], 100)
        self.assertEqual(o["volume"], 0.1)
        self.assertTrue(o["ducked"])
        self.assertEqual(o["tracks"][0]["url"], "/lv_music/a.mp3")

    def test_settings_clamped_and_roundtrip(self):
        p = os.path.join(tempfile.mkdtemp(), "s.json")
        music.save_settings({"enable": True, "volume": 500, "duck_volume": 900}, p)
        s = music.load_settings(p)
        self.assertEqual(s["volume"], 100)
        self.assertLessEqual(s["duck_volume"], s["volume"])
        self.assertTrue(s["enable"])


if __name__ == "__main__":
    unittest.main()
