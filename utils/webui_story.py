"""Story studio tab: write a plot, make a picture story (manhua / webtoon style), let the AI host narrate it on the live, or turn
it into a story-telling video to post and attract followers.

Same licence gate as the Novel reader: your own pictures / text, public domain, CC, or written permission. There is no
"fetch from a manhua site" button on purpose (those pictures are copyrighted). See docs/STORY.md.
"""
import json
import os
import sys
import time

from nicegui import app, run, ui

from . import music, novel, setup_wizard, story, story_video, voice_catalog
from .webui_novel import VOICES, _tour_running
from .webui_theme import page_title

PM_STORY = setup_wizard.ProcessManager()
OUT_DIR = os.path.join("out", "stories")
_ROUTES = [False]


def register_routes():
    if _ROUTES[0]:
        return
    _ROUTES[0] = True
    from fastapi.responses import FileResponse, Response

    @app.get("/story-img/{sid}/{i}")
    def _story_img(sid: str, i: int):
        meta = story.get_story(sid)
        if not meta or not 0 <= i < len(meta["panels"]):
            return Response(status_code=404)
        return FileResponse(story.image_path(meta, i), headers={"Cache-Control": "no-cache"})

    @app.get("/story-out/{name}")
    def _story_out(name: str):
        path = os.path.join(OUT_DIR, os.path.basename(name))
        if not os.path.isfile(path):
            return Response(status_code=404)
        return FileResponse(path)


def _copy(text: str):
    ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(text)})")
    ui.notify("Copied.", type="positive")


def _h(text, sub=None, first=False):
    ui.label(text).style("font-weight:700;font-size:16px")
    if sub:
        ui.label(sub).classes("lv-sub")


def _card(first=False):
    return ui.card().classes("lv-card w-full").style("padding:20px" + ("" if first else ";margin-top:30px"))


