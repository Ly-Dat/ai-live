"""Make a story-telling video (9:16, narration + burned-in captions) from picture panels or a novel chapter.

Needs ffmpeg (on PATH, or `pip install imageio-ffmpeg`), Pillow and edge-tts (free). Each caption piece is spoken
on its own, so the picture and the caption change exactly when the voice does. Output: an .mp4, a .srt, a cover .png.
The text-to-speech function is injectable so the whole pipeline is testable offline.
"""
import asyncio
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


def missing_tools() -> List[str]:
    out = []
    if not ffmpeg_exe():
        out.append("ffmpeg (install it, or run: pip install imageio-ffmpeg)")
    try:
        import PIL  # noqa: F401
    except Exception:
        out.append("Pillow (pip install Pillow)")
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
    import edge_tts
    v = voice or DEFAULT_VOICE.get(lang, DEFAULT_VOICE["en"])
    last = None
    for _ in range(3):
        try:
            asyncio.run(edge_tts.Communicate(text, v, rate=f"{int(rate):+d}%").save(out))
            if os.path.getsize(out) > 200:
                return
        except Exception as e:  # network hiccup: try again
            last = e
    raise RuntimeError(f"Text-to-speech failed ({type(last).__name__ if last else 'empty audio'}). Check the internet connection.")


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
                 top: str = "", title: str = "", seed: int = 0) -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H = size
    fp = find_font()

    def font(px):
        return ImageFont.truetype(fp, px) if fp else ImageFont.load_default()

    if image:
        src = Image.open(image).convert("RGB")
        bgc = src.copy()
        s = max(W / bgc.width, H / bgc.height)
        bgc = bgc.resize((int(bgc.width * s) + 1, int(bgc.height * s) + 1))
        bgc = bgc.crop(((bgc.width - W) // 2, (bgc.height - H) // 2, (bgc.width - W) // 2 + W, (bgc.height - H) // 2 + H))
        canvas = bgc.filter(ImageFilter.GaussianBlur(28)).point(lambda v: int(v * 0.45))
        area_h = int(H * 0.72)
        s = min(W / src.width, area_h / src.height)
        fg = src.resize((max(1, int(src.width * s)), max(1, int(src.height * s))))
        canvas.paste(fg, ((W - fg.width) // 2, int(H * 0.06) + (area_h - fg.height) // 2))
    else:  # text-only story: soft gradient, one colour pair per story
        pairs = [((30, 20, 70), (140, 50, 120)), ((10, 40, 70), (30, 120, 130)), ((50, 20, 40), (170, 70, 70)), ((20, 30, 60), (90, 70, 160))]
        c1, c2 = pairs[seed % len(pairs)]
        canvas = Image.new("RGB", (W, H))
        d0 = ImageDraw.Draw(canvas)
        for y in range(H):
            t = y / H
            d0.line([(0, y), (W, y)], fill=tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3)))
    d = ImageDraw.Draw(canvas, "RGBA")
    pad = 54
    if caption:
        px = 54 if image else 70
        f = font(px)
        lines = _wrap(d, caption, f, W - 2 * pad - 30)
        while len(lines) > (4 if image else 9) and px > 34:
            px -= 4
            f = font(px)
            lines = _wrap(d, caption, f, W - 2 * pad - 30)
        lh = int(px * 1.28)
        if image:
            bh = lh * len(lines) + 44
            y0 = int(H * 0.80)
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


def plan(panels: List[Dict], hook: str = "", outro: str = "", max_chars: int = 70) -> List[Dict]:
    """Ordered list of {image, caption, speak, top} - one entry per spoken caption piece."""
    segs: List[Dict] = []
    pron = novel.load_pron()
    first = next((p["image"] for p in panels if p.get("image")), None)
    last = next((p["image"] for p in reversed(panels) if p.get("image")), None)
    if hook.strip():
        segs.append({"image": first, "caption": hook.strip(), "speak": novel.clean_for_speech(hook, pron), "top": ""})
    for p in panels:
        pieces = story.caption_chunks(p.get("text", ""), max_chars)
        if not pieces:
            segs.append({"image": p.get("image"), "caption": "", "speak": "", "top": ""})
        for c in pieces:
            segs.append({"image": p.get("image"), "caption": c, "speak": novel.clean_for_speech(c, pron), "top": ""})
    if outro.strip():
        segs.append({"image": last, "caption": outro.strip(), "speak": novel.clean_for_speech(outro, pron), "top": ""})
    return segs


def build(panels: List[Dict], out_path: str, tts: Optional[Callable] = None, voice: str = "", rate: int = 0, lang: str = "vi",
          title: str = "", part: int = 0, hook: str = "", outro: str = "", music: Optional[str] = None, music_volume: float = 0.12,
          size: Tuple[int, int] = (1080, 1920), fps: int = 25, gap: float = 0.25, silent_s: float = 2.5,
          progress: Optional[Callable[[int, int, str], None]] = None, cancel: Optional[Callable[[], bool]] = None) -> Dict:
    """panels: [{image: path or None, text}]. Returns {video, srt, cover, seconds, pieces}."""
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
    total = len(segs) + 2
    t_now, srt, files = 0.0, [], []
    try:
        for i, sg in enumerate(segs):
            if cancel and cancel():
                raise RuntimeError("Cancelled.")
            if progress:
                progress(i, total, f"Voice + picture {i + 1}/{len(segs)}")
            frame = os.path.join(work, f"f{i:04d}.png")
            render_frame(sg["image"], sg["caption"], frame, size, badge, sg.get("top", ""), title, seed=sum(map(ord, title)))
            seg = os.path.join(work, f"s{i:04d}.mp4")
            if sg["speak"]:
                aud = os.path.join(work, f"a{i:04d}.mp3")
                tts(sg["speak"], voice, rate, aud)
                dur = audio_seconds(ff, aud) + gap
                cmd = [ff, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-i", frame, "-i", aud, "-t", f"{dur:.3f}",
                       "-af", f"apad=pad_dur={gap}"]
            else:
                dur = silent_s
                cmd = [ff, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-i", frame, "-f", "lavfi", "-i",
                       "anullsrc=r=44100:cl=stereo", "-t", f"{dur:.3f}"]
            cmd += ["-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-ar", "44100",
                    "-ac", "2", seg]
            _run(cmd)
            files.append(os.path.basename(seg))
            if sg["caption"]:
                srt.append((t_now, t_now + dur - gap, sg["caption"]))
            t_now += dur
            if i == 0:
                shutil.copyfile(frame, os.path.splitext(out_path)[0] + "-cover.png")
        if progress:
            progress(len(segs), total, "Joining the clips")
        with open(os.path.join(work, "list.txt"), "w", encoding="utf-8") as f:
            for fn in files:
                f.write(f"file '{fn}'\n")
        joined = os.path.join(work, "joined.mp4")
        _run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", joined], cwd=work)
        if music and os.path.exists(music):
            if progress:
                progress(len(segs) + 1, total, "Adding the music")
            _run([ff, "-y", "-loglevel", "error", "-i", joined, "-stream_loop", "-1", "-i", music, "-filter_complex",
                  f"[1:a]volume={music_volume}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                  "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", out_path])
        else:
            _run([ff, "-y", "-loglevel", "error", "-i", joined, "-c", "copy", "-movflags", "+faststart", out_path])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    srt_path = os.path.splitext(out_path)[0] + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for n, (a, b, t) in enumerate(srt, 1):
            f.write(f"{n}\n{_srt_time(a)} --> {_srt_time(b)}\n{t}\n\n")
    if progress:
        progress(total, total, "Done")
    return {"video": out_path, "srt": srt_path, "cover": os.path.splitext(out_path)[0] + "-cover.png", "seconds": round(t_now, 1),
            "pieces": len(segs)}


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
