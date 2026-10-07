from utils import teach


def test_is_unsure_matches_the_prompt_rule():
    assert teach.is_unsure("Mình không chắc về thông tin này, bạn xem thêm ở trang sản phẩm nhé.")
    assert teach.is_unsure("I'm not sure about that.")
    assert not teach.is_unsure("Áo này giá 149.000đ nha bạn.")


def test_taught_answer_roundtrip_and_matching(tmp_path):
    b = teach.TaughtBook(str(tmp_path / "t.json"))
    b.add("shop có ship đi Đà Nẵng không", "Shop ship toàn quốc, Đà Nẵng khoảng 3 ngày nha.")
    assert "Đà Nẵng" in b.answer("Shop ship ra Đà Nẵng được ko ạ")
    assert b.answer("áo này màu gì") is None
    assert teach.TaughtBook(str(tmp_path / "t.json")).entries()      # persisted
    b.add("ship Đà Nẵng", "Cập nhật.")                               # same question replaces, not duplicates
    assert len(b.entries()) == 1


def test_product_scope(tmp_path):
    b = teach.TaughtBook(str(tmp_path / "t.json"))
    b.add("giặt máy được không", "Giặt máy chế độ nhẹ.", product_id="P1")
    assert b.answer("giặt máy được ko", "P1")
    assert b.answer("giặt máy được ko", "P2") is None


def test_pending_groups_dedupes_and_hides_taught_or_ignored(tmp_path):
    b = teach.TaughtBook(str(tmp_path / "t.json"))
    ev = [{"kind": "unsure", "ts": 1, "text": "Ship đi Đà Nẵng bao lâu"},
          {"kind": "unsure", "ts": 2, "text": "ship đi đà nẵng bao lâu vậy"},
          {"kind": "unsure", "ts": 3, "text": "Có bảo hành không"},
          {"kind": "comment", "ts": 4, "text": "hello"}]
    p = teach.pending(ev, b)
    assert len(p) == 2 and p[0]["count"] == 2
    b.add("ship Đà Nẵng bao lâu", "3 ngày.")
    assert [g["q"] for g in teach.pending(ev, b)] == ["Có bảo hành không"]
    b.ignore("Có bảo hành không")
    assert teach.pending(ev, b) == []


def test_external_edit_is_picked_up(tmp_path):
    import json, os, time
    p = str(tmp_path / "t.json")
    live = teach.TaughtBook(p)                       # the live app holds one instance
    assert live.answer("giao hàng bao lâu") is None
    teach.TaughtBook(p).add("giao hàng bao lâu", "2-3 ngày.")   # the web UI process writes
    os.utime(p, (time.time() + 5, time.time() + 5))
    assert live.answer("giao hàng bao lâu") == "2-3 ngày."


def test_differently_worded_same_question_is_grouped():
    b = teach.TaughtBook("/nonexistent/none.json")
    ev = [{"kind": "unsure", "ts": 1, "text": "Shop có ship đi Đà Nẵng không ạ"},
          {"kind": "unsure", "ts": 2, "text": "ship đà nẵng bao lâu vậy shop"},
          {"kind": "unsure", "ts": 3, "text": "Áo này giặt máy được không"}]
    p = teach.pending(ev, b)
    assert [g["count"] for g in p] == [2, 1]
