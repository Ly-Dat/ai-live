"""'Schedule' tab: live-room templates (one click) and coverage hours (when you host vs when the AI hosts)."""
import datetime as dt
import os

from nicegui import ui

from . import coverage, live_analytics, live_templates, personas, setup_wizard
from .webui_theme import page_title

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _templates_section(config):
    cfg_path = os.path.join(ROOT, "config.json")
    products_path = os.path.join(ROOT, config.get("products", "path") or "data/products.json")
    personas_path = os.path.join(ROOT, "data", "personas.json")
    all_templates = live_templates.load(os.path.join(ROOT, live_templates.PATH))
    pmap = {p["id"]: p["name"] for p in personas.load(personas_path).get("personas", [])}

    ui.label("Live templates").style("font-weight:700;font-size:18px;margin-top:4px")
    ui.label("One click sets the host, the product tour pace and who gets greeted for a kind of live. Nothing starts by itself: "
             "prizes and discounts stay yours to enter in Live tools.").classes("lv-sub")

    @ui.refreshable
    def grid():
        setup = setup_wizard.load_setup()
        with ui.row().classes("w-full").style("gap:14px;flex-wrap:wrap"):
            for t in all_templates:
                _, changes = live_templates.apply(setup, t)
                active = not changes
                with ui.card().classes("lv-card").style("padding:16px;width:290px;gap:6px"):
                    with ui.row().classes("items-center").style("gap:8px"):
                        ui.icon(t.get("icon", "bolt")).style("color:var(--lv-accent,#8b5cf6);font-size:22px")
                        ui.label(t["name"]).style("font-weight:700;font-size:15px")
                        if active:
                            ui.label("Active").classes("lv-chip hot")
                    ui.label(("For creators. " if t["mode"] == "creator" else "") + t["description"]).classes("lv-sub").style("margin:0;min-height:60px")
                    ui.label(f"Host: {pmap.get(t['persona_id'], t['persona_id'])}").style("font-size:12px;opacity:.8")
                    ui.button("Using this" if active else "Use this", icon="check" if active else "play_arrow",
                              on_click=lambda t=t: confirm(t)).props("unelevated no-caps" + (" disable" if active else ""))

    def confirm(t):
        setup = setup_wizard.load_setup()
        new, changes = live_templates.apply(setup, t)
        with ui.dialog() as dlg, ui.card().classes("w-[34rem]"):
            ui.label(f"Use '{t['name']}'?").classes("text-bold")
            if changes:
                ui.label("This changes:")
                for label, old, newv in changes:
                    shown_old = pmap.get(old, old) if label == "Host" else old
                    shown_new = pmap.get(newv, newv) if label == "Host" else newv
                    ui.label(f"- {label}: {live_templates.show(shown_old)} -> {live_templates.show(shown_new)}")
            if t.get("ideas"):
                ui.label("Ideas for this kind of live:").classes("text-bold").style("margin-top:8px")
                for i in t["ideas"]:
                    ui.label("- " + i)
            ui.label("The new host is used the next time the app starts.").classes("lv-sub")

            def do():
                new_setup, _ = live_templates.apply(setup_wizard.load_setup(), t)
                setup_wizard.save_setup(new_setup)
                answers = dict(new_setup)
                answers["tiktok_username"] = new_setup.get("tiktok_username") or config.get("room_display_id") or ""
                try:
                    setup_wizard.apply_setup(cfg_path, products_path, personas_path, answers)
                except Exception as e:
                    ui.notify(f"Saved the template, but could not update config.json: {e}", type="warning")
                dlg.close()
                ui.notify(f"'{t['name']}' is set. Restart the app to use the new host.", type="positive")
                ui.run_javascript("setTimeout(()=>location.reload(),1200)")
            with ui.row():
                ui.button("Use it", on_click=do).props("unelevated no-caps")
                ui.button("Cancel", on_click=dlg.close).props("flat no-caps")
        dlg.open()

    grid()


