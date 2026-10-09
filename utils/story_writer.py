"""Write a whole picture story with an AI - the way a writers' room does it, not one big prompt.

  0. PITCH   three different concepts, an "editorial director" call picks the freshest one
  1. BIBLE   title, logline, hero (wants / flaw / look), rival, world, STAKES, SECRET twist, three planted CLUES, a recurring MOTIF, VOICE
  2. OUTLINE hook -> setup -> inciting incident -> rising -> reversal -> dark moment -> twist -> cliffhanger; every beat follows the
             last with BUT / THEREFORE, clues planted before the twist; a continuity editor checks it for plot holes and it is fixed once
  3. WRITE   beat by beat, each batch sees the bible, the beat and the narration so far (same names, same voice, continues the last panel)
  4. POLISH  a craft pass: concrete detail, spoken rhythm, no cliches
  5. CHECK   local checks (repeated openers / phrases, cliches, missing hero name, too short / long) + a continuity audit by the AI;
             every flagged panel is rewritten once with the reason
  6. HOOKS   five alternative first lines, and a pitch for part 2

Small local models cannot hold 15 panels in one go; this keeps every call small and gives each one the context it needs.
`llm_fn(prompt) -> str` is injected, so everything is unit tested offline. Output feeds the existing panels / pictures list.
"""
import re
from typing import Callable, Dict, List, Optional, Tuple

from . import story, story_tools

# beat name -> share of the panels (sums to 1.0); the first and last panel are always the hook and the cliffhanger
BEATS = [
    ("HOOK", "the most gripping moment, shown first: a shocking image or line that makes people stay", 0.07),
    ("SETUP", "the hero in their normal world: what they want, what is missing, one telling detail", 0.18),
    ("INCITING INCIDENT", "something happens that cannot be ignored and starts the real story", 0.12),
    ("RISING", "the hero tries, fails, pays a price; each step raises the stakes", 0.24),
    ("REVERSAL", "something they believed turns out false; the plan breaks", 0.14),
    ("DARK MOMENT", "the lowest point: they lose something that matters; a hard choice appears", 0.12),
    ("TWIST + CLIFFHANGER", "the secret is revealed or the choice is made; end on a question that makes people follow for part 2", 0.13),
]

CRAFT = {
    "vi": ("Viết tiếng Việt nói tự nhiên như kể cho bạn nghe, không văn dịch, không sáo rỗng (tránh 'bỗng nhiên', 'định mệnh', 'không ngờ rằng' "
           "lặp đi lặp lại). Giữ cách xưng hô nhất quán (ví dụ cô / anh / hắn). Lời thoại ngắn, đặt trong dấu ngoặc kép."),
    "en": "Write natural spoken English, like telling a friend. Avoid cliches. Keep the same pronouns and names. Short quoted dialogue.",
}

RULES = (
    "Craft rules: show, do not tell - give an action, an image or a line of dialogue instead of naming a feeling. "
    "One concrete detail per panel (a sound, a smell, an object). Vary sentence length. The hero WANTS something and something "
    "stands in the way. Every panel moves the story forward and ends on a small question or tension. Never repeat a sentence opening "
    "in two panels in a row. 2-3 sentences, 25-45 words per panel (it is read aloud). Only original characters and events.")


def allocate(panels: int) -> List[Tuple[str, str, int]]:
    """[(beat, description, panel_count)] - every beat gets at least 1 panel, the total is exactly `panels`."""
    panels = max(len(BEATS), int(panels))
    counts = [max(1, round(panels * b[2])) for b in BEATS]
    i = 0
    while sum(counts) != panels:           # fix rounding on the biggest beats first
        j = [3, 1, 4, 5, 2, 6, 0][i % 7]
        counts[j] += 1 if sum(counts) < panels else -1
        counts[j] = max(1, counts[j])
        i += 1
        if i > 200:
            break
    counts[0] = max(1, counts[0])
    return [(b[0], b[1], c) for b, c in zip(BEATS, counts)]


