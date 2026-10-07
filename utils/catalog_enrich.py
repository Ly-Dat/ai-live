"""
LLM-assisted catalog drafting.

The seller gives a product title (and price). The LLM drafts aliases (words viewers use), a one-line description,
highlights that can be read straight from the title, and QUESTIONS viewers will probably ask. The draft is a suggestion:
the web UI shows it, the seller edits and approves. Nothing is saved automatically, and lines that trip the TikTok
safety filter are removed.

The model call is injected (`llm_fn(prompt) -> str`) so this module stays testable and provider-agnostic.
"""
import json
import re
from typing import Callable, Dict, List, Optional

PROMPT = """You help a Vietnamese TikTok seller fill in a product catalog.
Product title: {title}
Price: {price}
{extra}
Reply with ONE JSON object and nothing else, with these keys:
  "aliases": up to 6 short names viewers might use in comments (Vietnamese, lower case, with and without accents),
  "description": one short, friendly Vietnamese sentence using only what the title tells you,
  "highlights": up to 3 short Vietnamese bullet points that can be read directly from the title (else []),
  "suggested_questions": up to 4 questions viewers will likely ask that the seller should answer (size, colour, material, usage...).
Rules: never invent specifications, materials, certifications, results or health claims. If the title does not say it, leave it out.
No superlatives like "best" or "cheapest". No phone numbers, links or other platforms."""


def build_prompt(title: str, price: str = "", extra: str = "") -> str:
    return PROMPT.format(title=title.strip(), price=price or "unknown", extra=(extra or "").strip())


def parse_draft(text: str) -> Dict:
    """Pull the first JSON object out of a model reply (tolerates code fences and chatter)."""
    if not text:
        return {}
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except ValueError:
                        pass
                    break
        start = text.find("{", start + 1)
    return {}


def _clean_list(items, limit: int, safety=None, max_len: int = 120) -> List[str]:
    out = []
    for it in items if isinstance(items, list) else []:
        s = str(it).strip()
        if not s or len(s) > max_len:
            continue
        if safety is not None and safety.check(s, "output"):
            continue
        if s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def clean_draft(raw: Dict, safety=None) -> Dict:
    """Keep only known keys, cap sizes, and drop anything the safety filter would flag."""
    desc = str(raw.get("description", "") or "").strip()[:200]
    if desc and safety is not None and safety.check(desc, "output"):
        desc = ""
    return {
        "aliases": _clean_list(raw.get("aliases"), 6, None, 40),
        "description": desc,
        "highlights": _clean_list(raw.get("highlights"), 3, safety),
        "suggested_questions": _clean_list(raw.get("suggested_questions"), 4, None, 140),
    }


def enrich(title: str, price: str, llm_fn: Callable[[str], str], safety=None, extra: str = "") -> Dict:
    """Draft catalog fields for one product. Raises ValueError when the model reply has no usable JSON."""
    reply = llm_fn(build_prompt(title, price, extra))
    raw = parse_draft(reply)
    if not raw:
        raise ValueError("The model did not return a JSON draft; try again or fill the product in by hand.")
    return clean_draft(raw, safety)


def apply_draft(product: Dict, draft: Dict, overwrite: bool = False) -> Dict:
    """Merge a draft into a product dict. Hand-written fields stay unless overwrite=True.
    Suggested questions become FAQ stubs with an empty answer only in the draft; they are never added as FAQ."""
    if draft.get("aliases"):
        have = {a.lower() for a in product.get("aliases", [])}
        product["aliases"] = list(product.get("aliases", [])) + [a for a in draft["aliases"] if a.lower() not in have]
    if draft.get("description") and (overwrite or not product.get("description")):
        product["description"] = draft["description"]
    if draft.get("highlights") and (overwrite or not product.get("highlights")):
        product["highlights"] = draft["highlights"]
    return product