def _coverage_section(config):
    log_dir = config.get("analytics", "dir") or "log/analytics"
    state = {"cfg": coverage.load()}

    ui.label("Coverage: you or the AI").style("font-weight:700;font-size:18px;margin-top:28px")
    ui.label("Mark the hours you will be on camera. Then the AI hosts the rest and stays quiet during yours: no tour, no "
             "spoken replies, no thank-yous over your voice. Questions viewers ask during your hours are kept for you below. "
             "Giveaways, polls and flash sales you start yourself still run.").classes("lv-sub")

    with ui.card().classes("lv-card w-full").style("padding:18px;gap:10px"):
        now_label = ui.label("").style("font-weight:700;font-size:16px")
        enabled = ui.switch("Use coverage hours", value=state["cfg"]["enabled"])

        @ui.refreshable
        def windows():
            ws = state["cfg"]["human_windows"]
            if not ws:
                ui.label("No hours yet. Add the hours you will be live yourself.").classes("lv-sub")
            for i, w in enumerate(ws):
                with ui.row().classes("items-center").style("gap:10px"):
                    ui.icon("person").style("opacity:.7")
                    ui.label(coverage.describe(w))
                    ui.button(icon="delete", on_click=lambda i=i: remove(i)).props("flat round dense color=negative")

        def persist():
            state["cfg"]["enabled"] = bool(enabled.value)
            coverage.save(state["cfg"])
            update_now()

        def remove(i):
            state["cfg"]["human_windows"].pop(i)
            persist()
            windows.refresh()

        enabled.on_value_change(lambda e: persist())
        windows()
        ui.separator()
        ui.label("Add your hours").classes("text-bold")
        with ui.row().classes("items-end").style("gap:12px;flex-wrap:wrap"):
            with ui.row().classes("items-center").style("gap:2px"):
                day_boxes = {i: ui.checkbox(n, value=i < 5) for i, n in enumerate(coverage.DAY_NAMES)}
            start = ui.input("From (24h)", value="19:00").classes("w-28")
            end = ui.input("To (24h)", value="23:00").classes("w-28")

            def add():
                try:
                    w = coverage.clean_window({"days": [i for i, cb in day_boxes.items() if cb.value], "start": start.value, "end": end.value})
                except ValueError as e:
                    ui.notify(str(e), type="warning")
                    return
                state["cfg"]["human_windows"].append(w)
                if not enabled.value:
                    enabled.value = True
                persist()
                windows.refresh()
            ui.button("Add", icon="add", on_click=add).props("unelevated no-caps")
        ui.label("Times use this computer's clock. A window can cross midnight (22:00 to 02:00).").classes("lv-sub").style("font-size:12px")

        def update_now():
            s = coverage.status(state["cfg"])
            if not state["cfg"]["enabled"] or not state["cfg"]["human_windows"]:
                now_label.text = "Coverage is off: the AI hosts whenever the app runs."
                return
            when = (" until " + s["until"] + (" tomorrow" if s["day_offset"] == 1 else (f" (+{s['day_offset']} days)" if s["day_offset"] > 1 else ""))) if s["until"] else ""
            now_label.text = ("Right now: you are hosting, the AI is quiet" if s["who"] == "human" else "Right now: the AI is hosting") + when + "."
        ui.timer(15.0, update_now)
        update_now()

    ui.label("Asked while you were hosting").style("font-weight:700;font-size:16px;margin-top:18px")

    @ui.refreshable
    def asked():
        path = live_analytics.latest_session_file(log_dir)
        rows = coverage.handoff_questions(live_analytics.load_events(path)) if path else []
        if not rows:
            ui.label("Nothing yet. Questions that arrive during your hours show up here.").classes("lv-sub")
            return
        with ui.card().classes("lv-card w-full").style("padding:14px;gap:6px"):
            for r in rows:
                with ui.row().classes("items-center").style("gap:8px;flex-wrap:nowrap"):
                    ui.label(dt.datetime.fromtimestamp(r["ts"]).strftime("%H:%M")).classes("lv-chip")
                    if r["intent"] != "chat":
                        ui.label(r["intent"]).classes("lv-chip hot")
                    ui.label(r["text"]).style("min-width:0")
            ui.label("Teach the host the answers in the Teach tab so it can reply next time.").classes("lv-sub").style("font-size:12px")
    asked()
    ui.timer(15.0, asked.refresh)


def build_schedule_tab(config):
    page_title("Schedule", "Pick a template for the kind of live you are doing, and set the hours you host yourself.")
    _templates_section(config)
    _coverage_section(config)
