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


def test_creator_mode_personas_and_checklist(tmp_path):
    import json
    from utils import home_status, personas, setup_wizard
    data = personas.load("data/personas.json")
    creators = personas.for_mode(data, "creator")
    sellers = personas.for_mode(data, "seller")
    assert creators and sellers and not ({p["id"] for p in creators} & {p["id"] for p in sellers})
    assert "product information" not in personas.build_before_prompt(data, creators[0])
    assert "product information" in personas.build_before_prompt(data, sellers[0])
    facts = {"tiktok_username": "a", "product_count": 0, "voice_ok": True, "api_ok": True, "bridge_on": True, "mode": "creator"}
    items = home_status.checklist(facts)
    assert "products" not in [i["id"] for i in items] and home_status.progress(items) == 100
    assert "products" in [i["id"] for i in home_status.checklist({**facts, "mode": "seller"})]
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"products": {"enable": True}, "edge-tts": {}}), encoding="utf-8")
    setup_wizard.apply_setup(str(cfg), str(tmp_path / "none.json"), "data/personas.json",
                             {"tiktok_username": "x", "persona_id": creators[0]["id"], "mode": "creator"})
    assert json.loads(cfg.read_text(encoding="utf-8"))["products"]["enable"] is False


def test_returning_viewers_adds_joins_flag():
    from utils import setup_wizard
    cmd = setup_wizard.bridge_command({"tiktok_username": "a", "returning_viewers": True}, "py")
    assert "--joins" in cmd
