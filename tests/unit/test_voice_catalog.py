import unittest
from utils import voice_catalog as vc


class VoiceCatalog(unittest.TestCase):
    def test_ids_unique_and_wellformed(self):
        ids = [v["id"] for v in vc.VOICES]
        self.assertEqual(len(ids), len(set(ids)))
        for i in ids:
            self.assertTrue(i.endswith("Neural"), i)

    def test_vietnamese_native_first(self):
        vi = vc.for_language("vi")
        self.assertEqual([v["id"] for v in vi[:2]], ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"])
        self.assertTrue(all(v["vi"] in (True, "try") for v in vi))

    def test_english_has_both_genders_and_many(self):
        self.assertGreaterEqual(len(vc.for_language("en", "F")), 8)
        self.assertGreaterEqual(len(vc.for_language("en", "M")), 8)
        self.assertTrue(all(v["lang"] == "en" for v in vc.for_language("en")))

    def test_try_voices_flagged_for_vi_only(self):
        opts_vi = vc.options("vi")
        self.assertIn("listen first", opts_vi["en-US-AvaMultilingualNeural"])
        self.assertNotIn("listen first", vc.options("en")["en-US-AvaMultilingualNeural"])

    def test_lang_of_and_sample(self):
        self.assertEqual(vc.lang_of("vi-VN-HoaiMyNeural"), "vi")
        self.assertEqual(vc.lang_of("en-GB-SoniaNeural"), "en")
        self.assertIn("shop", vc.sample("vi"))


if __name__ == "__main__":
    unittest.main()
