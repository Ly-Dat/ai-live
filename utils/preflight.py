"""Pre-live check: a short list of things that would embarrass you on air, each with the one-click fix.

Pure: `run(facts)` turns plain facts into rows, so it is easy to test. The web UI gathers the facts.
Each row: {"id", "ok" (True / False / None = heads-up), "label", "fix", "go"} where `go` is the tab that fixes it.
"""
from typing import Dict, List


def run(f: Dict) -> List[Dict]:
    rows = []

    def add(id_, ok, label, fix="", go=""):
        rows.append({"id": id_, "ok": ok, "label": label, "fix": "" if ok else fix, "go": "" if ok else go})

    user = (f.get("tiktok_username") or "").strip()
    add("account", bool(user), f"TikTok account: @{user}" if user else "No TikTok account set",
        "Enter the username that goes live.", "Setup")
    add("app", bool(f.get("api_ok")), "Host app is running" if f.get("api_ok") else "Host app is not running",
        "Start the app (python main.py), then check again.", "Setup")
    engine = f.get("engine") or "edge-tts"
    if engine == "vieneu":
        add("voice", bool(f.get("voice_ok")), "Voice server (VieNeu) is up" if f.get("voice_ok") else "Voice server (VieNeu) is not reachable",
            "Start the voice server from Setup. Until then the host falls back to Edge voice.", "Voice")
    else:
        add("voice", True, "Voice: Edge TTS (needs internet)")
    if f.get("mode") != "creator":
        n = int(f.get("product_count") or 0)
        add("products", n > 0, f"{n} active product{'s' if n != 1 else ''} in the cart" if n else "No products yet",
            "Add a product or use the 3 samples.", "Products")
        nop = int(f.get("no_price") or 0)
        if n and nop:
            add("prices", None, f"{nop} product{'s' if nop != 1 else ''} without a price",
                "Price questions get a weaker answer when the price is empty.", "Products")
    if f.get("host_state") in ("paused", "takeover"):
        add("host", None, "The AI host is paused" if f["host_state"] == "paused" else "You are hosting (the AI is silent)",
            "Resume it in Avatar studio > Control before you expect answers.", "Avatar studio")
    if f.get("avatar_enabled") and not f.get("avatar_ready"):
        add("avatar", None, "The avatar is on but has no picture yet", "Draw or pick a character in Avatar studio.", "Avatar studio")
    calls = int(f.get("llm_calls") or 0)
    if calls >= 3:
        p50, fail = int(f.get("llm_p50_ms") or 0), float(f.get("llm_fail_rate") or 0)
        if fail >= 0.3:
            add("ai_fail", False, f"{int(fail * 100)}% of AI replies failed", "Check the AI provider or set a fallback in AI engine.", "AI engine")
        elif p50 >= 4000:
            add("ai_speed", None, f"AI replies take {p50 / 1000:.1f} s", "Viewers wait that long. Try a faster model or a fallback in AI engine.", "AI engine")
    bh = f.get("bridge_health")
    if bh and bh.get("level") in ("down", "warn") and f.get("bridge_on"):
        add("bridge_health", False if bh["level"] == "down" else None, bh["message"],
            "Use 'Ask the host' or the browser relay in Live tools until it recovers.", "Live tools")
    add("bridge", bool(f.get("bridge_on")), "Chat bridge is connected" if f.get("bridge_on") else "Chat bridge is not started",
        "Press Go live (the bridge only runs once you are live on TikTok).", "Setup")
    if f.get("own_voice") and engine != "vieneu":
        add("own_voice", None, "Own voice is set but the engine is not VieNeu", "Save the Setup step again.", "Setup")
    return rows


def summary(rows: List[Dict]) -> str:
    bad = [r for r in rows if r["ok"] is False]
    warn = [r for r in rows if r["ok"] is None]
    if bad:
        return f"{len(bad)} thing{'s' if len(bad) != 1 else ''} to fix before going live."
    if warn:
        return f"Ready. {len(warn)} heads-up{'s' if len(warn) != 1 else ''}."
    return "All clear. You are ready to go live."
