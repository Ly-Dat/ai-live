"""Novel reading: library, chapters, sentence chunks, narrator / dialogue voices, licence gate, control + status files.

The reader (novel_reader.py) runs as its own process and talks to the host through the same /send "reread" API the
product tour uses. This module is pure logic (no network, no UI) so it is unit tested.

Licence gate: a story is only read on a live if the seller says they may (public domain, own text, CC0 / CC BY,
written permission). "Copyrighted, no permission" and "not sure" stories are blocked: reading someone else's novel on a
live is copyright infringement and TikTok / the author can take the live down.
"""
import html
import json
import os
import re
import shutil
import time
import zipfile
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

NOVELS_DIR = os.path.join("data", "novels")
CONTROL_PATH = os.path.join("data", "novel_state.json")      # UI -> reader
STATUS_PATH = os.path.join("data", "novel_status.json")      # reader -> UI + overlay
PROGRESS_PATH = os.path.join("data", "novel_progress.json")
PRON_PATH = os.path.join("data", "novel_pronunciations.json")
BOOKMARKS_PATH = os.path.join("data", "novel_bookmarks.json")

LICENSES: Dict[str, Dict] = {
    "public-domain": {"label": "Public domain (copyright expired)", "ok": True, "credit": False},
    "own": {"label": "I wrote it", "ok": True, "credit": False},
    "cc0": {"label": "CC0", "ok": True, "credit": False},
    "cc-by": {"label": "CC BY (credit the author)", "ok": True, "credit": True},
    "permission": {"label": "The author / publisher allowed me in writing", "ok": True, "credit": True},
    "copyrighted": {"label": "Copyrighted, no permission", "ok": False, "credit": False},
    "unknown": {"label": "Not sure - not read live", "ok": False, "credit": False},
}
DEFAULT_SETTINGS = {
    "voice_narrator": "", "voice_dialogue": "", "rate": 0, "pause_s": 0.4, "yield_comments": True,
    "auto_next": True, "announce_chapter": True, "show_text": True, "sleep_min": 0, "safety": True,
    "characters": {},   # name -> voice ("" = the dialogue voice): who says a line is found from tags like "Lan nói" / "said Mark"
}
DEFAULT_PRON = {"TP.HCM": "Thành phố Hồ Chí Minh", "TP. HCM": "Thành phố Hồ Chí Minh", "UBND": "Ủy ban nhân dân",
                "THPT": "trung học phổ thông", "THCS": "trung học cơ sở"}

_ROMAN = r"[ivxlcdm]+"
_HEADING = re.compile(r"^\s*(?:#{1,3}\s+\S.*|(?:chương|chuong|chapter|hồi|hoi|phần|phan|quyển|quyen|part)\s+(?:\d+|" + _ROMAN + r")\b.*)\s*$",
                      re.I)
_SENT = re.compile(r"(?<=[.!?…])[\"”»’)]*\s+")
_OPEN = "“«‘"
_CLOSE = "”»’"


