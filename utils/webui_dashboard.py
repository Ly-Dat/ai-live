"""
"Dashboard" tab for the web UI: live numbers from the newest analytics session (log/analytics/*.jsonl).

The web UI and the live app are separate processes, so the dashboard just re-reads the session file every few seconds.
"""
import json
import os

from nicegui import ui

from . import live_analytics


def build_dashboard_tab(config):
    log_dir = config.get("analytics", "dir") or "log/analytics"
    products_path = config.get("products", "path") or "data/products.json"

    def names():
        try:
            data = json.load(open(products_path, encoding="utf-8"))
            return {p["id"]: p["name"] for p in data.get("products", [])}, data.get("shop_name", "")
        except Exception:
            return {}, ""

    ui.label("Live dashboard").classes("text-h6")
    status = ui.label("").classes("text-caption")
    with ui.row().classes("w-full"):
        tiles = {}
        for key, label in [("comments", "Comments"), ("unique_viewers", "Viewers who commented"),
                           ("sales_comments", "Shopping questions"), ("buy_intent", "Buying signals"),
                           ("answered", "AI answers"), ("blocked", "Blocked by filter")]:
            with ui.card().classes("w-40"):
                ui.label(label).classes("text-caption")
                tiles[key] = ui.label("0").classes("text-h5")
    ui.label("Product interest").classes("text-subtitle1")
    interest = ui.table(columns=[
        {"name": "p", "label": "Product", "field": "p", "align": "left"},
        {"name": "n", "label": "Questions", "field": "n"},
        {"name": "d", "label": "Breakdown", "field": "d", "align": "left"},
    ], rows=[], row_key="p").classes("w-full")
    ui.label("Compliance log").classes("text-subtitle1")
    comp = ui.table(columns=[
        {"name": "c", "label": "Category", "field": "c", "align": "left"},
        {"name": "n", "label": "Hits", "field": "n"},
    ], rows=[], row_key="c").classes("w-full")
    hot = ui.label("").classes("text-subtitle2")

    def refresh():
        path = live_analytics.latest_session_file(log_dir)
        if not path:
            status.set_text("No session recorded yet. Start a live and this fills in automatically.")
            return
        s = live_analytics.summarize(live_analytics.load_events(path))
        nm, _ = names()
        status.set_text(f"Session file: {os.path.basename(path)} | {s['duration_min']} min")
        for k, t in tiles.items():
            t.set_text(str(s[k]))
        interest.rows = [{"p": nm.get(pid, pid), "n": sum(c.values()),
                          "d": ", ".join(f"{k}: {v}" for k, v in c.items())} for pid, c in s["product_interest"].items()]
        comp.rows = [{"c": k, "n": v} for k, v in s["blocked_by_category"].items()]
        hot.set_text("Hot right now: " + (", ".join(nm.get(p, p) for p in s["hot_products"]) or "-"))
        interest.update(); comp.update()

    def export():
        path = live_analytics.latest_session_file(log_dir)
        if not path:
            ui.notify("Nothing to export yet", type="warning"); return
        nm, shop = names()
        md = live_analytics.report_markdown(live_analytics.summarize(live_analytics.load_events(path)), nm, shop)
        out = path.replace(".jsonl", "-report.md")
        open(out, "w", encoding="utf-8").write(md)
        ui.notify(f"Report saved: {out}", type="positive")

    ui.button("Export report (.md)", on_click=export)
    ui.timer(5.0, refresh)
    refresh()
