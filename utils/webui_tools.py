"""
"Live tools" tab: flash-sale control. The live app reads data/flash_sale.json every few seconds and announces it.
"""
import os
import time

from nicegui import ui

from . import flash_sale, product_catalog
from .webui_theme import page_title

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def build_tools_tab(config):
    products_path = os.path.join(ROOT, config.get("products", "path") or "data/products.json")
    templates_path = os.path.join(ROOT, config.get("products", "templates_path") or "data/pitch_templates.json")
    sale_path = os.path.join(ROOT, config.get("products", "flash_sale_path") or flash_sale.DEFAULT_PATH)

    page_title("Live tools", "Flash sale: the AI announces the time left, the price and (only if you enter it) the stock. "
               "It never invents scarcity, and every line goes through the TikTok safety filter.")
    try:
        catalog = product_catalog.ProductCatalog(products_path, templates_path)
    except Exception as e:
        ui.label(f"Cannot load the catalog: {e}").classes("text-negative")
        return
    options = {p["id"]: f"{p.get('order', '')}. {p['name']}" for p in catalog.all_products()}
    card = ui.card().classes("lv-card w-full").style("padding:20px")
    card.__enter__()
    ui.label("Flash sale").style("font-weight:700;font-size:16px")
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
    card.__exit__(None, None, None)
    ui.timer(5.0, refresh)
    refresh()
