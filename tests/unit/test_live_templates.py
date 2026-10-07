import os
from utils import live_templates as lt, personas, setup_wizard

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_every_template_is_valid_and_uses_a_real_persona_of_its_mode():
    ts = lt.load(os.path.join(ROOT, "data", "live_templates.json"))
    assert len(ts) >= 8 and len({t["id"] for t in ts}) == len(ts)
    pdata = personas.load(os.path.join(ROOT, "data", "personas.json"))
    for t in ts:
        ids = {p["id"] for p in personas.for_mode(pdata, t["mode"])}
        assert t["persona_id"] in ids, t["id"]
        assert t["tour_min_minutes"] <= t["tour_max_minutes"] and t["name"] and t["description"]
        assert t["mode"] != "creator" or t["auto_tour"] is False        # creators have no cart to tour
        assert not any(w in " ".join(t.get("ideas", [])).lower() for w in ("100%", "guarantee", "limited stock"))


def test_apply_reports_only_real_changes_and_does_not_mutate():
    base = dict(setup_wizard.DEFAULT_SETUP)
    t = {"id": "x", "mode": "seller", "persona_id": base["persona_id"], "auto_tour": base["auto_tour"],
         "tour_min_minutes": 3, "tour_max_minutes": 6, "joins": True}
    new, changes = lt.apply(base, t)
    assert [c[0] for c in changes] == ["Tour min (min)", "Tour max (min)", "Greet new viewers"]
    assert new["tour_min_minutes"] == 3 and new["template_id"] == "x" and base.get("template_id") is None
    assert lt.apply(new, t)[1] == []                                      # idempotent


def test_for_mode_filters():
    ts = lt.load(os.path.join(ROOT, "data", "live_templates.json"))
    assert all(t["mode"] == "creator" for t in lt.for_mode(ts, "creator"))
    assert all(t["mode"] == "seller" for t in lt.for_mode(ts, "seller"))
