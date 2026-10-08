"""
"Voice" tab: pick the voice engine and audition voices side by side before going live.

Engines
  edge-tts  - free, zero setup, Microsoft neural voices (vi-VN-HoaiMyNeural / NamMinhNeural)
  vieneu    - free + open (Apache-2.0), runs on your PC (CPU or GPU), 20+ Vietnamese voices; falls back to edge-tts if its
              server is not running
Other engines (ElevenLabs, GPT-SoVITS, ...) stay available in the "Text-to-Speech" tab.
"""
import asyncio
import json
import os
import time

from nicegui import app, ui

from . import setup_wizard, vieneu_tts, voice_catalog
from .webui_theme import page_title

ROOT = setup_wizard.ROOT
PREVIEW_DIR = os.path.join(ROOT, "out", "preview")
SAMPLE = voice_catalog.sample("vi")

DEFAULT_VIE_VOICE = "Ngọc Huyền"

EXTRA_VIE_VOICES = [
    "Ngọc Huyền",   
    "Ngọc Linh",    
    "Trúc Ly",      
    "Bích Ngọc",    
    "Ngọc Trân",    
    "Thục Đoan",   
    "Mai Anh",      
    "Phạm Tuyên", 
    "Thanh Bình",   
    "Thái Sơn",    
]

def _merge_voices(server_voices, *must_have):
    "List of voices from the server + mandatory voices (no duplicates, Ngọc Huyền at the top"
    out = list(server_voices or [])
    for v in reversed([*EXTRA_VIE_VOICES, *must_have]):
        if v and v not in out:
            out.insert(0, v)
    return out

def _save_config(mutator):
    path = os.path.join(ROOT, "config.json")
    raw = open(path, "r", encoding="utf-8").read()
    crlf = "\r\n" in raw
    cfg = json.loads(raw)
    mutator(cfg)
    text = json.dumps(cfg, ensure_ascii=False, indent=2)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", "\r\n") if crlf else text)


