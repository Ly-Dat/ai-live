"""Long-form AI novel writer: a story workspace that remembers, instead of a "generate" button.

What the research briefs say makes people finish a story and come back to it, built here:
  * PREMISE options (hook, goal, conflict, stakes, twist), a STORY BIBLE (characters with goal / fear / flaw / secret / voice,
    world, rules, ending) and an editable chapter OUTLINE with turning points, hook types and planned clues and payoffs
  * chapter-by-chapter DRAFTING from a compact, task-specific context (canon + this chapter's plan + relevant characters + memory +
    open threads + style), never the whole book
  * NARRATIVE MEMORY after every chapter: facts, who knows what, new threads, paid threads, changes (injuries, objects, relationships)
  * OPEN-THREAD / foreshadowing tracker with overdue and unprepared-reveal warnings (no AI needed)
  * CHECKS: local (length, cliches, repeated openers, pacing, hook, unknown names, overdue threads) and an AI continuity audit with evidence
  * REVISION MODES on one paragraph or the whole chapter, shown as a DIFF to accept or reject; VERSION HISTORY; approve / lock chapters
  * STEERING: three consequential directions at the end of a chapter (or your own words) that shape the next chapter
  * READER-ENGAGEMENT REVIEW (diagnosis separate from fixes), STYLE profile from your own sample, "where we left off" resume card,
    daily word goal, Markdown export and publish into the Novel reader (it can then be read aloud on the live)
Every AI call takes an injected `llm_fn(prompt) -> str`, so it is unit tested offline. Projects live in data/novel_projects/*.json.
"""
import difflib
import json
import os
import re
import time
from typing import Callable, Dict, List, Optional, Tuple

from . import novel, story_writer
from .novel_companion import fold

PROJECTS_DIR = os.path.join("data", "novel_projects")
LLM = Callable[[str], str]
TEMP = {"premise": 1.0, "bible": 0.8, "outline": 0.7, "draft": 0.85, "memory": 0.1, "audit": 0.2, "revise": 0.7, "choices": 1.0, "review": 0.3}

HOOK_TYPES = {
    "question": "end on a meaningful unanswered question",
    "decision": "end on a consequential decision the hero has just made",
    "reveal": "end on a revelation that changes what the reader believed",
    "reversal": "end on a reversal: the plan fails or the ally turns",
    "threat": "end on a looming threat that is now close",
    "emotion": "end on a quiet emotional shift, no cliffhanger (vary the rhythm)",
}
REVISE_MODES = {
    "tension": "Raise the tension: tighter beats, a clearer obstacle, something at risk in every paragraph. Keep the events.",
    "emotion": "Deepen the emotion through action, body and concrete detail instead of naming the feeling. Keep the events.",
    "dialogue": "Make the dialogue less generic: each speaker has their own vocabulary, rhythm and aim; cut small talk and explaining.",
    "motivation": "Clarify the motivation: make clear what each character wants right now and why they act this way.",
    "pace": "Tighten the pacing: cut repetition and filler, keep the best lines, move faster to the turning point.",
    "senses": "Add concrete sensory detail (sound, smell, texture, light) in a few well-chosen places. Do not pile up adjectives.",
    "hook": "Strengthen the ending so the reader must continue, using the planned hook type. Change only the last paragraph or two.",
    "shorten": "Shorten by about 25% and preserve the voice. Cut, do not summarise.",
    "cliches": "Replace stock phrases and cliches with specific images. Keep the meaning and the voice.",
}
STEER_LANG = {"vi": "Vietnamese", "en": "English"}


# ------------------------------------------------------------------ files
def _lang(p: Dict) -> str:
    return STEER_LANG.get(p.get("lang", "vi"), "Vietnamese")


