"""
Pure logic behind the Home tab: which steps are done, what to do next, a greeting. No UI, no network.
"""
from typing import Dict, List, Optional

# (id, label, hint when missing, tab to open)
STEPS = [
    ("shop", "Shop details", "Add your TikTok username in Setup.", "Setup"),
    ("products", "Products in the cart", "Import a spreadsheet or add one product.", "Products"),
    ("voice", "Voice ready", "Pick a voice and preview it.", "Voice"),
    ("app", "AI streamer running", "Press Start Run (bottom bar) to launch the streamer.", "Setup"),
    ("bridge", "Connected to TikTok LIVE", "Setup step 5 starts the TikTok bridge.", "Setup"),
]


def checklist(facts: Dict) -> List[Dict]:
    ok = {
        "shop": bool(str(facts.get("tiktok_username") or "").strip()),
        "products": int(facts.get("product_count") or 0) > 0,
        "voice": bool(facts.get("voice_ok", True)),
        "app": bool(facts.get("api_ok")),
        "bridge": bool(facts.get("bridge_on")),
    }
    return [{"id": i, "label": l, "ok": ok[i], "hint": h, "tab": t} for i, l, h, t in STEPS]


def progress(items: List[Dict]) -> int:
    return round(100 * sum(1 for i in items if i["ok"]) / len(items)) if items else 0


def next_step(items: List[Dict]) -> Optional[Dict]:
    return next((i for i in items if not i["ok"]), None)


def greeting(hour: int, name: str = "") -> str:
    part = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 18 else "Good evening"
    return f"{part}, {name}" if name else part


TIPS = [
    "Pin your best-selling product: the host mentions it first when viewers ask 'what is this?'.",
    "Run the dry run in Setup before every live. It shows what the AI would say to typical viewers, offline.",
    "Flash sale announcements work best every 8-10 minutes; more than that feels like spam.",
    "Check the Dashboard after a live: the 'Hot right now' list tells you what to push next time.",
    "Use a different persona for sale hours vs chill hours. Switch in Setup, restart the app.",
    "Short product facts beat long ones: the host reads exactly what you write.",
]


def tip(day_ordinal: int) -> str:
    return TIPS[day_ordinal % len(TIPS)]
