"""Avatar studio tab: pick or create a character, draw it with a free AI, dress and stage it, grow it, and keep manual control.

Engine: utils/avatar_gen.py (local Stable Diffusion WebUI + Animagine XL 3.1). Roster: utils/avatar_roster.py. Display: utils/avatar.py via /overlay.
Journey (level, streak, achievements): utils/bond.py.
"""
import asyncio
import io
import os
import time

from nicegui import app, run, ui

from . import avatar, avatar_gen, avatar_roster, bond, host_control
from .webui_theme import page_title

_mounted = {"done": False}


def _mount():
    if _mounted["done"]:
        return
    try:
        os.makedirs(avatar.DIR, exist_ok=True)
        app.add_static_files("/lv_avatar", avatar.DIR)
        _mounted["done"] = True
    except Exception:
        pass


_mount()


def _card(first=False):
    return ui.card().classes("lv-card w-full").style("padding:20px" + ("" if first else ";margin-top:22px"))


def _h(text):
    ui.label(text).style("font-weight:700;font-size:16px")


def build_avatar_tab(config):
    _mount()
    page_title("Avatar studio", "Pick or draw a character with a free AI, show it on stream with 15 expressions, dress and stage it, and watch it grow "
                                "with every live. A Pause / Take-over switch is always within reach.")
    log_dir = config.get("analytics", "dir") or "log/analytics"
    st = {"sel": "", "busy": False, "msg": ""}
    journey = {"b": bond.refresh(log_dir)}
    S = avatar.load_settings()
    st["sel"] = S["active"] or (avatar_roster.list_all() or [{"id": ""}])[0]["id"]

    def level():
        return journey["b"]["level"]

    # ------------------------------------------------------------ journey strip (always visible)
    strip = ui.column().classes("w-full")

    def draw_strip():
        strip.clear()
        b = journey["b"]
        with strip, _card(True):
            with ui.row().classes("items-center").style("gap:18px;flex-wrap:wrap;width:100%"):
                ui.label(f"Level {b['level']}").style("font-weight:800;font-size:22px")
                with ui.column().style("gap:2px;min-width:260px;flex:1"):
                    ui.linear_progress(value=b["into"] / max(1, b["span"]), show_value=False)
                    ui.label(f"{b['into']} / {b['span']} XP to level {b['level'] + 1}").classes("lv-sub").style("margin:0")
                ui.label(f"{b['streak']}-day streak").classes("lv-chip hot" if b["streak"] >= 2 else "lv-chip")
                ui.label(f"{b['answered_today']}/{b['goal']} answers today").classes("lv-chip")
            if b["next_unlock"]:
                ui.label("Next unlock - " + b["next_unlock"]).classes("lv-sub")
    draw_strip()
    for a in journey["b"].get("new", []):
        ui.notify(f"Achievement unlocked: {a['title']}", type="positive")
    if journey["b"].get("new"):
        bond.mark_seen()

    with ui.tabs().classes("w-full") as tabs:
        t_chars, t_draw, t_stage, t_journey, t_ctrl = (ui.tab("Characters"), ui.tab("Draw"), ui.tab("Stage"), ui.tab("Journey"), ui.tab("Control"))
    with ui.tab_panels(tabs, value=t_chars).classes("w-full").style("background:transparent"):

        # ======================================================== Characters
        with ui.tab_panel(t_chars):
            @ui.refreshable
            def roster():
                chars = avatar_roster.list_all()
                active = avatar.load_settings()["active"]
                with _card(True):
                    _h("Your characters")
                    if not chars:
                        ui.label("None yet. Add a ready-made one below, or create your own.").classes("lv-sub")
                    with ui.row().style("gap:14px;flex-wrap:wrap"):
                        for c in chars:
                            files = avatar_roster.drawn(c["id"], c["look"])
                            with ui.card().style("width:190px;padding:12px;align-items:center;gap:6px"):
                                if "idle" in files:
                                    ui.image(f"/lv_avatar/characters/{c['id']}/looks/{c['look']}/idle.png?v={int(files['idle'])}").style(
                                        "height:150px;width:150px;object-fit:contain;background:#2a2540;border-radius:10px")
                                else:
                                    ui.label("not drawn yet").style("height:150px;width:150px;display:flex;align-items:center;justify-content:center;"
                                                                     "background:#2a2540;border-radius:10px;opacity:.6")
                                ui.label(c["name"] + ("  (on stream)" if c["id"] == active else "")).style("font-weight:700")
                                ui.label(f"{len(files)}/{len(avatar_gen.EXPRESSIONS)} pictures").classes("lv-sub").style("margin:0")

                                def use(cid=c["id"]):
                                    s = avatar.load_settings()
                                    s["active"] = cid
                                    avatar.save_settings(s)
                                    st["sel"] = cid
                                    roster.refresh()
                                    draw_panel.refresh()
                                    ui.notify("Now on stream.")

                                def edit(cid=c["id"]):
                                    st["sel"] = cid
                                    draw_panel.refresh()
                                    tabs.set_value(t_draw)

                                def drop(cid=c["id"]):
                                    avatar_roster.delete(cid)
                                    s = avatar.load_settings()
                                    if s["active"] == cid:
                                        s["active"] = ""
                                        avatar.save_settings(s)
                                    st["sel"] = ""
                                    roster.refresh()
                                    draw_panel.refresh()
                                with ui.row().style("gap:4px"):
                                    ui.button("Use", on_click=use).props("dense color=primary")
                                    ui.button("Edit", on_click=edit).props("dense flat")
                                    ui.button(icon="delete", on_click=drop).props("dense flat color=negative")
                with _card():
                    _h("Add a ready-made character")
                    ui.label("Original designs. Adding one only saves its description; draw it in the Draw tab.").classes("lv-sub")
                    with ui.row().style("gap:12px;flex-wrap:wrap"):
                        for p in avatar_roster.PRESETS:
                            with ui.card().style("width:200px;padding:12px;gap:2px"):
                                ui.label(p["name"]).style("font-weight:700")
                                ui.label(p["tagline"]).classes("lv-sub").style("margin:0")
                                ui.label(f"{p['hair']}; {p['eyes']}").style("font-size:12px;opacity:.7")

                                def add(pid=p["id"]):
                                    c = avatar_roster.create_from_preset(pid)
                                    st["sel"] = c["id"]
                                    roster.refresh()
                                    draw_panel.refresh()
                                    ui.notify(f"{c['name']} added. Open the Draw tab to paint it.")
                                ui.button("Add", on_click=add).props("dense flat")
                with _card():
                    _h("Create your own")
                    with ui.row().classes("items-center").style("gap:12px"):
                        nm = ui.input("Name").props("dense outlined")

                        def make():
                            if not (nm.value or "").strip():
                                ui.notify("Give it a name.", type="warning")
                                return
                            c = avatar_roster.create_custom(nm.value)
                            st["sel"] = c["id"]
                            roster.refresh()
                            draw_panel.refresh()
                            tabs.set_value(t_draw)
                        ui.button("Create", icon="add", on_click=make)
            roster()

        # ======================================================== Draw
        with ui.tab_panel(t_draw):
            prog = {"msg": ""}

            @ui.refreshable
            def draw_panel():
                c = avatar_roster.load(st["sel"]) if st["sel"] else None
                if not c:
                    with _card(True):
                        ui.label("Pick a character in the Characters tab first.")
                    return
                gen = {**avatar_gen.DEFAULTS, **avatar.load_settings().get("gen", {})}
                with _card(True):
                    _h(f"Describe {c['name']}")
                    ui.label("Use an original design; do not name an existing character or a real person.").classes("lv-sub")
                    with ui.row().style("gap:14px;flex-wrap:wrap;width:100%"):
                        name = ui.input("Name", value=c["name"]).style("min-width:160px")
                        gender = ui.select({"female": "Girl", "male": "Boy"}, value=c["gender"], label="Looks like").style("min-width:130px")
                        hair = ui.input("Hair", value=c["hair"]).style("min-width:280px")
                        eyes = ui.input("Eyes", value=c["eyes"]).style("min-width:160px")
                        extra = ui.input("Accessories / mood", value=c["extra"]).style("min-width:280px")
                    phrases = ui.input("Catchphrases (separate with |)", value=" | ".join(c["catchphrases"])).props("outlined dense").style("width:100%")
                    ui.label("Added to about every third short product reply. Product facts never change.").classes("lv-sub")
                    if c.get("persona"):
                        ui.label(f"Suggested voice: the \"{c['persona']}\" persona in the Voice tab.").classes("lv-sub")
                    _h("Looks (outfits)")
                    cap = bond.max_looks(level())
                    ui.label(f"{len(c['looks'])}/{cap} outfit slots used. More unlock as you level up.").classes("lv-sub")
                    look_sel = ui.select(list(c["looks"].keys()), value=c["look"], label="Current look").style("min-width:200px")
                    outfit = ui.input("Outfit of this look", value=c["looks"].get(c["look"], c["outfit"])).props("outlined dense").style("width:100%")
                    with ui.row().classes("items-center").style("gap:12px;flex-wrap:wrap"):
                        new_name = ui.input("New look name").props("dense outlined")
                        new_outfit = ui.input("Its outfit").props("dense outlined").style("min-width:300px")

                    def collect():
                        cur = avatar_roster.load(c["id"])
                        look = look_sel.value or cur["look"]
                        looks = {**cur["looks"], look: outfit.value or ""}
                        cur.update({"name": name.value or cur["name"], "gender": gender.value, "hair": hair.value or "", "eyes": eyes.value or "",
                                    "extra": extra.value or "", "look": look, "looks": looks, "outfit": looks.get("default", cur["outfit"]),
                                    "catchphrases": [p.strip() for p in (phrases.value or "").split("|") if p.strip()]})
                        return cur

                    def save_all():
                        avatar_roster.save(collect())
                        s = avatar.load_settings()
                        s["gen"] = {"engine": engine.value, "host": ghost.value, "port": int(gport.value or 7860), "checkpoint": ckpt.value or ""}
                        avatar.save_settings(s)
                        roster.refresh()
                        ui.notify("Saved.")

                    def add_look():
                        if not (new_name.value or "").strip():
                            ui.notify("Name the new look.", type="warning")
                            return
                        try:
                            cur = avatar_roster.add_look(collect(), new_name.value, new_outfit.value or "", bond.max_looks(level()))
                        except ValueError as e:
                            ui.notify(str(e), type="warning")
                            return
                        avatar_roster.save(cur)
                        draw_panel.refresh()
                    ui.button("Add this look", icon="checkroom", on_click=add_look).props("flat")

                with _card():
                    _h("Draw it with a free AI")
                    ui.label("Best: a Stable Diffusion WebUI (AUTOMATIC1111 or Forge) on this PC, started with --api, with Animagine XL 3.1 loaded. Free and offline; "
                             "needs a GPU with about 8 GB of memory; the model licence allows commercial use of the images (read the model card yourself). "
                             "No GPU? Upload your own pictures, or try the web option.").classes("lv-sub")
                    with ui.row().style("gap:14px;flex-wrap:wrap;width:100%"):
                        engine = ui.select({"local": "Local Stable Diffusion (recommended)", "pollinations": "Free web service (untested, no GPU)"},
                                           value=gen["engine"], label="Engine").style("min-width:300px")
                        ghost = ui.input("WebUI address", value=gen["host"]).style("min-width:160px")
                        gport = ui.number("Port", value=gen["port"], format="%.0f").style("min-width:100px")
                        ckpt = ui.input("Checkpoint (blank = loaded one)", value=gen["checkpoint"]).style("min-width:300px")
                    info = ui.label().classes("lv-sub")
                    gallery = ui.row().style("gap:10px;flex-wrap:wrap;margin-top:8px")

                    def look_now():
                        return avatar_roster.load(c["id"])["look"]

                    def refresh_gallery():
                        gallery.clear()
                        look = look_now()
                        files = avatar_roster.drawn(c["id"], look)
                        with gallery:
                            for ex in avatar_gen.EXPRESSIONS:
                                with ui.column().style("align-items:center;gap:2px"):
                                    if ex in files:
                                        ui.image(f"/lv_avatar/characters/{c['id']}/looks/{look}/{ex}.png?v={int(files[ex])}").style(
                                            "width:100px;height:100px;object-fit:contain;background:#2a2540;border-radius:10px")
                                    else:
                                        ui.label("-").style("width:100px;height:100px;display:flex;align-items:center;justify-content:center;"
                                                            "background:#2a2540;border-radius:10px;opacity:.5")
                                    ui.label(ex).classes("lv-sub").style("margin:0")

                                    def on_up(e, ex=ex):
                                        try:
                                            from PIL import Image
                                            im = Image.open(io.BytesIO(e.content.read())).convert("RGBA")
                                            d = avatar_roster.look_dir(c["id"], look_now())
                                            os.makedirs(d, exist_ok=True)
                                            im.save(os.path.join(d, ex + ".png"), "PNG")
                                            refresh_gallery()
                                        except Exception as err:
                                            ui.notify(f"Could not read that image: {err}", type="negative")
                                    ui.upload(on_upload=on_up, auto_upload=True, label="Replace").props("flat dense accept=image/*").style("width:100px")

                    def start(which):
                        if st["busy"]:
                            return
                        save_all()
                        cur = avatar_roster.load(c["id"])
                        gcfg = avatar.load_settings()["gen"]
                        have = avatar_roster.drawn(cur["id"], cur["look"])
                        exprs = {"core": avatar_gen.CORE, "all": avatar_gen.EXPRESSIONS,
                                 "missing": [e for e in avatar_gen.EXPRESSIONS if e not in have]}[which]
                        if not exprs:
                            ui.notify("Nothing missing.")
                            return
                        char = {**cur, "outfit": cur["looks"].get(cur["look"], cur["outfit"])}
                        out = avatar_roster.look_dir(cur["id"], cur["look"])
                        st.update(busy=True, msg="Starting ...")

                        def work():
                            return avatar_gen.generate_pack(char, gcfg, out, seed=cur["seed"], expressions=exprs, progress=lambda m: st.update(msg=m))

                        async def go():
                            r = await run.io_bound(work)
                            st["busy"] = False
                            st["msg"] = ("Done with problems: " + "; ".join(f"{k}: {v}" for k, v in r["failed"].items())) if r["failed"] else f"Done: {len(r['made'])} pictures."
                            refresh_gallery()
                            roster.refresh()
                        asyncio.ensure_future(go())

                    def new_seed():
                        cur = avatar_roster.load(c["id"])
                        cur["seed"] = (cur["seed"] * 1103515245 + 12345) % 2_000_000_000
                        avatar_roster.save(cur)
                        ui.notify("The next draw will have a new face.")
                    with ui.row().style("gap:10px;flex-wrap:wrap"):
                        ui.button("Save", icon="save", on_click=save_all)
                        ui.button("Draw the 6 core", icon="brush", on_click=lambda: start("core")).props("color=primary")
                        ui.button(f"Draw all {len(avatar_gen.EXPRESSIONS)}", icon="auto_awesome", on_click=lambda: start("all")).props("color=primary")
                        ui.button("Draw missing", icon="add_photo_alternate", on_click=lambda: start("missing")).props("flat")
                        ui.button("New face", icon="shuffle", on_click=new_seed).props("flat")
                    ui.label("The first picture takes a minute; all of them take several minutes on a mid-range card. Expressions are redrawn from the first picture so the "
                             "face stays the same. Results vary: redraw, or replace any picture by hand. A look with only the 6 core pictures still works.").classes("lv-sub")
                    ui.timer(1.0, lambda: info.set_text(st["msg"]))
                    refresh_gallery()
            draw_panel()

        # ======================================================== Stage
        with ui.tab_panel(t_stage):
            S = avatar.load_settings()
            stg = S["stage"]
            lv = level()
            frames, motions = bond.unlocked(bond.FRAMES, lv), bond.unlocked(bond.MOTIONS, lv)
            with _card(True):
                _h("On the overlay")
                ui.label("Add http://127.0.0.1:<web UI port>/overlay as a browser source (same link as polls and giveaways).").classes("lv-sub")
                enable = ui.switch("Show the avatar", value=S["enabled"])
                with ui.row().style("gap:18px;flex-wrap:wrap;width:100%"):
                    side = ui.select({"right": "Right", "left": "Left (polls are on the left too)", "center": "Centre"}, value=stg["side"], label="Position").style("min-width:220px")
                    motion = ui.select(motions, value=stg["motion"] if stg["motion"] in motions else "bob", label="Idle motion").style("min-width:150px")
                    frame = ui.select(frames, value=stg["frame"] if stg["frame"] in frames else "none", label="Glow").style("min-width:150px")
                    with ui.column().style("gap:0;min-width:220px"):
                        ui.label("Size (% of screen height)").classes("lv-sub").style("margin:0")
                        height = ui.slider(min=25, max=90, value=stg["height_vh"]).props("label-always")
                locked = [n for n, _ in bond.FRAMES + bond.MOTIONS if n not in frames + motions]
                if locked:
                    ui.label("Locked until you level up: " + ", ".join(locked)).classes("lv-sub")
                with ui.row().style("gap:18px"):
                    nametag = ui.switch("Name tag", value=stg["nametag"])
                    badge = ui.switch("Show level and streak to viewers", value=stg["badge"])
                    caption = ui.switch("Live caption of what she says", value=stg.get("caption", True))
                tips = ui.textarea("Hint bubbles, one per line (rotate under the avatar), e.g. Ask me about sizes!", value="\n".join(stg["tips"])).props("outlined dense").style("width:100%")
                ui.label("Short invitations make viewers type a question. Up to 6.").classes("lv-sub")

                def save_stage():
                    s = avatar.load_settings()
                    s["enabled"] = bool(enable.value)
                    s["stage"].update({"side": side.value, "motion": motion.value, "frame": frame.value, "height_vh": int(height.value),
                                       "nametag": bool(nametag.value), "badge": bool(badge.value), "caption": bool(caption.value),
                                       "tips": [t.strip() for t in (tips.value or "").splitlines() if t.strip()][:6]})
                    avatar.save_settings(s)
                    ui.notify("Saved.")
                ui.button("Save", icon="save", on_click=save_stage)
            with _card():
                _h("Try an expression")
                ui.label("Shows it on the overlay for 8 seconds. Missing pictures fall back to a close one.").classes("lv-sub")
                with ui.row().style("gap:8px;flex-wrap:wrap"):
                    for ex in avatar_gen.EXPRESSIONS:
                        ui.button(ex, on_click=lambda ex=ex: (avatar.set_preview(ex, time.time()), ui.notify(f"Showing {ex}"))).props("dense flat")

        # ======================================================== Journey
        with ui.tab_panel(t_journey):
            b = journey["b"]
            with _card(True):
                _h("Your journey")
                ui.label("Built from your real lives. XP: 50 per live, 2 per viewer question answered, 5 per gift, 10 per hour on air. "
                         "Unlocks are cosmetic only (glow, motions, outfit slots).").classes("lv-sub")
                with ui.row().style("gap:10px"):
                    ui.label(f"{b['lives']} lives").classes("lv-chip")
                    ui.label(f"{b['hours']} h on air").classes("lv-chip")
                    ui.label(f"{b['answered']} answers").classes("lv-chip")
                    ui.label(f"{b['week']} lives this week").classes("lv-chip")
                ui.label(f"Today's goal: answer {b['goal']} viewer questions ({b['answered_today']} so far)").style("margin-top:10px")
                ui.linear_progress(value=min(1, b["answered_today"] / b["goal"]), show_value=False)
            with _card():
                _h("Achievements")
                with ui.row().style("gap:12px;flex-wrap:wrap"):
                    for a in b["achievements"]:
                        with ui.card().style("width:210px;padding:12px;gap:2px;" + ("" if a["done"] else "opacity:.6")):
                            ui.label(("✓ " if a["done"] else "") + a["title"]).style("font-weight:700")
                            ui.label(a["desc"]).classes("lv-sub").style("margin:0")
                            if not a["done"]:
                                ui.linear_progress(value=min(1, a["have"] / a["goal"]), show_value=False)
                                ui.label(f"{a['have']} / {a['goal']}").style("font-size:12px;opacity:.7")

        # ======================================================== Control
        with ui.tab_panel(t_ctrl):
            with _card(True):
                _h("Host control")
                ui.label("Pause the AI at once, or take over and speak yourself. While not live the AI says nothing and the avatar rests; "
                         "viewer questions are still collected on the Dashboard.").classes("lv-sub")
                status = ui.label().style("font-weight:600")

                def show():
                    status.set_text({"live": "The AI is hosting.", "paused": "PAUSED: the AI is silent.",
                                     "takeover": "YOU are hosting: the AI is silent."}[host_control.load()["state"]])

                def set_to(state):
                    host_control.set_state(state)
                    show()
                    ui.notify({"live": "The AI is hosting again.", "paused": "Paused.", "takeover": "You have the mic."}[state])
                with ui.row().style("gap:12px;flex-wrap:wrap"):
                    ui.button("Pause AI", icon="pause", on_click=lambda: set_to("paused")).props("color=negative")
                    ui.button("I'll take over", icon="record_voice_over", on_click=lambda: set_to("takeover")).props("color=warning")
                    ui.button("Resume AI", icon="play_arrow", on_click=lambda: set_to("live")).props("color=positive")
                show()
            with _card():
                _h("Show plan preview")
                ui.label("What the host will introduce, in order, with the opening line it would use. Edit products in the Products tab.").classes("lv-sub")
                box = ui.column().style("gap:6px")

                def plan():
                    box.clear()
                    try:
                        from . import product_catalog
                        cat = product_catalog.get_default()
                        items = sorted(cat.all_products(), key=lambda p: p.get("order") or 999)
                    except Exception as e:
                        with box:
                            ui.label(f"Could not read the catalog: {e}")
                        return
                    with box:
                        if not items:
                            ui.label("No products yet.")
                        for i, p in enumerate(items, 1):
                            ui.label(f"{i}. {p['name']}  -  {p.get('price', '')}").style("font-weight:600")
                            try:
                                ui.label(cat.build_pitch(p, 0)).classes("lv-sub").style("margin:0 0 6px 16px")
                            except Exception:
                                pass
                ui.button("Preview the plan", icon="list", on_click=plan).props("flat")
