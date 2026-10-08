"""Novel reader tab: add a story, pick a voice, press Start - the AI host reads it on your live.

Layout: a "Now reading" card on top (pick the story, big Start / Pause / Stop, the line being read), and under it five sub-tabs:
Stories (licence + add), Voices (narrator, dialogue, characters, pronunciation), Options, Find & bookmarks, Help.
Same ideas as the popular novel-reading apps (library, chapters, resume, speed, narrator / dialogue voices, sleep timer, text on
screen) with one extra rule they do not have: a story must carry a licence you are allowed to read on a live. See docs/NOVEL.md.
"""
import os
import sys
import tempfile
import time

from nicegui import ui

from . import novel, setup_wizard, voice_catalog
from .webui_theme import page_title

ROOT = setup_wizard.ROOT
PM_NOVEL = setup_wizard.ProcessManager()  # module level: survives page reloads inside the web UI process
VOICES = {"": "Default voice (set in the Voice tab)"}
VOICES.update(voice_catalog.options("vi"))
VOICES.update({k: v for k, v in voice_catalog.options("en").items() if k not in VOICES})

_CSS = """
.nv-sub .q-tab-panel{ padding:18px 0 0 !important; max-width:none !important; }
.nv-sub .q-tabs{ border-bottom:1px solid rgba(255,255,255,.08); }
body.body--light .nv-sub .q-tabs{ border-bottom:1px solid rgba(0,0,0,.08); }
.nv-now{ font-size:22px; line-height:1.4; font-weight:600; margin:2px 0; }
.nv-dim{ font-size:15px; line-height:1.4; opacity:.5; margin:2px 0; }
.nv-box{ border-left:3px solid var(--lv-accent,#8b5cf6); padding:6px 0 6px 14px; margin-top:12px; min-height:96px; }
.nv-h{ font-weight:700; font-size:16px; }
.nv-group{ font-size:12px; letter-spacing:.08em; text-transform:uppercase; opacity:.6; margin:14px 0 4px; }
@media (max-width:700px){ .nv-now{ font-size:18px; } }
"""


def _tour_running() -> bool:
    try:
        from .webui_setup import PM
        return PM.running("tour")
    except Exception:
        return False


def _other_reader_running() -> str:
    if _tour_running():
        return "The product tour"
    try:
        from .webui_story import PM_STORY
        if PM_STORY.running("story"):
            return "The Story studio reader"
    except Exception:
        pass
    return ""


def _card(first=False):
    return ui.card().classes("lv-card w-full").style("padding:20px" + ("" if first else ";margin-top:30px"))


