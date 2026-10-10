import pytest

from utils import novel_writer as nw

PREMISES = """PREMISE 1
HOOK: A mage who forgets her brother each time she heals him.
PROTAGONIST: Lan, a healer
GOAL: save Nam
CONFLICT: every spell erases a memory
STAKES: Nam dies or is forgotten
TWIST: Nam remembers a crime Lan forgot
PREMISE 2
HOOK: A lighthouse that calls the dead.
PROTAGONIST: Quan
GOAL: shut it
CONFLICT: the town needs it
STAKES: the harbour
TWIST: Quan lit it first
"""
BIBLE = """TITLE: Ký ức cuối cùng
THEME: love costs memory
WORLD: The empire of Hắc Thành runs on memory-magic.
RULES: every spell erases one memory; the dead cannot be healed
ENDING: Lan chooses to keep Nam's name and lose her power
CHARACTER: Lan | healer | save Nam | forgetting | pride | she caused the fire | short sentences | learns to let go
CHARACTER: Nam | brother | be free | being a burden | hides pain | knows the crime | joking | accepts truth
CHARACTER: Quân | teacher | keep order | chaos | cold | he sold the key | formal | falls
THREAD: clue | the golden key in Quân's pocket | planted in chapter 1 | pays off in chapter 3
THREAD: mystery | who lit the fire | planted in chapter 1 | pays off in chapter 4
"""
OUTLINE = "\n".join([
    "CH 1 | Làng Thủy | Lan heals Nam and loses a memory | she notices the gap | question | plants: 1,2 | pays:",
    "CH 2 | Bến sông | Lan meets Quân | Quân offers help | decision | plants: | pays:",
    "CH 3 | Chìa khóa | the key is found | betrayal | reveal | plants: | pays: 1",
    "CH 4 | Ngọn lửa | the fire truth | Nam speaks | reversal | plants: | pays: 2"])
CH_TEXT = ("Lan nắm tay Nam. “Đừng đi,” cô nói. Nam cười khẽ. “Chị quên rồi à?” Lan nhìn chiếc chìa khóa vàng trong túi thầy Quân. "
           "Ngoài kia mưa rơi. Cô không biết rằng mình đã quên điều gì. Nhưng cô sẽ nhớ lại. " * 12)
MEM = """SUMMARY: Lan heals Nam and forgets something.
FACT: Lan healed Nam and lost a memory
KNOWS: Nam | Lan forgets him
CHANGE: Lan's hand is burned
NEWTHREAD: mystery | what did Lan forget
PAID: 1
"""


def scripted(counter=None):
    def llm(prompt):
        if counter is not None:
            counter.append(prompt)
        if "Pitch" in prompt:
            return PREMISES
        if "story bible" in prompt:
            return BIBLE
        if "chapter outline" in prompt:
            return OUTLINE
        if "Extract the durable story facts" in prompt:
            return MEM
        if "continuity editor" in prompt:
            return 'ISSUE: "chìa khóa vàng" | Quân did not have the key yet | move it to chapter 3'
        if "EDIT TASK" in prompt:
            return "Lan nắm tay Nam thật chặt. Mưa rơi ngoài kia."
        if "reader-engagement" in prompt:
            return "CURIOUS: the lost memory\nDROP: middle\nSCORE: 7 good hook"
        if "consequential directions" in prompt:
            return "A | Trust Quân | he helps | the key is lost\nB | Betray Quân | she steals the key | Nam is hurt"
        return CH_TEXT
    return llm


@pytest.fixture
def proj(tmp_path):
    root = str(tmp_path / "proj")
    p = nw.new_project("Truyện", "a healer", chapters=4, words=200, root=root)
    llm = scripted()
    nw.make_premises(p, llm)
    p["premise"] = nw.premise_text(p["premises"][0])
    nw.make_bible(p, llm)
    nw.make_outline(p, llm)
    return p, root, llm


def test_parsers_and_setup(proj):
    p, root, _ = proj
    assert len(p["premises"]) == 2 and p["premises"][0]["twist"].startswith("Nam")
    assert [c["name"] for c in p["characters"]] == ["Lan", "Nam", "Quân"] and p["title"] == "Truyện"
    assert [(t["planted"], t["due"]) for t in p["threads"]] == [(1, 3), (1, 4)]
    assert [o["n"] for o in p["outline"]] == [1, 2, 3, 4] and p["outline"][2]["pays"] == [1] and p["outline"][0]["plants"] == [1, 2]
    assert p["outline"][2]["hook"] == "reveal"
    nw.save(p, root)
    assert nw.load(p["id"], root)["title"] == "Truyện" and nw.load("../x", root) is None


def test_bad_ai_output_raises(tmp_path):
    p = nw.new_project("x", "y", root=str(tmp_path))
    with pytest.raises(RuntimeError):
        nw.make_premises(p, lambda s: "nothing useful")
    with pytest.raises(RuntimeError):
        nw.make_bible(p, lambda s: "nope")
    with pytest.raises(RuntimeError):
        nw.make_outline(p, lambda s: "nope")


def test_context_is_compact_and_task_specific(proj):
    p, _, llm = proj
    ctx = nw.chapter_context(p, 1)
    assert "Làng Thủy" in ctx and "Plant these threads: #1, #2" in ctx and "Lan (healer)" in ctx
    p["outline"][1]["steer"] = "Lan trusts Quân"
    nw.draft_chapter(p, 1, llm)
    ctx2 = nw.chapter_context(p, 2)
    assert "Lan trusts Quân" in ctx2 and "Lan healed Nam and lost a memory" in ctx2 and "Nam knows: Lan forgets him" in ctx2
    assert "LAST LINES OF THE PREVIOUS CHAPTER" in ctx2


