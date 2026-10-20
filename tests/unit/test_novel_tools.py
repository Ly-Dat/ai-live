import pytest

from utils import novel_writer as nw
from test_novel_writer import scripted, proj, CH_TEXT   # noqa: F401  (fixture reused)


def test_beat_is_appended_with_context_and_rules(proj):
    p, _, _ = proj
    seen = []
    nw.set_chapter_text(p, 1, "Lan mở cửa. Mưa tạt vào.")
    new = nw.write_beat(p, 1, "Lan finds Nam awake and he asks about the key", lambda pr: (seen.append(pr), "Nam ngồi dậy, mắt sáng.")[1], "tense")
    ch = nw.get_chapter(p, 1)
    assert new == "Nam ngồi dậy, mắt sáng." and ch["text"].endswith(new) and ch["text"].startswith("Lan mở cửa")
    pr = seen[0]
    assert "BEAT: Lan finds Nam awake" in pr and "MOOD: tense" in pr and "Mưa tạt vào" in pr and "no new named characters" in pr
    assert ch["beats"][0]["mood"] == "tense" and ch["versions"]              # old text kept as a version
    with pytest.raises(RuntimeError):
        nw.write_beat(p, 1, "  ", lambda s: "x")
    with pytest.raises(RuntimeError):
        nw.write_beat(p, 1, "a beat", lambda s: "")


def test_beat_refuses_locked_chapter(proj):
    p, _, _ = proj
    nw.set_chapter_text(p, 1, "Text.")
    nw.approve(p, 1, True)
    with pytest.raises(RuntimeError):
        nw.write_beat(p, 1, "something happens", lambda s: "x")
    with pytest.raises(RuntimeError):
        nw.continue_chapter(p, 1, lambda s: "x")


def test_continue_needs_text_and_uses_instruction(proj):
    p, _, _ = proj
    with pytest.raises(RuntimeError):
        nw.continue_chapter(p, 1, lambda s: "x")
    nw.set_chapter_text(p, 1, "Lan chạy ra bến sông.")
    seen = []
    nw.continue_chapter(p, 1, lambda pr: (seen.append(pr), "Quân đứng đợi.")[1], "Quân appears")
    assert "Quân appears" in seen[0] and nw.get_chapter(p, 1)["text"].endswith("Quân đứng đợi.")


def test_describe_parse_and_errors(proj):
    p, _, _ = proj
    out = "**SIGHT:** a | The lamp swung | Rain beaded on the glass\nSOUND: Water ticked in the gutter | -\nMETAPHOR: Fear sat like a coin in her mouth"
    r = nw.describe(p, 1, "Lan waits.", lambda s: out)
    assert r["sight"] == ["The lamp swung", "Rain beaded on the glass"] and r["sound"] == ["Water ticked in the gutter"] and r["touch"] == []
    with pytest.raises(RuntimeError):
        nw.describe(p, 1, "Lan waits.", lambda s: "no format")
    with pytest.raises(RuntimeError):
        nw.describe(p, 1, " ", lambda s: out)
    assert "Work this detail" in nw.weave_instruction("rain on glass")


def test_variants_dedupe_and_weave_via_revise(proj):
    p, _, llm = proj
    nw.draft_chapter(p, 1, llm)
    answers = iter(["Một. Hai.", "Một. Hai.", "Khác hẳn."])
    vs = nw.variants(p, 1, "show", lambda s: next(answers), None, k=3)
    assert [v["new"] for v in vs] == ["Một. Hai.", "Khác hẳn."]
    r = nw.revise(p, 1, nw.weave_instruction("rain on glass"), lambda s: "Mưa gõ lên kính.", 0)
    assert r["new"] == "Mưa gõ lên kính."


def test_brainstorm_uses_canon_and_parses(proj):
    p, _, _ = proj
    seen = []
    ideas = nw.brainstorm(p, "twists", lambda s: (seen.append(s), "1. Quân is Lan's father\n2) The key opens nothing\n- Nam never forgot\n")[1], "about the key", 8)
    assert ideas == ["Quân is Lan's father", "The key opens nothing", "Nam never forgot"]
    assert "Hắc Thành" in seen[0] and "Focus: about the key" in seen[0] and "Lan" in seen[0]
    with pytest.raises(RuntimeError):
        nw.brainstorm(p, "names", lambda s: "")


def test_authors_note_comes_last_in_draft_prompt(proj):
    p, _, _ = proj
    nw.steer(p, 2, "Quân must lie to Lan")
    pr = nw.draft_prompt(p, 2)
    assert "AUTHOR'S NOTE" in pr and pr.index("AUTHOR'S NOTE") > pr.index("TASK:") and pr.rstrip().endswith("Output only the chapter text.")
    assert "AUTHOR'S NOTE" not in nw.draft_prompt(p, 1)


def test_new_revise_modes_exist():
    for m in ("show", "expand", "tone"):
        assert m in nw.REVISE_MODES


def test_style_extras_and_profile(proj):
    p, _, _ = proj
    text = ("Mưa rơi. Tôi đi. Tôi không nói gì cả trong lúc con đường dài ra mãi mãi trước mặt tôi như một giấc mơ cũ. "
            "Tôi dừng lại... Mưa rơi — rất nhẹ. Tôi nhớ mẹ và những buổi chiều ngồi bên hiên nhà nhìn mưa rơi xuống mái ngói rêu phong. " * 3)
    ex = nw.style_extras(text)
    assert "rhythm varied" in ex and 'opens sentences with "tôi"' in ex and "dashes" in ex
    assert nw.style_extras("Too short.") == ""
    nw.set_style_sample(p, text)
    assert "sentences average" in p["style"]["profile"] and "rhythm" in p["style"]["profile"]