# ------------------------------------------------------------------ prompts
STAGE_TEMP = {"concepts": 1.0, "pick": 0.1, "bible": 0.9, "outline": 0.7, "write": 0.85, "polish": 0.4, "audit": 0.2, "repair": 0.6,
              "hooks": 1.0}


def concepts_prompt(idea: str, genre: str, tone: str, lang: str, n: int = 3) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    return (
        f"You are a story editor at a hit short-story channel. Pitch {n} DIFFERENT original story concepts. Genre: {genre}. Tone: {tone}. "
        f"Creator's idea: {idea.strip() or 'none - surprise me'}.\n"
        "Each concept needs a different hero, a different place and a different KIND of twist. Avoid the obvious versions: no chosen one, "
        "no amnesia, no 'it was all a dream', no secret royal blood. Prefer a specific, slightly strange situation with a human problem "
        "at its centre.\n"
        f"Write in {language}. Exactly this format, one line per concept, nothing else:\n"
        "CONCEPT 1: <who wants what, in one sentence> | TWIST: <the reveal that recolours everything>")


def parse_concepts(text: str) -> List[str]:
    out = []
    for m in re.finditer(r"(?im)^\s*[*_#\- ]*concept\s*#?\s*(\d+)\s*[*_]*\s*[:.\-)]\s*(.+)$", re.sub(r"[`]+", "", text or "")):
        c = re.sub(r"[*_]+", "", m.group(2)).strip()
        if len(c) > 15:
            out.append(c)
    return out[:5]


def pick_prompt(concepts: List[str], lang: str) -> str:
    lines = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(concepts))
    return ("You are the editorial director. Below are story pitches for a short picture story. Choose the one with the strongest hook, "
            "the freshest idea and the most surprising-but-fair twist.\nAnswer with the number only.\n\n" + lines)


def parse_pick(text: str, n: int) -> int:
    m = re.search(r"\d+", text or "")
    k = int(m.group(0)) if m else 1
    return k - 1 if 1 <= k <= n else 0


def bible_prompt(idea: str, genre: str, tone: str, lang: str) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    return (
        f"You are the head writer of a hit short-story channel. Invent an ORIGINAL story for picture panels. Genre: {genre}. Tone: {tone}. "
        f"Concept: {idea.strip() or 'surprise me with something fresh, not the usual chosen-one plot'}.\n"
        f"Write the story bible in {language}. Make the hero specific (a job, a habit, a flaw), give them a clear WANT, and plan a twist "
        "the reader will not see coming but that is fair in hindsight: that is why you also plant three small clues. "
        "Give the story one MOTIF (an object, a sound or a phrase) that shows up early and comes back changed at the end.\n"
        "Use exactly these labels, one per line, nothing else:\n"
        "TITLE: (short, intriguing)\nLOGLINE: (one sentence: who wants what, and what stands in the way)\n"
        "HERO: name | age | how they look (one sentence an illustrator can draw) | flaw | want\n"
        "OTHER: name | role | how they look | what they hide\n"
        "WORLD: (where and when, 1-2 sentences)\nSTAKES: (what is lost if the hero fails, and by when)\n"
        "SECRET: (the twist)\nCLUES: (three small things planted early that make the twist inevitable, separated by ;)\n"
        "MOTIF: (the recurring object / sound / phrase)\nVOICE: (who tells the story - the hero looking back, a neighbour, ... - and the voice in 5 words)\n"
        "THEME: (what the story is really about, 5-10 words)")


LABELS = ("TITLE", "LOGLINE", "HERO", "OTHER", "WORLD", "STAKES", "SECRET", "CLUES", "MOTIF", "VOICE", "THEME")


