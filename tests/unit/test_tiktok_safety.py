import os, sys
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from utils.tiktok_safety import TikTokSafety, fold  # noqa: E402


@pytest.fixture(scope="module")
def safety():
    return TikTokSafety(os.path.join(ROOT, "data", "tiktok_policy_terms.json"))


@pytest.mark.parametrize("text", [
    "shop ơi áo này có size L không", "kính đeo mắt đẹp quá", "chúc bạn ngủ ngon", "mặc đầm này xinh",
    "mua củ cải ở đâu", "đi du lịch mang bình này tiện không", "bom hàng", "có freeship không",
])
def test_benign_comments_pass(safety, text):
    assert safety.check(text, "input") == []


@pytest.mark.parametrize("text", [
    "cho mình xin zalo", "Z a l o nha", "z.a.l.o 0987 654 321", "inbox mình nhé", "gọi 0987654321",
    "vào www.abc.com", "chuyển khoản trước nhé", "đm shop", "đ.ụ má",
])
def test_bad_comments_are_blocked(safety, text):
    assert safety.sanitize(text, "input") is None


def test_claims_only_blocked_on_output(safety):
    text = "sản phẩm này cam kết 100% hiệu quả"
    assert safety.check(text, "input") == []
    assert safety.sanitize(text, "output") is None


def test_mask_action_keeps_rest_of_sentence(safety):
    out = safety.sanitize("hàng giả đấy", "output")
    assert out is not None and "đấy" in out and "giả" not in out


def test_fold_handles_d_stroke_and_marks():
    assert fold("Đẹp quá Nhỉ") == "dep qua nhi"
