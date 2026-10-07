import os, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from utils.live_analytics import LiveAnalytics, classify_intent, summarize, report_markdown, load_events  # noqa: E402
from utils.product_catalog import ProductCatalog  # noqa: E402


def test_intents():
    assert classify_intent("Áo này giá bao nhiêu") == "price"
    assert classify_intent("chốt đơn cho mình 1 cái") == "buy"
    assert classify_intent("shop ship về Cần Thơ mấy ngày") == "shipping"
    assert classify_intent("hàng có thật không shop") == "trust"
    assert classify_intent("hello cả nhà") == "chat"


def test_record_summarize_and_privacy(tmp_path):
    a = LiveAnalytics(str(tmp_path))
    a.record("comment", user="Nguyen Van A", text="giá bao nhiêu", intent="price", product_id="P001")
    a.record("comment", user="Nguyen Van A", text="chốt đơn", intent="buy", product_id="P001")
    a.record("comment", user="B", text="hi", intent="chat")
    a.record("blocked", scope="output", categories=["scam_finance"], action="drop")
    a.record("pitch", product_id="P001", source="tour")
    s = a.summary()
    assert s["comments"] == 3 and s["unique_viewers"] == 2
    assert s["buy_intent"] == 1 and s["sales_comments"] == 2
    assert s["blocked_output"] == 1 and s["hot_products"] == ["P001"]
    raw = open(a.path, encoding="utf-8").read()
    assert "Nguyen" not in raw  # viewer names are hashed
    assert summarize(load_events(a.path))["comments"] == 3


def test_disabled_writes_nothing(tmp_path):
    a = LiveAnalytics(str(tmp_path), enable=False)
    a.record("comment", user="x", text="y", intent="chat")
    assert not os.listdir(tmp_path)


def test_report_and_buy_reply(tmp_path):
    a = LiveAnalytics(str(tmp_path))
    a.record("comment", user="u", text="giá", intent="price", product_id="P001")
    md = report_markdown(a.summary(), {"P001": "Áo thun"}, "Shop")
    assert "Áo thun" in md and "Live session report" in md
    c = ProductCatalog(os.path.join(ROOT, "tests", "fixtures", "products.json"), os.path.join(ROOT, "data", "pitch_templates.json"))
    r = c.buy_reply(c.products[0])
    assert c.products[0]["name"] in r and "giỏ hàng" in r


def test_recent_sales_questions_window(tmp_path):
    a = LiveAnalytics(str(tmp_path))
    for _ in range(3):
        a.record("comment", user="u", text="giá", intent="price", product_id="P001")
    a.record("comment", user="u", text="hi", intent="chat", product_id="P001")
    a.record("comment", user="u", text="giá", intent="price", product_id="P002")
    assert a.recent_sales_questions("P001", 300) == 3
    a.events[0]["ts"] -= 1000  # outside the window
    assert a.recent_sales_questions("P001", 300) == 2
