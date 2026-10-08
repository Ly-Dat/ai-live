"""Story studio logic: picture stories (manhua / webtoon style panels with narration), plot prompts, post kit.

Pure logic (no network, no UI) so it is unit tested. A story is a folder data/stories/<id>/ with story.json and
panels/001.jpg ... Each panel is a picture plus the narration the AI host says while it is on screen.

Licence gate (same as the Novel reader): pictures and text must be yours (drawn, written, or made by you with a free
AI tool), public domain, CC, or used with written permission. Panels copied from a manhua / webtoon site are
copyrighted: they are blocked from the live and from video export. There is deliberately no "fetch from a site" button.
"""
import io
import os
import re
import shutil
import time
import zipfile
from typing import Dict, List, Optional, Tuple

from . import novel
from .novel import _atomic_write, _read

STORIES_DIR = os.path.join("data", "stories")
CONTROL_PATH = os.path.join("data", "story_state.json")     # UI -> story_reader.py
STATUS_PATH = os.path.join("data", "story_status.json")     # story_reader.py -> UI + overlay
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
MAX_IMG_BYTES = 15 * 1024 * 1024
MAX_PANELS = 300

LICENSE_LABELS = {
    "own": "I made it (drew it, or made it myself with a free AI tool)",
    "public-domain": "Public domain (copyright expired)",
    "cc0": "CC0",
    "cc-by": "CC BY (credit the author)",
    "permission": "The artist / publisher allowed me in writing",
    "copyrighted": "Copyrighted, no permission (e.g. a manhua site)",
    "unknown": "Not sure - not used live",
}
DEFAULT_SETTINGS = {"voice": "", "rate": 0, "min_panel_s": 4.0, "pause_s": 0.5, "yield_comments": True, "loop": False,
                    "show_text": True, "sleep_min": 0, "safety": True}

HASHTAGS = {
    "vi": ["#truyen", "#kechuyen", "#doctruyen", "#truyenngan", "#fyp", "#xuhuong", "#tiktokvietnam"],
    "en": ["#storytime", "#story", "#shortstory", "#audiostory", "#manhwa", "#fyp", "#foryou"],
}
GENRE_TAGS = {
    "fantasy": ["#fantasy", "#tienhiep"], "romance": ["#romance", "#ngontinh"], "horror": ["#horror", "#truyenma"],
    "comedy": ["#comedy", "#hai"], "mystery": ["#mystery", "#trinhtham"], "adventure": ["#adventure", "#phieuluu"],
    "slice of life": ["#sliceoflife", "#doisong"], "sci-fi": ["#scifi", "#vientuong"],
}
GENRES = list(GENRE_TAGS)


# ------------------------------------------------------------------ helpers
def natural_key(name: str):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name)]