def build_story_tab(config):
    register_routes()
    page_title("Story studio", "Write a story, put pictures to it, and let the AI host tell it - live or as a video you post to get "
                               "followers. Only your own pictures and text, public domain, CC, or with permission.")
    api_port = config.get("api_port") or 8082
    ref = {}
    sel = {"story": ""}
    ctl0 = story.read_control()
    s0 = ctl0["settings"]

    # ------------------------------------------------------------------ 1. plot
    with _card(True):
        _h("1. Write the plot (free)",
           "Pick a genre and an idea. You get a ready prompt: paste it into any free chat AI, paste its answer back, and the panels are "
           "filled for you. Every popular story channel uses this loop: hook, 10-15 panels, a cliffhanger, \"part 2\".")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            genre = ui.select(story.GENRES, label="Genre", value="fantasy").classes("w-44")
            tone = ui.select(["dramatic", "funny", "sweet", "scary", "mysterious", "inspiring"], label="Tone", value="dramatic").classes("w-40")
            lang = ui.select({"vi": "Vietnamese", "en": "English"}, label="Story language", value="vi").classes("w-44")
            n_panels = ui.number("Panels", value=12, min=4, max=40, format="%.0f").classes("w-28")
            hook = ui.switch("Start with a hook", value=True)
        premise = ui.input("Idea (one sentence, optional)", placeholder="A shy girl finds a door in her school that opens at midnight").classes("w-full")
        prompt_box = ui.textarea("Prompt to copy").classes("w-full").props("rows=5 readonly")

        def make_prompt():
            prompt_box.value = story.plot_prompt(genre.value, premise.value or "", int(n_panels.value or 12), tone.value, lang.value, hook.value)
        with ui.row().style("gap:10px"):
            ui.button("Make the prompt", icon="auto_fix_high", on_click=make_prompt).props("no-caps")
            ui.button("Copy", icon="content_copy", on_click=lambda: _copy(prompt_box.value or "")).props("flat no-caps")
        answer = ui.textarea("Paste the AI's answer here").classes("w-full").props("rows=5")
        pics_box = ui.textarea("Pictures to draw / generate (one per panel)").classes("w-full").props("rows=4 readonly")

        def use_answer():
            plot = story.parse_plot(answer.value or "")
            if not plot:
                ui.notify("Could not find PANEL / PICTURE / NARRATION blocks. Ask the AI to use the exact format.", type="warning")
                return
            ref["script"].value = story.plot_to_script(plot)
            pics_box.value = story.plot_to_picture_list(plot)
            ui.notify(f"{len(plot)} panels ready. Make or find one picture per panel (step 2).", type="positive")
        ui.button("Turn it into panels", icon="view_agenda", on_click=use_answer).props("no-caps")

    # ------------------------------------------------------------------ 2. add pictures
    pending = []
    with _card():
        _h("2. Add the pictures",
           "Upload the panel pictures (PNG / JPG / WEBP, or one .zip). They are used in name order: 01.png, 02.png ... "
           "Narration: one paragraph per panel (blank line between), or \"Panel 3: ...\".")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            t_title = ui.input("Title").classes("w-64")
            t_author = ui.input("Author / artist").classes("w-52")
            t_lic = ui.select(story.LICENSE_LABELS, label="Licence - may you use these pictures live?", value="own").classes("w-96")
            t_src = ui.input("Source link (optional)").classes("w-64")
        ui.label("Panels copied from a manhua / webtoon site are copyrighted. Choose \"Copyrighted\" and the app will refuse to show or "
                 "export them. Draw them, make them with a free AI image tool, or use public-domain / CC art.").classes("lv-sub")
        count = ui.label("No pictures chosen yet.").classes("lv-chip")

        async def on_upload(e):
            data = e.content.read()
            name = e.name or "panel.png"
            try:
                if name.lower().endswith(".zip"):
                    pending.extend(story.zip_images(data))
                elif name.lower().endswith(story.IMG_EXT):
                    pending.append((name, data))
                else:
                    ui.notify(f"{name}: use PNG, JPG, WEBP or a .zip of pictures.", type="warning")
            except Exception as ex:
                ui.notify(f"{name}: {ex}", type="negative")
            count.text = f"{len(pending)} picture(s) chosen."
        up = ui.upload(label="Panel pictures (several at once, or a .zip)", on_upload=on_upload, multiple=True,
                       auto_upload=True).props("accept=.png,.jpg,.jpeg,.webp,.zip flat dense").classes("w-full")
        script = ui.textarea("Narration (one paragraph per panel)").classes("w-full").props("rows=6")
        ref["script"] = script

        def add():
            try:
                m = story.add_story(t_title.value, t_author.value, t_lic.value, t_src.value, list(pending), script.value or "")
            except ValueError as ex:
                ui.notify(str(ex), type="warning")
                return
            pending.clear()
            up.reset()
            count.text = "No pictures chosen yet."
            script.value = ""
            sel["story"] = m["id"]
            ui.notify(f'Added "{m["title"]}" ({len(m["panels"])} panels).', type="positive")
            library.refresh()
        ui.button("Add to my stories", icon="add_photo_alternate", on_click=add).props("color=primary no-caps")

    # ------------------------------------------------------------------ 3. library + edit
    boxes = []
    with _card():
        _h("3. Your stories - check the narration")

        @ui.refreshable
        def library():
            boxes.clear()
            items = story.list_stories()
            opts = {m["id"]: f'{m["title"]} - {len(m["panels"])} panels' for m in items}
            if not opts:
                ui.label("No stories yet. Add one above.").classes("lv-sub")
                sel["story"] = ""
                return
            if sel["story"] not in opts:
                sel["story"] = ctl0["story"] if ctl0["story"] in opts else next(iter(opts))
            meta = story.get_story(sel["story"])
            with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
                pick = ui.select(opts, label="Story", value=sel["story"]).classes("w-80")
                lic = ui.select(story.LICENSE_LABELS, label="Licence", value=meta["license"]).classes("w-96")
            ok, why = story.can_use(meta)
            ui.label("Can be shown on a live and exported as a video." if ok else why).classes("lv-chip good" if ok else "lv-chip bad")

            def on_pick(e):
                sel["story"] = e.value
                library.refresh()

            def on_lic(e):
                story.update_license(sel["story"], e.value)
                library.refresh()
            pick.on_value_change(on_pick)
            lic.on_value_change(on_lic)
            v = int(time.time())
            for i, p in enumerate(meta["panels"]):
                with ui.row().classes("items-start w-full").style("gap:12px;margin-top:8px;flex-wrap:nowrap"):
                    ui.image(f'/story-img/{meta["id"]}/{i}?v={v}').style("width:84px;height:112px;object-fit:cover;border-radius:8px;flex:none")
                    ta = ui.textarea(f"Panel {i + 1}", value=p.get("text", "")).classes("grow").props("rows=2 autogrow")
                    boxes.append(ta)
                    with ui.column().style("gap:0;flex:none"):
                        ui.button(icon="arrow_upward", on_click=lambda i=i: change("move", i, -1)).props("flat round dense")
                        ui.button(icon="arrow_downward", on_click=lambda i=i: change("move", i, 1)).props("flat round dense")
                        ui.button(icon="delete", on_click=lambda i=i: change("del", i)).props("flat round dense color=negative")

            def save():
                story.set_texts(meta["id"], [b.value or "" for b in boxes])
                ui.notify("Saved.", type="positive")

            def change(kind, i, d=0):
                story.set_texts(meta["id"], [b.value or "" for b in boxes])
                story.move_panel(meta["id"], i, d) if kind == "move" else story.delete_panel(meta["id"], i)
                library.refresh()

            def delete():
                send("stop")
                story.delete_story(meta["id"])
                sel["story"] = ""
                library.refresh()
            with ui.row().style("gap:10px;margin-top:10px"):
                ui.button("Save narration", icon="save", on_click=save).props("color=primary no-caps")
                ui.button("Delete this story", icon="delete", on_click=delete).props("flat no-caps color=negative")
        library()

    # ------------------------------------------------------------------ 4. live
    with _card():
        _h("4. Read it on my live",
           "Each picture appears on the overlay while the AI host narrates it. Viewer comments always go first; the story continues "
           "a few seconds after the answer. Add the overlay as a browser source (Live tools -> Show these on screen).")
        with ui.row().classes("items-end").style("gap:16px;flex-wrap:wrap"):
            v_voice = ui.select(VOICES, label="Narrator voice", value=s0["voice"], with_input=True).classes("w-80")
            with ui.column().style("gap:0;min-width:200px"):
                ui.label("Speed (%)").classes("lv-sub").style("margin:0")
                rate = ui.slider(min=-40, max=60, value=s0["rate"]).props("label-always").style("margin-top:30px")
            with ui.column().style("gap:0;min-width:200px"):
                ui.label("Show each picture at least (seconds)").classes("lv-sub").style("margin:0")
                min_s = ui.slider(min=2, max=20, step=0.5, value=s0["min_panel_s"]).props("label-always").style("margin-top:30px")
            sleep_min = ui.number("Stop after (minutes, 0 = never)", value=s0["sleep_min"], min=0, max=720, format="%.0f").classes("w-56")
        with ui.row().style("gap:18px;flex-wrap:wrap"):
            yield_c = ui.switch("Pause for viewer comments", value=bool(s0["yield_comments"]))
            loop = ui.switch("Start again at the end", value=bool(s0["loop"]))
            show = ui.switch("Show the picture on screen (overlay)", value=bool(s0["show_text"]))
            safety = ui.switch("Skip lines the TikTok policy filter flags", value=bool(s0["safety"]))

        def collect():
            return {"voice": v_voice.value or "", "rate": int(rate.value or 0), "min_panel_s": float(min_s.value or 4),
                    "pause_s": s0["pause_s"], "yield_comments": yield_c.value, "loop": loop.value, "show_text": show.value,
                    "sleep_min": int(sleep_min.value or 0), "safety": safety.value}

        def send(command, **kw):
            c = story.read_control()
            c["settings"] = collect()
            c["command"] = command
            c["story"] = kw.get("story", c["story"] or sel["story"])
            if "panel" in kw:
                c.update(panel=kw["panel"], seq=c["seq"] + 1)
            story.write_control(c)

        def apply_settings(*_):
            c = story.read_control()
            c["settings"] = collect()
            story.write_control(c)
        for el in (v_voice, rate, min_s, sleep_min, yield_c, loop, show, safety):
            el.on_value_change(apply_settings)

        def start():
            meta = story.get_story(sel["story"])
            ok, why = story.can_use(meta)
            if not ok:
                ui.notify(why, type="warning")
                return
            if _tour_running() or _novel_running():
                ui.notify("The product tour or the Novel reader is running. Stop it first, or both will talk at once.", type="warning")
                return
            if not PM_STORY.running("story"):
                PM_STORY.start("story", [sys.executable, "story_reader.py", "--api", f"http://127.0.0.1:{api_port}/send"])
            send("play", story=meta["id"], panel=0)
            ui.notify("Reading. Make sure the app is running (Start Run).", type="positive")

        def pause_resume():
            send("play" if story.read_control()["command"] == "pause" else "pause")
        with ui.row().style("gap:10px;margin-top:8px;flex-wrap:wrap"):
            ui.button("Start", icon="play_arrow", on_click=start).props("color=positive")
            ui.button("Pause / continue", icon="pause", on_click=pause_resume).props("outline no-caps")
            ui.button("Stop", icon="stop", on_click=lambda: send("stop")).props("color=negative")
        status = ui.label("Not reading.").classes("lv-chip").style("margin-top:10px")
        bar = ui.linear_progress(value=0, show_value=False).classes("w-full").style("margin-top:6px")
        now_line = ui.label("").classes("lv-sub").style("font-size:15px;margin-top:6px;min-height:44px")

        def refresh():
            st = story.read_status()
            state = st.get("state") if time.time() - float(st.get("updated") or 0) < 10 else "idle"
            if state in ("playing", "paused"):
                status.text = f'{"Reading" if state == "playing" else "Paused"}: {st.get("title")} - panel {st.get("panel", 0) + 1}/{st.get("panels", 0)}'
                bar.value = (st.get("panel", 0) + 1) / max(1, st.get("panels", 1))
                now_line.text = st.get("text", "")
            elif state == "blocked":
                status.text, now_line.text = st.get("message", "Blocked"), ""
            elif state == "done":
                status.text, bar.value, now_line.text = "Finished.", 1, ""
            else:
                status.text, bar.value, now_line.text = ("Reader ready." if PM_STORY.running("story") else "Not reading."), 0, ""
        ui.timer(1.0, refresh)

    # ------------------------------------------------------------------ 5. video
    prog = {"a": 0, "b": 1, "msg": "", "busy": False, "cancel": False}
    with _card():
        _h("5. Make a video to post",
           "A vertical 9:16 video: the picture, the AI voice and captions burned in, a hook at the start and \"follow for part 2\" at the end. "
           "You also get the .srt subtitles, a cover picture and a caption with hashtags. Upload it to TikTok / Reels / Shorts yourself.")
        miss = story_video.missing_tools()
        if miss:
            ui.label("Missing on this computer: " + "; ".join(miss)).classes("lv-chip bad")
        src = ui.toggle({"story": "A picture story (step 3)", "novel": "A chapter from the Novel reader"}, value="story")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            books = {b["id"]: b["title"] for b in novel.list_books()}
            book_sel = ui.select(books, label="Novel reader story", value=next(iter(books), None)).classes("w-72")
            chap_sel = ui.select({}, label="Chapter").classes("w-72")

            def fill_chapters(*_):
                b = novel.get_book(book_sel.value) if book_sel.value else None
                chap_sel.set_options({i: f'{i + 1}. {c["title"]}' for i, c in enumerate(b["chapters"])} if b else {},
                                     value=0 if b else None)
            book_sel.on_value_change(fill_chapters)
            fill_chapters()
        book_row = [book_sel, chap_sel]
        for el in book_row:
            el.bind_visibility_from(src, "value", backward=lambda v: v == "novel")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            v_lang = ui.select({"vi": "Vietnamese", "en": "English"}, label="Language", value="vi").classes("w-40")
            v_voice2 = ui.select({"": "Default for the language", **{k: v for k, v in VOICES.items() if k}}, label="Voice", value="",
                                 with_input=True).classes("w-80")
            part = ui.number("Part number", value=1, min=0, max=99, format="%.0f").classes("w-32")
            with ui.column().style("gap:0;min-width:200px"):
                ui.label("Speed (%)").classes("lv-sub").style("margin:0")
                rate2 = ui.slider(min=-30, max=40, value=0).props("label-always").style("margin-top:30px")
        hook_in = ui.input("Hook (first line, makes people stay)", placeholder="Bạn có tin vào định mệnh?").classes("w-full")
        outro_in = ui.input("Ending line", value="Theo dõi để xem phần 2!").classes("w-full")
        tracks = {t["file"]: t for t in music.playable(music.tracks())}
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            mus = ui.select({"": "No music", **{f: f'{t["title"]}{" (credit)" if t["credit_needed"] else ""}' for f, t in tracks.items()}},
                            label="Background music (licensed tracks from Live tools)", value="").classes("w-96")
            with ui.column().style("gap:0;min-width:200px"):
                ui.label("Music volume (%)").classes("lv-sub").style("margin:0")
                mvol = ui.slider(min=3, max=30, value=12).props("label-always").style("margin-top:30px")
        est = ui.label("").classes("lv-sub")
        pbar = ui.linear_progress(value=0, show_value=False).classes("w-full")
        pmsg = ui.label("").classes("lv-sub")
        result = ui.column().classes("w-full")
        kit_box = ui.textarea("Caption + hashtags for the post").classes("w-full").props("rows=5")

        def panels_now():
            if src.value == "novel":
                b = novel.get_book(book_sel.value or "")
                return b, (story_video.panels_from_novel(b, int(chap_sel.value or 0)) if b else [])
            m = story.get_story(sel["story"])
            return m, (story_video.panels_from_story(m) if m else [])

        def update_est(*_):
            m, panels = panels_now()
            if panels:
                est.text = f"About {int(story_video.estimate_seconds(panels, hook_in.value or '', outro_in.value or '', rate=int(rate2.value or 0)))} seconds of video."
            else:
                est.text = ""
        for el in (src, book_sel, chap_sel, hook_in, outro_in, rate2):
            el.on_value_change(update_est)
        update_est()

        def tick():
            pbar.value = prog["a"] / max(1, prog["b"])
            pmsg.text = prog["msg"]
        ui.timer(0.5, tick)

        async def make():
            if prog["busy"]:
                return
            m, panels = panels_now()
            if src.value == "story":
                ok, why = story.can_use(m)
            else:
                ok, why = novel.can_read_live(m)
            if not ok:
                ui.notify(why, type="warning")
                return
            if not panels:
                ui.notify("Nothing to make a video from yet.", type="warning")
                return
            if story_video.missing_tools():
                ui.notify("Install the missing tools first (see the red note).", type="negative")
                return
            os.makedirs(OUT_DIR, exist_ok=True)
            base = f'{m["id"]}-p{int(part.value or 0)}-{int(time.time()) % 100000}'
            out_path = os.path.join(OUT_DIR, base + ".mp4")
            mt = tracks.get(mus.value) if mus.value else None
            prog.update(a=0, b=1, msg="Starting...", busy=True, cancel=False)
            result.clear()

            def progress(a, b, msg):
                prog.update(a=a, b=b, msg=msg)
            try:
                res = await run.io_bound(
                    story_video.build, panels, out_path, None, v_voice2.value or "", int(rate2.value or 0), v_lang.value, m["title"],
                    int(part.value or 0), hook_in.value or "", outro_in.value or "",
                    os.path.join(music.MUSIC_DIR, mt["file"]) if mt else None, (mvol.value or 12) / 100.0, (1080, 1920), 25, 0.25, 2.5,
                    progress, lambda: prog["cancel"])
            except Exception as ex:
                prog["busy"] = False
                prog["msg"] = f"Failed: {ex}"
                ui.notify(f"Video failed: {ex}", type="negative")
                return
            prog.update(busy=False, msg=f'Done: {res["pieces"]} pieces, {res["seconds"]} s')
            kit_box.value = story.post_kit(m, v_lang.value, int(part.value or 0), hook_in.value or "", "",
                                           mt["credit"] if mt and mt.get("credit") else "")
            with result:
                ui.video(f"/story-out/{os.path.basename(res['video'])}").style("max-width:280px;border-radius:12px")
                with ui.row().style("gap:8px"):
                    for key, label, icon in (("video", "Video (.mp4)", "movie"), ("srt", "Subtitles (.srt)", "subtitles"),
                                             ("cover", "Cover (.png)", "image")):
                        ui.button(label, icon=icon, on_click=lambda p=res[key]: ui.download(f"/story-out/{os.path.basename(p)}")).props(
                            "outline no-caps")
                ui.label("Saved in " + os.path.abspath(OUT_DIR)).classes("lv-sub")

        with ui.row().style("gap:10px;margin-top:8px"):
            ui.button("Make the video", icon="movie_creation", on_click=make).props("color=primary no-caps")
            ui.button("Cancel", icon="close", on_click=lambda: prog.update(cancel=True)).props("flat no-caps")
            ui.button("Copy caption", icon="content_copy", on_click=lambda: _copy(kit_box.value or "")).props("flat no-caps")

    with _card():
        _h("The loop that gets followers")
        for line in ("1. Write the plot (step 1) with a hook and a cliffhanger. 10-15 panels = a 60-90 second video.",
                     "2. Make or generate one picture per panel; keep the characters looking the same.",
                     "3. Make the video (step 5), upload it, paste the caption + hashtags. Post part 2 the next day.",
                     "4. Go live and read the story with the AI host (step 4): people who liked the video come to the live.",
                     "Always credit when the licence asks for it - the caption already contains it."):
            ui.label(line).classes("lv-sub").style("margin:2px 0")


def _novel_running() -> bool:
    try:
        from .webui_novel import PM_NOVEL
        return PM_NOVEL.running("novel")
    except Exception:
        return False
