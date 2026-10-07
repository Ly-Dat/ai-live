"""
"Dashboard" tab for the web UI: live numbers from the newest analytics session (log/analytics/*.jsonl).

The web UI and the live app are separate processes, so the dashboard just re-reads the session file every few seconds.
"""
import json
import os

from nicegui import ui

from . import live_analytics, moments
from .webui_theme import page_title, stat_card


def build_dashboard_tab(config):
    log_dir = config.get("analytics", "dir") or "log/analytics"
    products_path = config.get("products", "path") or "data/products.json"

    def names():
        try:
            data = json.load(open(products_path, encoding="utf-8"))
            return {p["id"]: p["name"] for p in data.get("products", [])}, data.get("shop_name", "")
        except Exception:
            return {}, ""

    page_title("Dashboard", "What viewers asked, what the AI answered, and what the compliance filter caught - updates every few seconds.")
    status = ui.label("").classes("lv-chip")
    empty = ui.card().classes("lv-card w-full items-center").style("padding:36px;margin-top:12px;gap:6px")
    with empty:
        ui.icon("insights").style("font-size:48px;color:var(--lv-muted)")
        ui.label("No live session yet").style("font-weight:700;font-size:18px")
        ui.label("Go live (or run the dry run in Setup) and this page fills in on its own: questions, buying signals, hot products and blocked comments.").classes("lv-sub").style("text-align:center;max-width:520px;margin:0")
    with ui.row().classes("w-full").style("gap:14px;margin-top:10px") as tiles_row:
        tiles = {}
        for key, label, icon in [("comments", "Comments", "chat_bubble"), ("unique_viewers", "Viewers", "groups"),
                                 ("sales_comments", "Shop questions", "shopping_cart"), ("buy_intent", "Buying signals", "local_fire_department"),
                                 ("answered", "AI answers", "smart_toy"), ("blocked", "Blocked", "shield")]:
            tiles[key] = stat_card(label, icon)
    hot = ui.label("").classes("lv-chip hot").style("margin:14px 0 0")
    with ui.row().classes("w-full").style("gap:16px;flex-wrap:nowrap;margin-top:14px;align-items:flex-start") as lower_row:
      with ui.card().classes("lv-card").style("flex:3;padding:16px;min-width:0"):
        ui.label("Product interest").style("font-weight:700;font-size:16px")
        interest = ui.table(columns=[
            {"name": "p", "label": "Product", "field": "p", "align": "left"},
            {"name": "n", "label": "Questions", "field": "n"},
            {"name": "d", "label": "Breakdown", "field": "d", "align": "left"},
        ], rows=[], row_key="p").classes("w-full").props("flat")
      with ui.card().classes("lv-card").style("flex:2;padding:16px;min-width:0"):
        ui.label("Compliance log").style("font-weight:700;font-size:16px")
        comp = ui.table(columns=[
            {"name": "c", "label": "Category", "field": "c", "align": "left"},
            {"name": "n", "label": "Hits", "field": "n"},
        ], rows=[], row_key="c").classes("w-full").props("flat")

    with ui.card().classes("lv-card w-full").style("padding:16px;margin-top:14px") as moments_card:
        ui.label("Best moments").style("font-weight:700;font-size:16px")
        ui.label("The busiest minutes of this live, counted from when the session started. Use them to find the spots in your "
                 "TikTok replay worth cutting into clips (the replay clock can differ by a few seconds or minutes).").classes("lv-sub")
        moments_box = ui.column().style("gap:6px;width:100%")
        copy_btn = ui.button("Copy list", icon="content_copy").props("flat no-caps color=primary")

    moments_state = {"text": ""}

    def copy_moments():
        ui.run_javascript("navigator.clipboard.writeText(" + json.dumps(moments_state["text"]) + ")")
        ui.notify("Copied", type="positive")
    copy_btn.on("click", copy_moments)

    def refresh():
        path = live_analytics.latest_session_file(log_dir)
        has = bool(path)
        for el in (tiles_row, hot, lower_row, export_btn, moments_card):
            el.set_visibility(has)   # no rows of zeros before the first live
        empty.set_visibility(not has)
        status.set_visibility(has)
        if not has:
            return
        try:
            s = live_analytics.summarize(live_analytics.load_events(path))
        except Exception as e:
            status.set_text(f"Could not read {os.path.basename(path)} ({type(e).__name__}); showing nothing for now.")
            return
        nm, _ = names()
        status.set_text(f"Session file: {os.path.basename(path)} | {s['duration_min']} min")
        for k, t in tiles.items():
            t.set_text(str(s[k]))
        interest.rows = [{"p": nm.get(pid, pid), "n": sum(c.values()),
                          "d": ", ".join(f"{k}: {v}" for k, v in c.items())} for pid, c in s["product_interest"].items()]
        comp.rows = [{"c": k, "n": v} for k, v in s["blocked_by_category"].items()]
        hot.set_text("Hot right now: " + (", ".join(nm.get(p, p) for p in s["hot_products"]) or "-"))
        interest.update(); comp.update()
        top = moments.best_moments(live_analytics.load_events(path))
        moments_box.clear()
        with moments_box:
            if not top:
                ui.label("Nothing stood out yet. Busy minutes show up here once chat picks up.").classes("lv-sub")
            for m in top:
                with ui.row().style("gap:10px;align-items:center;flex-wrap:nowrap"):
                    ui.label(m["at"]).classes("lv-chip hot").style("min-width:52px;text-align:center")
                    bits = [f"{m['comments']} comments"] + ([f"{m['buy']} buying signals"] if m["buy"] else []) + ([f"{m['gifts']} gifts"] if m["gifts"] else [])
                    ui.label(", ".join(bits) + (f'  "{m["sample"]}"' if m["sample"] else "")).style("min-width:0")
        copy_btn.set_visibility(bool(top))
        moments_state["text"] = moments.as_text(top)

    def export():
        path = live_analytics.latest_session_file(log_dir)
        if not path:
            ui.notify("Nothing to export yet", type="warning"); return
        nm, shop = names()
        md = live_analytics.report_markdown(live_analytics.summarize(live_analytics.load_events(path)), nm, shop)
        out = path.replace(".jsonl", "-report.md")
        open(out, "w", encoding="utf-8").write(md)
        ui.notify(f"Report saved: {out}", type="positive")

    export_btn = ui.button("Export report (.md)", icon="download", on_click=export).style("margin-top:16px")
    ui.timer(5.0, refresh)
    refresh()
