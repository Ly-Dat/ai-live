"""
TikTok-safe text filter (Vietnamese aware).

Used on BOTH directions:
  * incoming viewer comments  (scope="input")
  * what the AI streamer is about to say (scope="output")

Matching is accent-insensitive and resistant to simple evasion:
  "Zalo", "z a l o", "z.a.l.o", "záloooo", "z4l0" all fold to the same token stream.

Terms live in data/tiktok_policy_terms.json so they can be edited without touching code:
{
  "categories": {
    "<name>": {"scope": "input|output|both", "action": "drop|mask", "terms": ["..."]}
  }
}
action "drop"  -> the whole message is rejected
action "mask"  -> the matched span is replaced with the mask string

NOTE: TikTok's real enforcement is not public and changes over time. This list is a
conservative starting point built from TikTok's published LIVE / Shop rules and common
seller-side bans; review it regularly.
"""
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
_ZERO_WIDTH = re.compile(r"[​-‏⁠﻿]")

# Patterns that are not plain words
_URL_RE = re.compile(r"(https?://|www\.)\S+|\b[a-z0-9-]+\.(com|vn|net|org|me|io|co|shop|store|xyz|info|link|ly)\b", re.I)
_HANDLE_RE = re.compile(r"(?<![\w.])@[\w.]{3,}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# Vietnamese mobile/landline numbers, with common separators; also spaced digits
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)[\s.\-]?(?:\d[\s.\-]?){8,10}(?!\d)")
_LONG_DIGITS_RE = re.compile(r"(?<!\d)(?:\d[\s.\-]?){9,}(?!\d)")  # bank accounts etc.


def fold(text: str) -> str:
    """Lowercase, drop diacritics (including d-stroke), normalize look-alikes."""
    text = unicodedata.normalize("NFKC", text or "")
    text = _ZERO_WIDTH.sub("", text).lower().replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _normalize_variants(text: str) -> List[str]:
    """Return text variants to scan: plain fold, leetspeak fold, separator-free fold."""
    base = fold(text)
    leet = base.translate(_LEET)
    # collapse runs of the same letter (zaloooo -> zalo); keep digits/percent signs untouched
    collapsed = re.sub(r"([a-z])\1{2,}", r"\1", leet)
    # remove separators between letters: "z.a.l.o" / "z a l o" -> "zalo"
    squeezed = re.sub(r"(?<=\b\w)[\s._\-*,|/\\]+(?=\w\b)", "", collapsed)
    squeezed = re.sub(r"(?<=[a-z])[._\-*|]+(?=[a-z])", "", squeezed)
    return [base, collapsed, squeezed]


def _accent_variants(text: str) -> List[str]:
    """Variants that keep Vietnamese tone marks: NFC lowercase, and separator-squeezed."""
    base = unicodedata.normalize("NFC", _ZERO_WIDTH.sub("", text or "")).lower()
    collapsed = re.sub(r"(\w)\1{2,}", r"\1", base)
    squeezed = re.sub(r"(?<=\b\w)[\s._\-*,|/\\]+(?=\w\b)", "", collapsed)
    return [base, collapsed, squeezed]


@dataclass
class Hit:
    category: str
    term: str
    action: str


class TikTokSafety:
    def __init__(self, terms_path: str = "data/tiktok_policy_terms.json", mask: str = "*"):
        self.mask = mask
        self.categories = {}
        self.regex_rules = {}
        self.load(terms_path)

    # ------------------------------------------------------------------ loading
    def load(self, path: str) -> None:
        if not os.path.exists(path):
            raise FileNotFoundError(f"TikTok policy terms file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.categories = {}
        for name, cfg in data.get("categories", {}).items():
            patterns = []
            accent = bool(cfg.get("accent_sensitive", False))
            for term in cfg.get("terms", []):
                # accent_sensitive categories keep tone marks, because Vietnamese folds collide
                # (e.g. "đeo"/"đéo", "ngủ"/"ngu", "đầm"/"đâm"); they match lowercase NFC text only.
                t = (unicodedata.normalize("NFC", term).lower() if accent else fold(term)).strip()
                if not t:
                    continue
                # word-boundary match so "ib" does not hit "ribbon"; spaces match flexible whitespace
                body = r"\s+".join(re.escape(p) for p in t.split())
                patterns.append((term, re.compile(r"(?<!\w)" + body + r"(?!\w)")))
            self.categories[name] = {
                "accent": accent,
                "scope": cfg.get("scope", "both"),
                "action": cfg.get("action", "drop"),
                "patterns": patterns,
                "use_regex": cfg.get("regex", []),
            }

    # ------------------------------------------------------------------ checking
    def check(self, text: str, scope: str = "input") -> List[Hit]:
        """Return all policy hits for the text. scope is 'input' or 'output'."""
        hits: List[Hit] = []
        if not text:
            return hits
        variants = _normalize_variants(text)
        accent_variants = _accent_variants(text)
        for name, cat in self.categories.items():
            if cat["scope"] not in ("both", scope):
                continue
            scan = accent_variants if cat["accent"] else variants
            for term, pat in cat["patterns"]:
                if any(pat.search(v) for v in scan):
                    hits.append(Hit(name, term, cat["action"]))
                    break  # one hit per category is enough
            for rule in cat["use_regex"]:
                if self._regex_hit(rule, text):
                    hits.append(Hit(name, f"<{rule}>", cat["action"]))
        return hits

    @staticmethod
    def _regex_hit(rule: str, text: str) -> bool:
        if rule == "url":
            return bool(_URL_RE.search(text))
        if rule == "handle":
            return bool(_HANDLE_RE.search(text)) or bool(_EMAIL_RE.search(text))
        if rule == "phone":
            return bool(_PHONE_RE.search(text))
        if rule == "long_digits":
            return bool(_LONG_DIGITS_RE.search(text))
        return False

    # ------------------------------------------------------------------ sanitizing
    def sanitize(self, text: str, scope: str = "input") -> Optional[str]:
        """Return None if the message must be dropped, else the text with 'mask' hits masked."""
        hits = self.check(text, scope)
        if not hits:
            return text
        if any(h.action == "drop" for h in hits):
            return None
        # mask action: replace on the folded text positions is unreliable with accents,
        # so mask by matching each term's accent-insensitive pattern against a char-aligned fold.
        return self._mask(text, [h.term for h in hits])

    def _mask(self, text: str, terms: List[str]) -> str:
        # Build a char-aligned folded string (1 char -> 1 char) so offsets map back to the original.
        aligned = "".join((fold(ch) or ch)[:1] for ch in text)
        out = list(text)
        for term in terms:
            t = fold(term)
            for m in re.finditer(r"(?<![a-z0-9])" + r"\s+".join(re.escape(p) for p in t.split()) + r"(?![a-z0-9])", aligned):
                for i in range(m.start(), m.end()):
                    if not out[i].isspace():
                        out[i] = self.mask
        return "".join(out)


_default: Optional[TikTokSafety] = None


def get_default(terms_path: str = "data/tiktok_policy_terms.json", mask: str = "*") -> TikTokSafety:
    global _default
    if _default is None:
        _default = TikTokSafety(terms_path, mask)
    return _default
