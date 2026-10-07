"""Keep spoken pitches short, using ONLY the seller's own words.

Viewers drop off during a long spoken description. `spoken_seconds` measures the pitch the host would really say;
`shorten` proposes a tighter intro / description / highlights by picking sentences the seller already wrote (no new
claims are invented). The seller reviews and applies the proposal.
"""
import re
from typing import Dict, List

CPS = 13.0          # characters per second of Vietnamese speech (same rate the product tour assumes)
TARGET_S = 35       # a pitch above this starts to lose the room
_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")


def spoken_seconds(text: str) -> int:
    return int(round(len((text or "").strip()) / CPS))


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SPLIT.split(text or "") if s and s.strip()]


def _trim(sentence: str, limit: int) -> str:
    if len(sentence) <= limit:
        return sentence
    cut = sentence[:limit]
    for sep in (", ", "; ", " "):
        i = cut.rfind(sep)
        if i > limit * 0.5:
            return cut[:i].rstrip(",; ") + "."
    return cut.rstrip() + "."


def shorten(product: Dict, max_intro: int = 110, max_desc: int = 170, max_highlights: int = 3) -> Dict:
    """Propose {"intro", "description", "highlights"}: extractive, from the seller's own text."""
    intro_src = _sentences(product.get("intro") or "")
    desc_src = _sentences(product.get("description") or "")
    intro = _trim(intro_src[0], max_intro) if intro_src else ""
    desc, used = "", 0
    for s in desc_src:
        if desc and len(desc) + 1 + len(s) > max_desc:
            break
        desc = (desc + " " + s).strip() if desc else _trim(s, max_desc)
        used += 1
    highlights: List[str] = []
    seen = set(x.lower() for x in (product.get("highlights") or []))
    if not seen:   # never touch highlights the seller wrote; only whole short sentences (cutting mid-phrase reads badly)
        for s in (intro_src[1:] + desc_src[used:]):
            s = s.strip(" .")
            if 14 <= len(s) <= 70 and s.lower() not in desc.lower():
                highlights.append(s[0].upper() + s[1:])
            if len(highlights) >= max_highlights:
                break
    return {"intro": intro, "description": desc, "highlights": list(product.get("highlights") or []) or highlights}
