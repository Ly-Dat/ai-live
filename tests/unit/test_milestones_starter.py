from utils import milestones, starter


def test_lifetime_totals():
    t = milestones.lifetime([{"duration_min": 30, "comments": 10, "answered": 8, "buy_intent": 2},
                             {"duration_min": 90, "comments": 5, "answered": 4}])
    assert t["lives"] == 2 and t["hours"] == 2.0 and t["answered"] == 12 and t["comments"] == 15


def test_next_milestone_honest():
    t = milestones.lifetime([{"answered": 8}])
    m = milestones.next_milestone(t)
    assert m["have"] <= m["goal"] and m["left"] == m["goal"] - m["have"]
    assert milestones.next_milestone({"lives": 999, "answered": 99999}) is None


def test_starter_catalog_valid():
    c = starter.starter_catalog()
    assert len(c["products"]) == 3 and all(p["active"] and p["name"] for p in c["products"])
    assert len({p["id"] for p in c["products"]}) == 3


def test_recap_unmatched_tip():
    from utils import recap
    r = recap.recap({"comments": 9, "sales_unmatched": 4, "product_interest": {}})
    assert any("not about a specific product" in t for t in r["tips"])
