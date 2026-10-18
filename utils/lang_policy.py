"""Which language to answer a viewer in. The host speaks Vietnamese; an English comment gets a short English answer,
any other language gets a Vietnamese answer (with a one-line note), because the voice and the catalog are Vietnamese.

Detection is deliberately simple and conservative: Vietnamese is the default whenever there is any doubt (viewers often type
Vietnamese without accents). Only text that is clearly English is answered in English."""
import json
import os
import re
from typing import Dict

PATH = os.path.join("data", "lang_policy.json")
_VI_CHARS = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)
_VI_PLAIN = {"ao", "gia", "bao", "nhieu", "ship", "mua", "con", "khong", "shop", "oi", "nhe", "nha", "ban", "minh", "cho", "xin",
             "chao", "mau", "size", "dc", "duoc", "hang", "tien", "giam", "lay", "chot", "cam", "on", "the", "nao", "gi"}
_EN = {"the", "is", "are", "how", "much", "what", "price", "can", "do", "you", "this", "that", "does", "have", "ship", "shipping",
       "size", "color", "colour", "available", "hello", "hi", "please", "buy", "where", "when", "which", "i", "it", "in", "for",
       "to", "of", "and", "my", "your", "free", "return", "cost", "much?"}
_EN_STRONG = {"the", "is", "are", "how", "what", "can", "does", "you", "this", "that", "have", "where", "when", "which", "please", "much", "your"}
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
_THAI = re.compile(r"[฀-๿]")


def detect(text: str) -> str:
    """'vi' | 'en' | 'cjk' | 'th' | 'other'"""
    t = (text or "").strip()
    if not t:
        return "vi"
    if _VI_CHARS.search(t):
        return "vi"
    if _CJK.search(t):
        return "cjk"
    if _THAI.search(t):
        return "th"
    words = re.findall(r"[a-z']+", t.lower())
    if not words:
        return "vi"
    vi = sum(1 for w in words if w in _VI_PLAIN and w not in _EN)
    en = sum(1 for w in words if w in _EN)
    strong = sum(1 for w in words if w in _EN_STRONG)
    if vi == 0 and en >= 2 and strong >= 1 and en * 2 >= len(words):
        return "en"
    return "vi"


def settings(path: str = PATH) -> Dict:
    d = {"english": True}
    try:
        with open(path, "r", encoding="utf-8") as f:
            d.update({k: v for k, v in json.load(f).items() if k == "english"})
    except (OSError, ValueError, AttributeError):
        pass
    d["english"] = bool(d["english"])
    return d


def save(english: bool, path: str = PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"english": bool(english)}, f)


def note(text: str, english_ok: bool = True) -> str:
    """A short instruction to append to the model prompt for this comment ('' when the default Vietnamese is right)."""
    lang = detect(text)
    if lang == "en" and english_ok:
        return "\n(The viewer wrote in English: answer in one or two short, simple English sentences.)"
    if lang in ("cjk", "th", "other", "en"):
        return "\n(Trả lời bằng tiếng Việt, ngắn gọn, thân thiện; không dùng ngôn ngữ khác.)"
    return ""