def test_draft_memory_and_threads(proj):
    p, _, llm = proj
    res = nw.draft_chapter(p, 1, llm)
    assert res["chapter"]["summary"].startswith("Lan heals") and p["log"]
    assert [t["paid"] for t in p["threads"][:2]] == [1, 0] or p["threads"][0]["paid"] == 1
    assert any(t["text"] == "what did Lan forget" for t in p["threads"])
    n_threads = len(p["threads"])
    nw.draft_chapter(p, 1, llm)                                     # redraft: memory is replaced, not duplicated
    assert len(p["threads"]) == n_threads and len([f for f in p["memory"]["facts"] if f["ch"] == 1]) == 1
    h = nw.thread_health(p)
    assert h["paid"] and h["open"]


def test_short_draft_is_continued_once(proj):
    p, _, _ = proj
    calls = []
    def llm(prompt):
        calls.append(prompt)
        if "Extract" in prompt:
            return MEM
        return "Short." if len(calls) == 1 else CH_TEXT
    nw.draft_chapter(p, 1, llm)
    assert nw.get_chapter(p, 1)["text"].startswith("Short.") and nw._wc(nw.get_chapter(p, 1)["text"]) > 100


def test_report_flags(proj):
    p, _, llm = proj
    nw.set_chapter_text(p, 3, "Chìa khóa. " * 5)
    r = nw.chapter_report(p, 3)
    kinds = {i["kind"] for i in r["issues"]}
    assert "length" in kinds
    p["outline"][2]["pays"] = [1]
    p["threads"][0]["planted"] = 4
    assert "unprepared-reveal" in {i["kind"] for i in nw.chapter_report(p, 3)["issues"]}
    p["threads"][1]["due"] = 1
    nw.set_chapter_text(p, 2, "Mưa rơi xuống đất. " * 60 + "Hà nói: “Đi thôi.” Hà nói: “Ừ.”")
    k2 = {i["kind"] for i in nw.chapter_report(p, 2)["issues"]}
    assert "overdue-thread" in k2 and "repetition" in k2


def test_audit(proj):
    p, _, llm = proj
    nw.draft_chapter(p, 1, llm)
    a = nw.audit_chapter(p, 1, llm)
    assert a[0]["quote"] == "chìa khóa vàng" and "chapter 3" in a[0]["fix"]
    assert nw.parse_audit("NONE") == []


def test_revise_diff_accept_versions_lock(proj):
    p, _, llm = proj
    nw.set_chapter_text(p, 1, "Đoạn một. Câu hai.\n\nĐoạn hai dài hơn nhiều. Mưa rơi.")
    rev = nw.revise(p, 1, "tension", llm, paragraph=1)
    assert rev["old"].startswith("Đoạn hai") and any(op == "add" for op, _ in rev["ops"]) and any(op == "del" for op, _ in rev["ops"])
    assert nw.get_chapter(p, 1)["text"].startswith("Đoạn một") and not nw.get_chapter(p, 1)["versions"]    # nothing saved yet
    nw.accept_revision(p, 1, rev)
    ch = nw.get_chapter(p, 1)
    assert ch["text"].startswith("Đoạn một. Câu hai.\n\nLan nắm") and len(ch["versions"]) == 1
    nw.restore_version(p, 1, 0)
    assert nw.get_chapter(p, 1)["text"].startswith("Đoạn một. Câu hai.\n\nĐoạn hai dài")
    nw.approve(p, 1)
    with pytest.raises(RuntimeError):
        nw.set_chapter_text(p, 1, "x")
    with pytest.raises(RuntimeError):
        nw.draft_chapter(p, 1, llm)
    nw.approve(p, 1, False)
    nw.set_chapter_text(p, 1, "again")


def test_choices_review_style_resume(proj):
    p, _, llm = proj
    assert nw.resume_card(p)["actions"][0] == "Write chapter 1"
    nw.draft_chapter(p, 1, llm)
    ch = nw.make_choices(p, 1, llm)
    assert [c["key"] for c in ch] == ["A", "B"] and ch[1]["price"] == "Nam is hurt"
    nw.steer(p, 2, ch[1]["what"])
    assert p["outline"][1]["steer"] == "she steals the key"
    assert nw.parse_review(llm("reader-engagement"))["curious"] == ["the lost memory"]
    nw.set_style_sample(p, "Mưa rơi. Tôi đi. “Về đi,” mẹ nói. Tôi không nói gì.")
    assert "sentences average" in p["style"]["profile"] and "Match the voice" in nw.style_rules(p)
    rc = nw.resume_card(p)
    assert rc["last"] == 1 and rc["next"] == 2 and "Review and approve chapter 1" in rc["actions"] and rc["recap"].startswith("Lan heals")


def test_export_and_publish(proj, tmp_path):
    p, _, llm = proj
    nw.draft_chapter(p, 1, llm)
    nw.draft_chapter(p, 2, llm)
    md = nw.to_markdown(p, bible=True)
    assert md.startswith("# Truyện") and "## Chương 1: Làng Thủy" in md and "Story bible" in md
    root = str(tmp_path / "novels")
    meta = nw.publish_to_reader(p, root=root)
    assert len(meta["chapters"]) == 2 and meta["license"] == "own"
    first = p["reader_id"]
    nw.publish_to_reader(p, root=root)                               # republish replaces the book, no duplicates
    from utils import novel
    assert len(novel.list_books(root)) == 1 and p["reader_id"] != first or len(novel.list_books(root)) == 1
    with pytest.raises(RuntimeError):
        nw.publish_to_reader(p, only_approved=True, root=root)
