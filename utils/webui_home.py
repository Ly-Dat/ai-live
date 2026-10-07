"""
"Home" tab: the first thing a seller sees. A greeting, a readiness checklist with one-click fixes, the last session at a
glance, quick actions and a tip. Everything refreshes every few seconds.
"""
import datetime
import json
import os
import time

from nicegui import app, ui

from . import bridge_health, habit, home_status, preflight, live_analytics, milestones, personas, recap, recap_card, setup_wizard, starter, webui_mascot
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
            "api_ok": port_open(config.get("api_port")), "bridge_on": PM.running("bridge"),
            "mode": setup.get("mode", "seller")}, shop, count, engine


def build_home_tab(config, go):
    """`go(tab_label)` switches to another tab ("Setup", "Products", "Voice", "Dashboard", "Live tools")."""
    log_dir = config.get("analytics", "dir") or "log/analytics"

    def pdata_shop():
        try:
            return json.load(open(config.get("products", "path") or "data/products.json", encoding="utf-8")).get("shop_name", "")
        except Exception:
            return ""

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
    def preflight_card():
        with ui.card().classes("lv-card w-full").style("padding:18px 20px"):
            ui.label("Pre-live check").style("font-weight:700;font-size:16px")
            box = ui.column().style("gap:6px;width:100%")

            def check():
                facts, _shop, count, engine = _facts(config)
                setup = setup_wizard.load_setup()
                nop = 0
                try:
                    data = json.load(open(config.get("products", "path") or "data/products.json", encoding="utf-8"))
                    nop = sum(1 for p in data.get("products", []) if p.get("active", True) and not p.get("price"))
                except Exception:
                    pass
                rows = preflight.run(dict(facts, engine=engine, no_price=nop, own_voice=setup.get("own_voice"),
                                          bridge_health=bridge_health.assess(bridge_health.read())))
                box.clear()
                with box:
                    ui.label(preflight.summary(rows)).style("font-weight:600")
                    for r in rows:
                        with ui.row().style("gap:8px;align-items:center;flex-wrap:nowrap"):
                            icon, color = {True: ("check_circle", "#22c55e"), False: ("error", "#ef4444"), None: ("info", "#f59e0b")}[r["ok"]]
                            ui.icon(icon).style(f"color:{color};font-size:20px")
                            with ui.column().style("gap:0;min-width:0"):
                                ui.label(r["label"]).style("font-size:14px")
                                if r["fix"]:
                                    ui.label(r["fix"]).classes("lv-sub").style("margin:0;font-size:12px")
                            if r["go"]:
                                ui.button("Fix", on_click=lambda g=r["go"]: go(g)).props("flat dense no-caps color=primary")
            ui.button("Check now", icon="fact_check", on_click=check).props("unelevated no-caps")
            check()
            ui.timer(10.0, check)

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
            ui.label("Your checklist for the next live is below.").classes("lv-sub").style("margin:0 0 4px;font-size:13px")
            def save_card():
                try:
                    st = recap_card.card_stats(s, names, setup_wizard.load_setup().get("shop_name") or pdata_shop(), run)
                    out = os.path.join("out", "recap-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".png")
                    recap_card.render_card(st, out)
                    with open(out, "rb") as fh:
                        ui.download(fh.read(), os.path.basename(out))
                    ui.notify("Recap image saved in the out folder and downloaded.", type="positive")
                except Exception as e:
                    ui.notify(f"Could not make the image: {e}", type="negative")

            with ui.row().style("gap:4px;margin-top:8px"):
                ui.button("Open dashboard", icon="arrow_forward", on_click=lambda: go("Dashboard")).props("flat no-caps color=primary")
                ui.button("Save recap image", icon="image", on_click=save_card).props("flat no-caps color=primary")

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

    def welcome_card():
        """First visit only: value before any setup. Hear the host, see the dry run, then continue."""
        files = [f for f in (os.listdir(log_dir) if os.path.isdir(log_dir) else []) if f.startswith("session-")]
        if files or setup_wizard.load_setup().get("welcome_dismissed"):
            return
        try:
            from .webui_voice import PREVIEW_DIR
            os.makedirs(PREVIEW_DIR, exist_ok=True)
            app.add_static_files("/lv_preview", PREVIEW_DIR)
            pdata = personas.load(os.path.join(setup_wizard.ROOT, "data", "personas.json"))
        except Exception:
            return
        mode = setup_wizard.load_setup().get("mode", "seller")
        plist = personas.for_mode(pdata, mode)
        if not plist:
            return
        pmap = {p["id"]: p for p in plist}
        current = setup_wizard.load_setup().get("persona_id")
        with ui.card().classes("lv-card w-full").style("padding:20px 22px;border:1px solid var(--lv-accent)") as box:
            with ui.row().classes("items-center justify-between w-full no-wrap"):
                with ui.column().style("gap:2px"):
                    ui.label("Welcome. Meet your AI host in 10 seconds").style("font-weight:800;font-size:18px")
                    ui.label("No account, no TikTok connection needed yet. Pick a style and listen.").classes("lv-sub").style("margin:0")
                ui.button(icon="close", on_click=lambda: dismiss()).props("flat round dense").tooltip("Hide this")
            pick = ui.select({pid: p["name"] for pid, p in pmap.items()}, value=current if current in pmap else next(iter(pmap)),
                             label="Host style").props("dense outlined").classes("w-full").style("margin-top:10px")
            blurb = ui.label(pmap[pick.value]["description"]).classes("lv-sub").style("margin:0 0 6px")
            slot = ui.element("div").classes("w-full")
            note = ui.label("").classes("lv-sub").style("margin:4px 0 0")

            def on_pick(e):
                blurb.set_text(pmap[pick.value]["description"])
                setup_wizard.save_setup(dict(setup_wizard.load_setup(), persona_id=pick.value))
            pick.on_value_change(on_pick)

            async def hear():
                p = pmap[pick.value]
                fname = f"welcome-{p['id']}.mp3"
                path = os.path.join(PREVIEW_DIR, fname)
                note.set_text("Preparing the voice...")
                try:
                    if not os.path.exists(path):
                        import edge_tts
                        await edge_tts.Communicate(text=p["sample"], voice=p["voice"], rate=p.get("rate", "+0%")).save(path)
                    slot.clear()
                    with slot:
                        ui.audio(f"/lv_preview/{fname}?t={int(time.time())}").props("controls autoplay").classes("w-full")
                    note.set_text(f"\u201c{p['sample']}\u201d")
                except Exception as e:
                    note.set_text(f"Could not play the preview (needs internet for edge-tts): {type(e).__name__}")

            with ui.row().style("gap:8px;margin-top:6px;flex-wrap:wrap"):
                ui.button("Hear your host", icon="play_arrow", on_click=hear).props("unelevated color=primary no-caps")
                ui.button("See how it handles viewers", icon="science", on_click=lambda: go("Setup")).props("outline no-caps")

            def dismiss():
                setup_wizard.save_setup(dict(setup_wizard.load_setup(), welcome_dismissed=True))
                box.set_visibility(False)

    @ui.refreshable
    def plan_card():
        path = live_analytics.latest_session_file(log_dir)
        files = [f for f in (os.listdir(log_dir) if os.path.isdir(log_dir) else []) if f.startswith("session-")]
        today = datetime.date.today()
        dates = recap.session_dates(files)
        goal_now = int(setup_wizard.load_setup().get("weekly_goal", 3) or 3)
        prog = habit.weekly_progress(dates, today, goal_now)
        plan_path = os.path.join("data", "next_live.json")
        with ui.card().classes("lv-card w-full").style("padding:18px 20px"):
            ui.label("Before your next live").style("font-weight:700;font-size:16px")
            try:
                from .webui_teach import pending_for
                n_teach = len(pending_for(config))
            except Exception:
                n_teach = 0
            if n_teach:
                ui.button(f"{n_teach} question(s) the host was not sure about", icon="school", on_click=lambda: go("Teach")).props("flat no-caps color=primary").style("margin:2px 0 4px")
            if not path:
                ui.label("After your first live, the things worth fixing show up here as a checklist.").classes("lv-sub").style("margin:4px 0 0")
            else:
                s = live_analytics.summarize(live_analytics.load_events(path))
                try:
                    pdata = json.load(open(config.get("products", "path") or "data/products.json", encoding="utf-8"))
                    names = {p["id"]: p["name"] for p in pdata.get("products", [])}
                except Exception:
                    names = {}
                key = os.path.basename(path)
                tasks = habit.next_live_tasks(recap.recap(s, names)["actions"], habit.load_plan(plan_path, key))

                def toggle(tid, value):
                    done = habit.load_plan(plan_path, key)
                    (done.add if value else done.discard)(tid)
                    habit.save_plan(plan_path, key, done)
                    plan_card.refresh()
                left = sum(1 for t in tasks if not t["done"])
                ui.label(("Nothing needed this time. Go live whenever you're ready." if not tasks else "All done. You're ready.") if not left else f"{left} thing(s) to do, about a minute each.").classes("lv-sub").style("margin:2px 0 6px")
                for t in tasks:
                    ui.checkbox(t["text"], value=t["done"], on_change=lambda e, i=t["id"]: toggle(i, e.value)).style("line-height:1.35;font-size:14px")
            ui.separator().style("margin:10px 0")
            with ui.row().classes("items-center justify-between w-full no-wrap"):
                ui.label("This week").classes("lv-stat-label")
                ui.select({n: f"Goal: {n} live{'s' if n > 1 else ''}" for n in range(1, 8)}, value=prog["goal"],
                          on_change=lambda e: (setup_wizard.save_setup(dict(setup_wizard.load_setup(), weekly_goal=int(e.value))), plan_card.refresh())
                          ).props("dense borderless").style("font-size:13px")
            with ui.row().style("gap:6px;margin:6px 0 2px"):
                for i in range(prog["goal"]):
                    ui.element("div").style("width:22px;height:22px;border-radius:50%;border:2px solid var(--lv-accent);"
                                            + ("background:var(--lv-grad);" if i < prog["done"] else ""))
            ui.label("Goal reached this week. Nice." if prog["hit"] else f"{prog['done']} of {prog['goal']} lives this week.").classes("lv-sub").style("margin:2px 0 0;font-size:13px")
            sessions = []
            for f in files:
                try:
                    sessions.append(live_analytics.summarize(live_analytics.load_events(os.path.join(log_dir, f))))
                except Exception:
                    pass
            bh = habit.best_hour(sessions)
            if bh:
                ui.label(f"Your lives starting around {bh['hour']:02d}:00 drew {bh['rate']} comments/min vs {bh['overall']} on average ({bh['n']} lives).").classes("lv-sub").style("margin:8px 0 0;font-size:13px")

    with ui.row().classes("w-full").style("gap:18px;flex-wrap:wrap;align-items:flex-start"):
        with ui.column().style("flex:3;min-width:320px;gap:0;position:relative;padding-top:46px"):
            with ui.element("div").style("position:absolute;top:0;right:24px;z-index:2;line-height:0"):
                webui_mascot.mascot("cat", 96)
            hero_and_steps()
        with ui.column().style("flex:2;min-width:300px;gap:16px"):
            welcome_card()
            preflight_card()
            last_session()
            progress_card()
            plan_card()
            with ui.card().classes("lv-card w-full").style("padding:18px 20px"):
                ui.label("Tip").classes("lv-stat-label")
                ui.label(home_status.tip(datetime.date.today().toordinal())).style("margin-top:6px;line-height:1.5")

    ui.label("Quick actions").style("font-weight:700;font-size:16px;margin:26px 0 10px")
    with ui.row().classes("w-full").style("gap:14px"):
        creator = setup_wizard.load_setup().get("mode") == "creator"
        actions = [
            ("tune", "Choose your host", "Chat persona and voice", "Setup"),
            ("record_voice_over", "Try a voice", "Free Vietnamese voices", "Voice"),
            ("rocket_launch", "Go live", "Start the TikTok bridge", "Setup"),
            ("insights", "See stats", "What viewers asked", "Dashboard"),
        ] if creator else [
            ("add_shopping_cart", "Add a product", "Cart, facts and pitch", "Products"),
            ("bolt", "Flash sale", "Timed announcements", "Live tools"),
            ("record_voice_over", "Try a voice", "Free Vietnamese voices", "Voice"),
            ("insights", "See stats", "What viewers asked", "Dashboard"),
        ]
        for icon, title, sub, tab in actions:
            with ui.card().classes("lv-card lv-action").style("flex:1 1 200px;padding:18px;cursor:pointer").on("click", lambda t=tab: go(t)):
                with ui.element("div").classes("lv-ico"):
                    ui.icon(icon)
                ui.label(title).style("font-weight:700")
                ui.label(sub).classes("lv-sub").style("margin:0;font-size:13px")

    ui.timer(30.0, plan_card.refresh)
    ui.timer(4.0, lambda: (hero_and_steps.refresh(), last_session.refresh(), progress_card.refresh()))
