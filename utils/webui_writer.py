"""Novel writer tab: write a whole novel with the AI, chapter by chapter, with a story that remembers itself.

Library -> premise -> story bible -> outline -> chapter workspace (draft, check, revise with a diff, approve, steer the next chapter)
-> control room (threads, memory) -> export / publish into the Novel reader. The engine is utils/novel_writer.py.
"""
import html
import time

from nicegui import run, ui

from . import novel_writer as nw, story, story_llm
from .webui_theme import page_title

_CSS = """
.nw-h{ font-weight:700; font-size:16px; }
.nw-diff{ font-size:15px; line-height:1.55; padding:10px 14px; border-left:3px solid var(--lv-accent,#8b5cf6); }
.nw-diff del{ background:rgba(239,68,68,.22); text-decoration:line-through; }
.nw-diff ins{ background:rgba(34,197,94,.25); text-decoration:none; }
.nw-sev-high{ color:#ef4444; font-weight:600; } .nw-sev-medium{ color:#f59e0b; font-weight:600; } .nw-sev-low{ opacity:.7; }
"""


def _card(first=False):
    return ui.card().classes("lv-card w-full").style("padding:20px" + ("" if first else ";margin-top:26px"))


def build_writer_tab(config):
    ui.add_css(_CSS)
    page_title("Novel writer", "Write a whole novel with the AI: it plans, remembers the story, checks itself, and you stay in control "
                               "(approve, revise with a diff, steer, restore). Finished chapters can be read aloud on your live.")
    st = {"p": None, "rev": None, "choices": [], "audit": [], "review": {}}

    def llm(kind="draft"):
        if str(config.get("chat_type")) != "chatgpt":
            raise RuntimeError(f'Provider "{config.get("chat_type")}" is not supported here. Use the OpenAI-compatible setting (Ollama / LM Studio / OpenAI).')
        return story_llm.make_llm(config, ai_model.value or "", "", nw.TEMP.get(kind, 0.8))

    def project():
        if not st["p"]:
            raise RuntimeError("Create or open a project first.")
        return st["p"]

    async def job(btn, fn, *args, done=None, **kw):
        """Run a slow AI step off the UI thread with a spinner; autosave; show errors as a notification."""
        if btn is not None:
            btn.props("loading")
        try:
            res = await run.io_bound(fn, *args, **kw)
            nw.save(project())
            if done:
                done(res)
            return res
        except Exception as ex:
            ui.notify(str(ex), type="negative", multi_line=True)
        finally:
            if btn is not None:
                btn.props(remove="loading")

    # ------------------------------------------------------------------ AI + library
    with _card(True):
        with ui.row().classes("items-end w-full").style("gap:12px;flex-wrap:wrap"):
            proj_sel = ui.select({}, label="Project").classes("w-80")
            ai_model = ui.select([], label="AI model", with_input=True, new_value_mode="add-unique").classes("w-80")
            ui.button("Check the AI", icon="wifi_tethering", on_click=lambda: check_ai()).props("outline no-caps")
            ai_chip = ui.label("Not checked yet.").classes("lv-chip")
        with ui.expansion("New project", icon="add").classes("w-full").props("dense"):
            with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
                n_title = ui.input("Working title (optional)").classes("w-64")
                n_genre = ui.select(story.GENRES, label="Genre", value="fantasy").classes("w-40")
                n_tone = ui.select(["dramatic", "funny", "sweet", "scary", "mysterious", "inspiring"], label="Tone", value="dramatic").classes("w-40")
                n_lang = ui.select({"vi": "Vietnamese", "en": "English"}, label="Language", value="vi").classes("w-40")
                n_ch = ui.number("Chapters", value=12, min=3, max=60, format="%.0f").classes("w-28")
                n_words = ui.number("Words per chapter", value=700, min=200, max=3000, format="%.0f").classes("w-40")
            n_idea = ui.input("Idea (one or two sentences, optional)", placeholder="A healer whose spells erase her memories of the brother she saves").classes("w-full")
            ui.button("Create the project", icon="add", on_click=lambda: create()).props("color=primary no-caps unelevated")
        ui.label("Stories stay private on your PC (data/novel_projects). Tip: a 7B+ model, or a larger one for the bible and outline.").classes("lv-sub")

    @ui.refreshable
    def resume_card():
        p = st["p"]
        if not p:
            ui.label("Create a project to begin.").classes("lv-sub")
            return
        r = nw.resume_card(p)
        with _card():
            ui.label(f'Where we left off - {r["title"]}').classes("nw-h")
            ui.linear_progress(value=r["approved"] / max(1, r["total"]), show_value=False).classes("w-full")
            ui.label(f'{r["chapters"]} of {r["total"]} chapters written, {r["approved"]} approved, {r["words"]} words. '
                     f'Today {r["today"]} / {r["goal"]} words.').classes("lv-sub")
            if r["recap"]:
                ui.label(f'Last chapter: {r["recap"]}').classes("lv-sub")
            with ui.row().style("gap:8px;flex-wrap:wrap"):
                for a in r["actions"]:
                    ui.label(a).classes("lv-chip")

    resume_card()

    # ------------------------------------------------------------------ 1. premise
    with _card():
        ui.label("1. Premise").classes("nw-h")
        ui.label("Three distinct premises with goal, conflict, stakes and a twist. Pick one and edit it.").classes("lv-sub")
        prem_btn = ui.button("Suggest 3 premises", icon="lightbulb").props("outline no-caps")
        prem_pick = ui.radio({}, value=None).props("dense")
        prem_box = ui.textarea("Premise (editable)").props("autogrow outlined").classes("w-full")

    # ------------------------------------------------------------------ 2. bible
    with _card():
        ui.label("2. Story bible").classes("nw-h")
        ui.label("Characters (name | role | goal | fear | flaw | secret | voice | arc), world, rules, threads (clues and promises that must pay off), and your controls.").classes("lv-sub")
        bible_btn = ui.button("Build the story bible", icon="menu_book").props("outline no-caps")
        b_world = ui.textarea("World").props("autogrow outlined").classes("w-full")
        b_rules = ui.textarea("Rules (limits and costs - the AI may never break them)").props("autogrow outlined").classes("w-full")
        b_ending = ui.input("Ending direction").classes("w-full")
        b_chars = ui.textarea("Characters, one per line").props("autogrow outlined").classes("w-full")
        b_threads = ui.textarea("Threads: kind | what | planted in ch N | pays off in ch M").props("autogrow outlined").classes("w-full")
        with ui.expansion("Controls and style", icon="tune").classes("w-full"):
            with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
                c_pov = ui.select(["first person", "third person limited", "third person omniscient"], label="Point of view", value="third person limited").classes("w-56")
                c_tense = ui.select(["past", "present"], label="Tense", value="past").classes("w-32")
                c_dens = ui.select(["sparse", "balanced", "rich"], label="Prose density", value="balanced").classes("w-40")
                c_words = ui.number("Words per chapter", value=700, min=200, max=3000, format="%.0f").classes("w-40")
                c_goal = ui.number("Daily word goal", value=500, min=0, max=10000, format="%.0f").classes("w-40")
            with ui.row().classes("items-center").style("gap:18px;flex-wrap:wrap"):
                c_twist = ui.switch("AI may add major twists", value=True)
                c_rom = ui.select({0: "None", 1: "Light", 2: "Medium", 3: "Strong"}, label="Romance", value=1).classes("w-32")
                c_vio = ui.select({0: "None", 1: "Light", 2: "Medium", 3: "Strong"}, label="Violence", value=1).classes("w-32")
            c_forbid = ui.input("Never include (topics, tropes, outcomes)").classes("w-full")
            c_notes = ui.textarea("Style notes").props("autogrow outlined").classes("w-full")
            c_sample = ui.textarea("A sample of YOUR writing (the AI will match the voice)").props("autogrow outlined").classes("w-full")
        save_bible_btn = ui.button("Save the bible", icon="save").props("color=primary no-caps unelevated")

    # ------------------------------------------------------------------ 3. outline
    with _card():
        ui.label("3. Outline").classes("nw-h")
        ui.label("CH n | title | what changes | turning point | hook type (question/decision/reveal/reversal/threat/emotion) | plants: 1,2 | pays: 3. "
                 "Edit freely - your edits are canon.").classes("lv-sub")
        out_btn = ui.button("Write the outline", icon="list_alt").props("outline no-caps")
        out_box = ui.textarea("Outline").props("autogrow outlined").classes("w-full")
        save_out_btn = ui.button("Save the outline", icon="save").props("color=primary no-caps unelevated")

    # ------------------------------------------------------------------ 4. chapter workspace
    with _card():
        ui.label("4. Chapters").classes("nw-h")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            ch_sel = ui.select({}, label="Chapter").classes("w-72")
            draft_btn = ui.button("Draft this chapter", icon="edit_note").props("color=primary no-caps unelevated")
            check_btn = ui.button("Check", icon="rule").props("outline no-caps").tooltip("Local checks, no AI")
            audit_btn = ui.button("Continuity audit (AI)", icon="fact_check").props("outline no-caps")
            review_btn = ui.button("Reader review (AI)", icon="reviews").props("outline no-caps")
            appr_btn = ui.button("Approve", icon="lock").props("outline no-caps")
        ch_status = ui.label("").classes("lv-chip")
        ch_box = ui.textarea("Chapter text (you can edit it directly)").props("autogrow outlined").classes("w-full").style("min-height:260px")
        with ui.row().style("gap:10px;flex-wrap:wrap"):
            save_ch_btn = ui.button("Save my edits", icon="save").props("outline no-caps")
            ui.label("").bind_text_from(ch_box, "value", lambda v: f"{nw._wc(v or '')} words").classes("lv-sub").style("align-self:center")

        @ui.refreshable
        def report_view():
            p = st["p"]
            if not p or not ch_sel.value:
                return
            r = nw.chapter_report(p, int(ch_sel.value))
            ui.label(f'Checks: {r["stats"]["words"]} words, {r["stats"]["dialogue_pct"]}% dialogue').classes("lv-sub")
            for i in r["issues"]:
                ui.label(f'[{i["severity"]}] {i["text"]}').classes(f'nw-sev-{i["severity"]}')
            if not r["issues"]:
                ui.label("No problems found by the local checks.").classes("lv-sub")
            for a in st["audit"]:
                ui.label(f'Continuity: "{a["quote"]}" - {a["problem"]}. Fix: {a["fix"]}').classes("nw-sev-high")
            rv = st["review"]
            for key, label in (("curious", "Keeps the reader curious"), ("drop", "Attention may drop"), ("unclear", "Unclear"), ("predictable", "Predictable"),
                               ("unearned", "Unearned"), ("score", "Score")):
                for t in rv.get(key, []):
                    ui.label(f"{label}: {t}").classes("lv-sub")
        report_view()

        ui.separator().style("margin:14px 0")
        ui.label("Revise with a diff").classes("nw-h")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            rev_mode = ui.select({k: k for k in nw.REVISE_MODES}, label="What to improve", value="tension").classes("w-56")
            rev_par = ui.select({-1: "Whole chapter"}, label="Which part", value=-1).classes("w-80")
            rev_btn = ui.button("Suggest an edit", icon="auto_fix_high").props("outline no-caps")

        @ui.refreshable
        def diff_view():
            rev = st["rev"]
            if not rev:
                return
            parts = []
            for op, t in rev["ops"]:
                e = html.escape(t)
                parts.append(f"<del>{e}</del>" if op == "del" else f"<ins>{e}</ins>" if op == "add" else e)
            ui.html("<div class='nw-diff'>" + " ".join(parts) + "</div>").classes("w-full")
            with ui.row().style("gap:10px"):
                ui.button("Accept", icon="check", on_click=lambda: accept(True)).props("color=positive no-caps unelevated")
                ui.button("Reject", icon="close", on_click=lambda: accept(False)).props("outline no-caps")
        diff_view()

        ui.separator().style("margin:14px 0")
        ui.label("Versions and steering").classes("nw-h")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            ver_sel = ui.select({}, label="Earlier versions").classes("w-96")
            ui.button("Restore", icon="history", on_click=lambda: restore()).props("outline no-caps")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            ch_btn = ui.button("Offer 3 directions for the next chapter", icon="alt_route").props("outline no-caps")
        choices_row = ui.row().style("gap:10px;flex-wrap:wrap")
        steer_box = ui.input("Where should the next chapter go? (your own words, or pick above)").classes("w-full")
        steer_btn = ui.button("Set the direction", icon="flag").props("outline no-caps")

    # ------------------------------------------------------------------ 5. control room
    with _card():
        ui.label("5. Control room").classes("nw-h")
        ui.label("Open threads, what the story remembers, and who knows what. Correct it in the bible or by editing the chapter.").classes("lv-sub")

        @ui.refreshable
        def control_room():
            p = st["p"]
            if not p:
                return
            h = nw.thread_health(p)
            ui.label(f'Threads: {len(h["open"])} open, {len(h["paid"])} paid off, {len(h["overdue"])} overdue, {len(h["waiting"])} not planted yet').classes("lv-sub")
            for t in h["overdue"]:
                ui.label(f'Overdue #{t["id"]} {t["text"]} (due ch {t["due"]})').classes("nw-sev-high")
            for t in h["open"]:
                if t not in h["overdue"]:
                    ui.label(f'Open #{t["id"]} {t["kind"]}: {t["text"]} (planted ch {t.get("planted") or "?"}, pays off ch {t.get("due") or "?"})').classes("lv-sub")
            for t in h["paid"]:
                ui.label(f'Paid off in ch {t["paid"]}: #{t["id"]} {t["text"]}').classes("lv-sub").style("opacity:.5")
            with ui.expansion(f'Memory ({len(p["memory"]["facts"])} facts)', icon="psychology").classes("w-full"):
                for m in p["memory"]["facts"]:
                    ui.label(f'ch {m["ch"]}: {m["text"]}').classes("lv-sub").style("margin:0")
                for m in p["memory"]["knowledge"]:
                    ui.label(f'ch {m["ch"]}: {m["who"]} knows {m["text"]}').classes("lv-sub").style("margin:0")
                for m in p["memory"]["changes"]:
                    ui.label(f'ch {m["ch"]}: change - {m["text"]}').classes("lv-sub").style("margin:0")
        control_room()

    # ------------------------------------------------------------------ 6. export
    with _card():
        ui.label("6. Read it, export it").classes("nw-h")
        ui.label("Publish puts the chapters in the Novel reader (licence: your own work), so the AI host can read them on your live with the Companion tab's "
                 "spoiler-safe questions. Export gives you Markdown to keep or post.").classes("lv-sub")
        with ui.row().style("gap:10px;flex-wrap:wrap"):
            pub_btn = ui.button("Publish to the Novel reader", icon="menu_book").props("color=primary no-caps unelevated")
            only_appr = ui.switch("Only approved chapters", value=False)
            ui.button("Download Markdown", icon="download", on_click=lambda: export(False)).props("outline no-caps")
            ui.button("Download with story bible", icon="download", on_click=lambda: export(True)).props("outline no-caps")

    # ------------------------------------------------------------------ logic
    def projects_opts():
        return {x["id"]: f'{x["title"]} - {len(x["chapters"])} ch.' for x in nw.list_projects()}

    def fill():
        """Project -> all the boxes."""
        p = st["p"]
        st.update(rev=None, choices=[], audit=[], review={})
        if not p:
            return
        proj_sel.set_options(projects_opts(), value=p["id"])
        prem_pick.set_options({i: nw.premise_text(x).split("\n")[0] for i, x in enumerate(p["premises"])}, value=None)
        prem_box.value = p["premise"]
        b = p["bible"]
        b_world.value, b_rules.value, b_ending.value = b["world"], b["rules"], b["ending"]
        b_chars.value, b_threads.value = nw.characters_text(p), nw.threads_text(p)
        s, c = p["style"], p["controls"]
        c_pov.value, c_tense.value, c_dens.value = s["pov"], s["tense"], s["density"]
        c_words.value, c_goal.value = p["target_words"], p.get("goal_words", 500)
        c_twist.value, c_rom.value, c_vio.value, c_forbid.value = bool(c["twists"]), c["romance"], c["violence"], c["forbidden"]
        c_notes.value, c_sample.value = s.get("notes", ""), s.get("sample", "")
        out_box.value = nw.outline_text(p)
        n = max(p["target_chapters"], len(p["outline"]))
        ch_sel.set_options({i: f'{i}. {next((o["title"] for o in p["outline"] if o["n"] == i), "")}' for i in range(1, n + 1)}, value=(nw.resume_card(p)["next"] if nw.resume_card(p)["next"] <= n else n))
        show_chapter()
        resume_card.refresh()
        control_room.refresh()

    def collect_bible():
        p = project()
        p["premise"] = prem_box.value or ""
        p["bible"].update(world=b_world.value or "", rules=b_rules.value or "", ending=b_ending.value or "")
        nw.set_characters(p, b_chars.value or "")
        nw.set_threads(p, b_threads.value or "")
        p["style"].update(pov=c_pov.value, tense=c_tense.value, density=c_dens.value, notes=c_notes.value or "")
        if (c_sample.value or "") != p["style"].get("sample", ""):
            nw.set_style_sample(p, c_sample.value or "")
        p["controls"].update(twists=bool(c_twist.value), romance=c_rom.value, violence=c_vio.value, forbidden=c_forbid.value or "")
        p["target_words"], p["goal_words"] = int(c_words.value or 700), int(c_goal.value or 0)

    def create():
        try:
            p = nw.new_project(n_title.value or "", n_idea.value or "", n_genre.value, n_tone.value, n_lang.value, int(n_ch.value or 12), int(n_words.value or 700))
        except Exception as ex:
            ui.notify(str(ex), type="negative")
            return
        st["p"] = p
        proj_sel.set_options(projects_opts(), value=p["id"])
        fill()
        ui.notify("Project created. Start with the premise.", type="positive")

    def on_proj(e):
        if e.value and (not st["p"] or st["p"]["id"] != e.value):
            st["p"] = nw.load(e.value)
            fill()
    proj_sel.on_value_change(on_proj)

    async def check_ai():
        if str(config.get("chat_type")) != "chatgpt":
            ai_chip.text = f'Provider "{config.get("chat_type")}" cannot be used here. Use the OpenAI-compatible setting.'
            ai_chip.classes(replace="lv-chip bad")
            return
        try:
            names = await run.io_bound(story_llm.list_models, config)
        except Exception as ex:
            ai_chip.text = str(ex)
            ai_chip.classes(replace="lv-chip bad")
            return
        cur = story_llm.endpoint(config)["model"]
        ai_model.set_options(names, value=(ai_model.value if ai_model.value in names else story_llm.best_model(names, cur) or None))
        ai_chip.text = f"Connected: {len(names)} model(s). Using {ai_model.value or 'the model from Settings'}."
        ai_chip.classes(replace="lv-chip good")

    async def do_premises():
        p = project()
        collect_bible()
        await job(prem_btn, nw.make_premises, p, llm("premise"), done=lambda r: (prem_pick.set_options({i: nw.premise_text(x).split("\n")[0] for i, x in enumerate(r)}, value=None)))
    prem_btn.on_click(do_premises)
    prem_pick.on_value_change(lambda e: setattr(prem_box, "value", nw.premise_text(project()["premises"][e.value])) if e.value is not None else None)

    async def do_bible():
        p = project()
        collect_bible()
        await job(bible_btn, nw.make_bible, p, llm("bible"), done=lambda r: fill())
    bible_btn.on_click(do_bible)

    def save_bible():
        try:
            collect_bible()
            nw.save(project())
            resume_card.refresh()
            control_room.refresh()
            ui.notify("Saved.", type="positive")
        except Exception as ex:
            ui.notify(str(ex), type="negative")
    save_bible_btn.on_click(save_bible)

    async def do_outline():
        p = project()
        collect_bible()
        await job(out_btn, nw.make_outline, p, llm("outline"), done=lambda r: fill())
    out_btn.on_click(do_outline)

    def save_outline():
        try:
            nw.set_outline(project(), out_box.value or "")
            nw.save(project())
            fill()
            ui.notify("Outline saved.", type="positive")
        except Exception as ex:
            ui.notify(str(ex), type="negative")
    save_out_btn.on_click(save_outline)

    def cur_n():
        return int(ch_sel.value or 1)

    def show_chapter(*_):
        p = st["p"]
        if not p or not ch_sel.value:
            return
        ch = nw.get_chapter(p, cur_n())
        ch_box.value = ch["text"] if ch else ""
        locked = bool(ch and ch["status"] == "approved")
        ch_status.text = "Approved (locked)" if locked else ("Draft" if ch else "Not written yet")
        appr_btn.text = "Unlock" if locked else "Approve"
        paras = ch["text"].split("\n\n") if ch else []
        rev_par.set_options({-1: "Whole chapter", **{i: f'Paragraph {i + 1}: {t[:50]}...' for i, t in enumerate(paras)}}, value=-1)
        ver_sel.set_options({i: f'{time.strftime("%d/%m %H:%M", time.localtime(v["t"]))} - {v["label"]}' for i, v in enumerate(ch["versions"])} if ch else {}, value=None)
        st["rev"], st["audit"], st["review"] = None, [], {}
        diff_view.refresh()
        report_view.refresh()
    ch_sel.on_value_change(show_chapter)

    async def do_draft():
        p = project()
        collect_bible()
        n = cur_n()
        await job(draft_btn, nw.draft_chapter, p, n, llm("draft"), done=lambda r: (show_chapter(), resume_card.refresh(), control_room.refresh()))
    draft_btn.on_click(do_draft)

    def do_check():
        report_view.refresh()
    check_btn.on_click(do_check)

    async def do_audit():
        p = project()
        if not nw.get_chapter(p, cur_n()):
            ui.notify("Write the chapter first.", type="warning")
            return
        def done(r):
            st["audit"] = r
            if not r:
                ui.notify("No continuity problems found.", type="positive")
            report_view.refresh()
        await job(audit_btn, nw.audit_chapter, p, cur_n(), llm("audit"), done=done)
    audit_btn.on_click(do_audit)

    async def do_review():
        p = project()
        if not nw.get_chapter(p, cur_n()):
            ui.notify("Write the chapter first.", type="warning")
            return
        def done(r):
            st["review"] = nw.parse_review(r)
            report_view.refresh()
        await job(review_btn, lambda: llm("review")(nw.review_prompt(p, cur_n())), done=done)
    review_btn.on_click(do_review)

    def do_approve():
        p = project()
        ch = nw.get_chapter(p, cur_n())
        if not ch:
            ui.notify("Write the chapter first.", type="warning")
            return
        nw.approve(p, cur_n(), ch["status"] != "approved")
        nw.save(p)
        show_chapter()
        resume_card.refresh()
    appr_btn.on_click(do_approve)

    def save_edits():
        try:
            p = project()
            ch = nw.get_chapter(p, cur_n())
            if (ch["text"] if ch else "") == (ch_box.value or ""):
                return
            nw.set_chapter_text(p, cur_n(), ch_box.value or "", "my edit")
            nw.save(p)
            show_chapter()
            ui.notify("Saved (the previous text is in the versions).", type="positive")
        except Exception as ex:
            ui.notify(str(ex), type="negative")
    save_ch_btn.on_click(save_edits)

    async def do_revise():
        p = project()
        par = rev_par.value
        await job(rev_btn, nw.revise, p, cur_n(), rev_mode.value, llm("revise"), None if par in (-1, None) else int(par),
                  done=lambda r: (st.update(rev=r), diff_view.refresh()))
    rev_btn.on_click(do_revise)

    def accept(yes):
        p = project()
        try:
            if yes and st["rev"]:
                nw.accept_revision(p, cur_n(), st["rev"])
                nw.save(p)
        except Exception as ex:
            ui.notify(str(ex), type="negative")
        st["rev"] = None
        show_chapter()

    def restore():
        if ver_sel.value is None:
            ui.notify("Pick a version.", type="warning")
            return
        try:
            nw.restore_version(project(), cur_n(), int(ver_sel.value))
            nw.save(project())
            show_chapter()
        except Exception as ex:
            ui.notify(str(ex), type="negative")

    async def do_choices():
        p = project()
        if not nw.get_chapter(p, cur_n()):
            ui.notify("Write the chapter first.", type="warning")
            return
        def done(r):
            choices_row.clear()
            with choices_row:
                for c in r:
                    ui.button(f'{c["key"]}: {c["label"]}', on_click=lambda c=c: steer_box.set_value(f'{c["label"]}: {c["what"]} (price: {c["price"]})')).props("outline no-caps").tooltip(f'{c["what"]} - {c["price"]}')
            if not r:
                ui.notify("The AI did not offer directions in the expected format. Try again.", type="warning")
        await job(ch_btn, nw.make_choices, p, cur_n(), llm("choices"), done=done)
    ch_btn.on_click(do_choices)

    def set_steer():
        nw.steer(project(), cur_n() + 1, steer_box.value or "")
        nw.save(project())
        ui.notify(f"Chapter {cur_n() + 1} will follow this direction.", type="positive")
    steer_btn.on_click(set_steer)

    async def do_publish():
        p = project()
        def done(meta):
            ui.notify(f'Published "{meta["title"]}" ({len(meta["chapters"])} chapters) to the Novel reader.', type="positive")
        await job(pub_btn, nw.publish_to_reader, p, bool(only_appr.value), done=done)
    pub_btn.on_click(do_publish)

    def export(with_bible):
        p = project()
        ui.download(nw.to_markdown(p, with_bible).encode("utf-8"), f'{p["id"]}.md')

    proj_sel.set_options(projects_opts(), value=None)
    first = next(iter(projects_opts()), None)
    if first:
        proj_sel.value = first
    ui.timer(0.8, check_ai, once=True)
