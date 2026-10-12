"""Spec features: comment triage, honest unknowns, cheaper compare, speech gate, honest report."""
import json
from utils import live_analytics, seller_brain, speech_gate
from utils.product_catalog import ProductCatalog
from utils.triage import Triage


def cat(tmp_path, products, lang="vi"):
    import json
    pp = tmp_path / "p.json"
    pp.write_text(json.dumps({"products": products}), encoding="utf-8")
    c = ProductCatalog(str(pp), str(tmp_path / "t.json"))
    c.templates["lang"] = lang
    return c


P1 = {"id": "a", "order": 1, "name": "Áo thun basic", "price": "100.000₫", "aliases": ["áo thun"], "sizes_colors": "Size S, M, L", "highlights": ["cotton"], "faq": [], "shipping": "", "return_policy": ""}
P2 = {"id": "b", "order": 2, "name": "Quần jean", "price": "250.000₫", "aliases": ["quần jean"], "sizes_colors": "", "highlights": [], "faq": []}


def test_classification():
    t = Triage()
    assert t.classify("chốt đơn cho mình 1 cái") == "purchase"
    assert t.classify("áo này giá bao nhiêu") == "question"
    assert t.classify("xin chào shop") == "greeting"
    assert t.classify("cảm ơn nha hay quá") == "feedback"
    assert t.classify("aaaaaaaaaaaaaaaa") == "spam"
    assert t.classify("😀😀😀") == "spam"
    assert t.classify("xem nè http://x.com/abc") == "spam"
    assert t.classify("hôm nay trời đẹp") == "unrelated"
    assert Triage(is_prohibited=lambda s: "bad" in s).classify("bad word") == "prohibited"


def test_priority_order():
    t = Triage()
    d = {c: t.decide(f"u{i}", txt, 100 + i * 30) for i, (c, txt) in enumerate(
        [("buy", "chốt đơn"), ("q", "áo này giá bao nhiêu"), ("g", "xin chào"), ("c", "hôm nay trời đẹp")])}
    assert d["buy"]["priority"] > d["q"]["priority"] > d["g"]["priority"] > d["c"]["priority"]


def test_repeated_question_is_skipped_but_buying_is_not_lost():
    t = Triage()
    assert t.decide("a", "áo này giá bao nhiêu", 100)["action"] == "answer"
    d = t.decide("b", "áo này giá bao nhiêu vậy", 110)
    assert d["action"] == "skip" and d["reason"] == "repeated_question" and d["category"] == "faq_repeat"
    assert t.decide("c", "áo này giá bao nhiêu", 400)["action"] == "answer"   # after the window it may be asked again


def test_greeting_cooldown_and_same_viewer_flood():
    t = Triage()
    assert t.decide("a", "xin chào", 100)["action"] == "answer"
    assert t.decide("a", "hello", 160)["reason"] == "greeted_recently"
    assert t.decide("a", "hello", 161)["action"] == "skip"
    assert t.decide("z", "mua", 200)["action"] == "answer"
    assert t.decide("z", "mua", 205)["reason"] == "same_viewer_too_fast"


def test_busy_chat_never_bursts():
    t = Triage(busy_per_10s=5)
    spoken = 0
    for i in range(60):
        kind = "hôm nay trời đẹp" if i % 2 else "xin chào"
        if t.decide(f"u{i}", kind, 1000 + i * 0.1)["action"] == "answer":
            spoken += 1
    assert spoken <= 2          # one low-value reply per spacing window at most
    assert t.decide("buyer", "chốt đơn nhé", 1007)["action"] == "answer"   # buying still gets through while busy


def test_spam_and_prohibited_skip():
    t = Triage(is_prohibited=lambda s: "scam" in s)
    assert t.decide("a", "zzzzzzzzzzzzzz", 1)["reason"] == "spam"
    assert t.decide("b", "scam link", 2)["reason"] == "prohibited"
    assert t.summary()["skip_spam"] == 1


def test_known_size_answered_from_catalog(tmp_path):
    c = cat(tmp_path, [dict(P1), dict(P2)])
    assert "L" in c.unknown_answer("áo thun có size L không")
    msg = c.unknown_answer("áo thun có size XL không")
    assert "XL" in msg and "chưa xác nhận" in msg


def test_missing_fact_is_not_invented(tmp_path):
    c = cat(tmp_path, [dict(P1), dict(P2)])
    assert "chưa có thông tin" in c.unknown_answer("áo thun ship mấy ngày")
    assert "chưa có thông tin" in c.unknown_answer("áo thun đổi trả thế nào")
    assert c.unknown_answer("chào cả nhà") is None


