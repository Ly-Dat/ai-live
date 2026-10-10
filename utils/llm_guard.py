"""A guard around the AI reply so a slow or broken provider cannot stall the stream.

  * timeout: give up after N seconds (0 turns it off) instead of waiting forever
  * fallback: if the main provider fails or times out, ask a second one you chose (for example a local model)
  * breaker: after a few failures in a row the main provider is skipped for a short while, so each comment is not
    delayed by another timeout

Settings live in data/engine.json (edited in the Avatar studio's Engine tab). With the defaults (no fallback) a failure
simply returns None, which is what the app did before; the only change is that a hung request ends after the timeout.
"""
import json
import os
import threading
import time
import traceback
from typing import Callable, Dict, Optional

from . import engine_stats

PATH = os.path.join("data", "engine.json")
DEFAULTS = {"timeout_s": 25, "fallback": "", "breaker_fails": 3, "cooldown_s": 60, "tts_cache": True}
SKIP = ("reread", "chatterbot")          # local and instant: no need to guard
_state: Dict[str, Dict] = {}             # provider -> {"fails": n, "open_until": t}
_lock = threading.Lock()


def load(path: str = PATH) -> Dict:
    out = dict(DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        for k, default in DEFAULTS.items():
            if k in d:
                try:
                    out[k] = bool(d[k]) if isinstance(default, bool) else type(default)(d[k])
                except (TypeError, ValueError):
                    pass
    except (OSError, ValueError):
        pass
    out["timeout_s"] = max(0, min(300, int(out["timeout_s"])))
    out["breaker_fails"] = max(1, min(20, out["breaker_fails"]))
    out["cooldown_s"] = max(5, min(3600, out["cooldown_s"]))
    out["fallback"] = str(out["fallback"] or "").strip()
    return out


def tts_cache_enabled(path: str = PATH) -> bool:
    return bool(load(path)["tts_cache"])


def save(settings: Dict, path: str = PATH) -> Dict:
    d = {**DEFAULTS, **{k: v for k, v in (settings or {}).items() if k in DEFAULTS}}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return load(path)


def reset() -> None:
    with _lock:
        _state.clear()


def is_open(provider: str, now: Optional[float] = None) -> bool:
    now = time.time() if now is None else now
    with _lock:
        return _state.get(provider, {}).get("open_until", 0) > now


def _ok(provider: str) -> None:
    with _lock:
        _state.pop(provider, None)


def _bad(provider: str, cfg: Dict, now: float) -> None:
    with _lock:
        s = _state.setdefault(provider, {"fails": 0, "open_until": 0})
        s["fails"] += 1
        if s["fails"] >= cfg["breaker_fails"]:
            s["open_until"] = now + cfg["cooldown_s"]
            s["fails"] = 0


def _run_with_timeout(fn: Callable[[], Optional[str]], timeout: float):
    """(result, timed_out, error). A hung call is abandoned (its thread is a daemon), not killed."""
    if timeout <= 0:
        try:
            return fn(), False, ""
        except Exception as e:
            return None, False, f"{type(e).__name__}: {e}"
    box = {}

    def work():
        try:
            box["r"] = fn()
        except Exception as e:
            box["e"] = f"{type(e).__name__}: {e}"
            box["tb"] = traceback.format_exc()

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None, True, f"no answer after {timeout:g}s"
    return box.get("r"), False, box.get("e", "")


def call(primary: str, run: Callable[[str], Optional[str]], settings: Optional[Dict] = None,
         now: Callable[[], float] = time.time, log: Optional[Callable[[str], None]] = None) -> Optional[str]:
    """run(name) asks provider `name` and returns its text (or None). Returns the first usable answer."""
    cfg = settings or load()
    say = log or (lambda m: None)
    if primary in SKIP:
        return run(primary)
    fb = cfg["fallback"] if cfg["fallback"] and cfg["fallback"] != primary else ""
    order = [primary]
    if fb:
        order = [fb, primary] if is_open(primary, now()) else [primary, fb]
    for i, name in enumerate(order):
        t0 = now()
        res, timed_out, err = _run_with_timeout(lambda n=name: run(n), cfg["timeout_s"])
        ms = (now() - t0) * 1000
        good = isinstance(res, str) and res.strip() != ""
        engine_stats.record("llm", ms, ok=good, fallback=(name != primary and good), timeout=timed_out, error=err)
        if good:
            _ok(name)
            if name != primary:
                say(f"AI reply came from the fallback provider '{name}'.")
            return res
        _bad(name, cfg, now())
        say(f"AI provider '{name}' gave no answer ({err or 'empty reply'}).")
    return None
