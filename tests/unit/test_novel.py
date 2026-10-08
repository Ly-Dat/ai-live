import os
import tempfile
import time
import unittest
import zipfile
from utils import novel


class Chapters(unittest.TestCase):
    def test_headings(self):
        t = "Lời nói đầu " * 40 + "\n\nChương 1: Mở đầu\nNội dung một.\n\nChương 2\nNội dung hai.\n\n# Chương III\nBa."
        ch = novel.split_chapters(t)
        self.assertEqual([c["title"] for c in ch], ["Mở đầu", "Chương 1: Mở đầu", "Chương 2", "Chương III"])
        self.assertIn("Nội dung hai", t[ch[2]["start"]:ch[2]["end"]])

    def test_sentence_starting_with_chuong_trinh_is_not_a_heading(self):
        t = "Chương trình học rất vui và dài. " * 5
        self.assertEqual(len(novel.split_chapters(t)), 1)

    def test_fallback_split(self):
        t = ("Câu số một rất dài. " * 20 + "\n") * 40
        ch = novel.split_chapters(t, fallback_chars=1000)
        self.assertGreater(len(ch), 3)
        self.assertEqual(ch[0]["title"], "Phần 1")


class Roles(unittest.TestCase):
    def test_quotes(self):
        p = novel.paragraph_pieces('Cô nhìn anh. “Anh đi đâu?” cô hỏi.')
        self.assertEqual(p, [("narrator", "Cô nhìn anh."), ("dialogue", "Anh đi đâu?"), ("narrator", "cô hỏi.")])

    def test_dash_dialogue(self):
        p = novel.paragraph_pieces("— Anh đi đâu? — cô hỏi, giọng run run.")
        self.assertEqual(p[0], ("dialogue", "Anh đi đâu?"))
        self.assertEqual(p[1][0], "narrator")

    def test_straight_quotes(self):
        p = novel.paragraph_pieces('Anh nói "xin chào" rồi đi.')
        self.assertEqual([r for r, _ in p], ["narrator", "dialogue", "narrator"])


class Chunks(unittest.TestCase):
    def test_merge_and_limit(self):
        body = "Trời mưa. Gió thổi. Cây rung. " * 3 + "\n\n“Em về đi.” Anh nói."
        c = novel.chunks(body, max_chars=60)
        self.assertTrue(all(len(x["text"]) <= 100 for x in c))
        self.assertIn("dialogue", {x["role"] for x in c})

    def test_pronunciation_and_markdown(self):
        c = novel.chunks("**Anh** ở TP.HCM. Rất vui.", pron=novel.DEFAULT_PRON)
        self.assertIn("Thành phố Hồ Chí Minh", c[0]["text"])
        self.assertNotIn("*", c[0]["text"])

    def test_symbols_only_dropped(self):
        self.assertEqual(novel.chunks("***\n---\n...."), [])

    def test_long_sentence_cut(self):
        long = "từ " * 200
        c = novel.chunks(long, max_chars=100)
        self.assertGreater(len(c), 2)
        self.assertTrue(all(len(x["text"]) < 200 for x in c))

    def test_seconds(self):
        self.assertAlmostEqual(novel.spoken_seconds("a" * 26, cps=13), 2.0)
        self.assertLess(novel.spoken_seconds("a" * 26, cps=13, rate=50), 2.0)


