"""
"Live tools" tab: flash sale, giveaway and poll controls. The live app reads data/flash_sale.json and data/engage.json
every few seconds, counts entries / votes and speaks the announcements.
"""
import os
import time

from nicegui import ui

from . import engage, flash_sale, product_catalog
from .webui_theme import page_title

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENGAGE_PATH = os.path.join(ROOT, engage.DEFAULT_PATH)


def _flash_card(config):
    products_path = os.path.join(ROOT, config.get("products", "path") or "data/products.json")
    templates_path = os.path.join(ROOT, config.get("products", "templates_path") or "data/pitch_templates.json")
    sale_path = os.path.join(ROOT, config.get("products", "flash_sale_path") or flash_sale.DEFAULT_PATH)
    try:
        catalog = product_catalog.ProductCatalog(products_path, templates_path)
    except Exception as e:
        with ui.card().classes("lv-card w-full").style("padding:20px"):
            ui.label("Flash sale").style("font-weight:700;font-size:16px")
            ui.label(f"Needs a product catalog first ({e}). Add products in the Products tab.").classes("lv-sub")
        return
    options = {p["id"]: f"{p.get('order', '')}. {p['name']}" for p in catalog.all_products()}
    with ui.card().classes("lv-card w-full").style("padding:20px"):
        ui.label("Flash sale").style("font-weight:700;font-size:16px")
        ui.label("The AI announces the time left, the price and (only if you enter it) the stock. It never invents scarcity.").classes("lv-sub")
        with ui.row().classes("items-end"):
            prod = ui.select(options, label="Product", value=next(iter(options), None)).classes("w-64")
            minutes = ui.number("Minutes", value=15, min=1, max=240).classes("w-28")
            price = ui.input("Sale price (optional)").classes("w-40")
            stock = ui.number("Stock left (optional)", value=None, min=1).classes("w-40")
            every = ui.number("Remind every (min)", value=5, min=1, max=30).classes("w-40")
        status = ui.label("").classes("lv-chip")

        def start():
            if not prod.value:
                ui.notify("Pick a product", type="warning")
                return
            flash_sale.start_sale(sale_path, prod.value, float(minutes.value), price.value or "",
                                  int(stock.value) if stock.value else None, float(every.value or 5))
            ui.notify("Flash sale started; the AI will announce it within a few seconds.", type="positive")
            refresh()

        def stop():
            flash_sale.stop_sale(sale_path)
            ui.notify("Flash sale stopped.", type="info")
            refresh()

        def refresh():
            st = flash_sale.load_state(sale_path)
            if st and st.get("active"):
                left = max(0, int((st["ends_at"] - time.time()) / 60))
                status.text = f"ACTIVE: {options.get(st['product_id'], st['product_id'])}, about {left} min left"
            else:
                status.text = "No flash sale running."

        with ui.row():
            ui.button("Start flash sale", on_click=start).props("color=positive")
            ui.button("Stop", on_click=stop).props("color=negative")
        ui.timer(5.0, refresh)
        refresh()


