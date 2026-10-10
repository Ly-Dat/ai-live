"""Make a story-telling video (9:16, narration + burned-in captions) from picture panels or a novel chapter.

Needs ffmpeg (on PATH, or `pip install imageio-ffmpeg`), Pillow and edge-tts (free). Each caption piece is spoken
on its own, so the picture and the caption change exactly when the voice does. Output: an .mp4, a .srt, a cover .png.
The text-to-speech function is injectable so the whole pipeline is testable offline.
"""
import asyncio
import concurrent.futures
import os
import re
import shutil
import subprocess
import tempfile
from typing import Callable, Dict, List, Optional, Tuple

from . import novel, story

DEFAULT_VOICE = {"vi": "vi-VN-HoaiMyNeural", "en": "en-US-AriaNeural"}
FONT_CANDIDATES = [
    "data/fonts/story.ttf", "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def ffmpeg_exe() -> Optional[str]:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def missing_tools(need_edge: bool = True) -> List[str]:
    out = []
    if not ffmpeg_exe():
        out.append("ffmpeg (install it, or run: pip install imageio-ffmpeg)")
    try:
        import PIL  # noqa: F401
    except Exception:
        out.append("Pillow (pip install Pillow)")
    if need_edge:
        try:
            import edge_tts  # noqa: F401
        except Exception:
            out.append("edge-tts (pip install edge-tts)")
    return out


def find_font() -> Optional[str]:
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def edge_tts_file(text: str, voice: str, rate: int, out: str, lang: str = "vi") -> None:
    import time
    import edge_tts
    v = voice or DEFAULT_VOICE.get(lang, DEFAULT_VOICE["en"])
    last = None
    for attempt in range(4):
        try:
            asyncio.run(edge_tts.Communicate(text, v, rate=f"{int(rate):+d}%").save(out))
            if os.path.getsize(out) > 200:
                return
            last = RuntimeError("empty audio")
        except Exception as e:  # network hiccup / service busy: wait a little, then try again
            last = e
        time.sleep(1.5 * (attempt + 1))
    name = type(last).__name__ if last else "empty audio"
    raise RuntimeError(f"Text-to-speech failed ({name}: {str(last)[:160]}). Voice: {v}. Text: {text[:60]!r}. "
                       "Check the internet / VPN, update edge-tts (pip install -U edge-tts), or pick another voice.")


def vieneu_tts_file(text: str, cfg: dict, rate: int, out: str) -> str:
    """Speak one piece with the local VieNeu server (utils/vieneu_tts.py). Writes a WAV next to `out` and returns its path
    (build() uses the returned path). `rate` (%) is applied with ffmpeg atempo because VieNeu has no speed setting."""
    import time
    from . import vieneu_tts
    t = re.sub(r"\u2026\s*$", ".", text.strip())
    t = t.replace("\u2026", ",")
    wav = os.path.splitext(out)[0] + ".wav"
    last = None
    for attempt in range(3):
        try:
            if vieneu_tts.synthesize(t, cfg, wav):
                break
            last = RuntimeError("the VieNeu server returned no audio")
        except Exception as e:
            last = e
        time.sleep(1.5 * (attempt + 1))
    else:
        raise RuntimeError(f"VieNeu failed ({str(last)[:120]}). Is the VieNeu server running (Setup / Voice tab)? Text: {text[:60]!r}")
    if rate:
        ff = ffmpeg_exe()
        fast = os.path.splitext(out)[0] + "_t.wav"
        tempo = min(2.0, max(0.5, 1.0 + int(rate) / 100.0))
        _run([ff, "-y", "-loglevel", "error", "-i", wav, "-filter:a", f"atempo={tempo:.3f}", fast])
        return fast
    return wav


# ------------------------------------------------------------------ frames
def _wrap(draw, text: str, font, max_w: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_frame(image: Optional[str], caption: str, out: str, size: Tuple[int, int] = (1080, 1920), badge: str = "",
                 top: str = "", title: str = "", seed: int = 0, layer: str = "all") -> None:
    """layer: "all" = picture + text, "base" = only the picture / gradient, "text" = only the text on a transparent PNG
    (the zoom / pan effect moves the base and keeps the captions still)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H = size
    wide = W > H
    fp = find_font()

    def font(px):
        return ImageFont.truetype(fp, px) if fp else ImageFont.load_default()

    if layer == "text":  # the picture is kept only to choose the caption layout; its pixels live in the base layer
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    elif image:
        src = Image.open(image).convert("RGB")
        bgc = src.copy()
        s = max(W / bgc.width, H / bgc.height)
        bgc = bgc.resize((int(bgc.width * s) + 1, int(bgc.height * s) + 1))
        bgc = bgc.crop(((bgc.width - W) // 2, (bgc.height - H) // 2, (bgc.width - W) // 2 + W, (bgc.height - H) // 2 + H))
        canvas = bgc.filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.45))
        area_h = int(H * (0.74 if wide else 0.72))
        s = min(W / src.width, area_h / src.height)
        fg = src.resize((max(1, int(src.width * s)), max(1, int(src.height * s))))
        canvas.paste(fg, ((W - fg.width) // 2, int(H * (0.03 if wide else 0.06)) + (area_h - fg.height) // 2))
    else:  # text-only story: soft gradient, one colour pair per story
        pairs = [((30, 20, 70), (140, 50, 120)), ((10, 40, 70), (30, 120, 130)), ((50, 20, 40), (170, 70, 70)), ((20, 30, 60), (90, 70, 160))]
        c1, c2 = pairs[seed % len(pairs)]
        canvas = Image.new("RGB", (W, H))
        d0 = ImageDraw.Draw(canvas)
        for y in range(H):
            t = y / H
            d0.line([(0, y), (W, y)], fill=tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3)))
    if layer == "base":
        canvas.save(out)
        return
    d = ImageDraw.Draw(canvas, "RGBA")
    pad = 54
    if caption:
        px = (46 if wide else 54) if image else 70
        f = font(px)
        lines = _wrap(d, caption, f, W - 2 * pad - 30)
        while len(lines) > (3 if wide and image else 4 if image else 9) and px > 30:
            px -= 4
            f = font(px)
            lines = _wrap(d, caption, f, W - 2 * pad - 30)
        lh = int(px * 1.28)
        if image:
            bh = lh * len(lines) + 44
            y0 = int(H * (0.79 if wide else 0.80))
            d.rounded_rectangle((pad - 10, y0, W - pad + 10, y0 + bh), 28, fill=(0, 0, 0, 175))
            y = y0 + 22
        else:
            y = (H - lh * len(lines)) // 2
        for ln in lines:
            w = d.textlength(ln, font=f)
            d.text(((W - w) / 2 + 2, y + 2), ln, font=f, fill=(0, 0, 0, 200))
            d.text(((W - w) / 2, y), ln, font=f, fill=(255, 255, 255, 255))
            y += lh
    if top:
        f = font(76)
        lines = _wrap(d, top, f, W - 2 * pad)[:3]
        y = 70
        for ln in lines:
            w = d.textlength(ln, font=f)
            d.text(((W - w) / 2 + 3, y + 3), ln, font=f, fill=(0, 0, 0, 220))
            d.text(((W - w) / 2, y), ln, font=f, fill=(255, 214, 64, 255))
            y += 92
    if badge:
        f = font(40)
        w = d.textlength(badge, font=f)
        d.rounded_rectangle((36, 36, 36 + w + 40, 36 + 64), 32, fill=(236, 72, 153, 235))
        d.text((56, 44), badge, font=f, fill=(255, 255, 255, 255))
    if title and not image:
        f = font(36)
        w = d.textlength(title, font=f)
        d.text(((W - w) / 2, H - 150), title, font=f, fill=(255, 255, 255, 150))
    canvas.save(out)


# ------------------------------------------------------------------ ffmpeg helpers
def _run(cmd: List[str], cwd: Optional[str] = None) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + (r.stderr or "")[-400:])
    return r.stderr or ""


def audio_seconds(ff: str, path: str) -> float:
    r = subprocess.run([ff, "-i", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr or "")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


FORMATS = {"vertical": (1080, 1920), "wide": (1920, 1080)}
MOTION_CYCLE = ("zoom_in", "pan_right", "zoom_out", "pan_left")
ZOOM = 0.12      # a picture grows / moves by 12 % over its panel: slow enough to feel alive, never dizzy
FADE_S = 0.3
NEXT_PART = {"vi": "Còn tiếp, hẹn bạn ở phần {n}!", "en": "To be continued - see you in part {n}!"}


def plan(panels: List[Dict], hook: str = "", outro: str = "", max_chars: int = 200) -> List[Dict]:
    """Ordered list of {image, caption, speak, top, panel} - one entry per spoken caption piece. `panel` says which picture
    panel a piece belongs to (the hook joins the first panel and the ending joins the last, when they show the same picture)."""
    segs: List[Dict] = []
    pron = novel.load_pron()
    first = next((p["image"] for p in panels if p.get("image")), None)
    last = next((p["image"] for p in reversed(panels) if p.get("image")), None)
    n = len(panels)
    if hook.strip():
        segs.append({"image": first, "caption": hook.strip(), "speak": novel.clean_for_speech(hook, pron), "top": "",
                     "panel": 0 if n and panels[0].get("image") == first else -1, "hook": True})
    for k, p in enumerate(panels):
        pieces = story.caption_chunks(p.get("text", ""), max_chars, keep_phrases=True)
        if not pieces:
            segs.append({"image": p.get("image"), "caption": "", "speak": "", "top": "", "panel": k})
        for c in pieces:
            sp = novel.clean_for_speech(c, pron)
            segs.append({"image": p.get("image"), "caption": c, "speak": sp if re.search(r"\w", sp or "") else "", "top": "", "panel": k})
    if outro.strip():
        segs.append({"image": last, "caption": outro.strip(), "speak": novel.clean_for_speech(outro, pron), "top": "",
                     "panel": n - 1 if n and panels[-1].get("image") == last else n, "outro": True})
    return segs


def motion_for(mode: str, index: int) -> str:
    """mode: "off" | "zoom" (slowly in, then out) | "auto" (zoom in, pan, zoom out, pan back)."""
    if mode == "zoom":
        return "zoom_in" if index % 2 == 0 else "zoom_out"
    if mode == "auto":
        return MOTION_CYCLE[index % len(MOTION_CYCLE)]
    return ""


def zoompan_filter(kind: str, p0: float, p1: float, frames: int, size: Tuple[int, int], fps: int) -> str:
    """ffmpeg zoompan for one clip. p0..p1 is the part of the whole panel's movement this clip covers (0..1), so a panel that
    is spoken in several caption pieces moves smoothly across all of them instead of restarting every time."""
    W, H = size
    q = f"({p0:.4f}+{p1 - p0:.4f}*on/{max(1, frames)})"
    centre_x, centre_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if kind == "zoom_in":
        z, x, y = f"1+{ZOOM}*{q}", centre_x, centre_y
    elif kind == "zoom_out":
        z, x, y = f"1+{ZOOM}*(1-{q})", centre_x, centre_y
    elif kind in ("pan_right", "pan_left"):
        z, y = f"1+{ZOOM}", centre_y
        x = f"(iw-iw/zoom)*{q}" if kind == "pan_right" else f"(iw-iw/zoom)*(1-{q})"
    else:
        raise ValueError(kind)
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={fps}"


def split_panels(panels: List[Dict], max_seconds: float, cps: float = 13.0, rate: int = 0) -> List[List[Dict]]:
    """Cut a long story into parts of about `max_seconds` each (never inside a panel). 0 = one part."""
    if not max_seconds or max_seconds <= 0:
        return [panels]
    parts: List[List[Dict]] = []
    cur: List[Dict] = []
    t = 0.0
    for p in panels:
        d = estimate_seconds([p], cps=cps, rate=rate)
        if cur and t + d > max_seconds:
            parts.append(cur)
            cur, t = [], 0.0
        cur.append(p)
        t += d
    if cur:
        parts.append(cur)
    return parts or [panels]


def _mark_label(sg: Dict, k: int) -> str:
    txt = re.sub(r"\s+", " ", sg.get("caption") or "").strip()
    return (txt[:42].rstrip(" ,.;:-") + ("..." if len(txt) > 42 else "")) if txt else f"Scene {k + 1}"


def build(panels: List[Dict], out_path: str, tts: Optional[Callable] = None, voice: str = "", rate: int = 0, lang: str = "vi",
          title: str = "", part: int = 0, hook: str = "", outro: str = "", music: Optional[str] = None, music_volume: float = 0.12,
          size: Tuple[int, int] = (1080, 1920), fps: int = 25, gap: float = 0.25, silent_s: float = 2.5,
          progress: Optional[Callable[[int, int, str], None]] = None, cancel: Optional[Callable[[], bool]] = None,
          motion: str = "off", fade: bool = False, workers: int = 0, tts_workers: int = 4) -> Dict:
    """panels: [{image: path or None, text}]. motion: "off" | "zoom" | "auto"; fade: dip between different pictures.
    Returns {video, srt, cover, seconds, pieces, marks: [{t, label}] (one per scene, for YouTube chapters)}."""
    ff = ffmpeg_exe()
    if not ff:
        raise RuntimeError("ffmpeg was not found. Install it, or run: pip install imageio-ffmpeg")
    tts = tts or (lambda t, v, r, o: edge_tts_file(t, v, r, o, lang))
    segs = plan(panels, hook, outro)
    if not segs:
        raise ValueError("Nothing to say: add narration text to the panels.")
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    badge = f"Part {part}" if part else ""
    work = tempfile.mkdtemp(prefix="story_video_")
    n = len(segs)
    total = 3 * n + 2
    t_now, srt, files, marks = 0.0, [], [], []
    try:
        cover = os.path.splitext(out_path)[0] + "-cover.png"
        seed = sum(map(ord, title))
        # what each piece needs that does NOT depend on the voice length: scene order, picture movement, fades
        scene_order: List[int] = []
        for sg in segs:
            if sg["panel"] not in scene_order:
                scene_order.append(sg["panel"])
        kinds, fins, fouts = [], [], []
        for i, sg in enumerate(segs):
            k = sg["panel"]
            kinds.append(motion_for(motion, scene_order.index(k)) if sg["image"] else "")
            prev_img = segs[i - 1]["image"] if i else None
            next_img = segs[i + 1]["image"] if i + 1 < n else None
            fins.append(bool(fade and (i == 0 or (segs[i - 1]["panel"] != k and prev_img != sg["image"]))))
            fouts.append(bool(fade and (i == n - 1 or (segs[i + 1]["panel"] != k and next_img != sg["image"]))))
        cpu = os.cpu_count() or 2
        n_enc = max(1, int(workers) or min(4, cpu))
        n_img = max(1, min(3, cpu))
        n_tts = max(1, int(tts_workers))
        done = {"voice": 0, "pic": 0, "enc": 0}

        def report(msg):
            if progress:
                progress(done["voice"] + done["pic"] + done["enc"], total, msg)

        def check_cancel():
            if cancel and cancel():
                raise RuntimeError("Cancelled.")

        def voice_job(i):
            check_cancel()
            sg = segs[i]
            if not sg["speak"]:
                return i, None, silent_s
            aud = os.path.join(work, f"a{i:04d}.mp3")
            try:
                res = tts(sg["speak"], voice, rate, aud)
            except Exception as ex:
                raise RuntimeError(f"Piece {i + 1}/{len(segs)}: {ex}") from ex
            if isinstance(res, str) and os.path.exists(res):  # an engine may write its own file (VieNeu: .wav)
                aud = res
            return i, aud, audio_seconds(ff, aud) + gap

        def frame_job(i):
            check_cancel()
            sg = segs[i]
            frame = os.path.join(work, f"f{i:04d}.png")
            if i == 0:  # the cover is always the full first frame
                render_frame(sg["image"], sg["caption"], frame, size, badge, sg.get("top", ""), title, seed=seed)
                shutil.copyfile(frame, cover)
            if kinds[i]:
                render_frame(sg["image"], "", os.path.join(work, f"b{i:04d}.png"), size, "", "", title, seed=seed, layer="base")
                render_frame(sg["image"], sg["caption"], os.path.join(work, f"t{i:04d}.png"), size, badge, sg.get("top", ""), title,
                             seed=seed, layer="text")
            elif i != 0:
                render_frame(sg["image"], sg["caption"], frame, size, badge, sg.get("top", ""), title, seed=seed)
            return i

        SR = 44100

        def encode_job(i, dur, p0, p1, t0):
            check_cancel()
            kind = kinds[i]
            frame = os.path.join(work, f"f{i:04d}.png")
            seg = os.path.join(work, f"s{i:04d}.mp4")
            # Frames and audio samples are counted from the START of the whole video, so rounding never adds up and the
            # picture can not drift away from the voice (a per-clip AAC encode used to add ~24 ms to every clip).
            frames = max(1, int(round((t0 + dur) * fps)) - int(round(t0 * fps)))
            samples = max(1, int(round((t0 + dur) * SR)) - int(round(t0 * SR)))
            piece = os.path.join(work, f"v{i:04d}.wav")
            if auds[i]:
                acmd = [ff, "-y", "-loglevel", "error", "-i", auds[i], "-af", f"aresample={SR},apad=whole_len={samples},atrim=end_sample={samples}"]
            else:
                acmd = [ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-af", f"atrim=end_sample={samples}"]
            _run(acmd + ["-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", piece])
            fades = ""
            if fins[i]:
                fades += f"fade=t=in:st=0:d={FADE_S},"
            if fouts[i]:
                fades += f"fade=t=out:st={max(0.0, dur - FADE_S):.3f}:d={FADE_S},"
            if kind:
                big = (int(size[0] * 1.5) // 2 * 2, int(size[1] * 1.5) // 2 * 2)
                flt = (f"[0:v]scale={big[0]}:{big[1]}:flags=bicubic,{zoompan_filter(kind, p0, p1, frames, size, fps)}[bg];"
                       f"[bg][1:v]overlay=0:0:format=auto,{fades}format=yuv420p[v]")
                cmd = [ff, "-y", "-loglevel", "error", "-i", os.path.join(work, f"b{i:04d}.png"), "-loop", "1", "-framerate", str(fps),
                       "-i", os.path.join(work, f"t{i:04d}.png")]
            else:
                flt = f"[0:v]{fades}format=yuv420p[v]"
                cmd = [ff, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-i", frame]
            cmd += ["-filter_complex", flt, "-map", "[v]", "-an", "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
                    "-r", str(fps), seg]
            _run(cmd)
            return i

        def run_parallel(pools_jobs, on_done):
            """pools_jobs: [(n_workers, [(fn, args, tag)])]. Runs all pools at once; the first error cancels the rest."""
            pools, futs = [], {}
            try:
                for n_workers, jobs in pools_jobs:
                    ex = concurrent.futures.ThreadPoolExecutor(max_workers=n_workers)
                    pools.append(ex)
                    for fn, args, tag in jobs:
                        futs[ex.submit(fn, *args)] = tag
                for f in concurrent.futures.as_completed(list(futs)):
                    on_done(futs[f], f.result())
            finally:
                for ex in pools:
                    ex.shutdown(wait=True, cancel_futures=True)

        # pass 1: the voices AND the pictures are made at the same time (they do not depend on each other)
        durs, auds = [0.0] * n, [None] * n

        def on_pass1(tag, res):
            if tag == "voice":
                i, aud, d = res
                auds[i], durs[i] = aud, d
                done["voice"] += 1
            else:
                done["pic"] += 1
            report(f"Voice {done['voice']}/{n}, pictures {done['pic']}/{n}")
        report("Starting ...")
        run_parallel([(n_tts, [(voice_job, (i,), "voice") for i in range(n)]),
                      (n_img, [(frame_job, (i,), "pic") for i in range(n)])], on_pass1)
        # the real lengths are known now: where each scene starts and how far the picture moves in each piece
        scene_total: Dict[int, float] = {}
        for sg, d in zip(segs, durs):
            scene_total[sg["panel"]] = scene_total.get(sg["panel"], 0.0) + d
        scene_pos: Dict[int, float] = {}
        jobs3 = []
        for i, sg in enumerate(segs):
            dur, k = durs[i], sg["panel"]
            if k not in scene_pos:
                scene_pos[k] = 0.0
                marks.append({"t": round(t_now, 1), "label": _mark_label(sg, len(marks))})
            p0 = scene_pos[k] / scene_total[k]
            scene_pos[k] += dur
            p1 = scene_pos[k] / scene_total[k]
            jobs3.append((encode_job, (i, dur, p0, p1, t_now), "enc"))
            files.append(f"s{i:04d}.mp4")
            if sg["caption"]:
                srt.append((t_now, t_now + dur - gap, sg["caption"]))
            t_now += dur

        # pass 2: several clips are encoded at once
        def on_pass2(tag, res):
            done["enc"] += 1
            report(f"Video clips {done['enc']}/{n}")
        run_parallel([(n_enc, jobs3)], on_pass2)
        # the voice track: the exact-length pieces glued sample by sample (no per-clip encoder padding), encoded once later
        import wave
        voice_wav = os.path.join(work, "voice_all.wav")
        with wave.open(voice_wav, "wb") as wo:
            wo.setnchannels(2)
            wo.setsampwidth(2)
            wo.setframerate(SR)
            for i in range(n):
                with wave.open(os.path.join(work, f"v{i:04d}.wav"), "rb") as wi:
                    wo.writeframes(wi.readframes(wi.getnframes()))
        if progress:
            progress(3 * n, total, "Joining the clips")
        with open(os.path.join(work, "list.txt"), "w", encoding="utf-8") as f:
            for fn in files:
                f.write(f"file '{fn}'\n")
        joined = os.path.join(work, "joined.mp4")
        # silent clips + ONE continuous voice track -> the voice and the pictures stay in step from the first piece to the last
        _run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-i", voice_wav, "-map", "0:v", "-map", "1:a",
              "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", joined], cwd=work)
        if music and os.path.exists(music):
            if progress:
                progress(3 * n + 1, total, "Adding the music")
            _run([ff, "-y", "-loglevel", "error", "-i", joined, "-stream_loop", "-1", "-i", music, "-filter_complex",
                  f"[1:a]volume={music_volume}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                  "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", out_path])
        else:
            _run([ff, "-y", "-loglevel", "error", "-i", joined, "-c", "copy", "-movflags", "+faststart", out_path])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    srt_path = os.path.splitext(out_path)[0] + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for k, (a, b, t) in enumerate(srt, 1):
            f.write(f"{k}\n{_srt_time(a)} --> {_srt_time(b)}\n{t}\n\n")
    if progress:
        progress(total, total, "Done")
    return {"video": out_path, "srt": srt_path, "cover": os.path.splitext(out_path)[0] + "-cover.png", "seconds": round(t_now, 1),
            "pieces": n, "marks": marks}


def build_parts(panels: List[Dict], out_base: str, max_seconds: float = 0, first_part: int = 1, hook: str = "", outro: str = "",
                lang: str = "vi", progress: Optional[Callable[[int, int, str], None]] = None, **kw) -> List[Dict]:
    """Several videos from one story: parts of about `max_seconds`; the hook opens part 1, every part but the last ends on
    "to be continued - part N+1", the last one uses `outro`. Files: <out_base>-p<N>.mp4."""
    rate = int(kw.get("rate") or 0)
    chunks = split_panels(panels, max_seconds, rate=rate)
    results = []
    for k, chunk in enumerate(chunks):
        number = (first_part or 1) + k if len(chunks) > 1 else first_part
        last = k == len(chunks) - 1
        end = outro if last else NEXT_PART.get(lang, NEXT_PART["en"]).format(n=number + 1)

        def sub(a, b, msg, k=k):
            if progress:
                progress(a, b, (f"Part {k + 1}/{len(chunks)}: " if len(chunks) > 1 else "") + msg)
        res = build(chunk, f"{out_base}-p{number}.mp4" if len(chunks) > 1 else f"{out_base}.mp4", part=number, hook=hook if k == 0 else "",
                    outro=end, lang=lang, progress=sub, **kw)
        res["part"] = number
        results.append(res)
    return results


def make_thumbnail(image: Optional[str], text: str, out: str, size: Tuple[int, int] = (1280, 720), badge: str = "", seed: int = 0) -> str:
    """A YouTube thumbnail (16:9): the picture on the right, a few BIG words on the left. Pure Pillow, no network."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H = size
    fp = find_font()

    def font(px):
        return ImageFont.truetype(fp, px) if fp else ImageFont.load_default()

    if image:
        src = Image.open(image).convert("RGB")
        s = max(W / src.width, H / src.height)
        bg = src.resize((int(src.width * s) + 1, int(src.height * s) + 1))
        bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
        canvas = bg.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.5))
        ph = int(H * 0.92)
        s2 = min(int(W * 0.5) / src.width, ph / src.height)
        fg = src.resize((max(1, int(src.width * s2)), max(1, int(src.height * s2))))
        x0, y0 = W - fg.width - int(W * 0.04), (H - fg.height) // 2
        canvas.paste(fg, (x0, y0))
        ImageDraw.Draw(canvas).rectangle((x0 - 4, y0 - 4, x0 + fg.width + 3, y0 + fg.height + 3), outline=(255, 214, 64), width=6)
        text_w = x0 - int(W * 0.06)
    else:
        pairs = [((30, 20, 70), (140, 50, 120)), ((10, 40, 70), (30, 120, 130)), ((50, 20, 40), (170, 70, 70)), ((20, 30, 60), (90, 70, 160))]
        c1, c2 = pairs[seed % len(pairs)]
        canvas = Image.new("RGB", (W, H))
        d0 = ImageDraw.Draw(canvas)
        for x in range(W):
            t = x / W
            d0.line([(x, 0), (x, H)], fill=tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3)))
        text_w = W - int(W * 0.1)
    d = ImageDraw.Draw(canvas, "RGBA")
    left = int(W * 0.04)
    words = (text or "").strip().upper()
    px = 130
    lines = _wrap(d, words, font(px), text_w)
    while (len(lines) > 4 or any(d.textlength(l, font=font(px)) > text_w for l in lines)) and px > 48:
        px -= 8
        lines = _wrap(d, words, font(px), text_w)
    f = font(px)
    lh = int(px * 1.12)
    y = max(int(H * 0.12), (H - lh * len(lines)) // 2)
    for ln in lines[:4]:
        d.text((left, y), ln, font=f, fill=(255, 214, 64, 255), stroke_width=max(4, px // 14), stroke_fill=(0, 0, 0, 255))
        y += lh
    if badge:
        fb = font(48)
        w = d.textlength(badge, font=fb)
        d.rounded_rectangle((left, 28, left + w + 44, 100), 36, fill=(236, 72, 153, 245))
        d.text((left + 22, 36), badge, font=fb, fill=(255, 255, 255, 255))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    canvas.convert("RGB").save(out, quality=92)
    return out


# ------------------------------------------------------------------ sources
def panels_from_story(meta: Dict, root: str = story.STORIES_DIR) -> List[Dict]:
    return [{"image": story.image_path(meta, i, root), "text": p.get("text", "")} for i, p in enumerate(meta["panels"])]


def panels_from_novel(book: Dict, chapter: int, image: Optional[str] = None, max_chars: int = 230, max_panels: int = 40) -> List[Dict]:
    """A novel chapter as text panels (one per few lines), over one background picture or a gradient."""
    body = novel.chapter_body(book, chapter)
    out, cur = [], ""
    for c in novel.chunks(body, 180):
        if cur and len(cur) + 1 + len(c["text"]) > max_chars:
            out.append({"image": image, "text": cur})
            cur = c["text"]
        else:
            cur = (cur + " " + c["text"]).strip()
    if cur:
        out.append({"image": image, "text": cur})
    return out[:max_panels]


def estimate_seconds(panels: List[Dict], hook: str = "", outro: str = "", cps: float = 13.0, rate: int = 0) -> float:
    return sum(novel.spoken_seconds(s["speak"], cps, rate) + 0.25 if s["speak"] else 2.5 for s in plan(panels, hook, outro))
