"""
"Teach" tab: the questions the AI host was not sure about during your lives. Type the answer once; next time the host
says exactly that (through the TikTok safety filter). The more you teach, the less it has to say "I'm not sure".
"""
import json
import os

from nicegui import ui

from . import live_analytics, teach, tiktok_safety
from .webui_theme import page_title

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BOOK_PATH = os.path.join(ROOT, "data", "taught.json")


def pending_for(config, book=None, sessions: int = 10):
    """Unanswered questions from the newest session files (shared with the Home tab)."""
    log_dir = config.get("analytics", "dir") or "log/analytics"
    book = book or teach.TaughtBook(BOOK_PATH)
    events = []
    try:
        files = sorted(f for f in os.listdir(log_dir) if f.startswith("session-"))[-sessions:]
        for f in files:
            try:
                events += live_analytics.load_events(os.path.join(log_dir, f))
            except OSError:
                pass
    except OSError:
        pass
    return teach.pending(events, book)


def build_teach_tab(config):
    book = teach.TaughtBook(BOOK_PATH)
    products_path = config.get("products", "path") or "data/products.json"
    terms_path = os.path.join(ROOT, config.get("filter", "tiktok_safety", "terms_path") or "data/tiktok_policy_terms.json")
    try:
        names = {p["id"]: p["name"] for p in json.load(open(products_path, encoding="utf-8")).get("products", [])}
    except Exception:
        names = {}
    try:
        safety = tiktok_safety.TikTokSafety(terms_path)
    except Exception:
        safety = None

    def save(q, a, pid=None):
        a = (a or "").strip()
        if not a:
            ui.notify("Type the answer first.", type="warning")
            return False
        hits = safety.check(a, "output") if safety else []
        if hits:
            ui.notify("The host could not say this on TikTok (it would be filtered). Reword it: no contacts, links, "
                      "prices outside TikTok or absolute claims.", type="negative")
            return False
        book.add(q, a, pid)
        ui.notify("Taught. The host will use this answer from now on.", type="positive")
        return True

    page_title("Teach your host", "Questions the AI was not sure about. Answer once and it knows next time.")

    @ui.refreshable
    def inbox():
        items = pending_for(config, book)
        if not items:
            with ui.card().classes("lv-card w-full items-center").style("padding:30px;gap:6px"):
                ui.icon("school").style("font-size:44px;color:var(--lv-muted)")
                ui.label("Nothing to teach right now").style("font-weight:700;font-size:17px")
                ui.label("After a live, the questions the host was not sure about appear here, most asked first.").classes("lv-sub").style("margin:0;text-align:center")
            return
        ui.label(f"{len(items)} question(s) waiting").classes("lv-stat-label")
        for it in items:
            with ui.card().classes("lv-card w-full").style("padding:16px 18px;margin-top:10px"):
                with ui.row().classes("items-center").style("gap:8px"):
                    ui.label(f"“{it['q']}”").style("font-weight:700")
                    ui.label(f"asked {it['count']}x").classes("lv-chip")
                    if it.get("product_id") in names:
                        ui.label(names[it["product_id"]][:40]).classes("lv-chip")
                ans = ui.textarea(placeholder="Your answer, in the words the host should say (Vietnamese)").props("autogrow outlined dense").classes("w-full")
                only = None
                if it.get("product_id") in names:
                    only = ui.switch("Only for this product", value=True)
                with ui.row().style("gap:8px"):
                    def do_teach(it=it, ans=ans, only=only):
                        if save(it["q"], ans.value, it["product_id"] if (only is not None and only.value) else None):
                            inbox.refresh()
                            known.refresh()
                    ui.button("Teach", icon="check", on_click=do_teach).props("unelevated color=primary no-caps")
                    ui.button("Ignore", on_click=lambda it=it: (book.ignore(it["q"]), inbox.refresh())).props("flat no-caps color=grey")

    inbox()

    with ui.expansion("Add a question yourself", icon="add").classes("w-full").style("margin-top:14px"):
        q = ui.input("A question viewers ask", placeholder="Shop có ship đi Đà Nẵng không?").classes("w-full")
        a = ui.textarea("Your answer", placeholder="Shop ship toàn quốc, Đà Nẵng khoảng 3 ngày nha.").props("autogrow").classes("w-full")

        def add():
            if not (q.value or "").strip():
                ui.notify("Type the question first.", type="warning")
                return
            if save(q.value, a.value):
                q.value = a.value = ""
                known.refresh()
                inbox.refresh()
        ui.button("Add", icon="add", on_click=add).props("unelevated color=primary no-caps")

    @ui.refreshable
    def known():
        entries = book.entries()
        ui.label("What your host knows").style("font-weight:700;font-size:16px;margin:22px 0 4px")
        if not entries:
            ui.label("Nothing taught yet.").classes("lv-sub")
            return
        for e in reversed(entries):
            with ui.card().classes("lv-card w-full").style("padding:12px 16px;margin-top:8px"):
                with ui.row().classes("items-start justify-between w-full no-wrap"):
                    with ui.column().style("gap:2px;min-width:0"):
                        ui.label(e["q"]).style("font-weight:600")
                        ui.label(e["a"]).classes("lv-sub").style("margin:0")
                        if e.get("product_id") in names:
                            ui.label(names[e["product_id"]][:40]).classes("lv-chip")
                    ui.button(icon="delete", on_click=lambda e=e: (book.remove(e["q"]), known.refresh(), inbox.refresh())).props("flat round dense color=negative").tooltip("Forget this")
    known()

    last = {"sig": None}

    def poll():
        sig = tuple(i["key"] for i in pending_for(config, book))
        if last["sig"] is not None and sig != last["sig"]:
            inbox.refresh()
        last["sig"] = sig
    ui.timer(15.0, poll)
