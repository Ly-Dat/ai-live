"""Avatar studio tab: draw your own free AI seller character, see it on stream, and keep manual control of the host.

Engine: utils/avatar_gen.py (local Stable Diffusion WebUI + Animagine XL 3.1). Display: utils/avatar.py via /overlay.
"""
import io
import os

from nicegui import app, run, ui

from . import avatar, avatar_gen, host_control
from .webui_theme import page_title

_mounted = {"done": False}


def _mount():
    if _mounted["done"]:
        return
    try:
        os.makedirs(avatar.PACK_DIR, exist_ok=True)
        app.add_static_files("/lv_avatar", avatar.DIR)
        _mounted["done"] = True
    except Exception:
        pass


_mount()


def _card(first=False):
    return ui.card().classes("lv-card w-full").style("padding:20px" + ("" if first else ";margin-top:26px"))


def build_avatar_tab(config):
    _mount()
    page_title("Avatar studio", "Draw a free AI character for your seller, show it on stream with expressions, and keep a pause / take-over "
                                "switch within reach.")
    s = avatar.load_settings()
    gen = {**avatar_gen.DEFAULTS, **s.get("gen", {})}
    prog = {"msg": "", "busy": False}

    # ---------------------------------------------------------------- manual control
    with _card(True):
        ui.label("Host control").style("font-weight:700;font-size:16px")
        ui.label("Pause the AI at once, or take over and speak yourself. While it is not live the AI says nothing and the avatar rests; "
                 "viewer questions are still collected on the Dashboard.").classes("lv-sub")
        status = ui.label().style("font-weight:600")

        def show():
            st = host_control.load()["state"]
            status.set_text({"live": "The AI is hosting.", "paused": "PAUSED: the AI is silent.",
                             "takeover": "YOU are hosting: the AI is silent."}[st])

        def set_to(state):
            host_control.set_state(state)
            show()
            ui.notify({"live": "The AI is hosting again.", "paused": "Paused.", "takeover": "You have the mic."}[state])

        with ui.row().style("gap:12px;flex-wrap:wrap"):
            ui.button("Pause AI", icon="pause", on_click=lambda: set_to("paused")).props("color=negative")
            ui.button("I'll take over", icon="record_voice_over", on_click=lambda: set_to("takeover")).props("color=warning")
            ui.button("Resume AI", icon="play_arrow", on_click=lambda: set_to("live")).props("color=positive")
        show()

    # ---------------------------------------------------------------- character
    with _card():
        ui.label("Your character").style("font-weight:700;font-size:16px")
        ui.label("Describe an original character in plain English. Do not name an existing character or celebrity: the picture should be yours.").classes("lv-sub")
        c = s["character"]
        with ui.row().style("gap:14px;flex-wrap:wrap;width:100%"):
            name = ui.input("Name", value=c["name"]).style("min-width:160px")
            gender = ui.select({"female": "Girl", "male": "Boy"}, value=c["gender"], label="Looks like").style("min-width:140px")
            hair = ui.input("Hair", value=c["hair"]).style("min-width:260px")
            eyes = ui.input("Eyes", value=c["eyes"]).style("min-width:160px")
            outfit = ui.input("Outfit", value=c["outfit"]).style("min-width:300px")
            extra = ui.input("Anything else (accessories, mood)", value=c["extra"]).style("min-width:300px")
        phrases = ui.input("Catchphrases (separate with |)", value=" | ".join(s["catchphrases"])).props("outlined dense").style("width:100%")
        ui.label("The seller adds one now and then to short product replies (about every third). It never changes the product facts.").classes("lv-sub")
        expertise = ui.input("What this character knows well (shown in your notes only)", value=s["expertise"]).props("outlined dense").style("width:100%")
        with ui.row().classes("items-center").style("gap:24px;flex-wrap:wrap"):
            enable = ui.switch("Show the avatar on the overlay", value=s["enabled"])
            with ui.column().style("gap:0;min-width:220px"):
                ui.label("Size on screen (% of height)").classes("lv-sub").style("margin:0")
                height = ui.slider(min=25, max=90, value=s["height_vh"]).props("label-always")

        def save_char():
            cur = avatar.load_settings()
            cur.update({"enabled": bool(enable.value), "height_vh": int(height.value), "expertise": expertise.value or "",
                        "catchphrases": [p.strip() for p in (phrases.value or "").split("|") if p.strip()],
                        "character": {"name": name.value or "Mimi", "gender": gender.value or "female", "hair": hair.value or "",
                                      "eyes": eyes.value or "", "outfit": outfit.value or "", "extra": extra.value or ""},
                        "gen": {k: v for k, v in {"engine": engine.value, "host": ghost.value, "port": int(gport.value or 7860),
                                                  "checkpoint": ckpt.value or ""}.items()}})
            avatar.save_settings(cur)
            ui.notify("Saved.")

    # ---------------------------------------------------------------- generator
    with _card():
        ui.label("Draw it with a free AI").style("font-weight:700;font-size:16px")
        ui.label("Recommended: a Stable Diffusion WebUI (AUTOMATIC1111 or Forge) on this computer, started with --api, with the Animagine XL 3.1 model "
                 "loaded. It is free and offline, needs a graphics card with about 8 GB of memory, and its licence allows commercial use of the images "
                 "(read the model card yourself). No graphics card? Upload your own pictures below, or try the web option.").classes("lv-sub")
        with ui.row().style("gap:14px;flex-wrap:wrap;width:100%"):
            engine = ui.select({"local": "Local Stable Diffusion (recommended)", "pollinations": "Free web service (untested, no GPU)"},
                               value=gen["engine"], label="Engine").style("min-width:300px")
            ghost = ui.input("WebUI address", value=gen["host"]).style("min-width:160px")
            gport = ui.number("Port", value=gen["port"], format="%.0f").style("min-width:100px")
            ckpt = ui.input("Checkpoint name (blank = whatever is loaded)", value=gen["checkpoint"]).style("min-width:320px")
        ui.label("The first picture can take a minute; all six take a few minutes on a mid-range card. Expressions are redrawn from the first picture "
                 "so the face stays the same. Results vary: re-draw until you like it, or replace any picture by hand.").classes("lv-sub")
        info = ui.label().classes("lv-sub")
        gallery = ui.row().style("gap:12px;flex-wrap:wrap;margin-top:8px")

        def refresh_gallery():
            gallery.clear()
            files = avatar.pack_files()
            with gallery:
                for ex in avatar_gen.EXPRESSIONS:
                    with ui.column().style("align-items:center;gap:4px"):
                        if ex in files:
                            ui.image(f"/lv_avatar/pack/{ex}.png?v={int(files[ex])}").style("width:120px;background:#2a2540;border-radius:10px")
                        else:
                            ui.label("(none)").style("width:120px;height:120px;display:flex;align-items:center;justify-content:center;"
                                                     "background:#2a2540;border-radius:10px;opacity:.6")
                        ui.label(ex).classes("lv-sub").style("margin:0")

                        def on_up(e, ex=ex):
                            try:
                                from PIL import Image
                                im = Image.open(io.BytesIO(e.content.read())).convert("RGBA")
                                os.makedirs(avatar.PACK_DIR, exist_ok=True)
                                im.save(os.path.join(avatar.PACK_DIR, ex + ".png"), "PNG")
                                ui.notify(f"{ex} replaced.")
                                refresh_gallery()
                            except Exception as err:
                                ui.notify(f"Could not read that image: {err}", type="negative")
                        ui.upload(on_upload=on_up, auto_upload=True, label="Replace").props("flat dense accept=image/*").style("width:120px")

        def do_generate():
            if prog["busy"]:
                return
            save_char()
            cur = avatar.load_settings()
            prog.update(busy=True, msg="Starting ...")

            def work():
                return avatar_gen.generate_pack(cur["character"], cur["gen"], avatar.PACK_DIR, seed=cur["seed"],
                                                progress=lambda m: prog.update(msg=m))

            async def go():
                r = await run.io_bound(work)
                prog["busy"] = False
                if r["failed"]:
                    prog["msg"] = "Done with problems: " + "; ".join(f"{k}: {v}" for k, v in r["failed"].items())
                else:
                    prog["msg"] = f"Done: {len(r['made'])} pictures."
                refresh_gallery()
            import asyncio
            asyncio.ensure_future(go())

        def new_look():
            cur = avatar.load_settings()
            cur["seed"] = (cur["seed"] * 1103515245 + 12345) % 2_000_000_000
            avatar.save_settings(cur)
            ui.notify("Next draw will use a new look.")

        with ui.row().style("gap:12px;flex-wrap:wrap"):
            ui.button("Save settings", icon="save", on_click=save_char)
            ui.button("Draw all expressions", icon="brush", on_click=do_generate).props("color=primary")
            ui.button("Try a different look", icon="shuffle", on_click=new_look).props("flat")
        ui.timer(1.0, lambda: info.set_text(prog["msg"]))
        refresh_gallery()

    # ---------------------------------------------------------------- show-plan preview
    with _card():
        ui.label("Show plan preview").style("font-weight:700;font-size:16px")
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