def _sniff_ext(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ""


def zip_images(data: bytes) -> List[Tuple[str, bytes]]:
    """Pictures inside a .zip, in natural name order. Folders, odd names and non-pictures are ignored (no path tricks)."""
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = [i for i in z.infolist() if not i.is_dir() and i.filename.lower().endswith(IMG_EXT)
                 and "__MACOSX" not in i.filename and i.file_size <= MAX_IMG_BYTES]
        for i in sorted(infos, key=lambda i: natural_key(os.path.basename(i.filename)))[:MAX_PANELS]:
            out.append((os.path.basename(i.filename), z.read(i)))
    return out


def split_strip(data: bytes, name: str = "strip", min_h: int = 420, max_h: int = 1700, tol: int = 10, gutter: int = 16) -> List[Tuple[str, bytes]]:
    """Cut one tall webtoon-style strip into panels at the empty bands (gutters) between them.
    A band is a run of rows (>= `gutter` px at full size) where every pixel is almost the same colour. Pieces shorter than `min_h`
    are merged into a neighbour; a piece taller than `max_h` with no gutter is cut at its calmest row."""
    try:
        from PIL import Image
    except Exception:
        raise ValueError("Pillow is needed to cut strips (pip install Pillow).")
    im = Image.open(io.BytesIO(data))
    im = im.convert("RGB")
    W, H = im.size
    if H < max(min_h * 2, W * 1.8):
        return [(name + ".png", data)]
    aw = 48
    small = im.convert("L").resize((aw, H))
    px = small.load()
    rng = []
    for y in range(H):
        row = [px[x, y] for x in range(aw)]
        rng.append(max(row) - min(row))
    quiet = [r <= tol for r in rng]
    cuts, y = [], 0
    while y < H:
        if quiet[y]:
            z = y
            while z < H and quiet[z]:
                z += 1
            if z - y >= gutter:
                cuts.append((y + z) // 2)
            y = z
        else:
            y += 1
    bounds = [0] + [c for c in cuts if 0 < c < H] + [H]
    parts = [(a, b) for a, b in zip(bounds, bounds[1:]) if b - a > 4]
    merged: List[List[int]] = []
    for a, b in parts:
        if merged and (b - a < min_h or merged[-1][1] - merged[-1][0] < min_h) and (b - merged[-1][0]) <= max_h:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    final: List[List[int]] = []
    for a, b in merged:
        while b - a > max_h:   # no gutter: cut at the calmest row near the middle of the allowed range
            lo, hi = a + max_h // 2, a + max_h
            c = min(range(lo, hi), key=lambda r: rng[r])
            final.append([a, c])
            a = c
        final.append([a, b])
    out = []
    for i, (a, b) in enumerate(final):
        buf = io.BytesIO()
        im.crop((0, a, W, b)).save(buf, "PNG")
        out.append((f"{name}-{i + 1:03d}.png", buf.getvalue()))
    return out


def parse_script(text: str, n: int) -> List[str]:
    """Narration for `n` panels. Either "Panel 3: ..." markers, or paragraphs separated by a blank line.
    Extra paragraphs are joined onto the last panel; missing ones stay empty."""
    text = (text or "").replace("\r\n", "\n").strip()
    out = [""] * n
    if n <= 0 or not text:
        return out
    marks = list(re.finditer(r"(?im)^\s*(?:panel|trang|ảnh|anh|scene|cảnh|canh)\s*#?(\d+)\s*[:.)-]?\s*", text))
    if marks:
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
            i = int(m.group(1)) - 1
            if 0 <= i < n:
                out[i] = (out[i] + " " + text[m.end():end].strip()).strip()
        return out
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for i, p in enumerate(paras):
        out[min(i, n - 1)] = (out[min(i, n - 1)] + " " + p).strip() if i >= n else p
    return out


def caption_chunks(text: str, max_chars: int = 70) -> List[str]:
    """Short subtitle-sized pieces: split at sentence ends, then at commas / spaces."""
    t = re.sub(r"\s+", " ", novel.clean_for_speech(text or "")).strip()
    if not t:
        return []
    out: List[str] = []
    for sent in [s.strip() for s in novel._SENT.split(t) if s.strip()]:
        while len(sent) > max_chars:
            cut = max(sent.rfind(", ", 0, max_chars), sent.rfind("; ", 0, max_chars), sent.rfind(" ", 0, max_chars))
            cut = cut if cut > 20 else max_chars
            out.append(sent[:cut + 1].strip())
            sent = sent[cut + 1:].strip()
        if sent:
            out.append(sent)
    # merge tiny leftovers ("Yes.") into the previous piece when it still fits
    merged: List[str] = []
    for c in out:
        if merged and len(c) < 14 and len(merged[-1]) + 1 + len(c) <= max_chars + 15:
            merged[-1] += " " + c
        else:
            merged.append(c)
    return merged


# ------------------------------------------------------------------ library
def _folder(story_id: str, root: str) -> str:
    return os.path.join(root, os.path.basename(story_id))


def add_story(title: str, author: str, license_id: str, source: str, images: List[Tuple[str, bytes]], script: str = "",
              root: str = STORIES_DIR, split_strips: bool = False) -> Dict:
    pics = []
    if split_strips:
        expanded = []
        for name, data in images:
            if _sniff_ext(data) and len(data) <= MAX_IMG_BYTES:
                expanded.extend(split_strip(data, os.path.splitext(name)[0]))
            else:
                expanded.append((name, data))
        images = expanded
    for name, data in images:
        if len(data) > MAX_IMG_BYTES:
            raise ValueError(f"{name}: picture is larger than 15 MB.")
        ext = _sniff_ext(data)
        if not ext:
            raise ValueError(f"{name}: not a PNG / JPG / WEBP picture.")
        pics.append((name, data, ext))
    if not pics:
        raise ValueError("Add at least one picture.")
    if len(pics) > MAX_PANELS:
        raise ValueError(f"At most {MAX_PANELS} pictures per story.")
    pics.sort(key=lambda p: natural_key(p[0]))
    lic = license_id if license_id in novel.LICENSES else "unknown"
    sid = f"{novel.slug(title or 'story')}-{int(time.time()) % 100000}"
    folder = _folder(sid, root)
    os.makedirs(os.path.join(folder, "panels"), exist_ok=True)
    texts = parse_script(script, len(pics))
    panels = []
    for i, (_, data, ext) in enumerate(pics):
        fn = f"{i + 1:03d}{ext}"
        with open(os.path.join(folder, "panels", fn), "wb") as f:
            f.write(data)
        panels.append({"image": fn, "text": texts[i]})
    meta = {"id": sid, "title": (title or "Untitled").strip(), "author": (author or "").strip(), "license": lic,
            "source": (source or "").strip(), "panels": panels, "added": int(time.time())}
    _atomic_write(os.path.join(folder, "story.json"), meta)
    return meta


def list_stories(root: str = STORIES_DIR) -> List[Dict]:
    out = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return out
    for n in names:
        m = _read(os.path.join(root, n, "story.json"), None)
        if m:
            out.append(m)
    return out


def get_story(story_id: str, root: str = STORIES_DIR) -> Optional[Dict]:
    return _read(os.path.join(_folder(story_id or "x", root), "story.json"), None)


def save_story(meta: Dict, root: str = STORIES_DIR) -> None:
    _atomic_write(os.path.join(_folder(meta["id"], root), "story.json"), meta)


def update_license(story_id: str, license_id: str, root: str = STORIES_DIR) -> None:
    m = get_story(story_id, root)
    if m and license_id in novel.LICENSES:
        m["license"] = license_id
        save_story(m, root)


def set_texts(story_id: str, texts: List[str], root: str = STORIES_DIR) -> None:
    m = get_story(story_id, root)
    if not m:
        return
    for p, t in zip(m["panels"], texts):
        p["text"] = (t or "").strip()
    save_story(m, root)


def move_panel(story_id: str, i: int, delta: int, root: str = STORIES_DIR) -> None:
    m = get_story(story_id, root)
    j = i + delta
    if m and 0 <= i < len(m["panels"]) and 0 <= j < len(m["panels"]):
        m["panels"][i], m["panels"][j] = m["panels"][j], m["panels"][i]
        save_story(m, root)


def delete_panel(story_id: str, i: int, root: str = STORIES_DIR) -> None:
    m = get_story(story_id, root)
    if m and len(m["panels"]) > 1 and 0 <= i < len(m["panels"]):
        p = m["panels"].pop(i)
        try:
            os.remove(os.path.join(_folder(story_id, root), "panels", p["image"]))
        except OSError:
            pass
        save_story(m, root)


def delete_story(story_id: str, root: str = STORIES_DIR) -> None:
    if story_id:
        shutil.rmtree(_folder(story_id, root), ignore_errors=True)


def image_path(meta: Dict, i: int, root: str = STORIES_DIR) -> str:
    return os.path.join(_folder(meta["id"], root), "panels", meta["panels"][i]["image"])


def can_use(meta: Optional[Dict]) -> Tuple[bool, str]:
    """May this story be shown / read on a live and exported as a video?"""
    if not meta:
        return False, "Pick a story first."
    return novel.can_read_live(meta)


def credit_line(meta: Dict) -> str:
    return novel.credit_line(meta)


# ------------------------------------------------------------------ plot writer + post kit
def plot_prompt(genre: str, premise: str, panels: int = 12, tone: str = "dramatic", lang: str = "vi", hook: bool = True) -> str:
    """A prompt to paste into any free chat AI. The answer is parsed by parse_plot."""
    language = "Vietnamese" if lang == "vi" else "English"
    hook_line = "The first panel must be a hook: a shocking or curious moment that makes people keep watching.\n" if hook else ""
    return (
        f"Write an original short story as exactly {panels} picture panels, genre: {genre}, tone: {tone}.\n"
        f"Idea: {premise.strip() or 'surprise me'}\n"
        f"Language of the narration: {language}. Everything must be original (no existing characters, no copyrighted plots).\n"
        f"{hook_line}"
        "The last panel ends on a cliffhanger or a twist so viewers follow for the next part.\n"
        "Use this exact format for every panel and nothing else:\n"
        "PANEL 1\nPICTURE: one sentence describing the picture to draw / generate (characters, place, mood)\n"
        "NARRATION: 1-3 short sentences the narrator says (under 220 characters)\n\n"
        "Keep the same characters looking the same: describe each one once in the first PICTURE, then reuse the same words.")


def parse_plot(text: str) -> List[Dict]:
    """[{picture, narration}] from an AI answer in the PANEL / PICTURE / NARRATION format (forgiving)."""
    text = (text or "").replace("\r\n", "\n")
    blocks = re.split(r"(?im)^\s*\**\s*panel\s*#?\d+\s*\**\s*:?\s*$", text)
    out = []
    for b in blocks:
        pic = re.search(r"(?is)picture\s*\**\s*:\s*\**\s*(.+?)(?=\n\s*\**\s*narration|\Z)", b)
        nar = re.search(r"(?is)narration\s*\**\s*:\s*\**\s*(.+?)(?=\n\s*\**\s*picture|\n\s*\n|\Z)", b)
        if nar:
            out.append({"picture": re.sub(r"\s+", " ", pic.group(1)).strip() if pic else "",
                        "narration": re.sub(r"\s+", " ", nar.group(1)).strip()})
    return out


def plot_to_script(plot: List[Dict]) -> str:
    return "\n\n".join(f"Panel {i + 1}: {p['narration']}" for i, p in enumerate(plot))


def plot_to_picture_list(plot: List[Dict]) -> str:
    return "\n".join(f"{i + 1:03d}  {p['picture']}" for i, p in enumerate(plot) if p["picture"])


def post_kit(meta: Dict, lang: str = "vi", part: int = 1, hook: str = "", genre: str = "", extra_credits: str = "") -> str:
    """Caption + hashtags to paste into TikTok, with the licence credit when one is needed."""
    title = meta.get("title", "")
    head = hook.strip() or title
    follow = f"Theo dõi để xem phần {part + 1}!" if lang == "vi" else f"Follow for part {part + 1}!"
    tags = list(GENRE_TAGS.get(genre, [])) + HASHTAGS.get(lang, HASHTAGS["en"])
    seen, uniq = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    lines = [f"{head} (P{part})" if part else head, follow, " ".join(uniq[:8])]
    cr = novel.credit_line(meta) if meta.get("license") else ""
    if cr:
        lines.append("Credit: " + cr)
    if extra_credits:
        lines.append("Music: " + extra_credits)
    return "\n".join(lines)


# ------------------------------------------------------------------ control / status / overlay
def read_control(path: str = CONTROL_PATH) -> Dict:
    c = _read(path, {}) or {}
    s = dict(DEFAULT_SETTINGS)
    s.update({k: v for k, v in (c.get("settings") or {}).items() if k in DEFAULT_SETTINGS})
    return {"command": c.get("command") if c.get("command") in ("play", "pause", "stop") else "stop", "story": c.get("story") or "",
            "panel": int(c.get("panel") or 0), "seq": int(c.get("seq") or 0), "settings": s}


def write_control(ctl: Dict, path: str = CONTROL_PATH) -> None:
    _atomic_write(path, ctl)


def read_status(path: str = STATUS_PATH) -> Dict:
    return _read(path, {}) or {}


def write_status(st: Dict, path: str = STATUS_PATH) -> None:
    _atomic_write(path, dict(st, updated=time.time()))


def overlay_story(status: Dict, settings: Dict, now: float, fresh_s: float = 30.0) -> Optional[Dict]:
    """What the overlay shows while a picture story is read (None = nothing)."""
    if not status or not settings.get("show_text", True):
        return None
    if status.get("state") not in ("playing", "paused") or now - float(status.get("updated") or 0) > fresh_s:
        return None
    sid, i = status.get("story", ""), int(status.get("panel", 0))
    return {"title": status.get("title", ""), "image": f"/story-img/{sid}/{i}", "text": status.get("text", ""),
            "index": i + 1, "total": int(status.get("panels", 0)), "credit": status.get("credit", ""),
            "paused": status.get("state") == "paused"}
