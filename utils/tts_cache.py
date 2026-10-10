"""Remember synthesized voice lines so a repeated sentence costs nothing.

Pitches, thank-yous and FAQ answers repeat during a live. The same text + engine + voice settings gives the same audio, so
the file is kept in data/tts_cache/ and copied out instead of calling the TTS again (edge-tts needs a network round trip
of 1-3 s; VieNeu uses the GPU/CPU). The cache is trimmed to a size limit, oldest-used first.
"""
import hashlib
import json
import os
import shutil
import time
from typing import Optional

DIR = os.path.join("data", "tts_cache")
MAX_BYTES = 300 * 1024 * 1024
MAX_CHARS = 300          # long one-off replies are not worth keeping


def key(engine: str, text: str, settings=None) -> Optional[str]:
    t = " ".join((text or "").split())
    if not t or len(t) > MAX_CHARS:
        return None
    blob = json.dumps([engine, t, settings or {}], sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()


def lookup(k: Optional[str], ext: str, dest: str, cache_dir: str = DIR) -> Optional[str]:
    """Copy the cached audio to `dest` and return dest, or None on a miss."""
    if not k:
        return None
    src = os.path.join(cache_dir, k + ext)
    try:
        if os.path.getsize(src) < 200:
            return None
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        shutil.copyfile(src, dest)
        os.utime(src, None)           # mark as recently used
        return dest
    except OSError:
        return None


def store(k: Optional[str], ext: str, src: Optional[str], cache_dir: str = DIR, max_bytes: int = MAX_BYTES) -> bool:
    if not k or not src:
        return False
    try:
        if os.path.getsize(src) < 200:        # an empty or error file must not be cached
            return False
        os.makedirs(cache_dir, exist_ok=True)
        tmp = os.path.join(cache_dir, k + ext + ".tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, os.path.join(cache_dir, k + ext))
        prune(cache_dir, max_bytes)
        return True
    except OSError:
        return False


def prune(cache_dir: str = DIR, max_bytes: int = MAX_BYTES) -> int:
    """Delete the least recently used files until the folder fits. Returns how many were removed."""
    try:
        files = []
        for n in os.listdir(cache_dir):
            p = os.path.join(cache_dir, n)
            if os.path.isfile(p):
                st = os.stat(p)
                files.append((st.st_mtime, st.st_size, p))
    except OSError:
        return 0
    total = sum(s for _, s, _ in files)
    removed = 0
    for _, size, p in sorted(files):
        if total <= max_bytes:
            break
        try:
            os.remove(p)
            total -= size
            removed += 1
        except OSError:
            pass
    return removed


def stats(cache_dir: str = DIR) -> dict:
    try:
        sizes = [os.path.getsize(os.path.join(cache_dir, n)) for n in os.listdir(cache_dir)]
    except OSError:
        sizes = []
    return {"files": len(sizes), "mb": round(sum(sizes) / 1048576, 1)}


def clear(cache_dir: str = DIR) -> int:
    n = 0
    try:
        for name in os.listdir(cache_dir):
            try:
                os.remove(os.path.join(cache_dir, name))
                n += 1
            except OSError:
                pass
    except OSError:
        pass
    return n
