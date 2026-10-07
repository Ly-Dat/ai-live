"""
"Setup" tab: a five-step wizard so a seller can go from install to live without editing JSON.

  1 Shop      - shop name + TikTok username
  2 Products  - upload a CSV/XLSX (or use the Products tab)
  3 Persona   - voice + speaking style, with a spoken preview
  4 Check     - dry run of the demo viewers (no TikTok, no LLM) + AI/LLM reminder
  5 Go live   - start / stop the TikTok bridge and the product tour
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

from nicegui import ui

from . import my_voice, personas, setup_wizard, simulator, product_catalog, tiktok_safety
from .webui_theme import page_title

ROOT = setup_wizard.ROOT
PM = setup_wizard.ProcessManager()  # module level: survives page reloads inside the web UI process


def build_setup_tab(config):
    cfg_path = os.path.join(ROOT, "config.json")
    products_path = os.path.join(ROOT, config.get("products", "path") or "data/products.json")
    templates_path = os.path.join(ROOT, config.get("products", "templates_path") or "data/pitch_templates.json")
    terms_path = os.path.join(ROOT, config.get("filter", "tiktok_safety", "terms_path") or "data/tiktok_policy_terms.json")
    personas_path = os.path.join(ROOT, "data", "personas.json")
    scenario_path = os.path.join(ROOT, "data", "sim_scenario.json")
    api_url = f'http://127.0.0.1:{config.get("api_port")}/send'
    setup = setup_wizard.load_setup()
    pdata = personas.load(personas_path)
    pmap = {p["id"]: p for p in pdata["personas"]}

    with ui.element("div").classes("lv-hero w-full").style("margin-bottom:22px"):
        ui.label("Go live in five steps").classes("lv-title")
        ui.label("Shop, products, voice, a safe dry run, then press Start. Your answers are saved to data/setup.json and config.json.").style("opacity:.9")

    with ui.stepper().props("vertical").classes("w-full") as stepper:
        # ------------------------------------------------------------------ 1 shop
        with ui.step("Your shop"):
            mode = ui.toggle({"seller": "I sell products", "creator": "I'm a creator (no cart)"}, value=setup.get("mode", "seller"))
            ui.label("Creators get a chat host with no product pitches; sellers get the cart, tour and flash sales.").classes("lv-sub")
            shop = ui.input("Shop or channel name", value=setup["shop_name"]).classes("w-full").style("max-width:384px")
            user = ui.input("TikTok username that goes live (with or without @)", value=setup["tiktok_username"]).classes("w-full").style("max-width:384px")
            with ui.row():
                gifts = ui.switch("Thank viewers for gifts and follows", value=setup["gifts"])
                joins = ui.switch("Greet new viewers (noisy in big rooms)", value=setup["joins"])
            returning_sw = ui.switch("Welcome returning viewers (remembers a hashed id, never the name)", value=bool(setup.get("returning_viewers")))
            ui.button("Forget all remembered viewers", on_click=lambda: _forget()).props("flat dense no-caps color=negative")
            msg1 = ui.label("").classes("text-negative")

            def _forget():
                from . import returning
                returning.ViewerBook(os.path.join(ROOT, "data", "viewers.json")).forget_all()
                ui.notify("All remembered viewers were deleted.", type="positive")

            def next1():
                problems = setup_wizard.validate({"tiktok_username": user.value})
                msg1.text = " ".join(problems)
                if not problems:
                    stepper.next()
            ui.button("Next", on_click=next1)

        # ------------------------------------------------------------------ 2 products
        with ui.step("Products"):
            n = len(product_catalog.ProductCatalog(products_path, templates_path).products) if os.path.exists(products_path) else 0
            products_note = ui.label("Creator mode: you can skip this step, no products are needed.").classes("text-positive")
            products_note.set_visibility(setup.get("mode") == "creator")
            count_lbl = ui.label(f"The catalog has {n} product(s). Upload your Seller Center export (CSV/XLSX) or edit them in the Products tab.")

            async def on_upload(e):
                with tempfile.TemporaryDirectory() as tmp:
                    path = os.path.join(tmp, e.name)
                    with open(path, "wb") as fh:
                        fh.write(e.content.read())
                    res = await asyncio.to_thread(
                        subprocess.run, [sys.executable, "import_products.py", path, "--products", products_path],
                        cwd=ROOT, capture_output=True, text=True)
                ui.notify((res.stdout or res.stderr or "done").strip()[-300:], type="positive" if res.returncode == 0 else "negative")
            ui.upload(on_upload=on_upload, auto_upload=True).props('accept=".csv,.xlsx" flat bordered').classes("w-full").style("max-width:384px")
            with ui.stepper_navigation():
                ui.button("Next", on_click=stepper.next)
                ui.button("Back", on_click=stepper.previous).props("flat")

        # ------------------------------------------------------------------ 3 persona
        with ui.step("Voice and persona"):
            def persona_options(m):
                return {p["id"]: f"{p['name']} - {p['description']}" for p in personas.for_mode(pdata, m)}
            opts = persona_options(setup.get("mode", "seller"))
            radio = ui.radio(opts, value=setup["persona_id"] if setup["persona_id"] in opts else next(iter(opts)))

            def on_mode(e):
                o = persona_options(mode.value)
                radio.set_options(o, value=radio.value if radio.value in o else next(iter(o)))
                products_note.set_visibility(mode.value == "creator")
                auto_tour.set_value(auto_tour.value and mode.value != "creator")
            mode.on_value_change(on_mode)

            async def preview():
                p = pmap[radio.value]
                body = json.dumps({"type": "reread", "data": {"type": "reread", "username": "Streamer", "content": p["sample"]}}).encode()
                req = urllib.request.Request(api_url, data=body, headers={"Content-Type": "application/json"})
                try:
                    await asyncio.to_thread(urllib.request.urlopen, req, None, 10)
                    ui.notify("Sent to the streamer (it speaks with the voice currently active; Save and restart to switch voice).", type="info")
                except Exception as e:
                    ui.notify(f"The app is not running yet: {e}", type="warning")
            ui.button("Speak a sample line", on_click=preview).props("outline")

            # ---- Sound like me (clone the host's own voice; consent first)
            with ui.expansion("Sound like me (use your own voice)", icon="mic").classes("w-full"):
                ui.label("Record 3 to 8 seconds of you speaking Vietnamese clearly (a .wav is best). The clip stays on this "
                         "computer and goes only to your local VieNeu voice server. Only clone your own voice, or one you "
                         "have permission to use.").classes("lv-sub")
                consent = ui.checkbox(my_voice.STATEMENT)
                voice_name = ui.input("Name for this voice", value=setup.get("own_voice") or "My voice").classes("w-64")
                clip = {"path": ""}

                def got_clip(e):
                    fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(e.name)[1] or ".wav")
                    with os.fdopen(fd, "wb") as f:
                        f.write(e.content.read())
                    clip["path"] = tmp
                    voice_note.text = f"Got {e.name}."
                ui.upload(on_upload=got_clip, auto_upload=True, max_files=1).props("accept=.wav,.mp3,.m4a,.flac,.ogg flat bordered").classes("w-80")
                voice_note = ui.label("").classes("lv-chip")
                voice_note.bind_visibility_from(voice_note, "text", backward=bool)

                async def make_voice():
                    if not clip["path"]:
                        voice_note.text = "Add a clip first."
                        return
                    vcfg = dict(config.get("vieneu") or {})
                    ok, msg = await asyncio.to_thread(my_voice.enroll_own_voice, voice_name.value.strip(), clip["path"],
                                                      bool(consent.value), vcfg)
                    voice_note.text = msg
                    if ok:
                        setup["own_voice"] = voice_name.value.strip()
                        setup_wizard.save_setup(setup)
                        ui.notify("Voice created. Press 'Save and run dry run' on the Check step, then restart to use it.", type="positive")
                with ui.row():
                    btn = ui.button("Create my voice", on_click=make_voice).props("unelevated no-caps")
                    btn.bind_enabled_from(consent, "value")
                    ui.button("Use a built-in voice again", on_click=lambda: (setup.update(own_voice=""), setup_wizard.save_setup(setup),
                              ui.notify("Back to the persona voice after the next save."))).props("flat no-caps")
            with ui.stepper_navigation():
                ui.button("Next", on_click=stepper.next)
                ui.button("Back", on_click=stepper.previous).props("flat")

        # ------------------------------------------------------------------ 4 check
        with ui.step("Check"):
            ui.label("Dry run: what the bot does with demo viewers (spam, contact requests, price questions, buying signals).")
            out = ui.log().classes("w-full h-64")

            def save_answers():
                answers = dict(setup, shop_name=shop.value or "", tiktok_username=setup_wizard.clean_username(user.value),
                               persona_id=radio.value, gifts=gifts.value, joins=joins.value,
                               mode=mode.value, returning_viewers=bool(returning_sw.value),
                               auto_tour=bool(setup.get("auto_tour", True)) and mode.value != "creator")
                setup_wizard.save_setup(answers)
                changes = setup_wizard.apply_setup(cfg_path, products_path, personas_path, answers)
                return answers, changes

            def dry_run():
                out.clear()
                answers, changes = save_answers()
                for c in changes:
                    out.push("saved: " + c)
                safety = tiktok_safety.TikTokSafety(terms_path)
                catalog = product_catalog.ProductCatalog(products_path, templates_path)
                for s in json.load(open(scenario_path, encoding="utf-8"))["steps"]:
                    if s["type"] != "comment":
                        continue
                    r = simulator.evaluate_comment(s["data"]["content"], safety, catalog)
                    out.push(f"[{r['verdict']}] {r['text']}")
                    if r["reply"]:
                        out.push("    -> " + r["reply"])
                out.push("Settings saved. Restart the app so the new voice and persona are used.")
            ui.button("Save and run dry run", on_click=dry_run)
            ui.label("Reminder: choose your LLM (chat_type) and its API key in the Chat tab; simple price/size/shipping questions work without one.").classes("text-caption")
            with ui.stepper_navigation():
                ui.button("Next", on_click=stepper.next)
                ui.button("Back", on_click=stepper.previous).props("flat")

        # ------------------------------------------------------------------ 5 go live
        with ui.step("Go live"):
            ui.label("Make sure the app is running (python main.py), then start the bridge. The seller must already be LIVE on TikTok.")
            status = ui.label("")
            logbox = ui.log().classes("w-full h-40")
            auto_tour = ui.switch("Also start the product tour (introduces every product in a loop)", value=setup["auto_tour"])
            with ui.row().classes("items-center"):
                tour_min = ui.number("Min minutes per product", value=setup.get("tour_min_minutes", 5), min=1, max=60, format="%.0f").classes("w-48")
                tour_max = ui.number("Max minutes per product", value=setup.get("tour_max_minutes", 10), min=1, max=60, format="%.0f").classes("w-48")
                tour_quiet = ui.number("Resume after quiet (s)", value=setup.get("tour_quiet", 2), min=1, max=30, format="%.0f").classes("w-48")
            ui.label("The host presents each product for a random time in that range, repeating its script until time is up. "
                     "Viewer comments always go first; after the answer, it resumes where it stopped once chat is quiet.").classes("lv-sub")

            def refresh():
                status.text = f"Bridge: {'RUNNING' if PM.running('bridge') else 'stopped'}   |   Tour: {'RUNNING' if PM.running('tour') else 'stopped'}"
                logbox.clear()
                for line in setup_wizard.tail(os.path.join(ROOT, "log", "bridge.log"), 8).splitlines():
                    logbox.push(line)

            async def start():
                answers = setup_wizard.load_setup()
                if setup_wizard.validate(answers):
                    ui.notify("Finish step 1 and save in step 4 first.", type="warning")
                    return
                try:
                    py = await asyncio.to_thread(setup_wizard.ensure_bridge_env, ROOT)
                except Exception as e:
                    ui.notify(f"Could not prepare the TikTok bridge environment: {e}", type="negative")
                    return
                PM.start("bridge", setup_wizard.bridge_command(answers, py))
                answers.update({"tour_min_minutes": tour_min.value or 5, "tour_max_minutes": tour_max.value or 10,
                                "tour_quiet": tour_quiet.value or 2})
                setup_wizard.save_setup(answers)
                if auto_tour.value and answers.get("mode") != "creator":
                    PM.start("tour", setup_wizard.tour_command(answers))
                ui.notify("Started. Watch the log below.", type="positive")
                refresh()

            def stop():
                PM.stop_all()
                ui.notify("Stopped.", type="info")
                refresh()
            with ui.row():
                ui.button("Start", on_click=start).props("color=positive")
                ui.button("Stop", on_click=stop).props("color=negative")
            ui.timer(3.0, refresh)
            with ui.stepper_navigation():
                ui.button("Back", on_click=stepper.previous).props("flat")
