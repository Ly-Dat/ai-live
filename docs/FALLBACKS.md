# When the TikTok connection breaks

`tiktok_bridge.py` uses TikTokLive, an unofficial library. TikTok can change its protocol without notice.

**How you find out:** the bridge writes `data/bridge_status.json` every 15 s. Home > Pre-live check and Live tools >
"If the TikTok connection breaks" turn it into a plain message (failing 3+ times in a row = down; connected but no chat
for 10 min = heads-up).

**Version:** setup installs `TikTokLive>=7,<8` into `venv_tt` (a new major version is never pulled in by surprise). The
installed version is stored in the status file. To freeze a version that works: `venv_tt\Scripts\pip install TikTokLive==<version>`.
To try a fix: `venv_tt\Scripts\pip install -U "TikTokLive<8"` and restart the bridge.

**Fallbacks, in order:**
1. *Ask the host* (Live tools): type a viewer question yourself. Always works while the app runs.
2. *Browser relay*: `tools/tiktok_chat_relay.user.js` (Tampermonkey) reads chat from your own open live page and posts it to
   the app. Its selectors are unverified against TikTok's current page; edit `SELECTORS` if nothing arrives.
3. Keep running the stream without chat: the product tour and flash sales do not need the bridge.
