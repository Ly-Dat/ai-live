"""Keep the host speaking Vietnamese/English: drop Chinese / Japanese / Korean text from AI replies.

Some local models (Qwen, ChatGLM, ...) drift into Chinese mid-sentence, and the bundled demo Q&A files are Chinese.
`clean()` removes CJK runs; if nothing speakable is left it returns None so the reply is skipped instead of read out.
"""
import re
from typing import Optional

# Han, Kana, Hangul, CJK punctuation / full-width forms
_CJK = re.compile(r"[⺀-⿿　-〿぀-ヿ㄀-ㄯ㄰-㆏㇀-ㇿ"
                  r"㈀-㏿㐀-䶿一-鿿가-힯豈-﫿＀-￯]+")


def has_cjk(text: str) -> bool:
    return bool(text and _CJK.search(text))


def clean(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    if not has_cjk(text):
        return text
    out = _CJK.sub(" ", text)
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    out = re.sub(r"[\s,;:\-?!.]+$", "", out)  # dangling comma where the Chinese part started
    if sum(ch.isalpha() for ch in out) < 2:
        return None
    return out


RETRY_NOTE = "\n(Reply only in Vietnamese, in plain text. Do not use Chinese characters.)"


def needs_retry(text: Optional[str]) -> bool:
    """True when the model answered only in CJK, so nothing speakable is left after `clean`."""
    return bool(text) and has_cjk(text) and clean(text) is None