def parse_bible(text: str) -> Dict[str, str]:
    t = re.sub(r"[*_`#]+", "", (text or "").replace("\r\n", "\n"))
    out: Dict[str, str] = {}
    cur = None
    for line in t.split("\n"):
        m = re.match(r"\s*(?:[-•]\s*)?(" + "|".join(LABELS) + r")\s*[:\-–]\s*(.*)", line, re.I)
        if m:
            cur = m.group(1).upper()
            out[cur] = m.group(2).strip()
        elif cur and line.strip():
            out[cur] = (out[cur] + " " + line.strip()).strip()
    return out


def bible_text(b: Dict[str, str]) -> str:
    return "\n".join(f"{k}: {b[k]}" for k in LABELS if b.get(k))


def outline_prompt(bible: Dict[str, str], plan: List[Tuple[str, str, int]], lang: str) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    lines, a = [], 1
    for name, desc, c in plan:
        lines.append(f"BEAT {name} (panels {a}-{a + c - 1}): {desc}")
        a += c
    return (
        f"Story bible:\n{bible_text(bible)}\n\nPlan the story panel by panel in {language}. Below are the beats and how many panels each has. "
        "For every beat write what happens, in 1-3 sentences, concrete (who does what, where), using the bible's names.\n"
        "Rules: (1) every beat follows from the one before it with BUT or THEREFORE - a consequence or a complication, never just 'and then'; "
        "(2) plant the three CLUES in the beats before the twist and say which in brackets, e.g. [clue 2]; (3) show the MOTIF in SETUP and "
        "bring it back, changed, in the last beat; (4) the STAKES get worse in every beat; (5) the SECRET is revealed only in the last beat "
        "and must explain the clues; (6) the hero's choices - not luck - drive the story.\n"
        "Answer with exactly one line per beat, in this format and nothing else:\nBEAT <name>: <what happens>\n\n" + "\n".join(lines))


def parse_outline(text: str, plan: List[Tuple[str, str, int]]) -> List[str]:
    """What happens in each beat (same order as plan). Missing beats fall back to the plan's description."""
    t = re.sub(r"[*_`#]+", "", (text or "").replace("\r\n", "\n"))
    out = []
    for name, desc, _ in plan:
        m = re.search(r"(?im)^\s*(?:[-\u2022]\s*)?BEAT\s+" + re.escape(name).replace(r"\ ", r"\s+") + r"[^:\n]*:\s*(.+)", t)
        out.append(re.sub(r"\s+", " ", m.group(1)).strip() if m else desc)
    return out


def outline_check_prompt(bible: Dict[str, str], plan: List[Tuple[str, str, int]], outline: List[str]) -> str:
    beats = "\n".join(f"BEAT {p[0]}: {t}" for p, t in zip(plan, outline))
    return (f"You are a continuity editor. Read the story bible and the outline and look for PLOT HOLES: a beat that does not follow from the "
            "previous one, a character who knows something they could not know, a clue that is never planted, a twist that contradicts an "
            "earlier beat, stakes that disappear, a problem solved by luck.\nIf the outline is sound answer exactly: OK\n"
            "Otherwise list at most 4 problems, one per line, each starting with 'PROBLEM:' and naming the beat.\n\n"
            f"{bible_text(bible)}\n\n{beats}")


def parse_problems(text: str) -> List[str]:
    t = (text or "").strip()
    if re.match(r"(?i)^\W*ok\b", t) and "PROBLEM" not in t.upper():
        return []
    return [re.sub(r"(?i)^\W*problem\s*\d*\s*[:.\-]\s*", "", re.sub(r"[*_`]+", "", l)).strip()
            for l in t.split("\n") if re.match(r"\W*problem", l, re.I) and len(l) > 14][:4]


def outline_fix_prompt(bible: Dict[str, str], plan: List[Tuple[str, str, int]], outline: List[str], problems: List[str], lang: str) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    beats = "\n".join(f"BEAT {p[0]}: {t}" for p, t in zip(plan, outline))
    return (f"Story bible:\n{bible_text(bible)}\n\nThis outline has problems:\n" + "\n".join(f"- {x}" for x in problems) +
            f"\n\nRewrite the whole outline in {language} so every problem is fixed, keeping what already works. Same format, one line per beat, "
            "nothing else:\nBEAT <name>: <what happens>\n\n" + beats)


