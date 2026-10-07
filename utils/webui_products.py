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

from nicegui import ui, run, app

from . import catalog_enrich, pitch_draft, product_catalog, tiktok_safety
from .webui_theme import page_title

from .tiktok_fetch import fetch_tiktok_product, _download_images, _money, IMG_DIR

import time
from pathlib import Path

NEW_PRODUCT_DEFAULTS = {
    "shipping": "Shop gửi hàng qua TikTok Shop, thời gian giao tuỳ khu vực.",
    "return_policy": "Được đổi trả theo chính sách của TikTok Shop.",
    # no default stock claim: "limited stock" must be true, so the seller types it themselves
    "stock_note": "",
}

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

IMG_URL = "/product_images"
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


async def _read_upload(e):
    """Works with NiceGUI 1.x/2.x (e.content) and 3.x (e.file)."""
    if hasattr(e, "file"):
        return e.file.name, await e.file.read()
    return e.name, e.content.read()

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
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        app.add_static_files(IMG_URL, str(IMG_DIR))
    except Exception:
        pass
    
    def load():
        state["catalog"] = product_catalog.ProductCatalog(products_path, templates_path)
        return state["catalog"]

    def write_starter():
        import json as _json
        from . import starter
        os.makedirs(os.path.dirname(products_path) or ".", exist_ok=True)
        with open(products_path, "w", encoding="utf-8") as fh:
            _json.dump(starter.starter_catalog(), fh, ensure_ascii=False, indent=2)

    try:
        load()
    except Exception as e:
        with ui.card().classes('lv-card w-full').style('padding:24px;gap:8px'):
            ui.label("The products file could not be opened").style("font-weight:700;font-size:18px")
            ui.label(f"{products_path}: {e}").classes('lv-sub').style("margin:0")
            if not os.path.exists(products_path):
                ui.label("It does not exist yet. Start with three sample products, then replace them with yours.").classes('lv-sub').style("margin:0")
                ui.button("Create sample catalog", icon="auto_awesome", on_click=lambda: (write_starter(), ui.notify("Created. Reopen this tab.", type="positive"))).props("unelevated color=primary no-caps")
            else:
                ui.label("The file exists but is not valid JSON. Fix it by hand or restore it from git; nothing was overwritten.").classes('lv-sub').style("margin:0")
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
        has = bool(state["catalog"].products)
        table.set_visibility(has)
        empty_box.set_visibility(not has)

    def use_starter():
        if state["catalog"].products:
            ui.notify("You already have products; nothing was changed.", type="warning")
            return
        write_starter()
        load()
        refresh_table()
        ui.notify("3 sample products added. Edit or replace them any time.", type="positive")

    page_title('Products', 'Your cart as the AI knows it. Edit facts here; the host only says what is written.')
    with ui.row().classes('w-full items-start no-wrap'):
        with ui.card().classes('lv-card').style('width:49%;padding:18px;min-width:0'):
            ui.label('Cart products (in the order the streamer introduces them)').classes('text-bold')
            with ui.column().classes('items-center w-full').style('padding:14px 0;gap:6px') as empty_box:
                ui.icon('shopping_bag').style('font-size:40px;color:var(--lv-muted)')
                ui.label('Your cart is empty').style('font-weight:700')
                ui.label('Add one product, import a spreadsheet below, or start with three samples to hear how the host pitches.').classes('lv-sub').style('text-align:center;margin:0')
                ui.button('Start with 3 samples', icon='auto_awesome', on_click=lambda: use_starter()).props('unelevated color=primary no-caps')
            table = ui.table(columns=columns, rows=rows(), row_key='idx', selection='single').classes('w-full')
            table.set_visibility(bool(state["catalog"].products))
            empty_box.set_visibility(not state["catalog"].products)

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

        with ui.card().classes('lv-card').style('width:49%;padding:18px;min-width:0'):
            ui.label('Edit product').classes('text-bold')
            f = {}
            f["name"] = ui.input('Name').classes('w-full')
            f["aliases"] = ui.input('Aliases (comma separated, words viewers use)').classes('w-full')
            with ui.row().classes('w-full'):
                f["price"] = ui.input('Price').classes('w-40')
                f["original_price"] = ui.input('Original price').classes('w-40')
                f["active"] = ui.switch('Active (include in tour)', value=True)
            f["intro"] = ui.textarea('Intro line (spoken first; keep it to one short sentence)').classes('w-full')
            f["description"] = ui.textarea('Description').classes('w-full')
            f["highlights"] = ui.textarea('Highlights (one per line)').classes('w-full')
            f["sizes_colors"] = ui.input('Sizes / colours').classes('w-full')
            f["how_to_use"] = ui.input('How to use').classes('w-full')
            f["shipping"] = ui.input('Shipping').classes('w-full')
            f["return_policy"] = ui.input('Returns').classes('w-full')
            f["stock_note"] = ui.input('Stock note').classes('w-full')
            f["faq"] = ui.textarea('FAQ (one per line: question || answer)').classes('w-full')
            ui.label('Images')

            @ui.refreshable
            def gallery():
                i, cat = state["selected"], state["catalog"]
                p = cat.products[i] if i is not None and 0 <= i < len(cat.products) else None
                with ui.row().classes('items-center gap-2'):
                    if not p or not p.get("images"):
                        ui.label('No images yet').classes('text-grey')
                    else:
                        for path in list(p["images"]):
                            with ui.card().tight().classes('w-28'):
                                ui.image(f"{IMG_URL}/{Path(path).name}").classes('h-28 object-cover')
                                ui.button(icon='delete', on_click=lambda _, path=path: remove_image(path)) \
                                    .props('flat dense color=negative')
            gallery()

            async def on_img_upload(e):
                p = selected_product()
                if p is None:
                    ui.notify('Select a product first', type='warning')
                    return
                name, content = await _read_upload(e)
                ext = Path(name).suffix.lower()
                if ext not in IMG_EXT:
                    ui.notify(f'Unsupported file type: {ext}', type='negative')
                    return
                fname = f"{p.get('id') or 'product'}_{int(time.time() * 1000)}{ext}"
                (IMG_DIR / fname).write_bytes(content)
                p.setdefault("images", []).append(f"{IMG_DIR.as_posix()}/{fname}")
                persist()
                gallery.refresh()

            def remove_image(path):
                p = selected_product()
                if p is None:
                    return
                p["images"].remove(path)
                try:
                    Path(path).unlink()
                except OSError:
                    pass
                persist()
                gallery.refresh()

            ui.upload(label='Add images', multiple=True, auto_upload=True, on_upload=on_img_upload) \
                .props('accept=image/* flat bordered').classes('w-full')
            with ui.row():
                ui.button('Save product', on_click=lambda: save_product())
                ui.button('Say pitch now', on_click=lambda: pitch_now()).props('color=secondary')
                ui.button('Draft with AI', on_click=lambda: draft_ai()).props('color=secondary outline')
                ui.button('Check pitch length', on_click=lambda: check_pitch()).props('color=secondary outline')
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
        f["intro"].value = p.get("intro", "")
        f["sizes_colors"].value = p.get("sizes_colors", "")
        f["how_to_use"].value = p.get("how_to_use", "")
        f["shipping"].value = p.get("shipping", "")
        f["return_policy"].value = p.get("return_policy", "")
        f["stock_note"].value = p.get("stock_note", "")
        f["faq"].value = _faq_to_text(p.get("faq", []))
        gallery.refresh()
        
    def clear_form():
        for k, w in f.items():
            if k == "active":
                w.value = True
            else:
                w.value = ""
        gallery.refresh()
        
    def on_select(e):
        sel = table.selected
        if sel:
            state["selected"] = sel[0]["idx"]
            fill_form(selected_product())
        else:
            state["selected"] = None
            clear_form()
            
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
            "intro": f["intro"].value.strip(),
            "highlights": _lines(f["highlights"].value), "sizes_colors": f["sizes_colors"].value.strip(),
            "how_to_use": f["how_to_use"].value.strip(), "shipping": f["shipping"].value.strip(),
            "return_policy": f["return_policy"].value.strip(), "stock_note": f["stock_note"].value.strip(),
            "faq": _text_to_faq(f["faq"].value),
        })
        p.pop("auto_imported", None)  # edited by a human now
        persist()
        gallery.refresh()
        ui.notify('Deleted', type='info')
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
                             "shipping": "", "return_policy": "", "stock_note": "", "faq": [], "images": []})
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
        table.selected.clear()
        clear_form()
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

    def check_pitch():
        """How long the host talks per product, and a no-AI shortening built only from the seller's own words."""
        p = selected_product()
        if p is None:
            ui.notify("Select a product first", type="warning")
            return
        cat = state["catalog"]
        secs = pitch_draft.spoken_seconds(cat.build_pitch(p, 0))
        prop = pitch_draft.shorten(p)
        new_secs = pitch_draft.spoken_seconds(cat.build_pitch(dict(p, **prop), 0))
        with ui.dialog() as dlg, ui.card().classes("w-[36rem]"):
            ui.label("Pitch length").classes("text-bold")
            ui.label(f"The host takes about {secs} s to say this product. Viewers tend to leave after about "
                     f"{pitch_draft.TARGET_S} s, so shorter is better.")
            stock = (p.get("stock_note") or "").lower()
            if any(w in stock for w in ("có hạn", "co han", "limited", "sắp hết", "sap het")):
                ui.label("Heads-up: the stock note says stock is limited. Keep it only if that is true.").style("color:#f59e0b")
            if new_secs < secs - 3:
                ui.label(f"Shorter version: about {new_secs} s (your own sentences, nothing added):").classes("text-bold")
                if prop["intro"] != (p.get("intro") or ""):
                    ui.label("Intro: " + prop["intro"])
                if prop["description"] != (p.get("description") or ""):
                    ui.label("Description: " + prop["description"])
                if prop["highlights"] != (p.get("highlights") or []):
                    ui.label("Highlights: " + " | ".join(prop["highlights"]))

                def apply():
                    f["intro"].value = prop["intro"]
                    f["description"].value = prop["description"]
                    f["highlights"].value = "\n".join(prop["highlights"])
                    dlg.close()
                    ui.notify("Applied to the form. Press Save product to keep it.", type="positive")
                ui.button("Apply to form", on_click=apply)
            else:
                ui.label("Nothing obvious to cut from the intro and description. Price, sizes, shipping and the call to action make up the rest.")
            ui.button("Close", on_click=dlg.close).props("flat")
        dlg.open()

    llm_url = api_url.replace("/send", "/llm")

    def _ask_llm(prompt: str) -> str:
        import urllib.request
        body = json.dumps({"type": config.get("chat_type"), "username": "catalog", "content": prompt}).encode()
        req = urllib.request.Request(llm_url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode("utf-8"))
        if resp.get("code") != 200 or not (resp.get("data") or {}).get("content"):
            raise RuntimeError(resp.get("message") or "empty LLM reply (is an LLM configured in Settings?)")
        return resp["data"]["content"]

    async def draft_ai():
        """Ask the configured LLM for aliases / description / highlights / likely questions; the seller approves."""
        name = (f["name"].value or "").strip()
        if not name:
            ui.notify("Enter the product name first", type="warning")
            return
        ui.notify("Asking the AI for a draft ...", type="info")
        try:
            safety = tiktok_safety.TikTokSafety(terms_path)
            draft = await asyncio.to_thread(
                catalog_enrich.enrich, name, f["price"].value or "", _ask_llm, safety)
        except Exception as e:
            ui.notify(f"Draft failed: {e}", type="negative")
            return
        with ui.dialog() as dlg, ui.card().classes("w-[36rem]"):
            ui.label("AI draft (review before applying)").classes("text-bold")
            ui.label("Aliases: " + ", ".join(draft["aliases"]))
            ui.label("Description: " + draft["description"])
            ui.label("Highlights: " + " | ".join(draft["highlights"]))
            if draft["suggested_questions"]:
                ui.label("Questions viewers may ask - add answers in the FAQ box:").classes("text-bold")
                for q in draft["suggested_questions"]:
                    ui.label("- " + q)

            def apply():
                tmp = {"aliases": [a.strip() for a in (f["aliases"].value or "").split(",") if a.strip()],
                       "description": f["description"].value or "",
                       "highlights": _lines(f["highlights"].value)}
                catalog_enrich.apply_draft(tmp, draft)
                f["aliases"].value = ", ".join(tmp["aliases"])
                f["description"].value = tmp["description"]
                f["highlights"].value = "\n".join(tmp["highlights"])
                existing = f["faq"].value or ""
                f["faq"].value = existing
                dlg.close()
                ui.notify("Applied to the form. Press Save product to keep it.", type="positive")
            with ui.row():
                ui.button("Apply to form", on_click=apply)
                ui.button("Cancel", on_click=dlg.close).props("flat")
        dlg.open()

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
