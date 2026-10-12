"""Comment triage: decide which viewer comments deserve a spoken answer, and how urgent each one is.

Pure and clock-injected, so it is easy to test. It never writes anything and never touches the network.

Categories: purchase, question, faq_repeat, greeting, feedback, spam, unrelated. (Prohibited content is handled by the
safety filter before this runs; pass `is_prohibited` to also mark it here.)
Actions: "answer" (go on to the normal reply path) or "skip" (say nothing; the reason is kept for the report).
"""
import re
import time
from collections import deque
from typing import Callable, Deque, Dict, List, Optional, Tuple

from utils.live_analytics import SALES_INTENTS, classify_intent
from utils.tiktok_safety import fold

PRIORITY = {"purchase": 100, "question": 70, "faq_repeat": 20, "feedback": 30, "greeting": 10, "unrelated": 5, "spam": 0}
_GREET = ["xin chao", "chao", "hello", "hi", "hey", "alo", "chao ban", "chao shop", "minh den roi", "em den roi"]
_THANKS_PRAISE = ["cam on", "thanks", "thank", "hay qua", "dep qua", "xinh qua", "thich", "tuyet", "tot qua", "te qua", "do qua", "that vong"]
_QWORDS = ["khong", "sao", "nao", "gi", "bao nhieu", "the nao", "ai", "dau", "co the", "duoc khong", "?"]


def _has(folded: str, words: List[str]) -> bool:
    return any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", folded) for w in words if w != "?")


def _tokens(folded: str) -> frozenset:
    return frozenset(t for t in re.findall(r"[a-z0-9]+", folded) if len(t) > 1)


def _similar(a: frozenset, b: frozenset) -> bool:
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= 0.8


class Triage:
    def __init__(self, dedupe_sec: float = 90, greet_cooldown_sec: float = 600, user_cooldown_sec: float = 4,
                 busy_per_10s: int = 8, low_gap_sec: float = 15, is_prohibited: Optional[Callable[[str], bool]] = None):
        self.dedupe_sec, self.greet_cooldown_sec = dedupe_sec, greet_cooldown_sec
        self.user_cooldown_sec, self.busy_per_10s, self.low_gap_sec = user_cooldown_sec, busy_per_10s, low_gap_sec
        self.is_prohibited = is_prohibited
        self._recent: Deque[Tuple[float, frozenset]] = deque()      # answered questions (any viewer)
        self._last_by_user: Dict[str, Tuple[float, str]] = {}      # user -> (time, folded text)
        self._greeted: Dict[str, float] = {}
        self._arrivals: Deque[float] = deque()
        self._last_low = -1e9
        self.counts: Dict[str, int] = {}

    # -- classification ------------------------------------------------------------------------------------------
    def classify(self, text: str) -> str:
        f = fold(text or "")
        letters = re.sub(r"[^a-z0-9]", "", f)
        if self.is_prohibited and self.is_prohibited(text):
            return "prohibited"
        if not letters or len(text) > 220 or re.search(r"(.)\1{7,}", f) or re.search(r"https?://|www\.|\.com\b", f):
            return "spam"
        intent = classify_intent(text)
        if intent == "buy":
            return "purchase"
        if intent in SALES_INTENTS:
            return "question"
        if _has(f, _THANKS_PRAISE):
            return "feedback"
        words = f.split()
        if len(words) <= 4 and _has(f, _GREET):
            return "greeting"
        if "?" in text or _has(f, _QWORDS):
            return "question"
        return "unrelated"

    # -- decision ------------------------------------------------------------------------------------------------
    def decide(self, user: str, text: str, now: Optional[float] = None) -> Dict:
        now = time.time() if now is None else now
        cat = self.classify(text)
        f = fold(text or "")
        toks = _tokens(f)
        self._arrivals.append(now)
        while self._arrivals and now - self._arrivals[0] > 10:
            self._arrivals.popleft()
        busy = len(self._arrivals) > self.busy_per_10s
        while self._recent and now - self._recent[0][0] > self.dedupe_sec:
            self._recent.popleft()

        def out(action: str, reason: str = "", category: str = cat) -> Dict:
            key = category if action == "answer" else f"skip_{reason}"
            self.counts[key] = self.counts.get(key, 0) + 1
            return {"category": category, "priority": PRIORITY.get(category, 0), "action": action, "reason": reason, "busy": busy}

        if cat == "prohibited":
            return out("skip", "prohibited")
        if cat == "spam":
            return out("skip", "spam")
        last = self._last_by_user.get(user)
        self._last_by_user[user] = (now, f)
        if last and (last[1] == f and now - last[0] < 30 or now - last[0] < self.user_cooldown_sec and cat not in ("purchase",)):
            return out("skip", "same_viewer_too_fast")
        if cat == "greeting":
            if now - self._greeted.get(user, -1e9) < self.greet_cooldown_sec:
                return out("skip", "greeted_recently")
            self._greeted[user] = now
        if cat in ("purchase", "question") and any(_similar(toks, t) for _, t in self._recent):
            return out("skip", "repeated_question", "faq_repeat")
        if cat in ("greeting", "feedback", "unrelated"):
            if busy:
                return out("skip", "busy_chat")
            if now - self._last_low < self.low_gap_sec:
                return out("skip", "low_priority_spacing")
            self._last_low = now
        if cat in ("purchase", "question"):
            self._recent.append((now, toks))
        return out("answer")

    def summary(self) -> Dict[str, int]:
        return dict(self.counts)