def test_audit_lists_missing_facts(tmp_path):
    rows = cat(tmp_path, [dict(P1), dict(P2)]).audit()
    by = {r["id"]: r["missing"] for r in rows}
    assert "shipping" in by["a"] and "returns" in by["a"] and "price" not in by["a"]
    assert "sizes / colours" in by["b"]


def test_which_is_cheaper(tmp_path):
    c = cat(tmp_path, [dict(P1), dict(P2)])
    r = seller_brain.answer(c, "áo thun với quần jean cái nào rẻ hơn")
    assert "rẻ hơn" in r and "100.000₫" in r and r.index("Áo") < r.index("250.000")
    assert "rẻ hơn" in seller_brain.answer(c, "cái nào rẻ nhất")


def test_speech_gate():
    assert speech_gate.gate("", None) is None
    assert speech_gate.gate("hi", None) == "hi"
    assert speech_gate.gate("hi bad", lambda t: None) is None
    assert speech_gate.gate("hi bad", lambda t: t.replace("bad", "*")) == "hi *"
    assert speech_gate.gate("hi", lambda t: 1 / 0) == "hi"


def test_report_labels_unavailable_metrics():
    ev = [{"ts": 1, "kind": "comment", "user": "a", "intent": "buy"}, {"ts": 2, "kind": "triage_skip", "reason": "spam"},
          {"ts": 3, "kind": "handoff"}]
    md = live_analytics.report_markdown(live_analytics.summarize(ev))
    assert "Not available" in md and "NOT your audience size" in md
    assert "spam" in md and "kept them for you" in md


def test_preflight_flags_catalog_gaps():
    from utils import preflight
    from utils.product_catalog import audit_products
    gaps = audit_products([dict(P1), dict(P2), {"id": "c", "name": "x", "active": False}])
    assert [g["id"] for g in gaps] == ["a", "b"]
    rows = preflight.run({"tiktok_username": "u", "api_ok": True, "product_count": 2, "catalog_gaps": gaps})
    r = next(x for x in rows if x["id"] == "catalog_gaps")
    assert r["ok"] is None and "2 products" in r["label"]


def test_draft_facts_are_never_spoken(tmp_path):
    from utils.product_catalog import mark_draft, confirm_facts, draft_fields
    p = dict(P1, highlights=["chống nắng tuyệt đối"], shipping="Giao 2 ngày", fact_status={})
    c = cat(tmp_path, [p])
    mark_draft(c.products[0], ["highlights", "shipping"])
    prod = c.products[0]
    assert "chống nắng" not in c.build_pitch(prod) and "Giao 2 ngày" not in c.build_pitch(prod)
    assert "chống nắng" not in c.context_for("áo thun")
    assert c.quick_answer("áo thun ship mấy ngày") is None
    assert "chưa có thông tin" in c.unknown_answer("áo thun ship mấy ngày")     # a draft is treated as missing, never guessed
    assert seller_brain.answer(c, "áo thun có tốt không") is None or "chống nắng" not in seller_brain.answer(c, "áo thun có tốt không")
    assert any("AI draft" in m for r in c.audit() for m in r["missing"])
    assert set(draft_fields(prod)) == {"highlights", "shipping"}
    assert set(confirm_facts(prod)) == {"highlights", "shipping"} and "facts_confirmed_at" in prod
    assert "Giao 2 ngày" in c.quick_answer("áo thun ship mấy ngày") or "Giao 2 ngày" in c.build_pitch(prod, 0)


def test_degraded_mode_template_is_true_and_safe(tmp_path):
    c = cat(tmp_path, [dict(P1), dict(P2)])
    msg = c.safe_fallback("áo thun giá sao")
    assert "Áo thun basic" in msg and "100.000₫" in msg and "giỏ hàng" in msg
    assert c.safe_fallback("hôm nay trời đẹp") is None            # nothing to anchor on: stay quiet rather than invent
    c.templates["lang"] = "en"
    assert "can't answer" in c.safe_fallback("áo thun giá sao")


def test_start_override_is_logged(tmp_path):
    from utils import setup_wizard
    cfg = {"filter": {"tiktok_safety": {"enable": False}}}
    tp = tmp_path / "t.json"
    tp.write_text("{}")
    why = setup_wizard.safety_blockers(cfg, str(tp))
    assert len(why) == 2 and "safety filter" in why[0] and "disclosure" in why[1]
    tp.write_text('{"disclosure": "Mình là AI"}')
    assert setup_wizard.safety_blockers({"filter": {"tiktok_safety": {"enable": True}}}, str(tp)) == []
    log = tmp_path / "o.jsonl"
    setup_wizard.log_override(why, str(log), now=123)
    row = json.loads(log.read_text().strip())
    assert row == {"ts": 123, "overrode": why}
