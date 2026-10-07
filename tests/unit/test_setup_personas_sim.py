import json, os, shutil, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from utils import personas, setup_wizard, simulator, product_catalog  # noqa: E402
from utils.tiktok_safety import TikTokSafety  # noqa: E402

PERSONAS = os.path.join(ROOT, "data", "personas.json")


def test_clean_username_and_validate():
    assert setup_wizard.clean_username("@shop.abc") == "shop.abc"
    assert setup_wizard.clean_username("https://www.tiktok.com/@shop.abc/live") == "shop.abc"
    assert setup_wizard.clean_username("  plain ") == "plain"
    assert setup_wizard.validate({"tiktok_username": ""})
    assert not setup_wizard.validate({"tiktok_username": "@x"})


def test_personas_apply_keeps_compliance():
    data = personas.load(PERSONAS)
    cfg = {"before_prompt": "old", "edge-tts": {"voice": "x", "rate": "+0%"}, "live2d": {"name": "Hiyori"}}
    for p in data["personas"]:
        personas.apply_to_config(cfg, data, p["id"])
        assert "Never give phone numbers" in cfg["before_prompt"] and p["style"] in cfg["before_prompt"]
        assert cfg["edge-tts"]["voice"] == p["voice"]
    try:
        personas.apply_to_config(cfg, data, "nope")
        assert False
    except KeyError:
        pass


def test_apply_setup_roundtrip(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(open(os.path.join(ROOT, "config.json"), encoding="utf-8").read(), encoding="utf-8")
    prods = tmp_path / "products.json"
    shutil.copy(os.path.join(ROOT, "tests", "fixtures", "products.json"), prods)
    changes = setup_wizard.apply_setup(str(cfg), str(prods), PERSONAS,
                                       {"tiktok_username": "@myshop", "persona_id": "calm_expert", "shop_name": "My Shop"})
    out = json.load(open(cfg, encoding="utf-8"))
    assert out["room_display_id"] == "myshop" and out["edge-tts"]["voice"] == "vi-VN-NamMinhNeural"
    assert json.load(open(prods, encoding="utf-8"))["shop_name"] == "My Shop"
    assert any("room_display_id" in c for c in changes)


def test_own_voice_is_applied_only_when_set(tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text(open(os.path.join(ROOT, "config.json"), encoding="utf-8").read(), encoding="utf-8")
    prods = tmp_path / "products.json"
    shutil.copy(os.path.join(ROOT, "tests", "fixtures", "products.json"), prods)
    base = {"tiktok_username": "shop", "persona_id": "calm_expert"}
    setup_wizard.apply_setup(str(cfg), str(prods), PERSONAS, base)
    assert json.load(open(cfg, encoding="utf-8"))["audio_synthesis_type"] != "vieneu"
    setup_wizard.apply_setup(str(cfg), str(prods), PERSONAS, dict(base, own_voice="My voice"))
    out = json.load(open(cfg, encoding="utf-8"))
    assert out["vieneu"]["voice"] == "My voice" and out["audio_synthesis_type"] == "vieneu"


def test_commands():
    s = {"tiktok_username": "@shop", "gifts": True, "joins": False, "tour_min_minutes": 3, "tour_max_minutes": 6, "tour_quiet": 2}
    assert setup_wizard.bridge_command(s, "py") == ["py", "tiktok_bridge.py", "shop", "--gifts"]
    assert setup_wizard.tour_command(s, "py") == ["py", "product_tour.py", "--min-minutes", "3", "--max-minutes", "6", "--quiet", "2"]


def test_demo_scenario_expectations():
    steps = json.load(open(os.path.join(ROOT, "data", "sim_scenario.json"), encoding="utf-8"))["steps"]
    safety = TikTokSafety(os.path.join(ROOT, "data", "tiktok_policy_terms.json"))
    cat = product_catalog.ProductCatalog(os.path.join(ROOT, "tests", "fixtures", "products.json"), os.path.join(ROOT, "data", "pitch_templates.json"))
    checked = 0
    for s in steps:
        if s["type"] == "comment" and s.get("expect"):
            assert simulator.evaluate_comment(s["data"]["content"], safety, cat)["verdict"] == s["expect"], s
            checked += 1
    assert checked >= 6