def write_prompt(bible: Dict[str, str], beat: str, beat_text: str, first: int, count: int, total: int, written: List[str], lang: str,
                 tone: str) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    ctx = "\n".join(f"Panel {first - len(written) + i}: {t}" for i, t in enumerate(written)) if written else "(this is the start)"
    extra = ""
    if first + count - 1 >= total:
        extra += ("This is the LAST part: pay off the clues, bring the MOTIF back changed, and end on a cliffhanger or a question that "
                  "makes people follow for the next part.\n")
    if beat == "HOOK":
        extra += "Panel 1 is the HOOK: open in the middle of a shocking moment, no introductions, no 'once upon a time'.\n"
    elif written:
        extra += ("The first sentence of your first panel must continue directly from the last panel above (same place and time, or say "
                  "clearly what changed). Never restart or re-introduce the characters.\n")
    voice = bible.get("VOICE", "")
    return (
        f"You are writing panels {first}-{first + count - 1} of {total} of a {tone} picture story in {language}.\n\n"
        f"STORY BIBLE:\n{bible_text(bible)}\n\nBEAT: {beat} - {beat_text}\n\nNARRATION SO FAR (do not repeat it, continue from it):\n{ctx}\n\n"
        f"{RULES}\n{CRAFT.get(lang, CRAFT['en'])}\n"
        + (f"Keep the narrator's voice the same in every panel: {voice}.\n" if voice else "")
        + extra +
        f"Write exactly {count} panels. Keep every character looking the same: when a character appears, describe them in the PICTURE "
        "with the same words as in the bible. Plant clues quietly as normal details, never point at them.\nUse this exact format for every "
        f"panel and nothing else:\nPANEL {first}\nPICTURE: one sentence to draw / generate (who, where, mood, camera)\nNARRATION: 2-3 spoken sentences\n")


def hooks_prompt(bible: Dict[str, str], first_lines: List[str], lang: str) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    return (f"Story bible:\n{bible_text(bible)}\n\nThe story now starts with: {' '.join(first_lines)[:500]}\n\n"
            f"Write 5 different opening hook lines in {language}, each under 140 characters, each a different angle (a shocking fact, a "
            "question, a confession, a countdown, a contradiction). They must be true to this story, no spoilers of the twist. "
            "One per line, numbered 1-5, nothing else.")


def parse_hooks(text: str) -> List[str]:
    out = []
    for line in (text or "").replace("\r\n", "\n").split("\n"):
        m = re.match(r"\s*\d+\s*[.):\-]\s*(.+)", line)
        if m:
            h = re.sub(r"[*_`]+", "", m.group(1)).strip().strip('"\u201c\u201d')
            if 8 <= len(h) <= 220:
                out.append(h)
    return out[:5]


def part2_prompt(bible: Dict[str, str], last_lines: List[str], lang: str) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    return (f"Story bible:\n{bible_text(bible)}\n\nThe story ends with: {' '.join(last_lines)[:500]}\n\n"
            f"Pitch part 2 in {language} in 3 sentences: what the cliffhanger really means, what the hero must do next, and a new twist. "
            "Answer with the 3 sentences only.")


# ------------------------------------------------------------------ checks that need no AI
CLICHES = {
    "vi": ["bỗng nhiên", "bất chợt", "định mệnh", "không ngờ rằng", "ai ngờ", "cuộc đời cô ấy", "cuộc đời anh ấy", "mãi mãi", "như một giấc mơ",
           "trái tim đập thình thịch", "tim đập loạn nhịp", "chuyện gì đến cũng đến"],
    "en": ["little did", "suddenly", "everything changed", "destiny", "heart pounded", "heart skipped", "forever changed", "as if on cue",
           "a shiver ran down", "time seemed to stop"],
}


