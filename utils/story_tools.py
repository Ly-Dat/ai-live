"""Story studio tools: auto-crop long vertical strips into panels, read the text in a picture (OCR), build a recap prompt.

Pure logic (no UI, no network) so it is unit tested. They work on pictures you already have in the Story studio
(drawn by you, public domain, CC, or used with permission). The licence gate in story.py still decides what may be
shown live or exported as a video.
"""
import io
import re
from typing import Callable, List, Optional, Tuple

from . import story

MIN_PANEL_H = 120      # px: shorter pieces are merged into a neighbour
MAX_PANEL_RATIO = 1.8  # a piece taller than width * ratio is cut again (keeps it readable on a 9:16 video)


def _blank_rows(gray, tol: float, bg_tol: float):
    """True for rows that look like an empty gutter: almost one flat colour (white / black / any)."""
    import numpy as np
    flat = gray.std(axis=1) <= tol
    mean = gray.mean(axis=1)
    # the gutter colour is the most common flat-row colour; rows near it count, others (a flat blue sky) do not
    if flat.sum() == 0:
        return flat
    vals = np.round(mean[flat] / 8).astype(int)
    bg = np.bincount(vals).argmax() * 8
    return flat & (np.abs(mean - bg) <= bg_tol)


def split_strip(data: bytes, min_gap: int = 24, tol: float = 4.0, bg_tol: float = 24.0,
                min_h: int = MIN_PANEL_H, max_ratio: float = MAX_PANEL_RATIO) -> List[bytes]:
    """Cut one long picture at its empty horizontal gutters. Returns PNG bytes, top to bottom.
    A picture with no gutter is only cut by height (max_ratio), so nothing is lost."""
    import numpy as np
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = im.size
    gray = np.asarray(im.convert("L"), dtype=np.float32)
    blank = _blank_rows(gray, tol, bg_tol)

    cuts: List[Tuple[int, int]] = []   # content ranges (start, end)
    y = 0
    start: Optional[int] = None
    while y < h:
        if not blank[y]:
            if start is None:
                start = y
            y += 1
            continue
        j = y
        while j < h and blank[j]:
            j += 1
        if start is not None and (j - y) >= min_gap:
            cuts.append((start, y))
            start = None
        y = j
    if start is not None:
        cuts.append((start, h))
    if not cuts:
        cuts = [(0, h)]

    # merge too-short pieces into the previous one
    merged: List[List[int]] = []
    for a, b in cuts:
        if merged and (b - a) < min_h:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    if len(merged) > 1 and (merged[0][1] - merged[0][0]) < min_h:
        merged[1][0] = merged[0][0]
        merged.pop(0)

    # cut pieces that are still too tall
    limit = max(min_h, int(w * max_ratio))
    out: List[bytes] = []
    for a, b in merged:
        n = max(1, -(-(b - a) // limit))
        step = -(-(b - a) // n)
        for k in range(n):
            s, e = a + k * step, min(b, a + (k + 1) * step)
            if e - s < 8:
                continue
            buf = io.BytesIO()
            im.crop((0, s, w, e)).save(buf, "PNG")
            out.append(buf.getvalue())
    return out


def split_many(images: List[Tuple[str, bytes]], **kw) -> List[Tuple[str, bytes]]:
    """Auto-crop every picture of a chapter; names keep the order (01-01.png, 01-02.png, 02-01.png ...)."""
    res: List[Tuple[str, bytes]] = []
    for idx, (name, data) in enumerate(sorted(images, key=lambda p: story.natural_key(p[0]))):
        for k, piece in enumerate(split_strip(data, **kw)):
            res.append((f"{idx + 1:03d}-{k + 1:03d}.png", piece))
    return res[:story.MAX_PANELS]


# ------------------------------------------------------------------ OCR
def ocr_engine() -> str:
    """Which OCR is installed: 'rapidocr', 'tesseract' or '' (none)."""
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return "rapidocr"
    except Exception:
        pass
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return "tesseract"
    except Exception:
        return ""


def ocr_missing_hint() -> str:
    return "" if ocr_engine() else "No OCR installed. Run: pip install rapidocr-onnxruntime (easy), or install Tesseract + pytesseract."


def clean_ocr(text: str) -> str:
    t = re.sub(r"[ \t]+", " ", text or "")
    t = re.sub(r"\n{2,}", "\n", t).strip()
    return t


def ocr_image(data: bytes, lang: str = "vie+eng") -> str:
    """Text in one picture, top-to-bottom. Raises RuntimeError with a how-to when no OCR is installed."""
    eng = ocr_engine()
    if not eng:
        raise RuntimeError(ocr_missing_hint())
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if eng == "rapidocr":
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        res, _ = RapidOCR()(np.asarray(im))
        lines = sorted(res or [], key=lambda r: (min(p[1] for p in r[0]), min(p[0] for p in r[0])))
        return clean_ocr("\n".join(r[1] for r in lines))
    import pytesseract
    return clean_ocr(pytesseract.image_to_string(im, lang=lang))


def ocr_story(meta: dict, lang: str = "vie+eng", progress: Optional[Callable[[int, int], None]] = None,
              root: str = story.STORIES_DIR) -> List[str]:
    """OCR text of every panel of a story (same order as the panels)."""
    out = []
    n = len(meta["panels"])
    for i in range(n):
        with open(story.image_path(meta, i, root), "rb") as f:
            out.append(ocr_image(f.read(), lang))
        if progress:
            progress(i + 1, n)
    return out


# ------------------------------------------------------------------ recap prompt
def _source_language(texts: List[str]) -> str:
    """'Chinese', 'Japanese', 'Korean' or '' - the OCR often reads a raw manhua / webtoon in its original language."""
    blob = "".join(texts)
    if re.search(r"[\u3040-\u30ff]", blob):
        return "Japanese"
    if re.search(r"[\uac00-\ud7af]", blob):
        return "Korean"
    if re.search(r"[\u4e00-\u9fff]", blob):
        return "Chinese"
    return ""


def recap_prompt(texts: List[str], title: str = "", lang: str = "vi", style: str = "dramatic",
                 max_chars: int = 220, mode: str = "faithful") -> str:
    """A prompt to paste into any chat AI: it gets the text found in each panel and writes one narration per panel.
    mode "faithful" (default): translate / read the panel's own lines, in order, adding nothing - what a viewer expects when
    the video should tell what the pictures say. mode "recap": retell it in your own words (shorter, more storyteller).
    The answer goes back through story.parse_script ('Panel N: ...'), then you edit it in step 3."""
    language = "Vietnamese" if lang == "vi" else "English"
    body = "\n".join(f"Panel {i + 1}: {t.strip() or '(no text)'}" for i, t in enumerate(texts))
    name = f' "{title}"' if title else ""
    src = _source_language(texts)
    src_line = f"The text is in {src}: translate it into {language}. " if src else ""
    fmt = ("Answer with exactly this format and nothing else:\nPanel 1: ...\nPanel 2: ...\n"
           "(one line per panel, same numbers as below)\n\n")
    tail = f"--- PANEL TEXT ---\n{body}"
    if mode == "recap":
        return (
            f"You are a narrator for short story-recap videos{name}.\n"
            f"Below is the text OCR found in each picture panel (you cannot see the pictures). {src_line}Write ONE narration per panel in "
            f"{language}, style: {style}, like a storyteller who keeps the viewer hooked.\n\n"
            "Rules:\n"
            f"1. Retell what happens in your own words. 1-3 short sentences, under {max_chars} characters per panel, simple spoken "
            "language (it will be read aloud).\n"
            "2. Keep the story order. The first real story panel is a hook: a shocking or curious line that makes people stay. "
            "The last panel ends on a cliffhanger.\n"
            "3. Credits, staff names, publisher / platform names, logos and title cards are NOT story: for such a panel write "
            "exactly `-` (a dash).\n"
            "4. A panel marked (no text) is a picture only: write exactly `-` for it. Do not invent new characters, names, powers, "
            "places or events that the text does not support.\n"
            "5. The OCR has mistakes (missing spaces, wrong letters): fix them silently from context. If a panel is unclear, keep it "
            "short and vague instead of guessing.\n"
            "6. No explanations, titles, notes or markdown outside the format.\n\n" + fmt + tail)
    return (
        f"You are a translator for story videos{name}. Below is the text OCR found in each picture panel (you cannot see the "
        f"pictures). {src_line}For EVERY panel write what the panel says in natural spoken {language}, so a narrator can read it aloud.\n\n"
        "Rules:\n"
        "1. Be faithful: say what the panel says, in the same order, sentence by sentence, with the same meaning, tone and "
        "who-says-what. Do NOT summarise, shorten, comment, add events, add names or explain. Do not make the story up.\n"
        "2. Keep every sentence of the panel. Make it sound natural when spoken (not word-for-word machine translation), "
        "keep names consistent in every panel. Put the speaker first when the text makes it clear (\"Lan nói: ...\").\n"
        "3. Sound effects (e.g. bang, ah, ...) become a short natural equivalent or are dropped. "
        "Credits, staff names, publisher / platform names, logos, watermarks and title cards: write exactly `-`.\n"
        "4. A panel marked (no text), or whose text is only noise: write exactly `-`. Never invent a bridge sentence.\n"
        "5. The OCR has mistakes (missing spaces, wrong letters, stray symbols): fix them silently from context. "
        "If a word is really unclear, translate the clear part only.\n"
        "6. No explanations, titles, notes or markdown outside the format.\n\n" + fmt + tail)


# ------------------------------------------------------------------ the AI's answer
PROMPT_MARKERS = ("--- PANEL TEXT ---", "Answer with exactly this format")
_EMPTY = {"-", "--", "\u2014", "\u2013", "...", "\u2026", "n/a", "(none)"}


def parse_answer(text: str, n: int) -> Tuple[List[str], str]:
    """Narration for n panels from the AI's reply. Returns (texts, error). Error is "" when it worked.
    Refuses the prompt itself (a common slip: pasting the prompt instead of the AI's reply); a panel the AI
    answered with '-' (credits / title card) becomes empty, so it is shown silently."""
    t = (text or "").replace("\r\n", "\n")
    if any(m in t for m in PROMPT_MARKERS):
        return [], ("This is the prompt, not the AI's answer. Copy the prompt into a chat AI, then paste the AI's reply here.")
    t = re.sub(r"[*_`#]+", "", t)
    out = [("" if x.strip().lower() in _EMPTY else x.strip()) for x in story.parse_script(t, n)]
    if not any(out):
        return [], "Could not find lines like \"Panel 1: ...\" in the answer. Ask the AI to use exactly that format."
    return out, ""
