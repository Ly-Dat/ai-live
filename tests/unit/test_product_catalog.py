import json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from utils.product_catalog import ProductCatalog, merge_records  # noqa: E402


def make(tmp_path):
    src = os.path.join(ROOT, "data", "products.json")
    dst = tmp_path / "products.json"
    dst.write_text(open(src, encoding="utf-8").read(), encoding="utf-8")
    return ProductCatalog(str(dst), os.path.join(ROOT, "data", "pitch_templates.json"))


def test_all_products_skips_inactive(tmp_path):
    c = make(tmp_path)
    c.products[1]["active"] = False
    assert len(c.all_products()) == len(c.products) - 1


def test_pitch_mentions_name_and_price(tmp_path):
    c = make(tmp_path)
    p = c.products[0]
    pitch = c.build_pitch(p, 0)
    assert p["name"] in pitch and "129.000" in pitch


def test_quick_answer_price_and_fallthrough(tmp_path):
    c = make(tmp_path)
    assert "129.000" in c.quick_answer("áo thun giá bao nhiêu vậy shop")
    assert c.quick_answer("cái này có đẹp không") is None   # opinion -> LLM
    assert c.quick_answer("giá bao nhiêu") is None          # no product named -> LLM


def test_faq_answer(tmp_path):
    c = make(tmp_path)
    assert "size M" in c.quick_answer("áo thun mặc size nào nếu cao 1m65 nặng 55kg")


def test_upsert_pop_adds_and_dedups(tmp_path):
    c = make(tmp_path)
    n = len(c.products)
    p, new = c.upsert_pop({"title": "Quạt mini", "product_id": 5, "price": "89.000đ"})
    assert new and len(c.products) == n + 1 and p["auto_imported"]
    p2, new2 = c.upsert_pop({"title": "Quạt mini", "product_id": 5})
    assert not new2 and len(c.products) == n + 1
    saved = json.load(open(c.products_path, encoding="utf-8"))
    assert len(saved["products"]) == n + 1


def test_upsert_pop_keeps_handwritten_fields(tmp_path):
    c = make(tmp_path)
    p, new = c.upsert_pop({"title": "Áo thun cotton basic", "product_id": 77, "price": "1đ"})
    assert not new and p["price"] == "129.000đ" and p["highlights"]


def test_merge_records(tmp_path):
    c = make(tmp_path)
    added, updated = merge_records(c.products, [
        {"id": "P001", "name": "Áo thun cotton basic", "price": "99.000đ", "highlights": ["x"]},
        {"id": "N1", "name": "Mũ lưỡi trai", "price": "50.000đ"},
        {"name": ""},
    ])
    assert (added, updated) == (1, 1)
    first = c.products[0]
    assert first["price"] == "99.000đ" and "Mềm" not in first["highlights"] and len(first["highlights"]) == 3
