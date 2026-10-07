import json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from utils import flash_sale, catalog_enrich  # noqa: E402
from utils.tiktok_safety import TikTokSafety  # noqa: E402

TPL = json.load(open(os.path.join(ROOT, "data", "pitch_templates.json"), encoding="utf-8"))
SAFETY = TikTokSafety(os.path.join(ROOT, "data", "tiktok_policy_terms.json"))
P = {"id": "P001", "name": "Áo thun cotton basic", "price": "129.000đ"}


def test_flash_schedule(tmp_path):
    path = str(tmp_path / "f.json")
    st = flash_sale.start_sale(path, "P001", 10, stock_left=5, every_min=2, now=1000)
    t, st = flash_sale.next_announcement(st, P, TPL, now=1000)
    assert "129.000" in t and "10" in t and "5" in t
    t, st = flash_sale.next_announcement(st, P, TPL, now=1060)
    assert t is None                                   # too soon
    t, st = flash_sale.next_announcement(st, P, TPL, now=1000 + 130)
    assert t and "phút" in t                           # periodic reminder
    t, st = flash_sale.next_announcement(st, P, TPL, now=1000 + 560)
    assert t                                           # final-minute notice
    t2, st = flash_sale.next_announcement(st, P, TPL, now=1000 + 570)
    assert t2 is None
    t, st = flash_sale.next_announcement(st, P, TPL, now=1000 + 601)
    assert t and st["active"] is False
    assert flash_sale.next_announcement(st, P, TPL, now=5000)[0] is None


def test_flash_texts_pass_safety():
    st = {"active": True, "ends_at": 600, "sale_price": "99.000đ", "stock_left": 3, "every_sec": 120,
          "last_announce_ts": 0, "final_done": False}
    for now in (0, 130, 545, 601):
        t, st = flash_sale.next_announcement(st, P, TPL, now=now)
        if t:
            assert not SAFETY.check(t, "output"), t


def test_enrich_parse_and_clean():
    reply = 'Sure!\n```json\n{"aliases": ["áo thun", "ao thun"], "description": "Áo thun mềm, dễ phối đồ.", ' \
            '"highlights": ["Chất liệu cotton", "hiệu quả 100%"], "suggested_questions": ["Có size XL không?"], "x": 1}\n```'
    draft = catalog_enrich.enrich("Áo thun cotton", "129k", lambda p: reply, SAFETY)
    assert draft["aliases"] == ["áo thun", "ao thun"]
    assert draft["highlights"] == ["Chất liệu cotton"]      # unsupported claim removed
    assert draft["suggested_questions"] == ["Có size XL không?"]
    assert "x" not in draft


def test_enrich_bad_reply_and_apply():
    try:
        catalog_enrich.enrich("x", "", lambda p: "no json here", SAFETY)
        assert False
    except ValueError:
        pass
    p = {"aliases": ["áo"], "description": "hand written", "highlights": []}
    catalog_enrich.apply_draft(p, {"aliases": ["Áo", "áo phông"], "description": "new", "highlights": ["a"]})
    assert p["aliases"] == ["áo", "áo phông"] and p["description"] == "hand written" and p["highlights"] == ["a"]
