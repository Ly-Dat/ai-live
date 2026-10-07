"""Curated free voices for the Voice tab (Microsoft Edge neural voices via edge-tts: free, no key).

The Edge service has no official SLA and its list changes, so every voice here is a
suggestion: the Voice lab plays it before you save, and edge-tts stays the fallback.
"""
from typing import Dict, List, Optional

SAMPLES = {
    "vi": "Chào cả nhà, mình là trợ lý AI của shop. Hôm nay có nhiều sản phẩm hay lắm, cùng xem nhé!",
    "en": "Hi everyone, welcome to the stream! I'm the shop's AI host. Today's picks are really good, so stay a while.",
}

# (id, lang, gender, label, style, vi_ok)  vi_ok: True = native Vietnamese, "try" = multilingual, may sound accented
_V = [
    ("vi-VN-HoaiMyNeural", "vi", "F", "Hoài My", "Warm, friendly - default seller voice", True),
    ("vi-VN-NamMinhNeural", "vi", "M", "Nam Minh", "Calm, clear - expert / explainer", True),
    ("en-US-AvaMultilingualNeural", "en", "F", "Ava (multilingual)", "Expressive, natural - best English female", "try"),
    ("en-US-EmmaMultilingualNeural", "en", "F", "Emma (multilingual)", "Soft, cheerful", "try"),
    ("en-US-AndrewMultilingualNeural", "en", "M", "Andrew (multilingual)", "Warm, confident", "try"),
    ("en-US-BrianMultilingualNeural", "en", "M", "Brian (multilingual)", "Casual, friendly", "try"),
    ("en-US-JennyNeural", "en", "F", "Jenny", "Friendly, assistant-like", False),
    ("en-US-AriaNeural", "en", "F", "Aria", "Upbeat, good for hype / flash sales", False),
    ("en-US-AnaNeural", "en", "F", "Ana", "Young, playful (child-like timbre)", False),
    ("en-US-MichelleNeural", "en", "F", "Michelle", "Clear, professional", False),
    ("en-US-GuyNeural", "en", "M", "Guy", "Energetic announcer", False),
    ("en-US-ChristopherNeural", "en", "M", "Christopher", "Deep, authoritative", False),
    ("en-US-EricNeural", "en", "M", "Eric", "Neutral, easy to follow", False),
    ("en-US-RogerNeural", "en", "M", "Roger", "Mature, steady", False),
    ("en-US-SteffanNeural", "en", "M", "Steffan", "Smooth, relaxed", False),
    ("en-GB-SoniaNeural", "en", "F", "Sonia (UK)", "British, polished", False),
    ("en-GB-LibbyNeural", "en", "F", "Libby (UK)", "British, bright", False),
    ("en-GB-MaisieNeural", "en", "F", "Maisie (UK)", "British, young", False),
    ("en-GB-RyanNeural", "en", "M", "Ryan (UK)", "British, friendly", False),
    ("en-GB-ThomasNeural", "en", "M", "Thomas (UK)", "British, calm", False),
    ("en-AU-NatashaNeural", "en", "F", "Natasha (AU)", "Australian, easygoing", False),
    ("en-AU-WilliamNeural", "en", "M", "William (AU)", "Australian, relaxed", False),
    ("en-CA-ClaraNeural", "en", "F", "Clara (CA)", "Canadian, clear", False),
    ("en-CA-LiamNeural", "en", "M", "Liam (CA)", "Canadian, friendly", False),
    ("en-IN-NeerjaNeural", "en", "F", "Neerja (IN)", "Indian English, warm", False),
    ("en-IN-PrabhatNeural", "en", "M", "Prabhat (IN)", "Indian English, clear", False),
    ("en-IE-EmilyNeural", "en", "F", "Emily (IE)", "Irish, gentle", False),
    ("en-IE-ConnorNeural", "en", "M", "Connor (IE)", "Irish, friendly", False),
]

VOICES: List[Dict] = [dict(id=i, lang=l, gender=g, label=n, style=s, vi=v) for i, l, g, n, s, v in _V]


def for_language(lang: str, gender: Optional[str] = None) -> List[Dict]:
    """Voices that can speak `lang` ('vi' or 'en'). Multilingual voices are listed for Vietnamese last, as 'try'."""
    out = []
    for v in VOICES:
        if lang == "vi":
            ok = v["vi"] is True or v["vi"] == "try"
        else:
            ok = v["lang"] == "en"
        if ok and (not gender or v["gender"] == gender):
            out.append(v)
    if lang == "vi":
        out.sort(key=lambda v: v["vi"] != True)  # noqa: E712 - native first, stable otherwise
    return out


def get(voice_id: str) -> Optional[Dict]:
    return next((v for v in VOICES if v["id"] == voice_id), None)


def lang_of(voice_id: str) -> str:
    return "vi" if (voice_id or "").lower().startswith("vi-") else "en"


def option_label(v: Dict, lang: str) -> str:
    g = "Female" if v["gender"] == "F" else "Male"
    tail = " - may sound accented, listen first" if (lang == "vi" and v["vi"] == "try") else ""
    return f'{v["label"]} ({g}) - {v["style"]}{tail}'


def options(lang: str, gender: Optional[str] = None) -> Dict[str, str]:
    return {v["id"]: option_label(v, lang) for v in for_language(lang, gender)}


def sample(lang: str) -> str:
    return SAMPLES.get(lang, SAMPLES["en"])
