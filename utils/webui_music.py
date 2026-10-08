"""Live tools -> "Background music" card: licence-checked tracks played by the overlay page.

Tracks live in data/music/. Every track needs a licence tag; unknown / non-commercial ones are never played.
"""
import json
import os
import re

from nicegui import app, ui

from . import music

SOURCES = [
    ("Pixabay Music", "https://pixabay.com/music/", "Free for commercial use, credit optional. Check each track page."),
    ("Mixkit", "https://mixkit.co/free-stock-music/", "Free licence, commercial use, no credit."),
    ("Incompetech (Kevin MacLeod)", "https://incompetech.com/music/royalty-free/", "CC BY 4.0: free, but the credit must be shown (the overlay does it)."),
    ("Free Music Archive", "https://freemusicarchive.org/", "Filter by licence: use CC0 or CC BY only. Skip NC / SA / ND."),
]
_registered = {"done": False}


def _mount():
    """Serve data/music/ at /lv_music (the overlay page streams from it). Idempotent."""
    if _registered["done"]:
        return
    try:
        os.makedirs(music.MUSIC_DIR, exist_ok=True)
        app.add_static_files("/lv_music", music.MUSIC_DIR)
        _registered["done"] = True
    except Exception:
        pass


_mount()


def _safe_name(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", os.path.basename(name or "track.mp3")).strip(" .")
    return base if base.lower().endswith(music.AUDIO_EXT) else ""


def music_card(config):
    _mount()
    st = music.load_settings()
    rows = {}

    with ui.card().classes("lv-card w-full").style("padding:20px"):
        ui.label("Background music").style("font-weight:700;font-size:16px")
        ui.label("Plays softly on the overlay page and dips while the host speaks. Only tracks with a commercial-safe licence are played. "
                 "A TikTok LIVE must not use music you do not have the right to use, so every track needs a licence tag.").classes("lv-sub")
        with ui.row().classes("items-center").style("gap:18px;flex-wrap:wrap"):
            enable = ui.switch("Play music on the overlay", value=bool(st["enable"]))
            shuffle = ui.switch("Shuffle", value=bool(st["shuffle"]))
            duck = ui.switch("Lower while the host speaks", value=bool(st["duck"]))
        with ui.row().classes("items-center").style("gap:24px;flex-wrap:wrap"):
            with ui.column().style("gap:0;min-width:220px"):
                ui.label("Volume").classes("lv-sub").style("margin:0")
                vol = ui.slider(min=0, max=100, value=st["volume"]).props("label-always")
            with ui.column().style("gap:0;min-width:220px"):
                ui.label("Volume while speaking").classes("lv-sub").style("margin:0")
                dvol = ui.slider(min=0, max=100, value=st["duck_volume"]).props("label-always")
        ui.label("Tip: keep the music low (20-30). Voice should always be easy to hear; the dip is approximate (about 9 s after each reply).").classes("lv-sub")

        @ui.refreshable
        def track_list():
            rows.clear()
            tr = music.tracks()
            if not tr:
                ui.label("No tracks yet. Add an mp3 / ogg / wav / m4a below, or drop files in data/music/.").classes("lv-sub")
                return
            for t in tr:
                with ui.row().classes("items-end w-full").style("gap:10px;flex-wrap:wrap;border-top:1px solid var(--lv-border);padding-top:8px"):
                    ui.label(t["file"]).style("min-width:150px;max-width:190px;word-break:break-all;font-size:13px")
                    title = ui.input("Title", value=t["title"]).classes("w-40")
                    artist = ui.input("Artist", value=t["artist"]).classes("w-36")
                    lic = ui.select({k: v["label"] for k, v in music.LICENSES.items()}, label="Licence", value=t["license"]).classes("w-64")
                    src = ui.input("Source link", value=t["source"]).classes("w-56")
                    rows[t["file"]] = (title, artist, lic, src)
                    chip = ui.label("").classes("lv-chip")

                    def upd(_=None, f=t["file"], chip=chip):
                        ti, ar, li, so = rows[f]
                        tt = [x for x in music.tracks() if x["file"] == f]
                        info = music.LICENSES[li.value]
                        ok = info["ok"] and not (info["credit"] and not (ar.value or "").strip())
                        chip.text = "Will play" if ok else ("Add the artist (credit needed)" if info["ok"] else "Blocked: " + info["note"])
                        chip.classes(add="good" if ok else "bad", remove="bad" if ok else "good")
                    lic.on_value_change(upd)
                    artist.on_value_change(upd)
                    upd()

                    def remove(f=t["file"]):
                        try:
                            os.replace(os.path.join(music.MUSIC_DIR, f), os.path.join(music.MUSIC_DIR, f + ".removed"))
                        except OSError:
                            pass
                        m = music.load_manifest()
                        m.pop(f, None)
                        music.save_manifest(m)
                        track_list.refresh()
                    ui.button(icon="delete", on_click=remove).props("flat round dense").tooltip("Remove from the playlist (file kept as .removed)")

        track_list()

        async def on_upload(e):
            name = _safe_name(e.name)
            if not name:
                ui.notify("Use mp3, ogg, wav or m4a files.", type="warning")
                return
            data = e.content.read()
            with open(os.path.join(music.MUSIC_DIR, name), "wb") as f:
                f.write(data)
            ui.notify(f"Added {name}. Pick its licence below - it will not play until you do.", type="info")
            track_list.refresh()
        ui.upload(label="Add a track", on_upload=on_upload, auto_upload=True, multiple=True).props("accept=audio/* flat dense").classes("w-full").style("margin-top:8px")

        def save():
            m = music.load_manifest()
            for f, (ti, ar, li, so) in rows.items():
                m[f] = {"title": ti.value or "", "artist": ar.value or "", "license": li.value, "source": so.value or ""}
            music.save_manifest(m)
            music.save_settings({"enable": enable.value, "volume": int(vol.value), "shuffle": shuffle.value,
                                 "duck": duck.value, "duck_volume": int(dvol.value)})
            track_list.refresh()
            ui.notify("Saved. The overlay picks it up within a few seconds.", type="positive")

        def copy_credits():
            txt = music.credits_text(music.tracks())
            if not txt:
                ui.notify("No credit-required tracks are playing.", type="info")
                return
            ui.run_javascript("navigator.clipboard.writeText(" + json.dumps(txt) + ")")
            ui.notify("Credits copied. Paste them in your live description.", type="positive")

        with ui.row().style("gap:10px;margin-top:8px"):
            ui.button("Save music settings", icon="save", on_click=save)
            ui.button("Copy credits", icon="content_copy", on_click=copy_credits).props("flat no-caps")

        ui.label("Where to find free music").style("font-weight:700;margin-top:14px")
        for name, url, note in SOURCES:
            with ui.row().classes("items-center").style("gap:8px"):
                ui.link(name, url, new_tab=True)
                ui.label(note).classes("lv-sub").style("margin:0")
        ui.label("Always read the licence on the track's own page; sites change their terms. Do not use songs from TikTok's sound library, "
                 "streaming apps or YouTube - those are not licensed for your live.").classes("lv-sub")
