from utils import pitch_draft as pd

LONG = ("ViViApparel mang đến những mẫu cardigan nữ tay dài với thiết kế rộng rãi, thoải mái và mang phong cách cổ điển nhưng vẫn thời trang. "
        "Chất liệu mềm mại, dễ mặc giúp sản phẩm phù hợp cho nhiều hoàn cảnh, từ đi làm, đi chơi đến sử dụng hằng ngày. "
        "Thiết kế đa năng có thể phối cùng áo thun, váy hoặc quần jeans, tạo nên vẻ ngoài thanh lịch và trẻ trung. "
        "Đây là lựa chọn lý tưởng cho những ngày se lạnh.")


def test_spoken_seconds():
    assert pd.spoken_seconds("a" * 130) == 10 and pd.spoken_seconds("") == 0


def test_shorten_is_shorter_and_uses_only_seller_words():
    p = {"intro": LONG, "description": LONG, "highlights": []}
    out = pd.shorten(p)
    assert len(out["intro"]) <= 110 and len(out["description"]) <= 170
    assert len(out["intro"]) + len(out["description"]) < len(LONG) * 0.6
    for h in out["highlights"]:
        assert len(h) <= 70 and h.lower().strip(" .") in LONG.lower() or h.lower() in LONG.lower()
    assert 1 <= len(out["highlights"]) <= 3


def test_existing_highlights_are_kept_untouched():
    out = pd.shorten({"intro": "", "description": LONG, "highlights": ["Giặt máy được"]})
    assert out["highlights"] == ["Giặt máy được"]


def test_short_text_unchanged():
    out = pd.shorten({"intro": "Áo đẹp.", "description": "Áo cotton mềm.", "highlights": []})
    assert out["intro"] == "Áo đẹp." and out["description"] == "Áo cotton mềm."
