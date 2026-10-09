"""AI reading companion for the Novel reader - what the popular web-novel sites and AI reading apps are loved for:

  * Spoiler-safe questions ("who is Lan?") answered ONLY from the chapters you have read so far
  * Chapter summaries, and a TV-style "previously on ..." recap (main + minor characters) built from them
  * Character cards (role, traits, relations) that grow as you read
  * Reading stats and streaks (listening minutes, chapters finished)

Everything that needs an AI takes an injected `llm_fn(prompt) -> str` (see story_llm.make_llm), so it is unit tested offline and works
with a local model without pressing Start Run. Retrieval is plain keyword scoring: no embeddings, no extra packages.
"""
import json
import math
import os
import re
import unicodedata
import datetime
from typing import Callable, Dict, List, Optional, Tuple

from . import novel

SUMMARY_PATH = os.path.join("data", "novel_summaries.json")
STATS_PATH = os.path.join("data", "novel_stats.json")
STOP = set("la va cua cho voi mot nhung cac the nay do khong co duoc ma thi se da dang ai gi nao sao nhu tu den trong ra vao khi nen "
           "the a an of to and in is are was were who what why how when where did does do his her their it that this with for on at by "
           "be as from or not".split())


def fold(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower().replace("đ", "d")
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def tokens(text: str) -> List[str]:
    return [w for w in re.findall(r"\w+", fold(text), flags=re.UNICODE) if len(w) >= 2 and w not in STOP]


# ------------------------------------------------------------------ spoiler-safe passages
def book_passages(meta: Dict, chapter: int, chunk: Optional[int] = None, root: str = novel.NOVELS_DIR, size: int = 500) -> List[Dict]:
    """Passages {chapter, text} of everything up to the reading position: whole chapters before `chapter`, and of `chapter` itself the
    first chunk+1 lines (everything when chunk is None). Nothing after the position is ever returned - that is the spoiler shield."""
    out: List[Dict] = []
    for k in range(0, min(chapter, len(meta["chapters"]) - 1) + 1):
        body = novel.chapter_body(meta, k, root)
        if k == chapter and chunk is not None:
            body = " ".join(c["text"] for c in novel.chunks(body, 180)[:chunk + 1])
        cur = ""
        for p in [x.strip() for x in re.split(r"\n+", body) if x.strip()]:
            if cur and len(cur) + len(p) > size:
                out.append({"chapter": k, "text": cur})
                cur = p
            else:
                cur = (cur + " " + p).strip()
        if cur:
            out.append({"chapter": k, "text": cur})
    return out


def retrieve(passages: List[Dict], question: str, k: int = 5) -> List[Dict]:
    """The k passages that best match the question (keyword score with idf), returned in story order."""
    q = tokens(question)
    if not q or not passages:
        return passages[-k:] if passages else []
    docs = [tokens(p["text"]) for p in passages]
    n = len(docs)
    df = {w: sum(1 for d in docs if w in d) for w in set(q)}
    scored = []
    for i, d in enumerate(docs):
        score = 0.0
        for w in set(q):
            tf = d.count(w)
            if tf:
                score += (1 + math.log(tf)) * math.log(1 + n / (1 + df[w]))
        for a, b in zip(q, q[1:]):                      # neighbouring question words that are neighbours in the text
            if any(d[j] == a and d[j + 1] == b for j in range(len(d) - 1)):
                score += 1.5
        scored.append((score, i))
    best = [i for s, i in sorted(scored, key=lambda x: (-x[0], x[1])) if s > 0][:k]
    return [passages[i] for i in sorted(best)] or passages[-min(k, 2):]


def ask_prompt(title: str, question: str, excerpts: List[Dict], chapter: int, lang: str = "vi", summaries: str = "",
               max_words: int = 60) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    ex = "\n\n".join(f"[Chapter {e['chapter'] + 1}] {e['text']}" for e in excerpts) or "(nothing relevant found)"
    sm = f"Summary of the story so far:\n{summaries.strip()}\n\n" if summaries.strip() else ""
    return (
        f'You are a spoiler-safe reading companion for the story "{title}". The reader has read up to chapter {chapter + 1}.\n'
        "Answer the question using ONLY the text below. Never use anything you may know about this story from elsewhere, never mention or "
        "hint at events after what the text shows, and do not guess. If the text does not answer it, say in one sentence that it has "
        "not been revealed yet.\n"
        f"Answer in {language}, in at most {max_words} words, plain spoken sentences (it may be read aloud), no lists, no markdown.\n\n"
        f"{sm}TEXT:\n{ex}\n\nQUESTION: {question.strip()}")


def clean_answer(text: str, max_chars: int = 420) -> str:
    t = re.sub(r"[*_`#>]+", "", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > max_chars:
        cut = max(t.rfind(". ", 0, max_chars), t.rfind("! ", 0, max_chars), t.rfind("? ", 0, max_chars))
        t = t[:cut + 1] if cut > 80 else t[:max_chars].rstrip() + "..."
    return t


def ask(meta: Dict, question: str, chapter: int, chunk: Optional[int], llm_fn: Callable[[str], str], lang: str = "vi",
        root: str = novel.NOVELS_DIR, summary_path: str = SUMMARY_PATH, max_words: int = 60) -> str:
    """The companion's answer, from the text up to the reading position (+ cached summaries of earlier chapters)."""
    ex = retrieve(book_passages(meta, chapter, chunk, root), question, 5)
    sums = load_summaries(summary_path).get(meta["id"], {})
    so_far = "\n".join(f"Chapter {int(k) + 1}: {v}" for k, v in sorted(sums.items(), key=lambda kv: int(kv[0])) if int(k) < chapter)
    return clean_answer(llm_fn(ask_prompt(meta["title"], question, ex, chapter, lang, so_far[-1800:], max_words)))


def viewer_answer(meta: Dict, user: str, question: str, chapter: int, chunk: Optional[int], llm_fn: Callable[[str], str],
                  unsafe: Optional[Callable[[str, str], bool]] = None, lang: str = "vi", root: str = novel.NOVELS_DIR,
                  summary_path: str = SUMMARY_PATH) -> str:
    """What the host says for a viewer's `!hoi` question ('' = say nothing). `unsafe(text, scope)` is the TikTok policy filter:
    a question or answer it flags is dropped, so a troll cannot make the host read something out of policy."""
    if unsafe and unsafe(question, "input"):
        return ""
    try:
        ans = ask(meta, question, chapter, chunk, llm_fn, lang, root, summary_path, max_words=50)
    except Exception:
        return ""
    if not ans or (unsafe and unsafe(ans, "output")):
        return ""
    who = re.sub(r"[^\w .\-]", "", user or "", flags=re.UNICODE).strip()[:24] or ("ban" if lang == "vi" else "viewer")
    return (f"{who} hỏi: {question.strip()} {ans}" if lang == "vi" else f"{who} asks: {question.strip()} {ans}")


# ------------------------------------------------------------------ summaries and "previously on"
def load_summaries(path: str = SUMMARY_PATH) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_summaries(data: Dict, path: str = SUMMARY_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def chapter_summary_prompt(title: str, chapter_title: str, body: str, lang: str = "vi") -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    body = body if len(body) <= 7000 else body[:4500] + "\n[...]\n" + body[-2500:]
    return (f'Summarise this chapter of "{title}" ({chapter_title}) in {language}: 3-4 sentences, plain spoken style. Say who does what, '
            "what changes, and how the chapter ends. Use the characters' names. Only what the text says - no opinions, no guesses.\n\n"
            f"CHAPTER TEXT:\n{body}")


def summarize_chapters(meta: Dict, upto: int, llm_fn: Callable[[str], str], lang: str = "vi", root: str = novel.NOVELS_DIR,
                       path: str = SUMMARY_PATH, progress: Optional[Callable[[int, int, str], None]] = None,
                       cancel: Optional[Callable[[], bool]] = None, only_last: int = 0) -> Dict[int, str]:
    """Summaries of chapters 0..upto (cached in data/novel_summaries.json; only the missing ones are written).
    only_last > 0 limits it to the last N chapters of that range (what a recap needs)."""
    data = load_summaries(path)
    book = data.setdefault(meta["id"], {})
    first = max(0, upto - only_last + 1) if only_last else 0
    todo = [k for k in range(first, min(upto, len(meta["chapters"]) - 1) + 1) if not (book.get(str(k)) or "").strip()]
    for n, k in enumerate(todo):
        if cancel and cancel():
            raise RuntimeError("Cancelled.")
        if progress:
            progress(n, len(todo), f"Summarising chapter {k + 1}")
        text = clean_answer(llm_fn(chapter_summary_prompt(meta["title"], meta["chapters"][k]["title"], novel.chapter_body(meta, k, root), lang)), 900)
        if text:
            book[str(k)] = text
            save_summaries(data, path)
    if progress:
        progress(len(todo), len(todo), "Done")
    return {k: book[str(k)] for k in range(first, upto + 1) if book.get(str(k))}


def previously_prompt(title: str, summaries: List[Tuple[int, str]], lang: str = "vi") -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    body = "\n".join(f"Chapter {k + 1}: {t}" for k, t in summaries)
    return (f'Write a TV-style "previously on ..." recap for the story "{title}" in {language}: 2-4 spoken sentences, at most 70 words. '
            "Name the main characters, say the one thing that matters most from the chapters below, and end on the open question. "
            "Use only these summaries, add nothing, no spoilers beyond them, no markdown.\n\n" + body)


def previously_on(meta: Dict, chapter: int, llm_fn: Callable[[str], str], lang: str = "vi", root: str = novel.NOVELS_DIR,
                  path: str = SUMMARY_PATH, last: int = 3) -> str:
    """The spoken recap before chapter `chapter` (0-based): built from the summaries of the last `last` chapters. '' for chapter 1."""
    if chapter <= 0:
        return ""
    sums = summarize_chapters(meta, chapter - 1, llm_fn, lang, root, path, only_last=last)
    if not sums:
        return ""
    return clean_answer(llm_fn(previously_prompt(meta["title"], sorted(sums.items()), lang)), 520)


# ------------------------------------------------------------------ character cards
def characters_prompt(title: str, names: List[str], mentions: Dict[str, List[str]], chapter: int, lang: str = "vi") -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    body = "\n\n".join(f"{n}:\n" + "\n".join(f"- {m}" for m in mentions.get(n, [])[:3]) for n in names)
    return (f'Character cards for the story "{title}", written for a reader who has read up to chapter {chapter + 1}. Language: {language}. '
            "For each name below write ONE line: NAME | role in the story | 3 traits | relations to other named characters. "
            "Use ONLY what the quotes show; write '?' where the text does not say; never add later events.\n"
            "Format, one line per character and nothing else:\nNAME | role | traits | relations\n\n" + body)


def parse_characters(text: str) -> List[Dict[str, str]]:
    out = []
    for line in re.sub(r"[*_`]+", "", text or "").split("\n"):
        parts = [p.strip() for p in line.strip(" -•").split("|")]
        if len(parts) >= 3 and parts[0] and len(parts[0]) < 40:
            out.append({"name": parts[0], "role": parts[1], "traits": parts[2], "relations": parts[3] if len(parts) > 3 else ""})
    return out


def character_cards(meta: Dict, chapter: int, chunk: Optional[int], llm_fn: Callable[[str], str], lang: str = "vi",
                    root: str = novel.NOVELS_DIR, top: int = 8, names: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Cards for the main characters, from the text read so far."""
    ps = book_passages(meta, chapter, chunk, root)
    text = "\n".join(p["text"] for p in ps)
    names = names or novel.detect_characters(text, top=top)
    if not names:
        return []
    mentions = {n: [re.sub(r"\s+", " ", p["text"])[:260] for p in ps if n in p["text"]][:3] for n in names}
    cards = parse_characters(llm_fn(characters_prompt(meta["title"], names, mentions, chapter, lang)))
    known = {n.lower() for n in names}
    return [c for c in cards if c["name"].lower() in known] or cards


# ------------------------------------------------------------------ reading stats
def _day(now: Optional[float]) -> str:
    return datetime.date.fromtimestamp(now if now is not None else __import__("time").time()).isoformat()


def record_stats(seconds: float = 0.0, chapters: int = 0, path: str = STATS_PATH, now: Optional[float] = None) -> None:
    """Add listening time / finished chapters to today. Called by the reader after every line."""
    data = load_summaries(path)
    d = data.setdefault("days", {}).setdefault(_day(now), {"sec": 0.0, "chapters": 0})
    d["sec"] = round(float(d.get("sec", 0)) + max(0.0, seconds), 1)
    d["chapters"] = int(d.get("chapters", 0)) + int(chapters)
    save_summaries(data, path)


def stats_summary(path: str = STATS_PATH, now: Optional[float] = None) -> Dict:
    """{today_min, week_min, total_min, chapters, streak, best_streak}: a streak is consecutive days with any listening."""
    days = (load_summaries(path).get("days") or {})
    today = datetime.date.fromisoformat(_day(now))
    mins = lambda d: round(float((days.get(d.isoformat()) or {}).get("sec", 0)) / 60.0, 1)
    active = {k for k, v in days.items() if float(v.get("sec", 0)) >= 30 or int(v.get("chapters", 0)) > 0}
    streak, d = 0, today if today.isoformat() in active else today - datetime.timedelta(days=1)
    while d.isoformat() in active:
        streak += 1
        d -= datetime.timedelta(days=1)
    best = run = 0
    prev = None
    for k in sorted(active):
        cur = datetime.date.fromisoformat(k)
        run = run + 1 if prev and (cur - prev).days == 1 else 1
        best, prev = max(best, run), cur
    return {"today_min": mins(today), "week_min": round(sum(mins(today - datetime.timedelta(days=i)) for i in range(7)), 1),
            "total_min": round(sum(float(v.get("sec", 0)) for v in days.values()) / 60.0, 1),
            "chapters": sum(int(v.get("chapters", 0)) for v in days.values()), "streak": streak, "best_streak": best}
