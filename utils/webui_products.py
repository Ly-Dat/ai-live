"""
"Products" tab for the web UI: view / edit / reorder the live-shop catalog (data/products.json) without touching JSON.

Usage inside webui.py (one call):
    from utils.webui_products import build_products_tab
    with ui.tab_panel(products_page).style(tab_panel_css):
        build_products_tab(config)

Features: product table, edit form (all catalog fields incl. FAQ), new / delete / move up-down, spreadsheet import
(CSV/XLSX), "Say pitch now" (sends the pitch to the running app), and a test box that shows the quick answer and the
TikTok safety verdict for any text.
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile

from nicegui import ui, run

from . import product_catalog, tiktok_safety

from .tiktok_fetch import fetch_tiktok_product, _download_images, _money, IMG_DIR

NEW_PRODUCT_DEFAULTS = {
    "shipping": "Shop gửi hàng qua TikTok Shop, thời gian giao tuỳ khu vực.",
    "return_policy": "Được đổi trả theo chính sách của TikTok Shop.",
    "stock_note": "Số lượng có hạn trong phiên live này.",
}

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _lines(text: str):
    return [x.strip() for x in (text or "").splitlines() if x.strip()]


def _faq_to_text(faq):
    return "\n".join(f"{qa.get('q', '')} || {qa.get('a', '')}" for qa in faq)


def _text_to_faq(text: str):
    out = []
    for line in _lines(text):
        if "||" in line:
            q, a = line.split("||", 1)
            if q.strip() and a.strip():
                out.append({"q": q.strip(), "a": a.strip()})
    return out


def build_products_tab(config):
    products_path = config.get("products", "path") or "data/products.json"
    templates_path = config.get("products", "templates_path") or "data/pitch_templates.json"
    terms_path = config.get("filter", "tiktok_safety", "terms_path") or "data/tiktok_policy_terms.json"
    api_url = f'http://127.0.0.1:{config.get("api_port")}/send'
    state = {"catalog": None, "selected": None}

    def load():
        state["catalog"] = product_catalog.ProductCatalog(products_path, templates_path)
        return state["catalog"]

    try:
        load()
    except Exception as e:
        ui.label(f"Cannot load {products_path}: {e}").classes('text-red')
        return

    columns = [
        {"name": "order", "label": "#", "field": "order", "align": "left", "sortable": True},
        {"name": "name", "label": "Name", "field": "name", "align": "left"},
        {"name": "price", "label": "Price", "field": "price", "align": "left"},
        {"name": "status", "label": "Status", "field": "status", "align": "left"},
    ]

    def rows():
        out = []
        for i, p in enumerate(state["catalog"].products):
            flags = []
            if not p.get("active", True):
                flags.append("inactive")
            if p.get("auto_imported"):
                flags.append("auto-imported")
            out.append({"idx": i, "order": p.get("order", i + 1), "name": p.get("name", ""),
                        "price": p.get("price", ""), "status": ", ".join(flags) or "ok"})
        return out

    def refresh_table():
        table.rows = rows()
        table.update()

    with ui.row().classes('w-full items-start no-wrap'):
        with ui.column().classes('w-1/2'):
            ui.label('Cart products (in the order the streamer introduces them)').classes('text-bold')
            table = ui.table(columns=columns, rows=rows(), row_key='idx', selection='single').classes('w-full')

            # ---- dialog must be created BEFORE the Add button uses it ----
            with ui.dialog() as add_dialog, ui.card().classes('w-96'):
                link = ui.input('TikTok product link (empty = blank product)').classes('w-full')

                async def do_add():
                    add_dialog.close()
                    v = link.value or ""
                    link.value = ""
                    await add_product(v)

                link.on('keydown.enter', do_add)
                ui.button('Add', on_click=do_add)

            with ui.row():
                ui.button('New', on_click=lambda: new_product())
                ui.button('Add', icon='add', on_click=add_dialog.open)
                ui.button('Move up', on_click=lambda: move(-1))
                ui.button('Move down', on_click=lambda: move(1))
                ui.button('Reload file', on_click=lambda: (load(), refresh_table(), ui.notify('Reloaded', type='info')))
            ui.separator()
            ui.label('Import from spreadsheet (CSV / XLSX, e.g. Seller Center export)')

            async def on_upload(e):
                suffix = os.path.splitext(e.name)[1] or ".csv"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(e.content.read())
                r = await asyncio.to_thread(
                    subprocess.run, [sys.executable, os.path.join(ROOT, "import_products.py"), tmp.name, "--products", products_path],
                    capture_output=True, text=True, cwd=ROOT)
                os.unlink(tmp.name)
                load()
                refresh_table()
                ui.notify((r.stdout or r.stderr).strip().splitlines()[-2:][0] if (r.stdout or r.stderr).strip() else "done",
                          type='positive' if r.returncode == 0 else 'negative')
            ui.upload(on_upload=on_upload, auto_upload=True).props('accept=".csv,.xlsx" flat bordered').classes('w-full')

        with ui.column().classes('w-1/2'):
            ui.label('Edit product').classes('text-bold')
            f = {}
            f["name"] = ui.input('Name').classes('w-full')
            f["aliases"] = ui.input('Aliases (comma separated, words viewers use)').classes('w-full')
            with ui.row().classes('w-full'):
                f["price"] = ui.input('Price').classes('w-40')
                f["original_price"] = ui.input('Original price').classes('w-40')
                f["active"] = ui.switch('Active (include in tour)', value=True)
            f["description"] = ui.textarea('Description').classes('w-full')
            f["highlights"] = ui.textarea('Highlights (one per line)').classes('w-full')
            f["sizes_colors"] = ui.input('Sizes / colours').classes('w-full')
            f["how_to_use"] = ui.input('How to use').classes('w-full')
            f["shipping"] = ui.input('Shipping').classes('w-full')
            f["return_policy"] = ui.input('Returns').classes('w-full')
            f["stock_note"] = ui.input('Stock note').classes('w-full')
            f["faq"] = ui.textarea('FAQ (one per line: question || answer)').classes('w-full')
            with ui.row():
                ui.button('Save product', on_click=lambda: save_product())
                ui.button('Say pitch now', on_click=lambda: pitch_now()).props('color=secondary')
                ui.button('Delete', on_click=lambda: delete_product()).props('color=negative')

    def selected_product():
        i = state["selected"]
        cat = state["catalog"]
        return cat.products[i] if i is not None and 0 <= i < len(cat.products) else None

    def fill_form(p):
        f["name"].value = p.get("name", "")
        f["aliases"].value = ", ".join(p.get("aliases", []))
        f["price"].value = p.get("price", "")
        f["original_price"].value = p.get("original_price", "")
        f["active"].value = p.get("active", True)
        f["description"].value = p.get("description", "")
        f["highlights"].value = "\n".join(p.get("highlights", []))
        f["sizes_colors"].value = p.get("sizes_colors", "")
        f["how_to_use"].value = p.get("how_to_use", "")
        f["shipping"].value = p.get("shipping", "")
        f["return_policy"].value = p.get("return_policy", "")
        f["stock_note"].value = p.get("stock_note", "")
        f["faq"].value = _faq_to_text(p.get("faq", []))

    def on_select(e):
        sel = table.selected
        if sel:
            state["selected"] = sel[0]["idx"]
            fill_form(selected_product())
        else:
            state["selected"] = None
    table.on('selection', on_select)

    def save_product():
        p = selected_product()
        if p is None:
            ui.notify('Select a product or press New first', type='warning')
            return
        if not f["name"].value.strip():
            ui.notify('Name is required', type='negative')
            return
        p.update({
            "name": f["name"].value.strip(),
            "aliases": [a.strip() for a in f["aliases"].value.split(",") if a.strip()],
            "price": f["price"].value.strip(), "original_price": f["original_price"].value.strip(),
            "active": bool(f["active"].value), "description": f["description"].value.strip(),
            "highlights": _lines(f["highlights"].value), "sizes_colors": f["sizes_colors"].value.strip(),
            "how_to_use": f["how_to_use"].value.strip(), "shipping": f["shipping"].value.strip(),
            "return_policy": f["return_policy"].value.strip(), "stock_note": f["stock_note"].value.strip(),
            "faq": _text_to_faq(f["faq"].value),
        })
        p.pop("auto_imported", None)  # edited by a human now
        persist()
        ui.notify('Saved', type='positive')

    def persist():
        cat = state["catalog"]
        for n, p in enumerate(cat.products, 1):
            p["order"] = n
        cat._index = [(p, cat._keywords(p)) for p in cat.products]
        cat.save()
        refresh_table()

    def new_product():
        cat = state["catalog"]
        cat.products.append({"id": f"NEW{len(cat.products) + 1:03d}", "order": len(cat.products) + 1,
                             "name": "New product", "aliases": [], "price": "", "original_price": "",
                             "description": "", "highlights": [], "sizes_colors": "", "how_to_use": "",
                             "shipping": "", "return_policy": "", "stock_note": "", "faq": []})
        persist()
        state["selected"] = len(cat.products) - 1
        fill_form(cat.products[-1])

    async def add_product(raw: str = ""):
        info = {}
        raw = (raw or "").strip()
        if raw.startswith("http"):
            ui.notify("Reading the product in Chrome... if a check appears there, solve it.", timeout=8000)
            try:
                info = await run.io_bound(fetch_tiktok_product, raw)
            except Exception as ex:
                ui.notify(f"Browser problem: {ex}", type="negative", timeout=12000)
            if not info.get("name"):
                ui.notify("Couldn't read that page. Blank product created, fill it in manually.",
                          type="warning", timeout=8000)
        elif raw:
            try:
                info = json.loads(raw)
            except ValueError:
                ui.notify("Not a link or valid product data. Blank product created.", type="warning")

        cat = state["catalog"]
        n = len(cat.products) + 1
        existing = {p.get("id") for p in cat.products}
        while f"P{n:03d}" in existing:
            n += 1
        pid = f"P{n:03d}"
        IMG_DIR.mkdir(parents=True, exist_ok=True)
        imgs = await run.io_bound(_download_images, pid, info.get("images", []))
        cat.products.append({
            **NEW_PRODUCT_DEFAULTS,
            "id": pid, "order": len(cat.products) + 1,
            "name": info.get("name") or "New product", "aliases": [],
            "price": _money(info.get("price")), "original_price": _money(info.get("original_price")),
            "description": info.get("description", ""), "intro": info.get("intro", ""),
            "highlights": [], "sizes_colors": info.get("sizes_colors", ""), "how_to_use": "",
            "faq": [], "images": imgs, "active": True,
        })
        persist()                                   # renumbers order and saves data/products.json
        state["selected"] = len(cat.products) - 1
        fill_form(cat.products[-1])
        
    def delete_product():
        i = state["selected"]
        if i is None:
            return
        del state["catalog"].products[i]
        state["selected"] = None
        persist()
        ui.notify('Deleted', type='info')

    def move(delta):
        i = state["selected"]
        cat = state["catalog"]
        if i is None or not 0 <= i + delta < len(cat.products):
            return
        cat.products[i], cat.products[i + delta] = cat.products[i + delta], cat.products[i]
        state["selected"] = i + delta
        persist()

    async def pitch_now():
        p = selected_product()
        if p is None:
            return
        pitch = state["catalog"].build_pitch(p, 0)
        verdict = tiktok_safety.TikTokSafety(terms_path).check(pitch, "output")
        if verdict:
            ui.notify(f"Blocked by safety filter: {[(h.category, h.term) for h in verdict]}", type='negative')
            return
        body = json.dumps({"type": "reread", "data": {"type": "reread", "username": "Streamer", "content": pitch}}).encode()
        import urllib.request
        req = urllib.request.Request(api_url, data=body, headers={"Content-Type": "application/json"})
        try:
            await asyncio.to_thread(urllib.request.urlopen, req, None, 10)
            ui.notify('Pitch sent to the streamer', type='positive')
        except Exception as e:
            ui.notify(f'Cannot reach the app at {api_url}: {e}', type='negative')

    ui.separator()
    ui.label('Test a viewer comment: quick answer + TikTok safety check').classes('text-bold')
    with ui.row().classes('w-full items-center'):
        test_in = ui.input('Comment').classes('w-96')
        test_out = ui.label('').classes('w-full')

    def run_test():
        text = test_in.value or ""
        cat = state["catalog"]
        hits_in = tiktok_safety.TikTokSafety(terms_path).check(text, "input")
        qa = cat.quick_answer(text)
        msg = []
        msg.append("INPUT BLOCKED: " + str([(h.category, h.term) for h in hits_in]) if hits_in else "input OK")
        msg.append("quick answer: " + qa if qa else "no quick answer (goes to the LLM)")
        test_out.text = "  |  ".join(msg)
    ui.button('Test', on_click=run_test)
