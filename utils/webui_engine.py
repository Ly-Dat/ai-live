"""AI engine tab: how fast the AI reply and the voice are, and the switches that keep a live smooth.

Numbers come from utils/engine_stats.py (this run, plus the last saved run until the first call), settings from llm_guard.py
and tts_cache.py.
"""
import time

from nicegui import ui

from . import engine_stats, llm_guard, tts_cache
from .webui_theme import page_title

PROVIDERS = ["", "chatgpt", "zhipu", "gemini", "tongyi", "tongyixingchen", "custom_llm", "koboldcpp", "anythingllm", "gpt4free",
             "dify", "volcengine", "text_generation_webui", "llm_tpu", "bard"]


def _secs(ms: int) -> str:
    return "-" if not ms else f"{ms / 1000:.1f} s"


def verdict(s: dict) -> str:
    """One plain sentence about the AI reply speed."""
    if not s["calls"]:
        return "No AI reply yet in this run."
    if s["fail_rate"] >= 0.2:
        return "Many AI replies failed. Check the provider, or choose a fallback below."
    if s["p95_ms"] >= 8000:
        return "Slow: one reply in twenty takes 8 s or more. A faster model or the fallback below will help."
    if s["p50_ms"] >= 4000:
        return "A bit slow. Viewers wait about 4 s for most answers."
    return "Healthy."


def build_engine_tab(config):
    page_title("AI engine", "How fast the AI answers and speaks, and what protects the stream when a provider is slow or down.")
    with ui.card().classes("lv-card w-full").style("padding:20px"):
        ui.label("Speed in this run").style("font-weight:700;font-size:16px")
        box = ui.column().style("gap:4px;width:100%")

        def refresh():
            box.clear()
            # The AI runs in main.py (another process), which saves its numbers every few seconds.
            saved = engine_stats.load()
            use = saved.get("stats")
            with box:
                if not use:
                    ui.label("No numbers yet. They appear after the host answers its first comment.").classes("lv-sub")
                    return
                age = int(time.time() - float(saved.get("at") or 0))
                ui.label(f"Updated {age} s ago" if age < 600 else "From an earlier run (the host has not answered anything since).").classes("lv-sub")
                l, t = use["llm"], use["tts"]
                ui.label("AI reply: " + verdict(l)).style("font-weight:600")
                ui.label(f"typical {_secs(l['p50_ms'])}, slowest 1 in 20 {_secs(l['p95_ms'])}, {l['calls']} calls, "
                         f"{l['failed']} failed, {l['timeout']} timed out, {l['fallback']} answered by the fallback").classes("lv-sub")
                if l["last_error"]:
                    ui.label("Last problem: " + l["last_error"]).classes("lv-sub")
                ui.label("Voice").style("font-weight:600;margin-top:8px")
                ui.label(f"typical {_secs(t['p50_ms'])}, slowest 1 in 20 {_secs(t['p95_ms'])}, {t['calls']} lines, "
                         f"{int(t['cache_rate'] * 100)}% came from the voice cache").classes("lv-sub")
                c = tts_cache.stats()
                ui.label(f"Voice cache: {c['files']} lines, {c['mb']} MB").classes("lv-sub")
        refresh()
        ui.timer(5.0, refresh)
        ui.label("Replies answered from the catalog or the repeated-question cache never call the AI, so they do not appear here.").classes("lv-sub")

    cfg = llm_guard.load()
    with ui.card().classes("lv-card w-full").style("padding:20px;margin-top:22px"):
        ui.label("Protect the stream").style("font-weight:700;font-size:16px")
        ui.label("Current AI: " + str(config.get("chat_type"))).classes("lv-sub")
        timeout = ui.number("Give up on a reply after (seconds, 0 = never)", value=cfg["timeout_s"], min=0, max=300, step=5).props("outlined dense").style("width:320px")
        fb = ui.select({p: (p or "(none)") for p in PROVIDERS}, value=cfg["fallback"] if cfg["fallback"] in PROVIDERS else "",
                       label="Fallback AI when the main one fails").style("width:320px")
        ui.label("The fallback must be set up in AI model settings (its key or address filled in). A local model is a good choice.").classes("lv-sub")
        with ui.row().style("gap:16px;flex-wrap:wrap"):
            fails = ui.number("Skip the main AI after this many failures in a row", value=cfg["breaker_fails"], min=1, max=20).props("outlined dense").style("width:320px")
            cool = ui.number("...for this many seconds", value=cfg["cooldown_s"], min=5, max=3600, step=10).props("outlined dense").style("width:200px")
        ui.label("Streamed replies (stream mode) are not covered by the timeout and fallback; turn stream off in the AI settings if you want them.").classes("lv-sub")

        def save():
            llm_guard.save({"timeout_s": timeout.value or 0, "fallback": fb.value or "", "breaker_fails": fails.value or 3,
                            "cooldown_s": cool.value or 60, "tts_cache": bool(cache_sw.value)})
            ui.notify("Saved. It applies to the next reply.")
        cache_sw = ui.switch("Remember voice lines so repeated sentences play at once", value=cfg["tts_cache"])
        with ui.row().style("gap:12px"):
            ui.button("Save", icon="save", on_click=save)
            ui.button("Clear voice cache", icon="delete_sweep", on_click=lambda: (ui.notify(f"Removed {tts_cache.clear()} files."), refresh())).props("flat")
