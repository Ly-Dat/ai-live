"""Shared state between product_tour.py and the comment handler.

- Lets comments take priority over the product tour.
- Resolves which product a comment is about.
- Builds a prompt that restricts the LLM to data/products.json.
"""
import json
import re
import time
import unicodedata
from pathlib import Path

PRODUCTS_PATH = Path("data/products.json")
COMMENT_FLAG = Path("data/.last_comment")      # timestamp of the latest viewer comment
CURRENT_FLAG = Path("data/.current_product")   # id of the product the tour is presenting

# Spoken when the answer is not in the catalog (Vietnamese on purpose: this is what the streamer says).
NO_ANSWER = ("Phần này mình chưa có thông tin trong dữ liệu sản phẩm nên chưa trả lời chính xác được. "
             "Bạn hỏi thêm về giá, size, màu, giao hàng hoặc đổi trả nhé.")
GREETING = re.compile(r"^(xin chao|chao|hello|hi|alo|hey)\b")  # matched against accent-folded text

# product field -> label used in the LLM context
LABELS = [("name", "Tên"), ("price", "Giá"), ("original_price", "Giá gốc"),
          ("description", "Mô tả"), ("intro", "Giới thiệu"), ("sizes_colors", "Size/màu"),
          ("how_to_use", "Cách dùng"), ("shipping", "Giao hàng"),
          ("return_policy", "Đổi trả"), ("stock_note", "Tồn kho")]


def _fold(t) -> str:
    """Lowercase, strip Vietnamese accents, collapse punctuation (for tolerant matching)."""
    t = unicodedata.normalize("NFD", str(t or "").lower().replace("đ", "d"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


# ---------- comment priority ----------
def touch_comment() -> None:
    """Call whenever a viewer comment arrives, so the tour pauses."""
    try:
        COMMENT_FLAG.parent.mkdir(parents=True, exist_ok=True)
        COMMENT_FLAG.write_text(str(time.time()))
    except OSError:
        pass


def seconds_since_comment() -> float:
    try:
        return time.time() - float(COMMENT_FLAG.read_text())
    except (OSError, ValueError):
        return 1e9  # no comment seen yet


def wait_for_quiet(quiet: float = 10.0, max_wait: float = 60.0) -> None:
    """Block until no comment has arrived for `quiet` seconds.
    max_wait stops a very busy chat from freezing the tour forever."""
    t0 = time.time()
    while seconds_since_comment() < quiet and time.time() - t0 < max_wait:
        time.sleep(1)


def set_current(pid: str) -> None:
    """Remember which product the tour is presenting (used for comments that name no product)."""
    try:
        CURRENT_FLAG.write_text(pid or "")
    except OSError:
        pass


def _current_id() -> str:
    try:
        return CURRENT_FLAG.read_text().strip()
    except OSError:
        return ""


# ---------- product data ----------
def load_products() -> list:
    """Active products from data/products.json, sorted by cart order. Re-read on every call (live edits)."""
    try:
        data = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    ps = [p for p in data.get("products", []) if p.get("active", True)]
    return sorted(ps, key=lambda p: p.get("order", 0))


def find_product(comment: str, products: list):
    """Match a product by cart number ("số 3 ...") or by name/alias mentioned in the comment."""
    f = _fold(comment)
    m = re.search(r"\b(?:so|sp|san pham|gio hang)\s*(\d{1,3})\b", f)
    if m:
        for p in products:
            if p.get("order") == int(m.group(1)):
                return p
    best, score = None, 0
    for p in products:
        for name in [p.get("name", "")] + list(p.get("aliases", [])):
            n = _fold(name)
            if len(n) >= 3 and n in f and len(n) > score:  # longest match wins
                best, score = p, len(n)
    return best


def resolve(comment: str):
    """Product named in the comment; otherwise the product the tour is presenting right now."""
    products = load_products()
    p = find_product(comment, products)
    if p:
        return p
    cur = _current_id()
    return next((x for x in products if x.get("id") == cur), None)


def facts(p: dict) -> str:
    """Flatten one product into plain text for the LLM context."""
    lines = [f"{label}: {p[k]}" for k, label in LABELS if p.get(k)]
    if p.get("highlights"):
        lines.append("Điểm nổi bật: " + "; ".join(p["highlights"]))
    for qa in p.get("faq", []):
        lines.append(f"Hỏi: {qa.get('q')} -> Đáp: {qa.get('a')}")
    return "\n".join(lines)


def prepare(comment: str):
    """Decide how to answer a comment.

    Returns ("say", text)   -> speak this text directly, no LLM involved
            ("llm", prompt) -> send this prompt to the LLM (grounded in the product data)
    """
    f = _fold(comment)
    if len(f) <= 25 and GREETING.match(f):
        return "say", "Chào bạn, chào mừng bạn đến với phiên live nhé!"
    p = resolve(comment)
    if not p:
        return "say", NO_ANSWER  # no product context -> never let the LLM improvise
    return "llm", (
        "Bạn là người dẫn live bán hàng. CHỈ được dùng THÔNG TIN SẢN PHẨM bên dưới để trả lời khách.\n"
        f'- Nếu thông tin không có trong đó, trả lời đúng câu: "{NO_ANSWER}"\n'
        "- Không bịa giá, size, công dụng, khuyến mãi. Không đưa số điện thoại, link hay liên hệ ngoài TikTok.\n"
        "- Trả lời tiếng Việt, 1-2 câu ngắn.\n\n"
        f"THÔNG TIN SẢN PHẨM:\n{facts(p)}\n\n"
        f"Bình luận của khách: {comment}"
    )