# ------------------------------------------------------------------ files
def _atomic_write(path: str, data: Dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _read(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


# ------------------------------------------------------------------ loading text
class _Strip(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out: List[str] = []
        self.skip = 0
        self.title = ""
        self._in_head = False
        self._buf_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr"):
            self.out.append("\n")
        if tag in ("h1", "h2", "h3") and not self.title:
            self._buf_title = True

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "li", "h1", "h2", "h3", "h4"):
            self.out.append("\n")
        if tag in ("h1", "h2", "h3"):
            self._buf_title = False

    def handle_data(self, data):
        if self.skip:
            return
        self.out.append(data)
        if self._buf_title and data.strip() and not self.title:
            self.title = data.strip()


def html_to_text(markup: str) -> Tuple[str, str]:
    p = _Strip()
    p.feed(markup)
    text = html.unescape("".join(p.out))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text, p.title


def load_epub(path: str) -> Tuple[str, str]:
    """(text with '# Chapter' headings, title). Plain EPUB 2/3 without DRM only."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        container = z.read("META-INF/container.xml").decode("utf-8", "ignore")
        opf_path = re.search(r'full-path="([^"]+)"', container).group(1)
        base = os.path.dirname(opf_path)
        opf = z.read(opf_path).decode("utf-8", "ignore")
        manifest = {m.group(1): m.group(2) for m in re.finditer(r'<item\b[^>]*?\bid="([^"]+)"[^>]*?\bhref="([^"]+)"', opf)}
        manifest.update({m.group(2): m.group(1) for m in re.finditer(r'<item\b[^>]*?\bhref="([^"]+)"[^>]*?\bid="([^"]+)"', opf)
                         if m.group(2) not in manifest})
        spine = re.findall(r'<itemref\b[^>]*?\bidref="([^"]+)"', opf)
        title_m = re.search(r"<dc:title[^>]*>(.*?)</dc:title>", opf, re.S)
        title = html.unescape(title_m.group(1).strip()) if title_m else ""
        parts = []
        for ref in spine:
            href = manifest.get(ref)
            if not href:
                continue
            full = os.path.normpath(os.path.join(base, href)).replace("\\", "/")
            if full not in names:
                continue
            text, head = html_to_text(z.read(full).decode("utf-8", "ignore"))
            if len(text) < 40:
                continue
            first = text.splitlines()[0].strip() if text else ""
            if head and first == head:
                text = text[len(first):].lstrip()
            parts.append(("# " + (head or f"Phần {len(parts) + 1}")) + "\n\n" + text)
    return "\n\n".join(parts), title


def load_file(path: str) -> Tuple[str, str]:
    """(text, title guess) for .txt / .md / .epub."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".epub":
        return load_epub(path)
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "utf-16", "cp1258", "cp1252"):
        try:
            return raw.decode(enc).replace("\r\n", "\n"), os.path.splitext(os.path.basename(path))[0]
        except (UnicodeDecodeError, UnicodeError):
            continue
    return raw.decode("utf-8", "replace").replace("\r\n", "\n"), os.path.splitext(os.path.basename(path))[0]


# ------------------------------------------------------------------ chapters
def split_chapters(text: str, fallback_chars: int = 6000) -> List[Dict]:
    """[{title, start, end}] offsets into `text`. Headings: '# ...', 'Chương 3', 'Chapter IV', 'Hồi 2', 'Phần 1' ..."""
    heads = []
    pos = 0
    for line in text.splitlines(keepends=True):
        s = line.strip()
        if s and len(s) <= 90 and _HEADING.match(s):
            heads.append((pos, pos + len(line), re.sub(r"^#+\s*", "", s)))
        pos += len(line)
    chapters: List[Dict] = []
    if len(heads) >= 2 or (len(heads) == 1 and len(text) > fallback_chars):
        if heads[0][0] > 0 and len(text[:heads[0][0]].strip()) > 200:
            chapters.append({"title": "Mở đầu", "start": 0, "end": heads[0][0]})
        for i, (a, b, title) in enumerate(heads):
            end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
            chapters.append({"title": title, "start": b, "end": end})
    elif len(text) <= fallback_chars:
        chapters.append({"title": "Toàn bộ", "start": 0, "end": len(text)})
    else:  # no headings: cut at a paragraph / sentence boundary near every `fallback_chars`
        start, n = 0, 1
        while start < len(text):
            end = min(len(text), start + fallback_chars)
            if end < len(text):
                cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
                end = cut + 1 if cut > start + fallback_chars // 2 else end
            chapters.append({"title": f"Phần {n}", "start": start, "end": end})
            start, n = end, n + 1
    return [c for c in chapters if text[c["start"]:c["end"]].strip()]


# ------------------------------------------------------------------ narrator / dialogue
def _quote_pieces(par: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    buf, role, i = "", "narrator", 0
    straight_open = False
    for ch in par:
        opens = ch in _OPEN or (ch == '"' and not straight_open)
        closes = ch in _CLOSE or (ch == '"' and straight_open)
        if role == "narrator" and opens:
            if buf.strip():
                out.append(("narrator", buf.strip()))
            buf, role = "", "dialogue"
            straight_open = ch == '"'
            continue
        if role == "dialogue" and closes:
            if buf.strip():
                out.append(("dialogue", buf.strip()))
            buf, role = "", "narrator"
            straight_open = False
            continue
        buf += ch
    if buf.strip():
        out.append((role, buf.strip()))
    return out


def paragraph_pieces(par: str) -> List[Tuple[str, str]]:
    """Split one paragraph into (role, text). Handles “quotes”, "quotes" and Vietnamese dash dialogue lines."""
    par = par.strip()
    if not par:
        return []
    if re.match(r"^[—–-]\s*\S", par):
        segs = re.split(r"\s[—–-]\s", re.sub(r"^[—–-]\s*", "", par))
        return [("dialogue" if i % 2 == 0 else "narrator", s.strip()) for i, s in enumerate(segs) if s.strip()]
    return _quote_pieces(par)


def clean_for_speech(text: str, pron: Optional[Dict[str, str]] = None) -> str:
    t = re.sub(r"[*_`#>]+", " ", text)
    t = re.sub(r"(?m)^\s*[-=~_*]{3,}\s*$", " ", t)
    t = t.replace("...", "…")
    for k, v in (pron or {}).items():
        if k:
            t = re.sub(r"(?<!\w)" + re.escape(k) + r"(?!\w)", v, t)
    return re.sub(r"\s+", " ", t).strip()


_SPEECH_VERBS = (r"nói|hỏi|đáp|trả lời|thì thầm|thầm thì|kêu|quát|hét|gắt|cười|thở dài|lẩm bẩm|reo|mắng|bảo|said|asked|replied|whispered|shouted|"
                 r"cried|muttered|answered|sighed|laughed|snapped")
_NAME = r"[A-ZÀ-Ỹ][A-Za-zÀ-ỹ']+(?:\s[A-ZÀ-Ỹ][A-Za-zÀ-ỹ']+)?"
_BEFORE = re.compile(r"(" + _NAME + r")\s+(?:" + _SPEECH_VERBS + r")\b")
_AFTER = re.compile(r"\b(?:" + _SPEECH_VERBS + r")\s+(" + _NAME + r")")
_NOT_NAMES = {"Anh", "Chị", "Cô", "Ông", "Bà", "Em", "Hắn", "Nàng", "Chàng", "Họ", "Nó", "Mình", "Tôi", "Cậu", "Bạn", "He", "She", "They", "I", "It", "We",
              "You", "The", "And", "But", "Then", "Người", "Một", "Mọi", "Ai"}


def find_speaker(narration: str, names) -> str:
    """The first listed character mentioned in the narration part of a paragraph ('' if none)."""
    best, pos = "", 10 ** 9
    for n in names or []:
        m = re.search(r"(?<!\w)" + re.escape(n) + r"(?!\w)", narration, re.I)
        if m and m.start() < pos:
            best, pos = n, m.start()
    return best


def detect_characters(text: str, top: int = 8, min_count: int = 2) -> List[str]:
    """Names that appear next to a speech verb ('Lan nói', 'said Mark') often enough to be characters."""
    count: Dict[str, int] = {}
    for rx in (_BEFORE, _AFTER):
        for m in rx.finditer(text):
            n = m.group(1).strip()
            first = n.split()[0]
            if first in _NOT_NAMES or len(n) < 2:
                continue
            count[n] = count.get(n, 0) + 1
    return [n for n, c in sorted(count.items(), key=lambda kv: -kv[1]) if c >= min_count][:top]


def piece_speaker(pieces, k: int, names) -> str:
    """Who says dialogue piece k: the narration just before it when that ends with ':' or ',' ("Lan nói: “...”"), else the narration
    just after it ("“...” Lan nói."), else the one before, else anyone named in the paragraph."""
    if not names:
        return ""
    prev = pieces[k - 1][1] if k > 0 and pieces[k - 1][0] == "narrator" else ""
    nxt = pieces[k + 1][1] if k + 1 < len(pieces) and pieces[k + 1][0] == "narrator" else ""
    order = [prev, nxt, prev] if prev.rstrip().endswith((":", ",")) else [nxt, prev]
    for text in order:
        sp = find_speaker(text, names) if text else ""
        if sp:
            return sp
    return find_speaker(" ".join(t for r, t in pieces if r == "narrator"), names)


def chunks(body: str, max_chars: int = 180, pron: Optional[Dict[str, str]] = None, characters=None) -> List[Dict]:
    """[{role, text, speaker}] ready for TTS: same-role (and same-speaker) sentences merged up to `max_chars`."""
    out: List[Dict] = []
    for par in re.split(r"\n\s*\n|\n", body):
        pieces = paragraph_pieces(par)
        cur_role, cur, cur_sp = None, "", ""
        for k, (role, piece) in enumerate(pieces):
            piece = clean_for_speech(piece, pron)
            if not any(ch.isalnum() for ch in piece):
                continue
            sp = piece_speaker(pieces, k, characters) if role == "dialogue" else ""
            for sent in [x.strip() for x in _SENT.split(piece) if x.strip()]:
                if cur_role == role and cur_sp == sp and cur and len(cur) + 1 + len(sent) <= max_chars:
                    cur += " " + sent
                    continue
                if cur:
                    out.append({"role": cur_role, "text": cur, "speaker": cur_sp})
                cur_role, cur, cur_sp = role, sent, sp
        if cur:
            out.append({"role": cur_role, "text": cur, "speaker": cur_sp})
    # very long sentences: cut at commas / spaces so no TTS call is huge
    final: List[Dict] = []
    for c in out:
        t = c["text"]
        while len(t) > max_chars * 1.6:
            cut = max(t.rfind(", ", 0, max_chars), t.rfind("; ", 0, max_chars), t.rfind(" ", 0, max_chars))
            cut = cut if cut > 30 else max_chars
            final.append({"role": c["role"], "text": t[:cut + 1].strip(), "speaker": c.get("speaker", "")})
            t = t[cut + 1:].strip()
        if t:
            final.append({"role": c["role"], "text": t, "speaker": c.get("speaker", "")})
    return final


def spoken_seconds(text: str, cps: float = 13.0, rate: int = 0) -> float:
    return len(text) / max(3.0, cps * (1 + rate / 100.0))


# ------------------------------------------------------------------ library
def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", re.sub(r"[đĐ]", "d", title).lower().encode("ascii", "ignore").decode() or "story").strip("-")
    return (s or "story")[:40]


def add_book(title: str, author: str, license_id: str, source: str, text: str, root: str = NOVELS_DIR) -> Dict:
    text = text.replace("\r\n", "\n").strip()
    if len(text) < 100:
        raise ValueError("The text is too short to read.")
    lic = license_id if license_id in LICENSES else "unknown"
    bid = f"{slug(title or 'story')}-{int(time.time()) % 100000}"
    folder = os.path.join(root, bid)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "text.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    meta = {"id": bid, "title": (title or "Untitled").strip(), "author": (author or "").strip(), "license": lic,
            "source": (source or "").strip(), "chapters": split_chapters(text), "chars": len(text), "added": int(time.time())}
    _atomic_write(os.path.join(folder, "meta.json"), meta)
    return meta


def list_books(root: str = NOVELS_DIR) -> List[Dict]:
    out = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return out
    for n in names:
        m = _read(os.path.join(root, n, "meta.json"), None)
        if m:
            out.append(m)
    return out


def get_book(book_id: str, root: str = NOVELS_DIR) -> Optional[Dict]:
    if not book_id or os.sep in book_id or "/" in book_id or ".." in book_id:
        return None
    return _read(os.path.join(root, book_id, "meta.json"), None)


def update_license(book_id: str, license_id: str, root: str = NOVELS_DIR) -> None:
    m = get_book(book_id, root)
    if m and license_id in LICENSES:
        m["license"] = license_id
        _atomic_write(os.path.join(root, book_id, "meta.json"), m)


def delete_book(book_id: str, root: str = NOVELS_DIR) -> None:
    if get_book(book_id, root):
        shutil.rmtree(os.path.join(root, book_id), ignore_errors=True)


def book_text(book_id: str, root: str = NOVELS_DIR) -> str:
    try:
        with open(os.path.join(root, book_id, "text.txt"), "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def chapter_body(meta: Dict, idx: int, root: str = NOVELS_DIR) -> str:
    ch = meta["chapters"][idx]
    return book_text(meta["id"], root)[ch["start"]:ch["end"]]


def can_read_live(meta: Optional[Dict]) -> Tuple[bool, str]:
    if not meta:
        return False, "Pick a story first."
    info = LICENSES.get(meta.get("license"), LICENSES["unknown"])
    if not info["ok"]:
        return False, "Not allowed on a live: " + info["label"] + ". Use a public-domain, CC or your own story."
    if info["credit"] and not (meta.get("author") or "").strip():
        return False, "Add the author's name (a credit is needed for this licence)."
    return True, ""


def credit_line(meta: Dict) -> str:
    info = LICENSES.get(meta.get("license"), LICENSES["unknown"])
    if not info["credit"]:
        return ""
    s = f'"{meta["title"]}" by {meta["author"]}'
    if meta.get("source"):
        s += f' ({meta["source"]})'
    return s + " - " + info["label"].split(" (")[0]


# ------------------------------------------------------------------ settings / control / status / progress
def load_pron() -> Dict[str, str]:
    d = dict(DEFAULT_PRON)
    d.update(_read(PRON_PATH, {}) or {})
    return d


def save_pron(pron: Dict[str, str]) -> None:
    _atomic_write(PRON_PATH, {k: v for k, v in pron.items() if k})


def read_control(path: str = CONTROL_PATH) -> Dict:
    c = _read(path, {}) or {}
    s = dict(DEFAULT_SETTINGS)
    s.update({k: v for k, v in (c.get("settings") or {}).items() if k in DEFAULT_SETTINGS})
    return {"command": c.get("command") if c.get("command") in ("play", "pause", "stop") else "stop", "book": c.get("book") or "",
            "chapter": int(c.get("chapter") or 0), "chunk": int(c.get("chunk") or 0), "seq": int(c.get("seq") or 0), "settings": s}


def write_control(ctl: Dict, path: str = CONTROL_PATH) -> None:
    _atomic_write(path, ctl)


def read_status(path: str = STATUS_PATH) -> Dict:
    return _read(path, {}) or {}


def write_status(st: Dict, path: str = STATUS_PATH) -> None:
    st = dict(st, updated=time.time())
    _atomic_write(path, st)


def load_progress(path: str = PROGRESS_PATH) -> Dict:
    return _read(path, {}) or {}


def save_progress(book_id: str, chapter: int, chunk: int, path: str = PROGRESS_PATH) -> None:
    p = load_progress(path)
    p[book_id] = {"chapter": chapter, "chunk": chunk, "updated": int(time.time())}
    _atomic_write(path, p)


def overlay_novel(status: Dict, settings: Dict, now: float, fresh_s: float = 30.0) -> Optional[Dict]:
    """What the on-screen overlay shows while a story is being read (None = nothing)."""
    if not status or not settings.get("show_text", True):
        return None
    if status.get("state") not in ("playing", "paused") or now - float(status.get("updated") or 0) > fresh_s:
        return None
    return {"title": status.get("title", ""), "chapter": status.get("chapter_title", ""), "prev": status.get("prev", ""),
            "text": status.get("text", ""), "next": status.get("next", ""), "credit": status.get("credit", ""),
            "paused": status.get("state") == "paused", "role": status.get("role", "narrator")}


# ------------------------------------------------------------------ reading time, search, bookmarks
def chapter_minutes(meta: Dict, idx: int, cps: float = 13.0, rate: int = 0) -> float:
    ch = meta["chapters"][idx]
    return spoken_seconds("x" * max(0, ch["end"] - ch["start"]), cps, rate) / 60.0


def book_minutes(meta: Dict, cps: float = 13.0, rate: int = 0) -> float:
    return sum(chapter_minutes(meta, i, cps, rate) for i in range(len(meta["chapters"])))


def fmt_minutes(m: float) -> str:
    m = int(round(m))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{max(m, 1)} min"


def search(meta: Dict, query: str, limit: int = 20, characters=None, root: str = NOVELS_DIR) -> List[Dict]:
    """Lines of the story that contain `query`: [{chapter, chunk, text}] (so the reader can start right there)."""
    q = (query or "").strip().lower()
    out: List[Dict] = []
    if len(q) < 2:
        return out
    text = book_text(meta["id"], root).lower()
    for ci, ch in enumerate(meta["chapters"]):
        if q not in text[ch["start"]:ch["end"]]:
            continue
        for j, c in enumerate(chunks(chapter_body(meta, ci, root), 180, load_pron(), characters)):
            if q in c["text"].lower():
                out.append({"chapter": ci, "chunk": j, "text": c["text"]})
                if len(out) >= limit:
                    return out
    return out


def list_bookmarks(book_id: str, path: str = BOOKMARKS_PATH) -> List[Dict]:
    return (_read(path, {}) or {}).get(book_id, [])


def add_bookmark(book_id: str, chapter: int, chunk: int, note: str = "", path: str = BOOKMARKS_PATH) -> None:
    d = _read(path, {}) or {}
    d.setdefault(book_id, []).append({"chapter": int(chapter), "chunk": int(chunk), "note": (note or "").strip()[:80], "created": int(time.time())})
    _atomic_write(path, d)


def delete_bookmark(book_id: str, index: int, path: str = BOOKMARKS_PATH) -> None:
    d = _read(path, {}) or {}
    items = d.get(book_id, [])
    if 0 <= index < len(items):
        items.pop(index)
        _atomic_write(path, d)
