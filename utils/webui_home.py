"""
"Home" tab: the first thing a seller sees. A greeting, a readiness checklist with one-click fixes, the last session at a
glance, quick actions and a tip. Everything refreshes every few seconds.
"""
import datetime
import json
import os

from nicegui import ui

from . import home_status, live_analytics, milestones, recap, setup_wizard, starter
from .webui_theme import port_open


def _facts(config):
    from .webui_setup import PM
    setup = setup_wizard.load_setup()
    products_path = config.get("products", "path") or "data/products.json"
    count, shop = 0, setup.get("shop_name") or ""
    try:
        data = json.load(open(products_path, encoding="utf-8"))
        count = sum(1 for p in data.get("products", []) if p.get("active", True))
        shop = shop or data.get("shop_name", "")
    except Exception:
        pass
    engine = config.get("audio_synthesis_type") or "edge-tts"
    voice_ok = True
    if engine == "vieneu":
        try:
            from . import vieneu_tts
            voice_ok = vieneu_tts.is_up((config.get("vieneu") or {}).get("api_url") or vieneu_tts.DEFAULT_URL)
        except Exception:
            voice_ok = False
    return {"tiktok_username": setup.get("tiktok_username"), "product_count": count, "voice_ok": voice_ok,
            "api_ok": port_open(config.get("api_port")), "bridge_on": PM.running("bridge")}, shop, count, engine


