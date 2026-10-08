import unittest
from utils import lang_guard as lg


class LangGuard(unittest.TestCase):
    def test_plain_text_untouched(self):
        self.assertEqual(lg.clean("Chào cả nhà, shop có mẫu mới nhé!"), "Chào cả nhà, shop có mẫu mới nhé!")
        self.assertEqual(lg.clean(""), "")

    def test_mixed_reply_keeps_vietnamese_part(self):
        s = "Rất tiếc nghe bạn nói bạn tâm trạng không tốt, 也许我们可以聊聊或者其他话题转移一下注意力，有什么想聊的吗?"
        self.assertEqual(lg.clean(s), "Rất tiếc nghe bạn nói bạn tâm trạng không tốt")

    def test_pure_chinese_dropped(self):
        self.assertIsNone(lg.clean("打卡成功喵"))
        self.assertIsNone(lg.clean("在的呢，宝贝，诶嘿"))

    def test_japanese_korean(self):
        self.assertIsNone(lg.clean("こんにちは"))
        self.assertIsNone(lg.clean("안녕하세요"))

    def test_has_cjk(self):
        self.assertTrue(lg.has_cjk("a 好 b"))
        self.assertFalse(lg.has_cjk("Việt Nam"))


if __name__ == "__main__":
    unittest.main()