class Library(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.text = "Chương 1\n" + "Một câu truyện rất hay. " * 20 + "\n\nChương 2\n" + "Câu chuyện tiếp tục. " * 20

    def test_add_list_delete(self):
        m = novel.add_book("Tắt đèn", "Ngô Tất Tố", "public-domain", "", self.text, self.root)
        self.assertEqual(len(m["chapters"]), 2)
        self.assertEqual([b["id"] for b in novel.list_books(self.root)], [m["id"]])
        self.assertIn("Câu chuyện", novel.chapter_body(m, 1, self.root))
        novel.delete_book(m["id"], self.root)
        self.assertEqual(novel.list_books(self.root), [])

    def test_too_short(self):
        with self.assertRaises(ValueError):
            novel.add_book("x", "", "own", "", "ngắn", self.root)

    def test_get_book_rejects_paths(self):
        self.assertIsNone(novel.get_book("../etc", self.root))

    def test_licence_gate(self):
        ok, _ = novel.can_read_live({"license": "public-domain", "author": ""})
        self.assertTrue(ok)
        self.assertFalse(novel.can_read_live({"license": "copyrighted"})[0])
        self.assertFalse(novel.can_read_live({"license": "unknown"})[0])
        self.assertFalse(novel.can_read_live({"license": "cc-by", "author": ""})[0])
        self.assertTrue(novel.can_read_live({"license": "cc-by", "author": "A"})[0])
        self.assertFalse(novel.can_read_live(None)[0])

    def test_credit_line(self):
        self.assertEqual(novel.credit_line({"license": "public-domain", "title": "T", "author": "A"}), "")
        self.assertIn("by A", novel.credit_line({"license": "cc-by", "title": "T", "author": "A", "source": "x.org"}))


class Files(unittest.TestCase):
    def test_control_defaults_and_roundtrip(self):
        p = os.path.join(tempfile.mkdtemp(), "c.json")
        self.assertEqual(novel.read_control(p)["command"], "stop")
        novel.write_control({"command": "play", "book": "b", "chapter": 2, "chunk": 5, "seq": 3, "settings": {"rate": 10, "bogus": 1}}, p)
        c = novel.read_control(p)
        self.assertEqual((c["command"], c["chapter"], c["chunk"], c["seq"], c["settings"]["rate"]), ("play", 2, 5, 3, 10))
        self.assertNotIn("bogus", c["settings"])

    def test_overlay_novel(self):
        st = {"state": "playing", "updated": 100.0, "title": "T", "text": "x"}
        self.assertEqual(novel.overlay_novel(st, {"show_text": True}, 110)["title"], "T")
        self.assertIsNone(novel.overlay_novel(st, {"show_text": False}, 110))
        self.assertIsNone(novel.overlay_novel(st, {"show_text": True}, 200))      # stale
        self.assertIsNone(novel.overlay_novel({"state": "idle", "updated": 100.0}, {"show_text": True}, 101))

    def test_progress(self):
        p = os.path.join(tempfile.mkdtemp(), "p.json")
        novel.save_progress("b", 3, 9, p)
        self.assertEqual(novel.load_progress(p)["b"]["chapter"], 3)


class Epub(unittest.TestCase):
    def test_minimal_epub(self):
        path = os.path.join(tempfile.mkdtemp(), "b.epub")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/c.opf"/></rootfiles></container>')
            z.writestr("OEBPS/c.opf", '<package><metadata><dc:title>Sách thử</dc:title></metadata><manifest>'
                       '<item id="a" href="a.xhtml"/><item id="b" href="b.xhtml"/></manifest><spine><itemref idref="a"/><itemref idref="b"/></spine></package>')
            z.writestr("OEBPS/a.xhtml", "<html><body><h1>Chương một</h1><p>" + "Nội dung chương một. " * 5 + "</p></body></html>")
            z.writestr("OEBPS/b.xhtml", "<html><body><h1>Chương hai</h1><p>" + "Nội dung chương hai. " * 5 + "</p></body></html>")
        text, title = novel.load_epub(path)
        self.assertEqual(title, "Sách thử")
        ch = novel.split_chapters(text)
        self.assertEqual(len(ch), 2)
        self.assertIn("chương hai", text[ch[1]["start"]:ch[1]["end"]])

    def test_load_txt_encodings(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "t.txt")
        open(p, "wb").write("Xin chào các bạn".encode("utf-8-sig"))
        self.assertEqual(novel.load_file(p)[0], "Xin chào các bạn")


if __name__ == "__main__":
    unittest.main()
