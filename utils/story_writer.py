"""Write a whole picture story with an AI - the way a writers' room does it, not one big prompt.

  1. BIBLE   title, logline, hero (wants / flaw / how they look), rival, world, secret twist, theme
  2. OUTLINE hook -> setup -> inciting incident -> rising -> reversal -> dark moment -> twist -> cliffhanger, panels per beat
  3. WRITE   beat by beat, each batch sees the bible, the beat and the narration written so far (continuity, same names)
  4. POLISH  a craft pass: concrete detail, spoken rhythm, no cliches, every panel ends on a small question
  5. HOOKS   five alternative first lines to pick from

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
def bible_prompt(idea: str, genre: str, tone: str, lang: str) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    return (
        f"You are the head writer of a hit short-story channel. Invent an ORIGINAL story for picture panels. Genre: {genre}. Tone: {tone}. "
        f"Idea from the creator: {idea.strip() or 'surprise me with something fresh, not the usual chosen-one plot'}.\n"
        f"Write the story bible in {language}. Make the hero specific (a job, a habit, a flaw), give them a clear WANT and a secret, "
        "and plan a twist the reader will not see coming but that is fair in hindsight.\n"
        "Use exactly these labels, one per line, nothing else:\n"
        "TITLE: (short, intriguing)\nLOGLINE: (one sentence: who wants what, and what stands in the way)\n"
        "HERO: name | age | how they look (one sentence an illustrator can draw) | flaw | want\n"
        "OTHER: name | role | how they look | what they hide\n"
        "WORLD: (where and when, 1-2 sentences)\nSECRET: (the twist)\nTHEME: (what the story is really about, 5-10 words)")


LABELS = ("TITLE", "LOGLINE", "HERO", "OTHER", "WORLD", "SECRET", "THEME")


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
        "For every beat write what happens, in 1-3 sentences, concrete (who does what, where), using the bible's names. "
        "The secret is only revealed in the last beat; earlier beats must plant clues. Escalate: each beat is worse or stranger than the one before.\n"
        "Answer with exactly one line per beat, in this format and nothing else:\nBEAT <name>: <what happens>\n\n" + "\n".join(lines))


def parse_outline(text: str, plan: List[Tuple[str, str, int]]) -> List[str]:
    """What happens in each beat (same order as plan). Missing beats fall back to the plan's description."""
    t = re.sub(r"[*_`#]+", "", (text or "").replace("\r\n", "\n"))
    out = []
    for name, desc, _ in plan:
        m = re.search(r"(?im)^\s*(?:[-•]\s*)?BEAT\s+" + re.escape(name).replace(r"\ ", r"\s+") + r"[^:\n]*:\s*(.+)", t)
        out.append(re.sub(r"\s+", " ", m.group(1)).strip() if m else desc)
    return out


def write_prompt(bible: Dict[str, str], beat: str, beat_text: str, first: int, count: int, total: int, written: List[str], lang: str,
                 tone: str) -> str:
    language = "Vietnamese" if lang == "vi" else "English"
    ctx = "\n".join(f"Panel {first - len(written) + i}: {t}" for i, t in enumerate(written)) if written else "(this is the start)"
    last = ("This is the LAST part: end on a cliffhanger or twist that makes people follow for the next part.\n"
            if first + count - 1 >= total else "")
    if beat == "HOOK":
        last += "Panel 1 is the HOOK: open in the middle of a shocking moment, no introductions, no 'once upon a time'.\n"
    return (
        f"You are writing panels {first}-{first + count - 1} of {total} of a {tone} picture story in {language}.\n\n"
        f"STORY BIBLE:\n{bible_text(bible)}\n\nBEAT: {beat} - {beat_text}\n\nNARRATION SO FAR (do not repeat it, continue from it):\n{ctx}\n\n"
        f"{RULES}\n{CRAFT.get(lang, CRAFT['en'])}\n{last}"
        f"Write exactly {count} panels. Keep every character looking the same: when a character appears, describe them in the PICTURE "
        "with the same words as in the bible.\nUse this exact format for every panel and nothing else:\n"
        f"PANEL {first}\nPICTURE: one sentence to draw / generate (who, where, mood, camera)\nNARRATION: 2-3 spoken sentences\n")


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
            h = re.sub(r"[*_`]+", "", m.group(1)).strip().strip('"“”')
            if 8 <= len(h) <= 220:
                out.append(h)
    return out[:5]


# ------------------------------------------------------------------ the pipeline
def write_story(idea: str, llm_fn: Callable[[str], str], genre: str = "fantasy", tone: str = "dramatic", lang: str = "vi",
                panels: int = 12, polish: bool = True, hooks: bool = True,
                progress: Optional[Callable[[int, int, str], None]] = None, cancel: Optional[Callable[[], bool]] = None) -> Dict:
    """Returns {title, bible, outline, plot: [{picture, narration}], hooks, missing: [panel numbers], polished: bool}."""
    plan = allocate(panels)
    total_panels = sum(c for _, _, c in plan)
    steps = 2 + len(plan) + (1 if polish else 0) + (1 if hooks else 0)
    done = 0

    def tick(msg):
        nonlocal done
        if cancel and cancel():
            raise RuntimeError("Cancelled.")
        if progress:
            progress(done, steps, msg)
        done += 1

    tick("Inventing the characters and the twist")
    bible = parse_bible(llm_fn(bible_prompt(idea, genre, tone, lang)))
    if not bible.get("TITLE") and not bible.get("HERO"):
        raise RuntimeError("The AI did not return a story bible. Try again, or pick a stronger model.")
    tick("Planning the beats")
    outline = parse_outline(llm_fn(outline_prompt(bible, plan, lang)), plan)

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
            got += [p for p in story.parse_plot(llm_fn(prompt)) if p["narration"]][:need]
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
            texts, kept = story_tools.polish_narration([p["narration"] for p in plot], llm_fn, CRAFT_POLISH, lang, names)
            for p, t in zip(plot, texts):
                p["narration"] = t
            polished = len(kept) < len(plot)
        except RuntimeError:
            pass                                 # the first draft is already good enough to use
    hook_list: List[str] = []
    if hooks and plot and plot[0]["narration"]:
        tick("Thinking up hook lines")
        try:
            hook_list = parse_hooks(llm_fn(hooks_prompt(bible, [p["narration"] for p in plot[:2]], lang)))
        except RuntimeError:
            hook_list = []
    if progress:
        progress(steps, steps, "Done")
    return {"title": bible.get("TITLE", ""), "bible": bible, "outline": outline, "plot": plot, "hooks": hook_list,
            "missing": missing, "polished": polished}


CRAFT_POLISH = ("Edit like a sharp story editor: replace vague words with concrete ones, cut filler and cliches, make the rhythm "
                "good to hear aloud, keep every fact, name and quote. Do not add events and do not make it longer.")