def build_novel_tab(config):
    ui.add_css(_CSS)
    page_title("Novel reader", "The AI host reads a story aloud, chapter after chapter, and pauses to answer viewers. "
                               "Only stories you may read on a live (public domain, your own, CC, or with permission).")
    sel = {"book": ""}
    ctl0 = novel.read_control()
    s0 = ctl0["settings"]
    api_port = config.get("api_port") or 8082
    chars = dict(s0.get("characters") or {})

    def first_book():
        ids = [b["id"] for b in novel.list_books()]
        return ctl0["book"] if ctl0["book"] in ids else (ids[0] if ids else "")
    sel["book"] = first_book()

    # =================================================================== NOW READING
    with _card(True):
        with ui.row().classes("items-end w-full").style("gap:12px;flex-wrap:wrap"):
            book_pick = ui.select({}, label="Story").classes("w-80")
            chapter_sel = ui.select({}, label="Start at chapter").classes("w-80")
            chip = ui.label("").classes("lv-chip")
        empty = ui.row().classes("items-center").style("gap:12px;margin-top:6px")
        with empty:
            ui.label("No story yet.").classes("lv-sub").style("margin:0")
            ui.button("Add your first story", icon="add", on_click=lambda: tabs.set_value(t_stories)).props("no-caps color=primary")

        with ui.row().style("gap:10px;margin-top:14px;flex-wrap:wrap;align-items:center"):
            ui.button("Start", icon="play_arrow", on_click=lambda: start(False)).props("color=positive no-caps unelevated")
            ui.button("Resume", icon="history", on_click=lambda: start(True)).props("outline no-caps").tooltip("Continue where you stopped")
            ui.button("Pause", icon="pause", on_click=lambda: pause_resume()).props("outline no-caps")
            ui.button(icon="skip_previous", on_click=lambda: jump(-1)).props("flat round").tooltip("Previous chapter")
            ui.button(icon="skip_next", on_click=lambda: jump(1)).props("flat round").tooltip("Next chapter")
            ui.button("Stop", icon="stop", on_click=lambda: send("stop")).props("color=negative no-caps unelevated")
        status = ui.label("Not reading.").classes("lv-chip").style("margin-top:12px")
        bar = ui.linear_progress(value=0, show_value=False).classes("w-full").style("margin-top:8px")
        with ui.column().classes("nv-box w-full").style("gap:0"):
            prev_l = ui.label("").classes("nv-dim")
            now_l = ui.label("The line being read appears here.").classes("nv-now")
            next_l = ui.label("").classes("nv-dim")

    # =================================================================== sub tabs
    with ui.tabs().props("dense align=left no-caps inline-label").classes("w-full").style("margin-top:18px") as tabs:
        t_stories = ui.tab("Stories", icon="library_books")
        t_voices = ui.tab("Voices", icon="record_voice_over")
        t_options = ui.tab("Options", icon="tune")
        t_find = ui.tab("Find & bookmarks", icon="bookmarks")
        t_help = ui.tab("Help", icon="help_outline")
    with ui.tab_panels(tabs, value=t_stories).classes("w-full nv-sub"):
        # ----------------------------------------------------------------- stories
        with ui.tab_panel(t_stories):
            @ui.refreshable
            def book_info():
                m = novel.get_book(sel["book"])
                if not m:
                    ui.label("Add a story below to get started.").classes("lv-sub")
                    return
                with _card(True):
                    ui.label(m["title"]).classes("nv-h")
                    ui.label(f'{(m.get("author") or "Unknown author")} - {len(m["chapters"])} chapters - about '
                             f'{novel.fmt_minutes(novel.book_minutes(m))} to listen').classes("lv-sub").style("margin-bottom:8px")
                    lic = ui.select({k: v["label"] for k, v in novel.LICENSES.items()}, label="Licence - may you read it on a live?",
                                    value=m["license"]).classes("w-96")
                    ok, why = novel.can_read_live(m)
                    ui.label("Can be read on a live." if ok else why).classes("lv-chip " + ("good" if ok else "bad"))

                    def on_lic(e):
                        novel.update_license(sel["book"], e.value)
                        update_hero()
                        book_info.refresh()
                    lic.on_value_change(on_lic)

                    def delete():
                        send("stop")
                        novel.delete_book(sel["book"])
                        sel["book"] = first_book()
                        update_hero()
                        book_info.refresh()
                        bookmarks.refresh()
                    ui.button("Delete this story", icon="delete", on_click=delete).props("flat no-caps color=negative").style("margin-top:8px")
            book_info()

            with ui.expansion("Add a story", icon="add_circle_outline", value=not sel["book"]).classes("w-full").style("margin-top:14px"):
                ui.label("Paste the text or upload a file. Chapters are found from headings like \"Chương 1\", \"Chapter 2\", \"Hồi 3\" or "
                         "\"# Title\"; without headings the text is cut into parts.").classes("lv-sub")
                with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
                    t_title = ui.input("Title").classes("w-64")
                    t_author = ui.input("Author").classes("w-52")
                    t_lic = ui.select({k: v["label"] for k, v in novel.LICENSES.items()}, label="Licence - are you allowed to read it?",
                                      value="unknown").classes("w-80")
                    t_src = ui.input("Source link (optional)").classes("w-64")
                t_text = ui.textarea("Story text").classes("w-full").props("rows=6")

                async def on_upload(e):
                    name = e.name or "story.txt"
                    ext = os.path.splitext(name)[1].lower()
                    if ext not in (".txt", ".md", ".epub"):
                        ui.notify("Use a .txt, .md or .epub file.", type="warning")
                        return
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tf:
                        tf.write(e.content.read())
                        tmp = tf.name
                    try:
                        text, title = novel.load_file(tmp)
                    except Exception as ex:
                        ui.notify(f"Could not read that file: {ex}", type="negative")
                        return
                    finally:
                        try:
                            os.remove(tmp)
                        except OSError:
                            pass
                    t_text.value = text
                    if not t_title.value:
                        t_title.value = title
                    ui.notify(f"Loaded {len(text) // 1000}k characters. Check the licence, then press Add.", type="info")
                ui.upload(label="Upload .txt / .epub", on_upload=on_upload, auto_upload=True).props("accept=.txt,.md,.epub flat dense").classes("w-full")

                def add():
                    try:
                        m = novel.add_book(t_title.value, t_author.value, t_lic.value, t_src.value, t_text.value or "")
                    except ValueError as ex:
                        ui.notify(str(ex), type="warning")
                        return
                    sel["book"] = m["id"]
                    t_text.value = ""
                    ui.notify(f'Added "{m["title"]}" ({len(m["chapters"])} chapters).', type="positive")
                    update_hero()
                    book_info.refresh()
                    bookmarks.refresh()
                ui.button("Add to my stories", icon="add_box", on_click=add).props("color=primary no-caps")
                ui.label("Reading someone else's novel without permission is copyright infringement and can get your live taken down. "
                         "Free sources: Project Gutenberg, Wikisource (Vietnamese classics), your own writing.").classes("lv-sub").style("margin-top:10px")

        # ----------------------------------------------------------------- voices
        with ui.tab_panel(t_voices):
            with _card(True):
                ui.label("Narrator and dialogue").classes("nv-h")
                ui.label("Two voices make dialogue easy to follow: the narrator reads the story, the second voice reads what characters say "
                         "(inside quotes or after a dash).").classes("lv-sub")
                with ui.row().style("gap:12px;flex-wrap:wrap"):
                    v_nar = ui.select(VOICES, label="Narrator voice", value=s0["voice_narrator"], with_input=True).classes("w-80")
                    v_dia = ui.select({"": "Same as narrator", **{k: v for k, v in VOICES.items() if k}}, label="Dialogue voice",
                                      value=s0["voice_dialogue"], with_input=True).classes("w-80")
                with ui.row().classes("items-center").style("gap:28px;flex-wrap:wrap;margin-top:6px"):
                    with ui.column().style("gap:0;min-width:220px"):
                        ui.label("Speed (%)").classes("lv-sub").style("margin:0")
                        rate = ui.slider(min=-40, max=60, value=s0["rate"]).props("label-always").style("margin-top:30px")
                    with ui.column().style("gap:0;min-width:220px"):
                        ui.label("Pause between lines (seconds)").classes("lv-sub").style("margin:0")
                        pause = ui.slider(min=0, max=3, step=0.1, value=s0["pause_s"]).props("label-always").style("margin-top:30px")

            with _card():
                ui.label("Characters - a voice for each").classes("nv-h")
                ui.label("When a line of dialogue is tagged with a character (\"Lan nói\", \"Nam đáp\", \"said Mark\") that character's voice reads it. "
                         "Lines with no known speaker use the dialogue voice.").classes("lv-sub")
                char_voices = {"": "Dialogue voice", **{k: v for k, v in VOICES.items() if k}}

                @ui.refreshable
                def char_rows():
                    if not chars:
                        ui.label("No characters yet. Press \"Find characters\" or add a name.").classes("lv-sub")
                    for name in list(chars):
                        with ui.row().classes("items-center").style("gap:10px"):
                            ui.label(name).style("min-width:140px;font-weight:600")
                            pick_v = ui.select(char_voices, value=chars[name], with_input=True).classes("w-72")
                            pick_v.on_value_change(lambda e, n=name: (chars.__setitem__(n, e.value or ""), apply_settings()))
                            ui.button(icon="close", on_click=lambda n=name: (chars.pop(n, None), apply_settings(), char_rows.refresh())).props("flat round dense")
                char_rows()

                def find_chars():
                    m = novel.get_book(sel["book"])
                    if not m:
                        ui.notify("Pick a story first.", type="warning")
                        return
                    found = novel.detect_characters(novel.book_text(m["id"]))
                    for n in found:
                        chars.setdefault(n, "")
                    apply_settings()
                    char_rows.refresh()
                    ui.notify(f"Found {len(found)} character(s)." if found else "No speaker tags found (like \"Lan nói\"). Add names by hand.",
                              type="positive" if found else "info")

                def spread_voices():
                    pool = list(voice_catalog.options("vi")) or [k for k in VOICES if k]
                    for i, n in enumerate(chars):
                        chars[n] = pool[i % len(pool)]
                    apply_settings()
                    char_rows.refresh()
                with ui.row().classes("items-end").style("gap:10px;flex-wrap:wrap"):
                    new_name = ui.input("Character name").classes("w-52")

                    def add_char():
                        n = (new_name.value or "").strip()
                        if n:
                            chars.setdefault(n, "")
                            new_name.value = ""
                            apply_settings()
                            char_rows.refresh()
                    ui.button("Add", icon="person_add", on_click=add_char).props("outline no-caps")
                    ui.button("Find characters in this story", icon="manage_search", on_click=find_chars).props("no-caps")
                    ui.button("Give each a different voice", icon="shuffle", on_click=spread_voices).props("outline no-caps")

            with _card():
                ui.label("Pronunciation dictionary").classes("nv-h")
                ui.label("One per line: written = how to say it. For abbreviations, foreign names and anything the voice gets wrong.").classes("lv-sub")
                pron_in = ui.textarea(value="\n".join(f"{k} = {v}" for k, v in novel.load_pron().items())).classes("w-full").props("rows=5")

                def save_pron():
                    d = {}
                    for line in (pron_in.value or "").splitlines():
                        if "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() and v.strip():
                                d[k.strip()] = v.strip()
                    novel.save_pron(d)
                    ui.notify("Saved. It applies from the next chapter.", type="positive")
                ui.button("Save dictionary", icon="save", on_click=save_pron).props("no-caps")

        # ----------------------------------------------------------------- options
        with ui.tab_panel(t_options):
            with _card(True):
                ui.label("While reading").classes("nv-group").style("margin-top:0")
                yield_c = ui.switch("Pause for viewer comments", value=bool(s0["yield_comments"]))
                ui.label("Viewers always come first: the story waits, the host answers, then the story continues.").classes("lv-sub").style("margin:-6px 0 4px 48px")
                auto_next = ui.switch("Continue to the next chapter", value=bool(s0["auto_next"]))
                announce = ui.switch("Say the chapter title", value=bool(s0["announce_chapter"]))
                ui.label("On screen and safety").classes("nv-group")
                show_text = ui.switch("Show the text on screen (overlay)", value=bool(s0["show_text"]))
                safety = ui.switch("Skip lines the TikTok policy filter flags", value=bool(s0["safety"]))
                ui.label("Timer").classes("nv-group")
                sleep_min = ui.number("Stop after (minutes, 0 = never)", value=s0["sleep_min"], min=0, max=720, format="%.0f").classes("w-56")

        # ----------------------------------------------------------------- find
        with ui.tab_panel(t_find):
            with _card(True):
                ui.label("Search the story").classes("nv-h")
                ui.label("Find a line and start reading from it.").classes("lv-sub")
                with ui.row().classes("items-end").style("gap:10px;flex-wrap:wrap"):
                    q_in = ui.input("Search text").classes("w-72").on("keydown.enter", lambda: do_search())
                    ui.button("Search", icon="search", on_click=lambda: do_search()).props("no-caps")
                results = ui.column().classes("w-full").style("gap:2px;margin-top:6px")

                def do_search():
                    results.clear()
                    m = novel.get_book(sel["book"])
                    hits = novel.search(m, q_in.value or "", 15, list(chars)) if m else []
                    with results:
                        if not hits:
                            ui.label("Nothing found (type at least 2 letters).").classes("lv-sub")
                        for h in hits:
                            with ui.row().classes("items-center w-full").style("gap:8px;flex-wrap:nowrap"):
                                ui.button(icon="play_arrow", on_click=lambda h=h: start(False, (h["chapter"], h["chunk"]))).props("flat round dense color=positive")
                                ui.label(f'Ch. {h["chapter"] + 1}: {h["text"][:140]}').classes("lv-sub").style("margin:0")
            with _card():
                ui.label("Bookmarks").classes("nv-h")
                ui.label("Save the place you are at and jump back later.").classes("lv-sub")
                with ui.row().classes("items-end").style("gap:10px;flex-wrap:wrap"):
                    bm_note = ui.input("Note (optional)").classes("w-72")

                    def add_bm():
                        m = novel.get_book(sel["book"])
                        if not m:
                            return
                        st = novel.read_status()
                        live = st.get("book") == m["id"] and st.get("state") in ("playing", "paused")
                        novel.add_bookmark(m["id"], st.get("chapter", 0) if live else int(chapter_sel.value or 0), st.get("chunk", 0) if live else 0, bm_note.value or "")
                        bm_note.value = ""
                        bookmarks.refresh()
                    ui.button("Bookmark where I am", icon="bookmark_add", on_click=add_bm).props("outline no-caps")

                @ui.refreshable
                def bookmarks():
                    m = novel.get_book(sel["book"])
                    items = novel.list_bookmarks(m["id"]) if m else []
                    if not items:
                        ui.label("No bookmarks for this story.").classes("lv-sub").style("margin-top:8px")
                    for i, b in enumerate(items):
                        with ui.row().classes("items-center w-full").style("gap:8px;flex-wrap:nowrap"):
                            ui.button(icon="play_arrow", on_click=lambda b=b: start(False, (b["chapter"], b["chunk"]))).props("flat round dense color=positive")
                            ui.label(f'Chapter {b["chapter"] + 1}, line {b["chunk"] + 1}' + (f' - {b["note"]}' if b["note"] else "")).classes("lv-sub").style("margin:0")
                            ui.button(icon="delete", on_click=lambda i=i: (novel.delete_bookmark(m["id"], i), bookmarks.refresh())).props("flat round dense color=negative")
                bookmarks()

        # ----------------------------------------------------------------- help
        with ui.tab_panel(t_help):
            with _card(True):
                ui.label("Going live with a story").classes("nv-h")
                for line in ("1. Start the app (Start Run) and the TikTok bridge (Setup). Do not run the product tour at the same time.",
                             "2. Add the overlay as a browser source (Live tools -> Show these on screen) to show the text being read.",
                             "3. Pick a story above and press Start. Viewer comments always go first; the story continues a few seconds after the answer.",
                             "4. If the story needs a credit (CC BY / permission), it is shown on the overlay and in the story card.",
                             "Tip: press Resume to continue where you stopped last time. Want a video of a chapter to post? Use the Story studio tab."):
                    ui.label(line).classes("lv-sub").style("margin:2px 0")

    # =================================================================== logic
    def collect():
        return {"characters": dict(chars), "voice_narrator": v_nar.value or "", "voice_dialogue": v_dia.value or "", "rate": int(rate.value or 0),
                "pause_s": float(pause.value or 0), "yield_comments": yield_c.value, "auto_next": auto_next.value,
                "announce_chapter": announce.value, "show_text": show_text.value, "sleep_min": int(sleep_min.value or 0),
                "safety": safety.value}

    def send(command, **kw):
        c = novel.read_control()
        c["settings"] = collect()
        c["command"] = command
        c["book"] = kw.get("book", c["book"] or sel["book"])
        if "chapter" in kw:
            c.update(chapter=kw["chapter"], chunk=kw.get("chunk", 0), seq=c["seq"] + 1)
        novel.write_control(c)

    def apply_settings(*_):
        c = novel.read_control()
        c["settings"] = collect()
        novel.write_control(c)
    for el in (v_nar, v_dia, rate, pause, sleep_min, yield_c, auto_next, announce, show_text, safety):
        el.on_value_change(apply_settings)

    def update_hero():
        """Fill the story / chapter pickers and the licence chip from the library."""
        books = novel.list_books()
        opts = {b["id"]: f'{b["title"]} - {len(b["chapters"])} ch.' for b in books}
        if sel["book"] not in opts:
            sel["book"] = next(iter(opts), "")
        book_pick.set_options(opts, value=sel["book"] or None)
        empty.set_visibility(not opts)
        m = novel.get_book(sel["book"])
        if m:
            chapter_sel.set_options({i: f'{i + 1}. {c["title"]}' for i, c in enumerate(m["chapters"])},
                                    value=min(chapter_sel.value or 0, len(m["chapters"]) - 1))
            ok, why = novel.can_read_live(m)
            chip.text = "Ready to read live" if ok else why
            chip.classes(add="good" if ok else "bad", remove="bad" if ok else "good")
        else:
            chapter_sel.set_options({}, value=None)
            chip.text = ""

    def on_book(e):
        if e.value and e.value != sel["book"]:
            sel["book"] = e.value
            update_hero()
            book_info.refresh()
            bookmarks.refresh()
    book_pick.on_value_change(on_book)
    update_hero()

    def ensure_reader():
        if not PM_NOVEL.running("novel"):
            PM_NOVEL.start("novel", [sys.executable, "novel_reader.py", "--api", f"http://127.0.0.1:{api_port}/send"])

    def start(resume=False, at=None):
        m = novel.get_book(sel["book"])
        ok, why = novel.can_read_live(m)
        if not ok:
            ui.notify(why, type="warning")
            return
        other = _other_reader_running()
        if other:
            ui.notify(f"{other} is running. Stop it first, or both will talk at once.", type="warning")
            return
        ci, ck = int(chapter_sel.value or 0), 0
        if resume:
            p = novel.load_progress().get(m["id"])
            if p:
                ci, ck = min(p["chapter"], len(m["chapters"]) - 1), p["chunk"]
        if at:
            ci, ck = int(at[0]), int(at[1])
        ensure_reader()
        send("play", book=m["id"], chapter=ci, chunk=ck)
        ui.notify("Reading. Make sure the app is running (Start Run).", type="positive")

    def pause_resume():
        send("play" if novel.read_control()["command"] == "pause" else "pause")

    def jump(delta):
        m = novel.get_book(sel["book"])
        if not m:
            return
        st = novel.read_status()
        ci = min(max(int(st.get("chapter", 0)) + delta, 0), len(m["chapters"]) - 1)
        ensure_reader()
        send("play", book=m["id"], chapter=ci, chunk=0)

    def refresh():
        st = novel.read_status()
        fresh = time.time() - float(st.get("updated") or 0) < 10
        state = st.get("state") if fresh else "idle"
        if state in ("playing", "paused"):
            status.text = (f'{"Reading" if state == "playing" else "Paused"}: {st.get("title")} - {st.get("chapter_title")} '
                           f'(line {st.get("chunk", 0) + 1}/{st.get("chunks", 0)})' + (f', {st.get("skipped")} skipped by the filter' if st.get("skipped") else ""))
            bar.value = (st.get("chunk", 0) + 1) / max(1, st.get("chunks", 1))
            m = novel.get_book(st.get("book", ""))
            if m and state == "playing" and st.get("chapter", 0) < len(m["chapters"]):
                left = novel.chapter_minutes(m, st["chapter"], rate=int(rate.value or 0)) * (1 - bar.value)
                status.text += f" - about {novel.fmt_minutes(left)} left in this chapter"
            prev_l.text, now_l.text, next_l.text = st.get("prev", ""), st.get("text", ""), st.get("next", "")
        elif state == "blocked":
            status.text = st.get("message", "Blocked")
            prev_l.text, now_l.text, next_l.text = "", "", ""
        elif state == "done":
            status.text = "Finished. Pick another story or chapter."
            bar.value = 1
            prev_l.text, now_l.text, next_l.text = "", "", ""
        else:
            status.text = "Not reading." if not PM_NOVEL.running("novel") else "Reader ready. Press Start."
            bar.value = 0
            prev_l.text, now_l.text, next_l.text = "", "The line being read appears here.", ""
    ui.timer(1.0, refresh)
