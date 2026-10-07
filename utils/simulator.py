"""
Offline evaluation of viewer comments, used by simulate_live.py --offline and the unit tests.

It runs the same pieces as the live pipeline (input safety filter, intent classifier, catalog quick answer / buy CTA)
without TikTok, an LLM or the web server, and says what the bot would do with each comment:
  blocked  - dropped (or masked) by the compliance filter
  quick    - answered from the catalog
  buy_cta  - buying signal answered with a "tap the cart" call-to-action
  llm      - would go to the LLM with product context
"""
from typing import Dict

from .live_analytics import classify_intent


def evaluate_comment(text: str, safety, catalog=None) -> Dict:
    hits = safety.check(text, "input") if safety is not None else []
    intent = classify_intent(text)
    out = {"text": text, "intent": intent, "verdict": "llm", "reply": "", "product": None,
           "categories": sorted({h.category for h in hits})}
    if any(h.action == "drop" for h in hits):
        out["verdict"] = "blocked"
        return out
    if hits:  # mask-only hits: the comment goes on with the masked text
        text = safety.sanitize(text, "input") or text
    if catalog is not None:
        found = catalog.find_relevant(text, 1)
        product = found[0] if found else None
        out["product"] = product["name"] if product else None
        quick = catalog.quick_answer(text)
        if quick:
            out.update(verdict="quick", reply=quick)
        elif intent == "buy" and product:
            out.update(verdict="buy_cta", reply=catalog.buy_reply(product))
    return out