def build_voice_tab(config, on_engine_saved=None):
    """on_engine_saved(engine): optional callback, called after 'Save voice settings' so webui.py can sync the
    'Speech synthesis' select in Common config (otherwise the global Save Config would write the old engine back)."""
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    app.add_static_files("/lv_preview", PREVIEW_DIR)
    vcfg = dict(config.get("vieneu") or {})
    edge_cfg = config.get("edge-tts") or {}
    current = config.get("audio_synthesis_type") or "edge-tts"
    url_default = vcfg.get("api_url") or vieneu_tts.DEFAULT_URL
    state = {"voices": []}

    page_title("Voice", "Choose how the host sounds. Both engines below are free; try them side by side and save your pick.")

    # ---------------------------------------------------------------- engine cards
    engine = {"value": current if current in ("edge-tts", "vieneu") else "edge-tts"}
    cards = {}

    def pick(name):
        engine["value"] = name
        for k, c in cards.items():
            c.classes(add="lv-selected" if k == name else None, remove=None if k == name else "lv-selected")

    ui.add_css(".lv-engine{cursor:pointer;transition:all .15s} .lv-engine:hover{transform:translateY(-2px)}"
               ".lv-selected{outline:2px solid var(--lv-accent);box-shadow:0 14px 34px rgba(139,92,246,.35)!important}")
    with ui.row().classes("w-full").style("gap:16px;flex-wrap:wrap"):
        for key, title, badge, text in [
            ("edge-tts", "Edge TTS", "Instant", "Zero setup. 2 native Vietnamese voices (HoaiMy, NamMinh) plus 20+ English neural voices (US, UK, AU, CA, IN, IE). Needs internet; it uses Microsoft's Edge read-aloud service, which has no official SLA."),
            ("vieneu", "VieNeu-TTS", "Local - Apache-2.0", "Open Vietnamese model that runs on your own PC (CPU is fast enough, GPU is faster). 20+ voices, 48 kHz, no per-character cost. Falls back to Edge automatically if the server is off."),
        ]:
            c = ui.card().classes("lv-card lv-engine").style("flex:1 1 320px;padding:18px").on("click", lambda k=key: pick(k))
            cards[key] = c
            with c:
                with ui.row().classes("items-center justify-between w-full"):
                    ui.label(title).style("font-weight:800;font-size:18px")
                    ui.label(badge).classes("lv-chip good")
                ui.label(text).classes("lv-sub").style("margin:8px 0 0")
    pick(engine["value"])

    # ---------------------------------------------------------------- VieNeu server
    with ui.card().classes("lv-card w-full").style("padding:18px;margin-top:16px"):
        ui.label("VieNeu server").style("font-weight:700;font-size:16px")
        ui.label("First start creates its own environment (venv_voice) and downloads the model once (needs internet, a few hundred MB).").classes("lv-sub")
        with ui.row().classes("items-center").style("gap:12px"):
            url_in = ui.input("Server URL", value=url_default).classes("w-72")
            status = ui.label("").classes("lv-chip")
            btn_start = ui.button("Start server", icon="play_arrow")
            btn_stop = ui.button("Stop", icon="stop").props("outline")
            btn_refresh = ui.button(icon="refresh").props("flat round").tooltip("Check again / reload voices")
        log = ui.label("").classes("lv-sub")

    # ---------------------------------------------------------------- voice lab
    with ui.card().classes("lv-card w-full").style("padding:18px;margin-top:16px"):
        ui.label("Voice lab").style("font-weight:700;font-size:16px")
        ui.label("Type a line, pick a voice, press play. Nothing is saved until you press Save.").classes("lv-sub")
        text_in = ui.textarea("Sample line", value=SAMPLE).classes("w-full")
        with ui.row().classes("items-end").style("gap:12px"):
            cur_edge = edge_cfg.get("voice") or "vi-VN-HoaiMyNeural"
            lang_sel = ui.select({"vi": "Vietnamese", "en": "English"}, label="Language", value=voice_catalog.lang_of(cur_edge)).classes("w-40")
            gender_sel = ui.select({"": "Any", "F": "Female", "M": "Male"}, label="Voice type", value="").classes("w-32")
            edge_sel = ui.select(voice_catalog.options(lang_sel.value), label="Edge voice", value=cur_edge).classes("w-96")
            vie_default = vcfg.get("voice") or DEFAULT_VIE_VOICE
            vie_sel = ui.select(_merge_voices([], vie_default), label="VieNeu voice", value=vie_default).classes("w-64")
        with ui.row().style("gap:10px;margin-top:6px"):
            b_edge = ui.button("Play with Edge", icon="volume_up").props("outline")
            b_vie = ui.button("Play with VieNeu", icon="graphic_eq")
        audio_box = ui.column().classes("w-full")
        play_note = ui.label("").classes("lv-sub")

    def refill_edge(*_):
        opts = voice_catalog.options(lang_sel.value, gender_sel.value or None)
        cur = edge_sel.value
        if cur not in opts:
            cur = next(iter(opts), cur)
        edge_sel.set_options(opts, value=cur)

    def lang_changed(*_):
        text_in.value = voice_catalog.sample(lang_sel.value)
        refill_edge()

    lang_sel.on_value_change(lang_changed)
    gender_sel.on_value_change(refill_edge)
    if voice_catalog.lang_of(edge_sel.value) == "en":
        text_in.value = voice_catalog.sample("en")
    if edge_sel.value not in edge_sel.options:  # a voice set by hand in config.json stays selectable
        edge_sel.set_options({**edge_sel.options, edge_sel.value: edge_sel.value}, value=edge_sel.value)

    def show_audio(fname):
        audio_box.clear()
        with audio_box:
            a = ui.audio(f"/lv_preview/{fname}?t={int(time.time())}").props("controls autoplay").classes("w-full")

    async def play_edge():
        play_note.text = "Synthesizing with Edge ..."
        fname = f"edge_{int(time.time())}.mp3"
        try:
            import edge_tts
            comm = edge_tts.Communicate(text=text_in.value, voice=edge_sel.value,
                                        rate=edge_cfg.get("rate") or "+0%", volume=edge_cfg.get("volume") or "+0%")
            await comm.save(os.path.join(PREVIEW_DIR, fname))
            show_audio(fname)
            play_note.text = ""
        except Exception as e:
            play_note.text = f"Edge preview failed: {e}"

    async def play_vie():
        play_note.text = "Synthesizing with VieNeu (the first line after a start can take a few seconds) ..."
        fname = f"vieneu_{int(time.time())}.wav"
        cfg = dict(vcfg, api_url=url_in.value, voice=vie_sel.value, timeout=120)
        path = await asyncio.to_thread(vieneu_tts.synthesize, text_in.value, cfg, os.path.join(PREVIEW_DIR, fname))
        if path:
            show_audio(fname)
            play_note.text = ""
        else:
            play_note.text = "VieNeu server is not reachable. Press 'Start server' above."

    b_edge.on("click", play_edge)
    b_vie.on("click", play_vie)

    async def refresh_status():
        up = await asyncio.to_thread(vieneu_tts.is_up, url_in.value)
        running = setup_wizard.PM_VOICE.running("voice")
        if up:
            status.text = "Server online"
            status.classes(add="good", remove="bad")
            voices = await asyncio.to_thread(vieneu_tts.list_voices, url_in.value, vcfg.get("api_key", ""))
            voices = _merge_voices(voices, vie_sel.value)
            if voices != state["voices"]:
                state["voices"] = voices
                cur = vie_sel.value if vie_sel.value in voices else voices[0]
                vie_sel.set_options(voices, value=cur)
        else:
            status.text = "Starting ..." if running else "Server offline"
            status.classes(add=None if running else "bad", remove="good")

    async def start_server():
        btn_start.disable()
        log.text = "Preparing the voice environment (first time only) ..."
        try:
            py = await asyncio.to_thread(setup_wizard.ensure_voice_env, ROOT)
            host_port = url_in.value.rsplit(":", 1)[-1].strip("/")
            setup_wizard.PM_VOICE.start("voice", setup_wizard.voice_command(py),
                                        env={"HOST": "127.0.0.1", "PORT": host_port if host_port.isdigit() else "8000"})
            log.text = "Server starting. The first start downloads the model; this chip turns green when it is ready."
        except Exception as e:
            log.text = f"Could not start the server: {e}"
        btn_start.enable()

    def stop_server():
        setup_wizard.PM_VOICE.stop("voice")
        log.text = "Stopped."

    btn_start.on("click", start_server)
    btn_stop.on("click", stop_server)
    btn_refresh.on("click", refresh_status)
    ui.timer(4.0, refresh_status)

    # ---------------------------------------------------------------- save
    def save():
        def mut(cfg):
            cfg["audio_synthesis_type"] = engine["value"]
            cfg.setdefault("edge-tts", {})["voice"] = edge_sel.value
            v = cfg.setdefault("vieneu", {})
            v["voice"] = vie_sel.value
            v["api_url"] = url_in.value
        _save_config(mut)
        if on_engine_saved:
            try:
                on_engine_saved(engine["value"])  # keep Common config in sync with this choice
            except Exception:
                pass
        ui.notify("Saved. Restart the app so it uses the new voice.", type="positive")

    with ui.row().style("margin-top:16px;gap:10px"):
        ui.button("Save voice settings", icon="save", on_click=save)
        ui.label("Tip: edge-tts stays as the automatic fallback, so the stream never goes silent.").classes("lv-sub").style("margin:8px 0 0")
