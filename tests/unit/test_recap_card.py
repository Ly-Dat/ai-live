import datetime
import os

from utils import recap_card


S = {"duration_min": 47.4, "comments": 312, "unique_viewers": 88, "buy_intent": 19, "answered": 120,
     "product_interest": {"P1": {"price": 5, "buy": 3}, "P2": {"price": 1}}}


def test_card_stats_real_numbers_only():
    st = recap_card.card_stats(S, {"P1": "Áo thun"}, "Shop A", 3, datetime.date(2026, 10, 8))
    assert st["minutes"] == 47 and st["comments"] == 312 and st["buying"] == 19
    assert st["top"] == {"name": "Áo thun", "questions": 8}
    assert st["date"] == "08 Oct 2026" and st["streak"] == 3
    assert "user" not in str(st).lower()


def test_card_stats_empty():
    st = recap_card.card_stats({})
    assert st["top"] is None and st["comments"] == 0 and st["shop"]


def test_render_png(tmp_path):
    from PIL import Image
    out = recap_card.render_card(recap_card.card_stats(S, {"P1": "Áo thun cotton basic rất dài " * 3}, "Shop Mẫu", 4), str(tmp_path / "c.png"))
    assert os.path.exists(out)
    assert Image.open(out).size == (1080, 1350)
