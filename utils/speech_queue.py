"""Small helpers for the speech queue, kept pure so they can be tested without audio hardware."""
import re
from typing import Dict, Iterable


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def is_duplicate(queue: Iterable[Dict], item: Dict) -> bool:
    """True when the same line is already waiting to be spoken (so a burst of identical questions or a repeated pitch
    cannot make the host say it twice in a row). Empty lines are never duplicates."""
    c = _norm(item.get("content"))
    return bool(c) and any(_norm(m.get("content")) == c for m in queue)