def _write(path: str, data: Dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def new_project(title: str = "", idea: str = "", genre: str = "fantasy", tone: str = "dramatic", lang: str = "vi", chapters: int = 12,
                words: int = 700, root: str = PROJECTS_DIR) -> Dict:
    pid = f"{novel.slug(title or idea[:30] or 'novel')}-{int(time.time()) % 100000}"
    p = {"id": pid, "title": title.strip() or "Untitled novel", "idea": idea.strip(), "genre": genre, "tone": tone, "lang": lang,
         "target_chapters": max(3, int(chapters)), "target_words": max(200, int(words)),
         "style": {"pov": "third person limited", "tense": "past", "density": "balanced", "notes": "", "sample": "", "profile": ""},
         "controls": {"twists": True, "romance": 1, "violence": 1, "forbidden": ""},
         "premises": [], "premise": "", "bible": {"world": "", "rules": "", "ending": "", "theme": ""}, "characters": [],
         "outline": [], "threads": [], "chapters": [], "memory": {"facts": [], "knowledge": [], "changes": []},
         "goal_words": 500, "log": {}, "reader_id": "", "created": int(time.time()), "updated": int(time.time())}
    save(p, root)
    return p


def save(p: Dict, root: str = PROJECTS_DIR) -> None:
    p["updated"] = int(time.time())
    _write(os.path.join(root, p["id"] + ".json"), p)


def load(pid: str, root: str = PROJECTS_DIR) -> Optional[Dict]:
    if not pid or "/" in pid or os.sep in pid or ".." in pid:
        return None
    try:
        with open(os.path.join(root, pid + ".json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def list_projects(root: str = PROJECTS_DIR) -> List[Dict]:
    out = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return out
    for n in names:
        if n.endswith(".json"):
            p = load(n[:-5], root)
            if p:
                out.append(p)
    return sorted(out, key=lambda x: -x.get("updated", 0))


def delete_project(pid: str, root: str = PROJECTS_DIR) -> None:
    try:
        os.remove(os.path.join(root, pid + ".json"))
    except OSError:
        pass


# ------------------------------------------------------------------ small parsing helpers
def _lines(text: str) -> List[str]:
    return [re.sub(r"^[\s*#>\-•\d.)]+(?=[A-Za-zÀ-ỹ\[])", "", l).strip() for l in re.sub(r"[*_`]+", "", text or "").split("\n") if l.strip()]


def _labelled(text: str, labels: List[str]) -> Dict[str, str]:
    """{LABEL: value} from lines like 'LABEL: value' (value may continue on the next lines until the next label)."""
    out: Dict[str, str] = {}
    cur = None
    pat = re.compile(r"^\s*[*#\-•]*\s*(" + "|".join(labels) + r")\s*[:：\-]\s*(.*)$", re.I)
    for raw in re.sub(r"[*_`]+", "", text or "").split("\n"):
        m = pat.match(raw)
        if m:
            cur = m.group(1).upper()
            out[cur] = m.group(2).strip()
        elif cur and raw.strip():
            out[cur] = (out[cur] + " " + raw.strip()).strip()
    return out


def _wc(text: str) -> int:
    return len(re.findall(r"\w+", text or "", flags=re.UNICODE))


_fold = fold


# ------------------------------------------------------------------ 1. premise
def premise_prompt(p: Dict, n: int = 3) -> str:
    return (f"You are a story editor. Pitch {n} DIFFERENT premises for a {p['genre']} novel, tone {p['tone']}, in {_lang(p)}.\n"
            f"Seed idea: {p['idea'] or '(none - surprise me)'}\n"
            f"Avoid: {p['controls'].get('forbidden') or 'nothing special'}. Be specific: a named protagonist, personal stakes, a difficult choice, "
            "a contradiction in the hero, a mystery, and a twist that changes the meaning of the story.\n"
            "Format for each premise, exactly:\nPREMISE 1\nHOOK: one sentence\nPROTAGONIST: name and who they are\nGOAL: what they want\n"
            "CONFLICT: what stands in the way\nSTAKES: what is lost if they fail\nTWIST: the surprise\n")


def parse_premises(text: str) -> List[Dict[str, str]]:
    out = []
    for block in re.split(r"(?im)^\s*[*#]*\s*premise\s*\d*\s*[:.)]*\s*$", text or ""):
        f = _labelled(block, ["HOOK", "PROTAGONIST", "GOAL", "CONFLICT", "STAKES", "TWIST"])
        if f.get("HOOK") and f.get("PROTAGONIST"):
            out.append({k.lower(): v for k, v in f.items()})
    return out


def premise_text(x: Dict[str, str]) -> str:
    return "\n".join(f"{k.upper()}: {x[k]}" for k in ("hook", "protagonist", "goal", "conflict", "stakes", "twist") if x.get(k))


def make_premises(p: Dict, llm_fn: LLM, n: int = 3) -> List[Dict[str, str]]:
    p["premises"] = parse_premises(llm_fn(premise_prompt(p, n)))
    if not p["premises"]:
        raise RuntimeError("The AI did not return premises in the expected format. Try again or use a bigger model.")
    return p["premises"]


# ------------------------------------------------------------------ 2. bible
def bible_prompt(p: Dict) -> str:
    c = p["controls"]
    return (f"Build the story bible for this {p['genre']} novel ({p['tone']}), written in {_lang(p)}, {p['target_chapters']} chapters.\n"
            f"PREMISE:\n{p['premise'] or p['idea']}\n"
            f"Rules: twists {'allowed' if c.get('twists') else 'NOT allowed - keep it straightforward'}; romance level {c.get('romance')}/3; violence {c.get('violence')}/3; "
            f"avoid: {c.get('forbidden') or 'nothing special'}.\n"
            "Give 3-5 characters. Each must WANT something, FEAR something, have a FLAW and a SECRET, speak in a distinct VOICE, and have an ARC. "
            "Give two characters competing goals. Also list 4-6 THREADS: clues, promises or mysteries planted early that must pay off, "
            "with the chapter where each is planted and where it pays off.\n"
            "Format exactly (one line per item, fields separated by |):\n"
            "TITLE: ...\nTHEME: ...\nWORLD: 2-3 sentences\nRULES: limits and costs of anything unusual, separated by ;\nENDING: how it ends\n"
            "CHARACTER: name | role | goal | fear | flaw | secret | voice | arc\n"
            "THREAD: kind (clue/promise/mystery) | what it is | planted in chapter N | pays off in chapter M\n")


def parse_bible(text: str) -> Dict:
    f = _labelled(re.sub(r"(?im)^\s*(CHARACTER|THREAD)\s*:.*$", "", text or ""), ["TITLE", "THEME", "WORLD", "RULES", "ENDING"])
    chars, threads = [], []
    for line in re.sub(r"[*_`]+", "", text or "").split("\n"):
        m = re.match(r"^\s*[-•]*\s*(CHARACTER|THREAD)\s*[:：]\s*(.*)$", line, re.I)
        if not m:
            continue
        parts = [x.strip() for x in m.group(2).split("|")]
        if m.group(1).upper() == "CHARACTER" and len(parts) >= 3 and parts[0]:
            keys = ["name", "role", "goal", "fear", "flaw", "secret", "voice", "arc"]
            chars.append({k: (parts[i] if i < len(parts) else "") for i, k in enumerate(keys)})
        elif m.group(1).upper() == "THREAD" and len(parts) >= 2:
            nums = [int(x) for x in re.findall(r"\d+", " ".join(parts[2:]))]
            kind = parts[0].lower()
            kind = kind if kind in ("clue", "promise", "mystery") else "clue"
            threads.append({"kind": kind, "text": parts[1] if parts[1] else parts[0], "planted": nums[0] if nums else 0,
                            "due": nums[1] if len(nums) > 1 else 0, "paid": 0})
    return {"title": f.get("TITLE", ""), "theme": f.get("THEME", ""), "world": f.get("WORLD", ""), "rules": f.get("RULES", ""),
            "ending": f.get("ENDING", ""), "characters": chars, "threads": threads}


def make_bible(p: Dict, llm_fn: LLM) -> Dict:
    b = parse_bible(llm_fn(bible_prompt(p)))
    if not b["characters"]:
        raise RuntimeError("The AI did not return characters in the expected format. Try again or use a bigger model.")
    p["bible"].update({k: b[k] for k in ("theme", "world", "rules", "ending")})
    if b["title"] and p["title"] in ("", "Untitled novel"):
        p["title"] = b["title"]
    p["characters"] = b["characters"]
    p["threads"] = [dict(t, id=i + 1) for i, t in enumerate(b["threads"])]
    return b


def characters_text(p: Dict) -> str:
    return "\n".join(" | ".join(c.get(k, "") for k in ("name", "role", "goal", "fear", "flaw", "secret", "voice", "arc")) for c in p["characters"])


def set_characters(p: Dict, text: str) -> None:
    out = []
    for line in (text or "").split("\n"):
        parts = [x.strip() for x in line.split("|")]
        if parts and parts[0]:
            keys = ["name", "role", "goal", "fear", "flaw", "secret", "voice", "arc"]
            out.append({k: (parts[i] if i < len(parts) else "") for i, k in enumerate(keys)})
    p["characters"] = out


def threads_text(p: Dict) -> str:
    return "\n".join(f"{t['kind']} | {t['text']} | planted {t.get('planted') or '?'} | pays off {t.get('due') or '?'}" for t in p["threads"])


def set_threads(p: Dict, text: str) -> None:
    old = {t["text"]: t for t in p["threads"]}
    out = []
    for line in (text or "").split("\n"):
        parts = [x.strip() for x in line.split("|")]
        if len(parts) >= 2 and parts[1]:
            nums = [int(x) for x in re.findall(r"\d+", " ".join(parts[2:]))]
            kind = parts[0].lower() if parts[0].lower() in ("clue", "promise", "mystery") else "clue"
            keep = old.get(parts[1], {})
            out.append({"id": len(out) + 1, "kind": kind, "text": parts[1], "planted": nums[0] if nums else 0,
                        "due": nums[1] if len(nums) > 1 else 0, "paid": keep.get("paid", 0)})
    p["threads"] = out


# ------------------------------------------------------------------ 3. outline
def outline_prompt(p: Dict) -> str:
    n = p["target_chapters"]
    hooks = ", ".join(HOOK_TYPES)
    return (f"Write the chapter outline for the novel \"{p['title']}\" ({p['genre']}, {p['tone']}) in {_lang(p)}: exactly {n} chapters.\n"
            f"PREMISE:\n{p['premise'] or p['idea']}\n{canon_text(p)}\n"
            "Structure: setup, an inciting incident by chapter 2-3, rising trouble where every chapter follows the last with BUT or THEREFORE, a midpoint "
            f"reversal around chapter {max(2, n // 2)}, a dark moment, a climax, then the ending. Plant every thread before it pays off. "
            f"Vary the hook types ({hooks}) - not every chapter is a cliffhanger.\n"
            "Format, one line per chapter, fields separated by |:\nCH 1 | title | purpose: what changes | turning point | hook type | plants: thread numbers | pays: thread numbers\n")


def parse_outline(text: str, n: int) -> List[Dict]:
    rows: Dict[int, Dict] = {}
    for line in re.sub(r"[*_`]+", "", text or "").split("\n"):
        m = re.match(r"^\s*[-•#]*\s*(?:ch(?:apter|ương)?\.?\s*)?(\d{1,3})\s*[|:.)\-]\s*(.*)$", line, re.I)
        if not m or "|" not in m.group(2):
            continue
        k = int(m.group(1))
        parts = [x.strip() for x in m.group(2).split("|")]
        hook = next((h for h in HOOK_TYPES if len(parts) > 3 and h in parts[3].lower()), "question")
        nums = lambda s: [int(x) for x in re.findall(r"\d+", s)]
        plants = nums(next((x for x in parts[4:] if re.match(r"(?i)plants?", x)), ""))
        pays = nums(next((x for x in parts[4:] if re.match(r"(?i)pays?", x)), ""))
        if 1 <= k <= n and k not in rows:
            rows[k] = {"n": k, "title": parts[0], "purpose": re.sub(r"(?i)^purpose\s*:\s*", "", parts[1] if len(parts) > 1 else ""),
                       "turn": parts[2] if len(parts) > 2 else "", "hook": hook, "plants": plants, "pays": pays, "steer": ""}
    return [rows[k] for k in sorted(rows)]


def make_outline(p: Dict, llm_fn: LLM) -> List[Dict]:
    rows = parse_outline(llm_fn(outline_prompt(p)), p["target_chapters"])
    if len(rows) < max(3, p["target_chapters"] // 2):
        raise RuntimeError("The AI did not return a usable outline (chapter lines with | separators). Try again or use a bigger model.")
    p["outline"] = rows
    return rows


def outline_text(p: Dict) -> str:
    return "\n".join(f"CH {o['n']} | {o['title']} | {o['purpose']} | {o['turn']} | {o['hook']} | plants: {','.join(map(str, o['plants']))} | "
                     f"pays: {','.join(map(str, o['pays']))}" for o in p["outline"])


def set_outline(p: Dict, text: str) -> None:
    old = {o["n"]: o for o in p["outline"]}
    rows = parse_outline(text, max(p["target_chapters"], 200))
    for r in rows:
        r["steer"] = old.get(r["n"], {}).get("steer", "")
    p["outline"] = rows
    p["target_chapters"] = max(p["target_chapters"], len(rows))


# ------------------------------------------------------------------ 4. context + drafting
def canon_text(p: Dict) -> str:
    b = p["bible"]
    chars = "\n".join(f"- {c['name']} ({c['role']}): wants {c['goal']}; fears {c['fear']}; flaw {c['flaw']}" for c in p["characters"])
    th = "\n".join(f"- #{t['id']} {t['kind']}: {t['text']} (plant ch {t.get('planted') or '?'}, pay off ch {t.get('due') or '?'})" for t in p["threads"])
    return (f"WORLD: {b['world']}\nRULES: {b['rules']}\nTHEME: {b['theme']}\nENDING DIRECTION: {b['ending']}\nCHARACTERS:\n{chars}\nTHREADS:\n{th}")


def relevant_characters(p: Dict, n: int) -> List[Dict]:
    o = next((x for x in p["outline"] if x["n"] == n), {})
    text = _fold(f"{o.get('title', '')} {o.get('purpose', '')} {o.get('turn', '')} {o.get('steer', '')}")
    prev = _fold(" ".join(m["text"] for m in p["memory"]["facts"] if m["ch"] >= n - 2))
    hit = [c for c in p["characters"] if _fold(c["name"]) and (_fold(c["name"]) in text or _fold(c["name"]) in prev)]
    return hit or p["characters"][:3]


def open_threads(p: Dict, n: int) -> List[Dict]:
    return [t for t in p["threads"] if not t.get("paid") and (t.get("planted") or 0) <= n]


def style_rules(p: Dict) -> str:
    s = p["style"]
    parts = [f"Point of view: {s['pov']}; tense: {s['tense']}; prose density: {s['density']}."]
    if s.get("notes"):
        parts.append(f"Author notes: {s['notes']}")
    if s.get("profile"):
        parts.append(f"Voice of the author's own writing: {s['profile']}")
    if s.get("sample"):
        parts.append(f"Match the voice of this sample (do not copy it):\n\"\"\"{s['sample'][:700]}\"\"\"")
    return "\n".join(parts)


def chapter_context(p: Dict, n: int) -> str:
    """The compact context for chapter n: only what that chapter needs."""
    o = next((x for x in p["outline"] if x["n"] == n), {"title": f"Chapter {n}", "purpose": "", "turn": "", "hook": "question", "plants": [], "pays": []})
    nxt = next((x for x in p["outline"] if x["n"] == n + 1), None)
    chars = "\n".join(f"- {c['name']} ({c['role']}): wants {c['goal']}; fears {c['fear']}; flaw {c['flaw']}; voice: {c['voice']}; arc: {c['arc']}"
                      for c in relevant_characters(p, n))
    facts = "\n".join(f"- (ch {m['ch']}) {m['text']}" for m in p["memory"]["facts"][-14:])
    know = "\n".join(f"- {m['who']} knows: {m['text']}" for m in p["memory"]["knowledge"][-10:])
    chg = "\n".join(f"- {m['text']}" for m in p["memory"]["changes"][-8:])
    th = "\n".join(f"- #{t['id']} {t['text']}" for t in open_threads(p, n))
    plants = ", ".join(f"#{i}" for i in o.get("plants", [])) or "none"
    pays = ", ".join(f"#{i}" for i in o.get("pays", [])) or "none"
    prev = next((c for c in p["chapters"] if c["n"] == n - 1), None)
    tail = (prev["text"][-700:] if prev and prev.get("text") else "")
    return (f"NOVEL: {p['title']} ({p['genre']}, {p['tone']}). Language: {_lang(p)}.\nPREMISE: {p['premise'] or p['idea']}\n"
            f"WORLD: {p['bible']['world']}\nRULES (never break): {p['bible']['rules']}\nENDING DIRECTION: {p['bible']['ending']}\n"
            f"\nTHIS CHAPTER (chapter {n} of {p['target_chapters']}): {o['title']}\nPurpose: {o['purpose']}\nTurning point: {o['turn']}\n"
            f"Plant these threads: {plants}. Pay off these threads: {pays}.\n"
            f"{('Reader steering - the author chose: ' + o['steer']) if o.get('steer') else ''}\n"
            f"\nCHARACTERS IN PLAY:\n{chars}\n\nWHAT HAS HAPPENED (memory):\n{facts or '(this is the first chapter)'}\n"
            f"WHO KNOWS WHAT:\n{know or '(nothing special)'}\nCHANGES TO KEEP TRUE:\n{chg or '(none)'}\nOPEN THREADS:\n{th or '(none)'}\n"
            f"{('LAST LINES OF THE PREVIOUS CHAPTER (continue from here):' + chr(10) + tail) if tail else ''}\n\nSTYLE:\n{style_rules(p)}")


def draft_prompt(p: Dict, n: int, words: int = 0, extra: str = "") -> str:
    o = next((x for x in p["outline"] if x["n"] == n), {"hook": "question", "title": f"Chapter {n}"})
    words = words or p["target_words"]
    c = p["controls"]
    return (chapter_context(p, n) + "\n\n"
            f"TASK: write chapter {n} \"{o['title']}\" in {_lang(p)}, about {words} words, as finished prose (no outline, no notes, no headings). "
            "Make it 2-4 scenes; each scene has a viewpoint character, an immediate goal, an obstacle and a change at the end. "
            "Show, do not tell; one concrete sensory detail per scene; dialogue that sounds different for each speaker and reveals motive. "
            "Characters may only act on what they know (see WHO KNOWS WHAT). Obey the RULES. "
            f"Hook: {HOOK_TYPES.get(o.get('hook', 'question'), HOOK_TYPES['question'])}. Do not resolve the open threads early. "
            f"Content limits: romance {c.get('romance')}/3, violence {c.get('violence')}/3; avoid {c.get('forbidden') or 'nothing special'}. "
            f"Only original characters and events.{(' ' + extra) if extra else ''}\nOutput only the chapter text.")


def clean_chapter(text: str, title: str = "") -> str:
    t = re.sub(r"[*#]+", "", text or "").strip()
    t = re.sub(r"(?is)^\s*(ch(?:apter|ương)\s*\d+[^\n]*\n+)", "", t)
    t = re.sub(r"(?im)^\s*(note|ghi chú|word count)\s*[:(].*$", "", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def get_chapter(p: Dict, n: int) -> Optional[Dict]:
    return next((c for c in p["chapters"] if c["n"] == n), None)


def set_chapter_text(p: Dict, n: int, text: str, label: str = "edit") -> Dict:
    """Store `text` as chapter n; the previous text becomes a version. Locked (approved) chapters cannot be overwritten except by restore."""
    ch = get_chapter(p, n)
    o = next((x for x in p["outline"] if x["n"] == n), {})
    if ch is None:
        ch = {"n": n, "title": o.get("title", f"Chapter {n}"), "text": "", "status": "draft", "versions": [], "summary": ""}
        p["chapters"].append(ch)
        p["chapters"].sort(key=lambda c: c["n"])
    if ch["status"] == "approved":
        raise RuntimeError("This chapter is approved (locked). Unlock it first.")
    if ch["text"] and ch["text"] != text:
        ch["versions"].append({"text": ch["text"], "label": label, "t": int(time.time())})
        ch["versions"] = ch["versions"][-30:]
    added = max(0, _wc(text) - _wc(ch["text"]))
    ch["text"] = text
    if added:
        d = time.strftime("%Y-%m-%d")
        p["log"][d] = p["log"].get(d, 0) + added
    return ch


def draft_chapter(p: Dict, n: int, llm_fn: LLM, words: int = 0, extract: bool = True) -> Dict:
    """Draft chapter n from its compact context, then update the memory. Returns {chapter, report}."""
    if get_chapter(p, n) and get_chapter(p, n)["status"] == "approved":
        raise RuntimeError("This chapter is approved (locked). Unlock it first.")
    text = clean_chapter(llm_fn(draft_prompt(p, n, words)))
    target = words or p["target_words"]
    if _wc(text) < target * 0.5:      # a small model stopped early: ask once for the rest
        more = clean_chapter(llm_fn(draft_prompt(p, n, words, "Continue the chapter from where this text stops, do not repeat it, and finish it with the planned hook.\n"
                                                 "TEXT SO FAR:\n" + text[-1500:])))
        text = (text + "\n\n" + more).strip()
    if not text:
        raise RuntimeError("The AI answered with nothing. Try again or pick another model.")
    ch = set_chapter_text(p, n, text, "draft")
    if extract:
        remember(p, n, llm_fn)
    return {"chapter": ch, "report": chapter_report(p, n)}


# ------------------------------------------------------------------ 5. narrative memory
def memory_prompt(p: Dict, n: int) -> str:
    ch = get_chapter(p, n)
    th = "\n".join(f"#{t['id']} {t['text']}" for t in p["threads"] if not t.get("paid"))
    return (f"Extract the durable story facts from chapter {n} of \"{p['title']}\" in {_lang(p)}. Only what the text says.\n"
            "Format, one item per line:\nSUMMARY: 2-3 sentences\nFACT: an event or fact that must stay true\n"
            "KNOWS: character | what they learned or were told\nCHANGE: injury, object gained or lost, promise, relationship change, location\n"
            f"NEWTHREAD: kind (clue/promise/mystery) | a new unresolved question or clue\nPAID: number of an open thread that was resolved here\n"
            f"Open threads:\n{th or '(none)'}\n\nCHAPTER TEXT:\n{ch['text'][:9000]}")


def parse_memory(text: str) -> Dict:
    out = {"summary": "", "facts": [], "knows": [], "changes": [], "newthreads": [], "paid": []}
    for raw in re.sub(r"[*_`]+", "", text or "").split("\n"):
        m = re.match(r"^\s*[-•]*\s*(SUMMARY|FACT|KNOWS|CHANGE|NEWTHREAD|PAID)\s*[:：]\s*(.+)$", raw, re.I)
        if not m:
            continue
        key, val = m.group(1).upper(), m.group(2).strip()
        if key == "SUMMARY":
            out["summary"] = val
        elif key == "FACT":
            out["facts"].append(val)
        elif key == "KNOWS" and "|" in val:
            who, what = [x.strip() for x in val.split("|", 1)]
            out["knows"].append({"who": who, "text": what})
        elif key == "CHANGE":
            out["changes"].append(val)
        elif key == "NEWTHREAD":
            kind, _, what = val.partition("|")
            what = what.strip() or kind.strip()
            kind = kind.strip().lower() if what != kind.strip() and kind.strip().lower() in ("clue", "promise", "mystery") else "clue"
            out["newthreads"].append({"kind": kind, "text": what})
        elif key == "PAID":
            out["paid"] += [int(x) for x in re.findall(r"\d+", val)]
    return out


def remember(p: Dict, n: int, llm_fn: LLM) -> Dict:
    """Update the canon ledger from chapter n (replaces what chapter n added before, so redrafting never duplicates facts)."""
    ch = get_chapter(p, n)
    m = parse_memory(llm_fn(memory_prompt(p, n)))
    mem = p["memory"]
    mem["facts"] = [f for f in mem["facts"] if f["ch"] != n]
    mem["knowledge"] = [f for f in mem["knowledge"] if f["ch"] != n]
    mem["changes"] = [f for f in mem["changes"] if f["ch"] != n]
    for t in p["threads"]:
        if t.get("paid") == n:
            t["paid"] = 0
    p["threads"] = [t for t in p["threads"] if t.get("added") != n]
    mem["facts"] += [{"ch": n, "text": t} for t in m["facts"]]
    mem["knowledge"] += [{"ch": n, "who": k["who"], "text": k["text"]} for k in m["knows"]]
    mem["changes"] += [{"ch": n, "text": t} for t in m["changes"]]
    for nt in m["newthreads"]:
        if not any(_fold(nt["text"]) == _fold(t["text"]) for t in p["threads"]):
            p["threads"].append({"id": max([t["id"] for t in p["threads"]] + [0]) + 1, "kind": nt["kind"], "text": nt["text"], "planted": n,
                                 "due": 0, "paid": 0, "added": n})
    for i in m["paid"]:
        for t in p["threads"]:
            if t["id"] == i and not t.get("paid"):
                t["paid"] = n
    ch["summary"] = m["summary"] or ch.get("summary", "")
    return m


# ------------------------------------------------------------------ 6. checks
CLICHE_EXTRA = {"vi": ["trong khoảnh khắc", "một cách kỳ lạ", "không thể tin được"], "en": ["in that moment", "she let out a breath she didn't know", "a mix of"]}


def chapter_report(p: Dict, n: int) -> Dict:
    """Local checks, no AI: {issues: [{severity, kind, text}], stats}. Severity: high / medium / low."""
    ch = get_chapter(p, n)
    text = ch["text"] if ch else ""
    issues: List[Dict] = []

    def add(sev, kind, msg):
        issues.append({"severity": sev, "kind": kind, "text": msg})
    words = _wc(text)
    target = p["target_words"]
    if words < target * 0.6:
        add("high", "length", f"Only {words} words (target about {target}).")
    elif words > target * 1.8:
        add("low", "length", f"{words} words, much longer than the target {target}: consider tightening.")
    paras = [x.strip() for x in re.split(r"\n+", text) if x.strip()]
    sents = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    openers = [" ".join(s.lower().split()[:2]) for s in sents if len(s.split()) >= 3]
    for op in set(openers):
        if openers.count(op) >= 4:
            add("medium", "repetition", f"{openers.count(op)} sentences start with \"{op}\": vary the openings.")
    low = text.lower()
    lang = p.get("lang", "vi")
    hits = [c for c in story_writer.CLICHES.get(lang, []) + CLICHE_EXTRA.get(lang, []) if c in low]
    if hits:
        add("medium", "cliche", "Stock phrases: " + ", ".join(f"\"{h}\"" for h in hits[:4]) + ".")
    quoted = sum(len(m) for m in re.findall(r"[“\"«]([^”\"»]+)[”\"»]", text))
    dialogue = quoted / max(1, len(text))
    if words > 150 and dialogue < 0.05:
        add("low", "pacing", "Almost no dialogue: a long stretch of narration. Add a scene with people talking.")
    if words > 150 and dialogue > 0.65:
        add("low", "pacing", "Almost all dialogue: add action, setting or thought between the lines.")
    if paras and max(_wc(x) for x in paras) > 260:
        add("low", "pacing", "One paragraph is very long: break it up or cut it.")
    o = next((x for x in p["outline"] if x["n"] == n), None)
    if o and words > 80:
        last = " ".join(sents[-2:]).lower()
        weak = not re.search(r"[?]|\b(but|until|then|suddenly|nobody|never|still|không ai|nhưng|cho đến|vẫn|chưa)\b", last)
        if o.get("hook") != "emotion" and weak:
            add("low", "hook", f"The ending may not land the planned hook ({o['hook']}): check the last paragraph.")
    known = {_fold(c["name"]) for c in p["characters"]}
    known |= {tok for k in list(known) for tok in k.split()}
    for nm in novel.detect_characters(text, top=10):
        if _fold(nm) not in known:
            add("medium", "new-name", f"\"{nm}\" speaks but is not in the character list: add them to the bible or rename.")
    for t in p["threads"]:
        if t.get("due") and t["due"] < n and not t.get("paid"):
            add("medium", "overdue-thread", f"Thread #{t['id']} \"{t['text']}\" was due in chapter {t['due']} and is still open.")
    if o:
        for i in o.get("pays", []):
            t = next((x for x in p["threads"] if x["id"] == i), None)
            if t and t.get("planted") and t["planted"] > n:
                add("high", "unprepared-reveal", f"Chapter {n} pays off thread #{i} but it is only planted in chapter {t['planted']}.")
    return {"issues": issues, "stats": {"words": words, "paragraphs": len(paras), "dialogue_pct": round(dialogue * 100)}}


def thread_health(p: Dict, upto: int = 0) -> Dict:
    """Foreshadowing tracker: {open, paid, overdue, never_planted, unplanned_pay} (thread dicts)."""
    upto = upto or max([c["n"] for c in p["chapters"]] + [0])
    th = p["threads"]
    return {"open": [t for t in th if not t.get("paid") and (t.get("planted") or 0) <= upto],
            "paid": [t for t in th if t.get("paid")],
            "overdue": [t for t in th if t.get("due") and t["due"] <= upto and not t.get("paid")],
            "waiting": [t for t in th if not t.get("paid") and (t.get("planted") or 0) > upto]}


def audit_prompt(p: Dict, n: int) -> str:
    ch = get_chapter(p, n)
    facts = "\n".join(f"(ch {m['ch']}) {m['text']}" for m in p["memory"]["facts"] if m["ch"] < n)
    know = "\n".join(f"{m['who']} knows: {m['text']}" for m in p["memory"]["knowledge"] if m["ch"] < n)
    chg = "\n".join(m["text"] for m in p["memory"]["changes"] if m["ch"] < n)
    return (f"You are a continuity editor. Check chapter {n} of \"{p['title']}\" against the canon. Report only real problems with evidence: "
            "contradicted facts, timeline errors, a character knowing something they could not know yet, an injury or object that vanished, "
            "broken world rules, actions without a plausible cause. If there are none, answer exactly NONE.\n"
            f"Format, one per line: ISSUE: \"quote from the chapter\" | what it contradicts | suggested fix\n\n"
            f"WORLD RULES: {p['bible']['rules']}\nPAST FACTS:\n{facts or '(none)'}\nWHO KNOWS WHAT:\n{know or '(none)'}\nCHANGES:\n{chg or '(none)'}\n\n"
            f"CHAPTER {n}:\n{ch['text'][:9000]}")


def parse_audit(text: str) -> List[Dict[str, str]]:
    out = []
    for raw in re.sub(r"[*_`]+", "", text or "").split("\n"):
        m = re.match(r"^\s*[-•]*\s*ISSUE\s*[:：]\s*(.+)$", raw, re.I)
        if m:
            parts = [x.strip() for x in m.group(1).split("|")]
            out.append({"quote": parts[0].strip('"“”'), "problem": parts[1] if len(parts) > 1 else "", "fix": parts[2] if len(parts) > 2 else ""})
    return out


def audit_chapter(p: Dict, n: int, llm_fn: LLM) -> List[Dict[str, str]]:
    if not get_chapter(p, n):
        return []
    return parse_audit(llm_fn(audit_prompt(p, n)))


# ------------------------------------------------------------------ 7. revision with diff
def revise_prompt(p: Dict, n: int, passage: str, mode: str, whole: bool = False) -> str:
    instruction = REVISE_MODES.get(mode, mode)
    o = next((x for x in p["outline"] if x["n"] == n), {})
    return (f"You are a line editor for the novel \"{p['title']}\" ({p['genre']}, {p['tone']}), written in {_lang(p)}.\n"
            f"EDIT TASK: {instruction}\nKeep the same events, names, facts and the author's voice. Do not add new plot. "
            f"Planned hook for this chapter: {o.get('hook', 'question')}.\nSTYLE:\n{style_rules(p)}\n\n"
            f"{'CHAPTER' if whole else 'PASSAGE'} TO EDIT:\n{passage}\n\nOutput only the edited {'chapter' if whole else 'passage'}, nothing else.")


def revise(p: Dict, n: int, mode: str, llm_fn: LLM, paragraph: Optional[int] = None) -> Dict:
    """Propose an edit. Nothing is saved: returns {old, new, ops} for the diff; call accept_revision() to keep it."""
    ch = get_chapter(p, n)
    if not ch:
        raise RuntimeError("Write the chapter first.")
    paras = ch["text"].split("\n\n")
    whole = paragraph is None
    old = ch["text"] if whole else paras[paragraph]
    new = clean_chapter(llm_fn(revise_prompt(p, n, old, mode, whole)))
    if not new:
        raise RuntimeError("The AI answered with nothing. Try again.")
    return {"mode": mode, "paragraph": paragraph, "old": old, "new": new, "ops": diff_ops(old, new)}


def diff_ops(old: str, new: str) -> List[Tuple[str, str]]:
    """Sentence-level diff: [('same'|'del'|'add', text)]."""
    split = lambda t: [s for s in re.split(r"(?<=[.!?…])\s+|\n+", t) if s.strip()]
    a, b = split(old), split(new)
    out: List[Tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append(("same", " ".join(a[i1:i2])))
        else:
            if i2 > i1:
                out.append(("del", " ".join(a[i1:i2])))
            if j2 > j1:
                out.append(("add", " ".join(b[j1:j2])))
    return out


def accept_revision(p: Dict, n: int, rev: Dict) -> Dict:
    ch = get_chapter(p, n)
    if rev.get("paragraph") is None:
        text = rev["new"]
    else:
        paras = ch["text"].split("\n\n")
        paras[rev["paragraph"]] = rev["new"]
        text = "\n\n".join(paras)
    return set_chapter_text(p, n, text, f"revise: {rev['mode']}")


def restore_version(p: Dict, n: int, index: int) -> Dict:
    ch = get_chapter(p, n)
    v = ch["versions"][index]
    ch["status"] = "draft"
    return set_chapter_text(p, n, v["text"], "restore")


def approve(p: Dict, n: int, on: bool = True) -> None:
    ch = get_chapter(p, n)
    if ch:
        ch["status"] = "approved" if on else "draft"


# ------------------------------------------------------------------ 8. steering and review
def choices_prompt(p: Dict, n: int) -> str:
    ch = get_chapter(p, n)
    return (f"Chapter {n} of \"{p['title']}\" just ended. Offer 3 consequential directions for chapter {n + 1} in {_lang(p)}: each changes later events, "
            "not just the next paragraph (for example trust or betray, reveal or conceal, escape or confront). Respect the ending direction: "
            f"{p['bible']['ending']}.\nFormat, one per line: A | short label | what happens next | the price or consequence\n\nCHAPTER SUMMARY: "
            f"{ch.get('summary') or ch['text'][-800:]}")


def parse_choices(text: str) -> List[Dict[str, str]]:
    out = []
    for raw in re.sub(r"[*_`]+", "", text or "").split("\n"):
        m = re.match(r"^\s*[-•(]*\s*([A-Da-d1-4])[).:\]]*\s*\|\s*(.+)$", raw)
        if m:
            parts = [x.strip() for x in m.group(2).split("|")]
            out.append({"key": m.group(1).upper(), "label": parts[0], "what": parts[1] if len(parts) > 1 else "", "price": parts[2] if len(parts) > 2 else ""})
    return out


def make_choices(p: Dict, n: int, llm_fn: LLM) -> List[Dict[str, str]]:
    return parse_choices(llm_fn(choices_prompt(p, n)))


def steer(p: Dict, n: int, text: str) -> None:
    """The author's choice for chapter n (free text or a choice) - the next draft of that chapter must follow it."""
    o = next((x for x in p["outline"] if x["n"] == n), None)
    if o is None:
        o = {"n": n, "title": f"Chapter {n}", "purpose": "", "turn": "", "hook": "question", "plants": [], "pays": [], "steer": ""}
        p["outline"].append(o)
        p["outline"].sort(key=lambda x: x["n"])
    o["steer"] = (text or "").strip()


def review_prompt(p: Dict, n: int) -> str:
    ch = get_chapter(p, n)
    return (f"You are a first reader giving an editorial reader-engagement review of chapter {n} of \"{p['title']}\". Diagnose only; do NOT suggest rewrites. "
            "Be honest and specific, quote short phrases. Answer in " + _lang(p) + ".\nFormat, one per line:\n"
            "CURIOUS: what makes the reader want to continue\nDROP: where attention may fall and why\nUNCLEAR: stakes or facts that are unclear\n"
            "PREDICTABLE: what feels predictable\nUNEARNED: a character choice or event that feels unearned\nSCORE: curiosity 1-10 and one reason\n\n"
            f"CHAPTER:\n{ch['text'][:9000]}")


def parse_review(text: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {k: [] for k in ("curious", "drop", "unclear", "predictable", "unearned", "score")}
    for raw in re.sub(r"[*_`]+", "", text or "").split("\n"):
        m = re.match(r"^\s*[-•]*\s*(CURIOUS|DROP|UNCLEAR|PREDICTABLE|UNEARNED|SCORE)\s*[:：]\s*(.+)$", raw, re.I)
        if m:
            out[m.group(1).lower()].append(m.group(2).strip())
    return out


# ------------------------------------------------------------------ 9. style
def style_profile(sample: str) -> str:
    """A short, local description of the author's own writing (sentence length, dialogue, paragraph size)."""
    sents = [s for s in re.split(r"(?<=[.!?…])\s+", sample or "") if len(s.split()) >= 2]
    if not sents:
        return ""
    avg = sum(len(s.split()) for s in sents) / len(sents)
    quoted = sum(len(m) for m in re.findall(r"[“\"«]([^”\"»]+)[”\"»]", sample)) / max(1, len(sample))
    paras = [x for x in re.split(r"\n+", sample) if x.strip()]
    first = sum(1 for w in re.findall(r"\w+", sample.lower()) if w in ("i", "me", "my", "tôi", "mình", "em")) / max(1, _wc(sample))
    return (f"sentences average {avg:.0f} words ({'short and punchy' if avg < 11 else 'long and flowing' if avg > 20 else 'medium'}); "
            f"{'dialogue-heavy' if quoted > 0.3 else 'mostly narration' if quoted < 0.1 else 'balanced dialogue and narration'}; "
            f"paragraphs of about {_wc(sample) // max(1, len(paras))} words; {'first-person feel' if first > 0.02 else 'third-person feel'}")


def set_style_sample(p: Dict, sample: str) -> None:
    p["style"]["sample"] = (sample or "").strip()[:1200]
    p["style"]["profile"] = style_profile(sample)


# ------------------------------------------------------------------ 10. resume card, goals, export
def words_today(p: Dict) -> int:
    return int(p["log"].get(time.strftime("%Y-%m-%d"), 0))


def resume_card(p: Dict) -> Dict:
    """What a returning writer sees first: where they left off, a recap, and 2-4 next actions."""
    chs = p["chapters"]
    done = [c for c in chs if c["status"] == "approved"]
    last = chs[-1] if chs else None
    nxt = (last["n"] + 1) if last else 1
    actions = []
    if not p["premise"]:
        actions.append("Pick a premise")
    elif not p["characters"]:
        actions.append("Build the story bible")
    elif not p["outline"]:
        actions.append("Write the outline")
    else:
        if last and last["status"] != "approved":
            actions += [f"Review and approve chapter {last['n']}", f"Revise chapter {last['n']}"]
        if nxt <= max(p["target_chapters"], len(p["outline"])):
            actions.append(f"Write chapter {nxt}")
        h = thread_health(p)
        if h["overdue"]:
            actions.append(f"Resolve {len(h['overdue'])} overdue thread(s)")
    return {"title": p["title"], "last": last["n"] if last else 0, "next": nxt, "chapters": len(chs), "approved": len(done),
            "total": max(p["target_chapters"], len(p["outline"])), "recap": (last.get("summary") if last else "") or "",
            "words": sum(_wc(c["text"]) for c in chs), "today": words_today(p), "goal": p.get("goal_words", 0), "actions": actions[:4]}


def chapter_heading(p: Dict, n: int, title: str) -> str:
    return f"{'Chương' if p.get('lang') == 'vi' else 'Chapter'} {n}: {title}"


def to_markdown(p: Dict, bible: bool = False) -> str:
    out = [f"# {p['title']}", ""]
    if p.get("premise"):
        out += [f"_{p['premise'].splitlines()[0]}_", ""]
    for c in p["chapters"]:
        out += [f"## {chapter_heading(p, c['n'], c['title'])}", "", c["text"], ""]
    if bible:
        out += ["---", "# Story bible", "", f"World: {p['bible']['world']}", "", f"Rules: {p['bible']['rules']}", "", f"Ending: {p['bible']['ending']}", "",
                "## Characters", ""] + [f"- **{c['name']}** ({c['role']}): wants {c['goal']}; fears {c['fear']}; flaw {c['flaw']}; secret {c['secret']}" for c in p["characters"]]
        out += ["", "## Threads", ""] + [f"- #{t['id']} {t['kind']}: {t['text']} - {'paid in ch ' + str(t['paid']) if t.get('paid') else 'open'}" for t in p["threads"]]
    return "\n".join(out).strip() + "\n"


def publish_to_reader(p: Dict, only_approved: bool = False, root: str = novel.NOVELS_DIR, author: str = "") -> Dict:
    """Put the written chapters into the Novel reader library (licence: your own work) so the AI host can read them on the live."""
    chs = [c for c in p["chapters"] if c["text"].strip() and (c["status"] == "approved" or not only_approved)]
    if not chs:
        raise RuntimeError("No chapters to publish yet.")
    text = "\n\n".join(f"{chapter_heading(p, c['n'], c['title'])}\n\n{c['text']}" for c in chs)
    if p.get("reader_id"):
        try:
            novel.delete_book(p["reader_id"], root)
        except Exception:
            pass
    meta = novel.add_book(p["title"], author or "me", "own", "written with the Novel writer", text, root)
    p["reader_id"] = meta["id"]
    return meta
