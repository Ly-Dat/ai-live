"""Last line of defence: every line must pass the output safety filter right before it is turned into speech.

Replies are already filtered where they are written; this repeats the check at the one place all speech goes through,
so a code path that forgot to filter can still not reach the speaker. Returns the (possibly masked) text, or None to drop.
"""
from typing import Callable, Optional


def gate(text: str, sanitize: Optional[Callable[[str], Optional[str]]]) -> Optional[str]:
    """`sanitize` is the output filter (text -> cleaned text or None). With no filter configured, text passes unchanged."""
    if not text or not str(text).strip():
        return None
    if sanitize is None:
        return text
    try:
        return sanitize(text)
    except Exception:    # a broken filter must not silence the whole stream; the error is logged by the caller
        return text
