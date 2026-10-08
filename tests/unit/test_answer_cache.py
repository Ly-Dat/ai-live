import unittest
from utils import answer_cache as ac


class AnswerCache(unittest.TestCase):
    def test_normalize_ignores_case_punct_and_stretching(self):
        self.assertEqual(ac.normalize("Ship bao lâu vậy???"), ac.normalize("ship  bao lâu vậy"))
        self.assertEqual(ac.normalize("đẹppppp quá"), ac.normalize("đẹpp quá"))

    def test_key_depends_on_product_and_version(self):
        a = ac.make_key("có size L không", "p1", "v1")
        self.assertNotEqual(a, ac.make_key("có size L không", "p2", "v1"))
        self.assertNotEqual(a, ac.make_key("có size L không", "p1", "v2"))
        self.assertIsNone(ac.make_key("ok", "p1"))

    def test_ttl_and_lru(self):
        c = ac.AnswerCache(ttl=10, max_items=2)
        c.put("a", "one", now=0)
        c.put("b", "two", now=0)
        c.put("c", "three", now=1)
        self.assertIsNone(c.get("a", now=1))      # evicted (oldest)
        self.assertEqual(c.get("c", now=5), "three")
        self.assertIsNone(c.get("c", now=20))     # expired

    def test_cacheable_rules(self):
        self.assertTrue(ac.cacheable("Áo này có size M và L nha."))
        self.assertFalse(ac.cacheable("Mình không chắc, bạn xem trang sản phẩm nhé", unsure=True))
        self.assertFalse(ac.cacheable("Chào Hùng Phạm nha", username="hùng phạm"))
        self.assertFalse(ac.cacheable(""))
        self.assertFalse(ac.cacheable("x" * 500))


class Latency(unittest.TestCase):
    def test_summary_has_median_and_cache_source(self):
        from utils import live_analytics as la
        ev = [{"ts": 1.0, "kind": "answer", "source": "cache"}, {"ts": 2.0, "kind": "answer", "source": "llm"},
              {"ts": 3.0, "kind": "latency", "ms": 3000}, {"ts": 4.0, "kind": "latency", "ms": 1000}, {"ts": 5.0, "kind": "latency", "ms": 2000}]
        s = la.summarize(ev)
        self.assertEqual(s["llm_median_ms"], 2000)
        self.assertEqual(s["answer_sources"], {"cache": 1, "llm": 1})
        self.assertIsNone(la.summarize([])["llm_median_ms"])


if __name__ == "__main__":
    unittest.main()
