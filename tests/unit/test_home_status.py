from utils import home_status as h


def test_all_missing():
    items = h.checklist({})
    assert h.progress(items) == 20  # voice defaults to ready
    assert h.next_step(items)["id"] == "shop"


def test_ready_flow():
    facts = {"tiktok_username": "@shop", "product_count": 3, "voice_ok": True, "api_ok": True, "bridge_on": True}
    items = h.checklist(facts)
    assert h.progress(items) == 100 and h.next_step(items) is None


def test_next_step_order():
    facts = {"tiktok_username": "x", "product_count": 0, "voice_ok": False}
    assert h.next_step(h.checklist(facts))["id"] == "products"


def test_greeting_and_tip():
    assert h.greeting(8, "Mai") == "Good morning, Mai"
    assert h.greeting(20) == "Good evening"
    assert h.tip(0) != "" and h.tip(len(h.TIPS)) == h.tip(0)