def _giveaway_card():
    with ui.card().classes("lv-card w-full").style("padding:20px"):
        ui.label("Giveaway").style("font-weight:700;font-size:16px")
        ui.label("Viewers comment your keyword to enter (one entry each). The AI announces it, reminds, then draws "
                 "uniformly at random and says how many entered. Check TikTok's rules for giveaways and give the real prize.").classes("lv-sub")
        with ui.row().classes("items-end"):
            keyword = ui.input("Keyword viewers type", value="tham gia").classes("w-44")
            prize = ui.input("Prize", placeholder="e.g. a free tote bag").classes("w-64")
            minutes = ui.number("Minutes", value=5, min=1, max=60).classes("w-28")
            winners = ui.number("Winners", value=1, min=1, max=5).classes("w-28")
        status = ui.label("").classes("lv-chip")
        result = ui.label("").style("font-weight:600")

        def start():
            try:
                st = engage.load_state(ENGAGE_PATH)
                engage.start_giveaway(st, keyword.value, prize.value, float(minutes.value or 5), int(winners.value or 1))
                engage.save_state(st, ENGAGE_PATH)
            except ValueError as e:
                ui.notify(str(e), type="warning")
                return
            ui.notify("Giveaway started; the AI announces it within a few seconds.", type="positive")
            refresh()

        def stop():
            st = engage.stop(engage.load_state(ENGAGE_PATH), "giveaway")
            engage.save_state(st, ENGAGE_PATH)
            ui.notify("Giveaway stopped (no draw).", type="info")
            refresh()

        def refresh():
            g = engage.load_state(ENGAGE_PATH).get("giveaway")
            result.text = ""
            if not g:
                status.text = "No giveaway yet."
            elif g.get("active"):
                left = max(0, int((g["ends_at"] - time.time()) / 60))
                status.text = f"ACTIVE: \"{g['keyword']}\" for {g['prize']}, {len(g['entrants'])} entered, about {left} min left"
            elif g.get("drawn"):
                status.text = f"Finished: {len(g['entrants'])} entered."
                result.text = ("Winner(s): " + ", ".join(g["winners"])) if g["winners"] else "Nobody entered."
            else:
                status.text = "Stopped without a draw."
        with ui.row():
            ui.button("Start giveaway", on_click=start).props("color=positive")
            ui.button("Stop", on_click=stop).props("color=negative")
        ui.timer(3.0, refresh)
        refresh()


def _poll_card():
    with ui.card().classes("lv-card w-full").style("padding:20px"):
        ui.label("Poll").style("font-weight:700;font-size:16px")
        ui.label("Viewers comment the option number (1 to 4). One vote each, the first vote counts. The AI announces the result.").classes("lv-sub")
        question = ui.input("Question", placeholder="Which colour next live?").classes("w-full")
        options = ui.textarea("Options (one per line, 2 to 4)", placeholder="Black\nWhite").classes("w-full")
        minutes = ui.number("Minutes", value=3, min=1, max=30).classes("w-28")
        status = ui.label("").classes("lv-chip")

        def start():
            try:
                st = engage.load_state(ENGAGE_PATH)
                engage.start_poll(st, question.value, (options.value or "").splitlines(), float(minutes.value or 3))
                engage.save_state(st, ENGAGE_PATH)
            except ValueError as e:
                ui.notify(str(e), type="warning")
                return
            ui.notify("Poll started; the AI announces it within a few seconds.", type="positive")
            refresh()

        def stop():
            st = engage.stop(engage.load_state(ENGAGE_PATH), "poll")
            engage.save_state(st, ENGAGE_PATH)
            ui.notify("Poll stopped.", type="info")
            refresh()

        def refresh():
            p = engage.load_state(ENGAGE_PATH).get("poll")
            if not p:
                status.text = "No poll yet."
                return
            counts = ", ".join(f"{o}: {c}" for o, c in zip(p["options"], engage.tally(p)))
            status.text = ("ACTIVE. " if p.get("active") else "Finished. ") + counts
        with ui.row():
            ui.button("Start poll", on_click=start).props("color=positive")
            ui.button("Stop", on_click=stop).props("color=negative")
        ui.timer(3.0, refresh)
        refresh()


def _sales_card():
    from . import sales
    cfg = sales.load_settings()
    with ui.card().classes("lv-card w-full").style("padding:20px"):
        ui.label("Thank the room for sales").style("font-weight:700;font-size:16px")
        ui.label("TikTok never tells us who bought, only a sold counter per product. When that counter really goes up, "
                 "the host thanks everyone (no names, no made-up numbers). Off by default.").classes("lv-sub")
        with ui.row().classes("items-end"):
            on = ui.switch("Thank the room when sales go up", value=cfg["enable"])
            step = ui.number("At least this many new sales", value=cfg["step"], min=1, max=100).classes("w-52")
            cool = ui.number("Not more often than (seconds)", value=cfg["cooldown"], min=30, max=900).classes("w-56")
        note = ui.label("").classes("lv-chip")
        note.bind_visibility_from(note, "text", backward=bool)

        def save():
            sales.save_settings({"enable": bool(on.value), "step": int(step.value or 5),
                                 "cooldown": int(cool.value or 120)})
            note.text = "Saved. " + ("On" if on.value else "Off")
        ui.button("Save", on_click=save).props("unelevated no-caps")