def _words(t: str) -> List[str]:
    return re.findall(r"\w+", (t or "").lower(), flags=re.UNICODE)


def hero_name(bible: Dict[str, str]) -> str:
    return (bible.get("HERO", "").split("|")[0] or "").strip().strip(".")


def quality_report(plot: List[Dict], bible: Dict[str, str], lang: str = "vi") -> Dict:
    """Flag the weak panels without asking an AI: {issues: [{panel, reason}], stats: {...}}. Panel numbers are 1-based."""
    texts = [p.get("narration", "") for p in plot]
    issues: List[Dict] = []
    seen: set = set()

    def add(k: int, why: str):
        if (k, why) not in seen:
            seen.add((k, why))
            issues.append({"panel": k, "reason": why})
    prev_first = ""
    grams: Dict[str, List[int]] = {}
    for i, t in enumerate(texts, 1):
        w = _words(t)
        if not w:
            continue
        if len(w) < 10:
            add(i, f"too short ({len(w)} words): give it a concrete detail or a line of dialogue")
        elif len(w) > 70:
            add(i, f"too long ({len(w)} words): cut it to 2-3 spoken sentences")
        if w[0] == prev_first and len(w[0]) > 1:
            add(i, f"starts with the same word as the previous panel (\"{w[0]}\"): open differently")
        prev_first = w[0]
        for j in range(len(w) - 2):
            grams.setdefault(" ".join(w[j:j + 3]), []).append(i)
    for g, ks in grams.items():
        ks = sorted(set(ks))
        if len(ks) >= 3 and len(g) > 8:
            for k in ks[1:]:
                add(k, f"repeats the phrase \"{g}\" used in panel {ks[0]}")
    low = CLICHES.get(lang, CLICHES["en"])
    for i, t in enumerate(texts, 1):
        hits = [c for c in low if c in t.lower()]
        if len(hits) >= 2 or (hits and sum(1 for x in texts if hits[0] in x.lower()) >= 3):
            add(i, f"cliche wording (\"{hits[0]}\"): say it with a concrete image instead")
    name = hero_name(bible)
    if name and len(name) > 1 and len(texts) >= 6:
        mentions = [i for i, t in enumerate(texts, 1) if name.lower() in t.lower()]
        if len(mentions) < max(2, len(texts) // 5):
            add(1, f"the hero {name} is hardly named (only in {len(mentions)} panels): use the name so viewers can follow")
    words = [len(_words(t)) for t in texts if t.strip()]
    return {"issues": issues, "stats": {"panels": len(texts), "avg_words": round(sum(words) / len(words), 1) if words else 0}}


def audit_prompt(bible: Dict[str, str], texts: List[str]) -> str:
    body = "\n".join(f"Panel {i + 1}: {t}" for i, t in enumerate(texts))
    return (f"You are a continuity editor. Read the finished narration of a picture story with its bible and find real contradictions or "
            "confusions only: a name or fact that changes, a character who appears without being introduced, something that happens "
            "without cause, a clue that is never paid off, an ending that does not match the SECRET.\n"
            "If the story holds together answer exactly: OK\nOtherwise list at most 5 problems, one per line, in the form "
            "'Panel N: problem'.\n\n" + f"{bible_text(bible)}\n\n{body}")


def parse_audit(text: str, n: int) -> List[Dict]:
    t = (text or "").strip()
    if re.match(r"(?i)^\W*ok\W*$", t):
        return []
    out = []
    for m in re.finditer(r"(?im)^\W*panel\s*(\d+)\s*[:.\-]\s*(.{8,})$", re.sub(r"[*_`]+", "", t)):
        k = int(m.group(1))
        if 1 <= k <= n:
            out.append({"panel": k, "reason": m.group(2).strip()})
    return out[:5]


def repair_prompt(bible: Dict[str, str], texts: List[str], k: int, reasons: List[str], lang: str) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    prev = texts[k - 2] if k >= 2 else "(none)"
    nxt = texts[k] if k < len(texts) else "(none)"
    return (f"Rewrite ONE panel of a picture story in {language}. Problems to fix: " + "; ".join(reasons) + ".\n\n"
            f"Story bible:\n{bible_text(bible)}\n\nPrevious panel: {prev}\nPANEL {k} (rewrite this): {texts[k - 1]}\nNext panel: {nxt}\n\n"
            "Keep the same events so the story still connects with the previous and the next panel, fix the problems, 2-3 spoken sentences "
            "(25-45 words). Answer with the new narration only.")


def _clean_one(text: str, k: int) -> str:
    t = re.sub(r"[*_`]+", "", (text or "").strip())
    t = re.sub(r"(?is)^\s*(panel\s*\d+\s*[:.\-]\s*|narration\s*[:.\-]\s*)", "", t).strip().strip('"\u201c\u201d')
    return re.sub(r"\s+", " ", t)


def repair_panels(plot: List[Dict], issues: List[Dict], bible: Dict[str, str], llm_fn: Callable[[str], str], lang: str,
                  limit: int = 6) -> List[int]:
    """Rewrite each flagged panel once, with its reasons. Returns the panel numbers that were changed."""
    by: Dict[int, List[str]] = {}
    for it in issues:
        by.setdefault(it["panel"], []).append(it["reason"])
    changed = []
    for k in sorted(by)[:limit]:
        texts = [p["narration"] for p in plot]
        try:
            new = _clean_one(llm_fn(repair_prompt(bible, texts, k, by[k], lang)), k)
        except RuntimeError:
            continue
        if new and 8 <= len(_words(new)) <= 90 and new != plot[k - 1]["narration"]:
            plot[k - 1]["narration"] = new
            changed.append(k)
    return changed


# ------------------------------------------------------------------ the pipeline
def write_story(idea: str, llm_fn: Callable[[str], str], genre: str = "fantasy", tone: str = "dramatic", lang: str = "vi",
                panels: int = 12, polish: bool = True, hooks: bool = True,
                progress: Optional[Callable[[int, int, str], None]] = None, cancel: Optional[Callable[[], bool]] = None,
                llm_for: Optional[Callable[[float], Callable[[str], str]]] = None, concepts: bool = True, check: bool = True) -> Dict:
    """Returns {title, bible, outline, plot: [{picture, narration}], hooks, missing, polished, concepts, chosen, problems, fixed, part2}.
    `llm_for(temperature)` (optional) gives a model function per stage: wild for ideas, careful for editing."""
    plan = allocate(panels)
    total_panels = sum(c for _, _, c in plan)
    cache: Dict[str, Callable[[str], str]] = {}

    def L(stage: str) -> Callable[[str], str]:
        if llm_for is None:
            return llm_fn
        if stage not in cache:
            cache[stage] = llm_for(STAGE_TEMP[stage])
        return cache[stage]
    steps = 2 + len(plan) + (1 if concepts else 0) + (4 if check else 0) + (1 if polish else 0) + (2 if hooks else 0)   # upper bound
    done = 0

    def tick(msg):
        nonlocal done
        if cancel and cancel():
            raise RuntimeError("Cancelled.")
        if progress:
            progress(done, steps, msg)
        done += 1

    pitches: List[str] = []
    chosen = idea
    if concepts:
        tick("Pitching three different story ideas")
        try:
            pitches = parse_concepts(L("concepts")(concepts_prompt(idea, genre, tone, lang)))
            if len(pitches) >= 2:
                chosen = pitches[parse_pick(L("pick")(pick_prompt(pitches, lang)), len(pitches))]
            elif pitches:
                chosen = pitches[0]
        except RuntimeError:
            pitches = []
    tick("Inventing the characters, clues and twist")
    bible = parse_bible(L("bible")(bible_prompt(chosen, genre, tone, lang)))
    if not bible.get("TITLE") and not bible.get("HERO"):
        raise RuntimeError("The AI did not return a story bible. Try again, or pick a stronger model.")
    tick("Planning the beats")
    outline = parse_outline(L("outline")(outline_prompt(bible, plan, lang)), plan)
    problems: List[str] = []
    if check:
        tick("A continuity editor reads the outline")
        try:
            problems = parse_problems(L("audit")(outline_check_prompt(bible, plan, outline)))
            if problems:
                tick("Fixing the plot holes")
                outline = parse_outline(L("outline")(outline_fix_prompt(bible, plan, outline, problems, lang)), plan)
            else:
                tick("Outline is sound")
        except RuntimeError:
            tick("Outline check skipped")

    plot: List[Dict] = []
    missing: List[int] = []
    for (name, _desc, count), what in zip(plan, outline):
        tick(f"Writing: {name.title()}")
        first = len(plot) + 1
        got: List[Dict] = []
        for attempt in range(2):
            need = count - len(got)
            if need <= 0:
                break
            written = [p["narration"] for p in plot][-4:] + [p["narration"] for p in got]
            prompt = write_prompt(bible, name, what, first + len(got), need, total_panels, written, lang, tone)
            got += [p for p in story.parse_plot(L("write")(prompt)) if p["narration"]][:need]
        for k in range(count):
            if k < len(got):
                plot.append(got[k])
            else:
                plot.append({"picture": "", "narration": ""})
                missing.append(len(plot))

    polished = False
    if polish and any(p["narration"] for p in plot):
        tick("Polishing the writing")
        try:
            names = "; ".join(f"{k}: {bible[k]}" for k in ("HERO", "OTHER") if bible.get(k))
            texts, kept = story_tools.polish_narration([p["narration"] for p in plot], L("polish"), CRAFT_POLISH, lang, names)
            for p, t in zip(plot, texts):
                p["narration"] = t
            polished = len(kept) < len(plot)
        except RuntimeError:
            pass                                 # the first draft is already good enough to use
    fixed: List[int] = []
    report: Dict = {"issues": [], "stats": {}}
    if check and any(p["narration"] for p in plot):
        tick("Checking the story for repeats, cliches and contradictions")
        report = quality_report(plot, bible, lang)
        issues = list(report["issues"])
        try:
            issues += parse_audit(L("audit")(audit_prompt(bible, [p["narration"] for p in plot])), len(plot))
        except RuntimeError:
            pass
        issues = [i for i in issues if plot[i["panel"] - 1]["narration"]]
        if issues:
            tick("Rewriting the weak panels")
            fixed = repair_panels(plot, issues, bible, L("repair"), lang)
        else:
            tick("Nothing to fix")
        report["issues"] = issues
    hook_list: List[str] = []
    part2 = ""
    if hooks and plot and plot[0]["narration"]:
        tick("Thinking up hook lines")
        try:
            hook_list = parse_hooks(L("hooks")(hooks_prompt(bible, [p["narration"] for p in plot[:2]], lang)))
        except RuntimeError:
            hook_list = []
        tick("Pitching part 2")
        try:
            part2 = re.sub(r"\s+", " ", re.sub(r"[*_`]+", "", L("hooks")(part2_prompt(bible, [p["narration"] for p in plot[-2:]], lang)))).strip()
        except RuntimeError:
            part2 = ""
    if progress:
        progress(steps, steps, "Done")
    return {"title": bible.get("TITLE", ""), "bible": bible, "outline": outline, "plot": plot, "hooks": hook_list, "missing": missing,
            "polished": polished, "concepts": pitches, "chosen": chosen, "problems": problems, "fixed": fixed,
            "issues": report["issues"], "stats": report["stats"], "part2": part2}


CRAFT_POLISH = ("Edit like a sharp story editor: replace vague words with concrete ones, cut filler and cliches, make the rhythm "
                "good to hear aloud, keep every fact, name and quote. Do not add events and do not make it longer.")
