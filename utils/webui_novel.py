"""Novel reader tab: add a story, pick a voice, press Start - the AI host reads it on your live.

Same ideas as the popular novel-reading apps (library, chapters, resume, speed, narrator / dialogue voices, pronunciation
dictionary, sleep timer, text on screen) with one extra rule they do not have: a story must carry a licence you are allowed
to read on a live. See docs/NOVEL.md.
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


def _tour_running() -> bool:
    try:
        from .webui_setup import PM
        return PM.running("tour")
    except Exception:
        return False


def build_novel_tab(config):
    page_title("Novel reader", "The AI host reads a story aloud, chapter after chapter, and pauses to answer viewers. "
                               "Only stories you may read on a live (public domain, your own, CC, or with permission).")
    sel = {"book": ""}
    ctl0 = novel.read_control()
    s0 = ctl0["settings"]
    api_port = config.get("api_port") or 8082

    # ------------------------------------------------------------------ library + add
    with ui.card().classes("lv-card w-full").style("padding:20px"):
        ui.label("Your stories").style("font-weight:700;font-size:16px")

        @ui.refreshable
        def library():
            books = novel.list_books()
            opts = {b["id"]: f'{b["title"]} - {len(b["chapters"])} ch.' for b in books}
            if not opts:
                ui.label("No stories yet. Add one below (paste text, or upload a .txt / .epub).").classes("lv-sub")
                sel["book"] = ""
                return
            if sel["book"] not in opts:
                sel["book"] = ctl0["book"] if ctl0["book"] in opts else next(iter(opts))
            with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
                pick = ui.select(opts, label="Story", value=sel["book"]).classes("w-80")
                lic = ui.select({k: v["label"] for k, v in novel.LICENSES.items()}, label="Licence",
                                value=novel.get_book(sel["book"])["license"]).classes("w-80")
            note = ui.label("").classes("lv-chip")

            def refresh_note():
                m = novel.get_book(sel["book"])
                ok, why = novel.can_read_live(m)
                note.text = f'{len(m["chapters"])} chapters, {m["chars"] // 1000}k characters. ' + ("Can be read on a live." if ok else why)
                note.classes(add="good" if ok else "bad", remove="bad" if ok else "good")
                chapter_sel.set_options({i: f'{i + 1}. {c["title"]}' for i, c in enumerate(m["chapters"])},
                                        value=min(chapter_sel.value or 0, len(m["chapters"]) - 1))

            def on_pick(e):
                sel["book"] = e.value
                lic.value = novel.get_book(e.value)["license"]
                refresh_note()

            def on_lic(e):
                novel.update_license(sel["book"], e.value)
                refresh_note()
            pick.on_value_change(on_pick)
            lic.on_value_change(on_lic)

            def delete():
                if novel.get_book(sel["book"]):
                    send("stop")
                    novel.delete_book(sel["book"])
                    sel["book"] = ""
                    library.refresh()
            ui.button("Delete this story", icon="delete", on_click=delete).props("flat no-caps color=negative")
            library.refresh_note = refresh_note
            try:
                refresh_note()   # first build: the chapter list does not exist yet, the Reader card calls it again below
            except NameError:
                pass

        library()

    with ui.card().classes("lv-card w-full").style("padding:20px;margin-top:16px"):
        ui.label("Add a story").style("font-weight:700;font-size:16px")
        ui.label("Paste the text or upload a file. Chapters are found from headings like \"Chương 1\", \"Chapter 2\", \"Hồi 3\" or \"# Title\"; "
                 "without headings the text is cut into parts.").classes("lv-sub")
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
            library.refresh()
        ui.button("Add to my stories", icon="library_add", on_click=add)
        ui.label("Reading someone else's novel without permission is copyright infringement and can get your live taken down. "
                 "Free sources: Project Gutenberg, Wikisource (Vietnamese classics), your own writing.").classes("lv-sub").style("margin-top:6px")

    # ------------------------------------------------------------------ reader
    with ui.card().classes("lv-card w-full").style("padding:20px;margin-top:16px"):
        ui.label("Reader").style("font-weight:700;font-size:16px")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            chapter_sel = ui.select({0: "-"}, label="Start at chapter", value=0).classes("w-80")
            v_nar = ui.select(VOICES, label="Narrator voice", value=s0["voice_narrator"], with_input=True).classes("w-80")
            v_dia = ui.select({"": "Same as narrator", **{k: v for k, v in VOICES.items() if k}}, label="Dialogue voice",
                              value=s0["voice_dialogue"], with_input=True).classes("w-80")
        ui.label("Two voices make dialogue easy to follow: the narrator reads the story, the second voice reads what characters say "
                 "(inside quotes or after a dash).").classes("lv-sub")
        with ui.row().classes("items-center").style("gap:28px;flex-wrap:wrap"):
            with ui.column().style("gap:0;min-width:220px"):
                ui.label("Speed (%)").classes("lv-sub").style("margin:0")
                rate = ui.slider(min=-40, max=60, value=s0["rate"]).props("label-always").style("margin-top:16px")
            with ui.column().style("gap:0;min-width:220px"):
                ui.label("Pause between lines (seconds)").classes("lv-sub").style("margin:0")
                pause = ui.slider(min=0, max=3, step=0.1, value=s0["pause_s"]).props("label-always").style("margin-top:16px")
            sleep_min = ui.number("Stop after (minutes, 0 = never)", value=s0["sleep_min"], min=0, max=720, format="%.0f").classes("w-56")
        with ui.row().style("gap:18px;flex-wrap:wrap"):
            yield_c = ui.switch("Pause for viewer comments", value=bool(s0["yield_comments"]))
            auto_next = ui.switch("Continue to the next chapter", value=bool(s0["auto_next"]))
            announce = ui.switch("Say the chapter title", value=bool(s0["announce_chapter"]))
            show_text = ui.switch("Show the text on screen (overlay)", value=bool(s0["show_text"]))
            safety = ui.switch("Skip lines the TikTok policy filter flags", value=bool(s0["safety"]))

        def collect():
            return {"voice_narrator": v_nar.value or "", "voice_dialogue": v_dia.value or "", "rate": int(rate.value or 0),
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

        def ensure_reader():
            if not PM_NOVEL.running("novel"):
                PM_NOVEL.start("novel", [sys.executable, "novel_reader.py", "--api", f"http://127.0.0.1:{api_port}/send"])

        def start(resume=False):
            m = novel.get_book(sel["book"])
            ok, why = novel.can_read_live(m)
            if not ok:
                ui.notify(why, type="warning")
                return
            if _tour_running():
                ui.notify("The product tour is running. Stop it first (Setup -> Stop), or both will talk at once.", type="warning")
                return
            ci, ck = int(chapter_sel.value or 0), 0
            if resume:
                p = novel.load_progress().get(m["id"])
                if p:
                    ci, ck = min(p["chapter"], len(m["chapters"]) - 1), p["chunk"]
            ensure_reader()
            send("play", book=m["id"], chapter=ci, chunk=ck)
            ui.notify("Reading. Make sure the app is running (Start Run).", type="positive")

        def pause_resume():
            c = novel.read_control()
            send("play" if c["command"] == "pause" else "pause")

        def jump(delta):
            m = novel.get_book(sel["book"])
            if not m:
                return
            st = novel.read_status()
            ci = min(max(int(st.get("chapter", 0)) + delta, 0), len(m["chapters"]) - 1)
            ensure_reader()
            send("play", book=m["id"], chapter=ci, chunk=0)

        with ui.row().style("gap:10px;margin-top:8px;flex-wrap:wrap"):
            ui.button("Start", icon="play_arrow", on_click=lambda: start(False)).props("color=positive")
            ui.button("Resume where I stopped", icon="history", on_click=lambda: start(True)).props("outline no-caps")
            ui.button("Pause / continue", icon="pause", on_click=pause_resume).props("outline no-caps")
            ui.button(icon="skip_previous", on_click=lambda: jump(-1)).props("flat round").tooltip("Previous chapter")
            ui.button(icon="skip_next", on_click=lambda: jump(1)).props("flat round").tooltip("Next chapter")
            ui.button("Stop", icon="stop", on_click=lambda: send("stop")).props("color=negative")

        status = ui.label("Not reading.").classes("lv-chip").style("margin-top:10px")
        bar = ui.linear_progress(value=0, show_value=False).classes("w-full").style("margin-top:6px")
        now_line = ui.label("").classes("lv-sub").style("font-size:15px;margin-top:6px;min-height:44px")

        def refresh():
            st = novel.read_status()
            fresh = time.time() - float(st.get("updated") or 0) < 10
            state = st.get("state") if fresh else "idle"
            if state in ("playing", "paused"):
                status.text = (f'{"Reading" if state == "playing" else "Paused"}: {st.get("title")} - {st.get("chapter_title")} '
                               f'(line {st.get("chunk", 0) + 1}/{st.get("chunks", 0)})' + (f', {st.get("skipped")} skipped by the filter' if st.get("skipped") else ""))
                bar.value = (st.get("chunk", 0) + 1) / max(1, st.get("chunks", 1))
                now_line.text = st.get("text", "")
            elif state == "blocked":
                status.text = st.get("message", "Blocked")
                now_line.text = ""
            elif state == "done":
                status.text = "Finished. Pick another story or chapter."
                bar.value = 1
                now_line.text = ""
            else:
                status.text = "Not reading." if not PM_NOVEL.running("novel") else "Reader ready."
                bar.value = 0
                now_line.text = ""
        ui.timer(1.0, refresh)
        if sel["book"]:
            library.refresh_note() if hasattr(library, "refresh_note") else None

    # ------------------------------------------------------------------ pronunciation
    with ui.card().classes("lv-card w-full").style("padding:20px;margin-top:16px"):
        ui.label("Pronunciation dictionary").style("font-weight:700;font-size:16px")
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
        ui.button("Save dictionary", icon="save", on_click=save_pron)

    with ui.card().classes("lv-card w-full").style("padding:20px;margin-top:16px"):
        ui.label("Going live with a story").style("font-weight:700;font-size:16px")
        for line in ("1. Start the app (Start Run) and the TikTok bridge (Setup). Do not run the product tour at the same time.",
                     "2. Add the overlay as a browser source (Live tools -> Show these on screen) to show the text being read.",
                     "3. Press Start. Viewer comments always go first; the story continues a few seconds after the answer.",
                     "4. If the story needs a credit (CC BY / permission), it is shown on the overlay and in the story card."):
            ui.label(line).classes("lv-sub").style("margin:2px 0")