def build_home_tab(config, go):
    """`go(tab_label)` switches to another tab ("Setup", "Products", "Voice", "Dashboard", "Live tools")."""
    log_dir = config.get("analytics", "dir") or "log/analytics"

    def load_starter():
        path = config.get("products", "path") or "data/products.json"
        try:
            have = json.load(open(path, encoding="utf-8")).get("products")
        except Exception:
            have = None
        if have:
            ui.notify("You already have products; nothing was changed.", type="warning")
            return
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(starter.starter_catalog(), f, ensure_ascii=False, indent=2)
        ui.notify("3 sample products added. Replace them with yours any time in Products.", type="positive")
        hero_and_steps.refresh()

    @ui.refreshable
    def hero_and_steps():
        facts, shop, count, engine = _facts(config)
        items = home_status.checklist(facts)
        pct = home_status.progress(items)
        nxt = home_status.next_step(items)
        name = shop.strip() if shop else ""
        with ui.element("div").classes("lv-hero w-full"):
            with ui.row().classes("w-full items-center justify-between").style("gap:18px"):
                with ui.column().style("gap:4px;min-width:0"):
                    ui.label(home_status.greeting(datetime.datetime.now().hour, name)).classes("lv-title")
                    if nxt is None:
                        ui.label("Everything is connected. Your AI host is live and answering viewers.").style("opacity:.92")
                    else:
                        ui.label(f"{pct}% ready. Next: {nxt['label'].lower()}. {nxt['hint']}").style("opacity:.92")
                    ui.linear_progress(value=pct / 100, show_value=False, size="8px").props("color=white track-color=transparent rounded").style("margin-top:10px;max-width:420px")
                if nxt is None:
                    ui.button("Open live dashboard", on_click=lambda: go("Dashboard")).props("icon-right=insights unelevated color=white text-color=primary no-wrap").classes("lv-cta")
                else:
                    ui.button(f"Continue: {nxt['label']}", on_click=lambda t=nxt["tab"]: go(t)).props("icon-right=arrow_forward unelevated color=white text-color=primary no-wrap").classes("lv-cta")

        with ui.card().classes("lv-card w-full").style("padding:8px 20px;margin-top:18px"):
            for it in items:
                with ui.row().classes("items-center w-full no-wrap").style("padding:12px 0;gap:14px;border-bottom:1px solid var(--lv-border)"):
                    ui.icon("check_circle" if it["ok"] else "radio_button_unchecked").style(
                        "font-size:24px;color:" + ("var(--lv-good)" if it["ok"] else "var(--lv-muted)"))
                    with ui.column().style("gap:0;flex:1;min-width:0"):
                        ui.label(it["label"]).style("font-weight:700")
                        ui.label("Done" if it["ok"] else it["hint"]).classes("lv-sub").style("margin:0;font-size:13px")
                    if not it["ok"]:
                        if it["id"] == "products":
                            ui.button("Use 3 samples", on_click=load_starter).props("flat dense no-caps color=primary")
                        ui.button("Fix", on_click=lambda t=it["tab"]: go(t)).props("flat dense no-caps color=primary")
        return count, engine

    @ui.refreshable
    def last_session():
        path = live_analytics.latest_session_file(log_dir)
        with ui.card().classes("lv-card w-full").style("padding:18px 20px"):
            ui.label("Last live recap").style("font-weight:700;font-size:16px")
            if not path:
                with ui.column().classes("items-center w-full").style("padding:18px 0;gap:6px"):
                    ui.icon("insights").style("font-size:40px;color:var(--lv-muted)")
                    ui.label("No session yet").style("font-weight:600")
                    ui.label("Run the dry run in Setup to see how the host answers, or go live to start collecting stats.").classes("lv-sub").style("text-align:center;margin:0")
                    ui.button("Try the dry run", icon="science", on_click=lambda: go("Setup")).props("flat no-caps color=primary")
                return
            s = live_analytics.summarize(live_analytics.load_events(path))
            try:
                pdata = json.load(open(config.get("products", "path") or "data/products.json", encoding="utf-8"))
                names = {p["id"]: p["name"] for p in pdata.get("products", [])}
            except Exception:
                names = {}
            r = recap.recap(s, names)
            today = datetime.date.today()
            dates = recap.session_dates(os.listdir(log_dir))
            run, week = recap.streak(dates, today), recap.week_count(dates, today)
            with ui.row().style("gap:6px"):
                ui.label(f"{s['duration_min']} min").classes("lv-chip")
                if run >= 2:
                    ui.label(f"{run}-day streak").classes("lv-chip hot")
                ui.label(f"{week} live{'s' if week != 1 else ''} this week").classes("lv-chip")
            ui.label(r["headline"]).style("margin:10px 0 6px;font-weight:600")
            ui.label("Do this next live").classes("lv-stat-label").style("margin-top:6px")
            for t in r["tips"]:
                with ui.row().classes("no-wrap items-start").style("gap:8px;margin-top:6px"):
                    ui.icon("tips_and_updates").style("color:var(--lv-accent);font-size:18px;margin-top:2px")
                    ui.label(t).style("line-height:1.45;font-size:14px")
            ui.button("Open dashboard", icon="arrow_forward", on_click=lambda: go("Dashboard")).props("flat no-caps color=primary").style("margin-top:8px")

    @ui.refreshable
    def progress_card():
        files = [f for f in (os.listdir(log_dir) if os.path.isdir(log_dir) else []) if f.startswith("session-")]
        if not files:
            return
        sums = []
        for f in files:
            try:
                sums.append(live_analytics.summarize(live_analytics.load_events(os.path.join(log_dir, f))))
            except Exception:
                pass
        t = milestones.lifetime(sums)
        m = milestones.next_milestone(t)
        with ui.card().classes("lv-card w-full").style("padding:18px 20px"):
            ui.label("Your host so far").style("font-weight:700;font-size:16px")
            ui.label(f"{t['lives']} live(s), {t['hours']} h on air, {t['answered']} viewer answers.").classes("lv-sub").style("margin:0 0 8px")
            if m:
                ui.linear_progress(value=m["fraction"], show_value=False, size="8px").props("rounded")
                ui.label(f"{m['left']} more {m['noun']} to reach {m['goal']}.").classes("lv-sub").style("margin:6px 0 0;font-size:13px")

    with ui.row().classes("w-full").style("gap:18px;flex-wrap:wrap;align-items:flex-start"):
        with ui.column().style("flex:3;min-width:320px;gap:0"):
            hero_and_steps()
        with ui.column().style("flex:2;min-width:300px;gap:16px"):
            last_session()
            progress_card()
            with ui.card().classes("lv-card w-full").style("padding:18px 20px"):
                ui.label("Tip").classes("lv-stat-label")
                ui.label(home_status.tip(datetime.date.today().toordinal())).style("margin-top:6px;line-height:1.5")

    ui.label("Quick actions").style("font-weight:700;font-size:16px;margin:26px 0 10px")
    with ui.row().classes("w-full").style("gap:14px"):
        for icon, title, sub, tab in [
            ("add_shopping_cart", "Add a product", "Cart, facts and pitch", "Products"),
            ("bolt", "Flash sale", "Timed announcements", "Live tools"),
            ("record_voice_over", "Try a voice", "Free Vietnamese voices", "Voice"),
            ("insights", "See stats", "What viewers asked", "Dashboard"),
        ]:
            with ui.card().classes("lv-card lv-action").style("flex:1 1 200px;padding:18px;cursor:pointer").on("click", lambda t=tab: go(t)):
                with ui.element("div").classes("lv-ico"):
                    ui.icon(icon)
                ui.label(title).style("font-weight:700")
                ui.label(sub).classes("lv-sub").style("margin:0;font-size:13px")

    ui.timer(4.0, lambda: (hero_and_steps.refresh(), last_session.refresh(), progress_card.refresh()))
