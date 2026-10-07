"""Is the TikTok chat bridge actually delivering? Read from the heartbeat file that tiktok_bridge.py writes.

TikTokLive is an unofficial library; when TikTok changes something it fails with errors. This turns that into a plain
message plus a flag telling the UI to offer the fallbacks (manual 'Ask the host' box, browser relay).
"""
import json
import os
import time
from typing import Dict, Optional

PATH = os.path.join("data", "bridge_status.json")
STALE_S = 60          # heartbeat is written every 15 s
SILENT_S = 600        # connected but no chat for this long -> heads-up
BROKEN_AFTER = 3      # consecutive failed connection attempts


def read(path: str = PATH) -> Optional[Dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def assess(status: Optional[Dict], now: Optional[float] = None) -> Dict:
    """{"level": ok|warn|down|off, "message": str, "fallback": bool}"""
    now = now or time.time()
    if not status:
        return {"level": "off", "message": "The TikTok bridge has not been started.", "fallback": False}
    if now - float(status.get("updated") or 0) > STALE_S:
        return {"level": "off", "message": "The TikTok bridge is not running.", "fallback": False}
    state = status.get("state")
    err = status.get("last_error") or ""
    lib = status.get("lib") or "?"
    if state == "error" and int(status.get("failures") or 0) >= BROKEN_AFTER:
        return {"level": "down", "fallback": True,
                "message": f"TikTok connection keeps failing ({err or 'unknown error'}). TikTok may have changed something; "
                           f"update TikTokLive (now {lib}) or use a fallback below."}
    if state == "rate_limited":
        return {"level": "warn", "message": "TikTok is rate limiting the connection; retrying shortly.", "fallback": True}
    if state == "waiting_live":
        return {"level": "warn", "message": "Waiting for your TikTok live to start.", "fallback": False}
    if state == "connected":
        quiet = now - float(status.get("last_event_ts") or now)
        if quiet > SILENT_S:
            return {"level": "warn", "fallback": True,
                    "message": f"Connected, but no chat for {int(quiet // 60)} min. Quiet room, or the feed stopped."}
        return {"level": "ok", "message": "Connected to TikTok chat.", "fallback": False}
    return {"level": "warn", "message": "Connecting to TikTok ...", "fallback": False}