def _fallback_card(config):
    import asyncio, json, urllib.request
    from . import bridge_health
    api = f"http://127.0.0.1:{config.get('api_port') or 8082}/send"
    with ui.card().classes("lv-card w-full").style("padding:20px"):
        ui.label("If the TikTok connection breaks").style("font-weight:700;font-size:16px")
        health = ui.label("").style("font-weight:600")
        ui.label("TikTok can change things without warning and the chat library we use is unofficial. Two backups: type the "
                 "question yourself below, or use the browser relay (tools/tiktok_chat_relay.user.js, instructions inside the file).").classes("lv-sub")
        with ui.row().classes("items-end w-full").style("flex-wrap:nowrap"):
            who = ui.input("Viewer name", value="viewer").classes("w-40")
            msg = ui.input("Ask the host as a viewer", placeholder="e.g. ao size M con khong shop?").classes("grow")

        async def ask():
            text = (msg.value or "").strip()
            if not text:
                return
            body = json.dumps({"type": "comment", "data": {"platform": "manual", "username": (who.value or "viewer").strip(),
                                                          "content": text}}).encode()
            req = urllib.request.Request(api, data=body, headers={"Content-Type": "application/json"})
            try:
                await asyncio.to_thread(urllib.request.urlopen, req, None, 10)
                msg.value = ""
                ui.notify("Sent to the host.", type="positive")
            except Exception as e:
                ui.notify(f"The app is not running: {e}", type="warning")
        msg.on("keydown.enter", ask)
        ui.button("Send", on_click=ask).props("unelevated no-caps")

        def refresh():
            r = bridge_health.assess(bridge_health.read())
            health.text = r["message"]
            health.style("color:" + {"ok": "#22c55e", "warn": "#f59e0b", "down": "#ef4444", "off": "var(--lv-muted)"}[r["level"]])
        ui.timer(5.0, refresh)
        refresh()


def _overlay_card(config):
    port = (config.get("webui", "port") or 8081)
    url = f"http://127.0.0.1:{port}/overlay"
    with ui.card().classes("lv-card w-full").style("padding:20px"):
        ui.label("Show these on screen").style("font-weight:700;font-size:16px")
        ui.label("Giveaway, poll and flash-sale countdowns appear as a transparent panel. In TikTok LIVE Studio or OBS add a "
                 "Browser / Link source with this address, bottom-left of your scene. It only shows what is running right now.").classes("lv-sub")
        with ui.row().classes("items-center"):
            ui.input(value=url).props("readonly").classes("w-80")
            ui.button("Copy", icon="content_copy",
                      on_click=lambda: (ui.run_javascript("navigator.clipboard.writeText(" + __import__("json").dumps(url) + ")"),
                                        ui.notify("Copied", type="positive"))).props("flat no-caps color=primary")
            ui.button("Open preview", icon="open_in_new", on_click=lambda: ui.run_javascript(
                "window.open(" + __import__("json").dumps(url) + ")")).props("flat no-caps")


def build_tools_tab(config):
    page_title("Live tools", "Flash sales, giveaways and polls that the AI host runs for you. Every line goes through the TikTok safety filter.")
    _flash_card(config)
    with ui.row().classes("w-full").style("gap:16px;flex-wrap:wrap;margin-top:16px;align-items:flex-start"):
        with ui.column().style("flex:1;min-width:320px"):
            _giveaway_card()
        with ui.column().style("flex:1;min-width:320px"):
            _poll_card()
    with ui.column().classes("w-full").style("margin-top:16px"):
        _sales_card()
    with ui.column().classes("w-full").style("margin-top:16px"):
        _overlay_card(config)
    with ui.column().classes("w-full").style("margin-top:16px"):
        from .webui_music import music_card
        music_card(config)
    with ui.column().classes("w-full").style("margin-top:16px"):
        _fallback_card(config)
