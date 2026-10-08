"""Audiobook export: turn chapters of a licensed story into one MP3 (narrator, dialogue and per-character voices), plus a
chapter-timestamp list for the post description. Same free edge-tts voices and the same ffmpeg as the video export.
The text-to-speech function is injectable so the pipeline is testable offline."""
import os
import shutil
import subprocess
import tempfile
from typing import Callable, Dict, List, Optional

from . import novel, story_video


def estimate_seconds(book: Dict, chapters: List[int], rate: int = 0, gap: float = 0.35) -> float:
    return sum(novel.chapter_minutes(book, i, rate=rate) * 60 for i in chapters) + gap * 10 * len(chapters)


def _stamp(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def build(book: Dict, chapters: List[int], out_path: str, settings: Dict, tts: Optional[Callable] = None, lang: str = "vi",
          announce: bool = True, gap: float = 0.35, root: str = novel.NOVELS_DIR,
          progress: Optional[Callable[[int, int, str], None]] = None, cancel: Optional[Callable[[], bool]] = None) -> Dict:
    """settings: voice_narrator / voice_dialogue / characters / rate. Returns {audio, timestamps, seconds, pieces}."""
    ff = story_video.ffmpeg_exe()
    if not ff:
        raise RuntimeError("ffmpeg was not found. Install it, or run: pip install imageio-ffmpeg")
    tts = tts or (lambda t, v, r, o: story_video.edge_tts_file(t, v, r, o, lang))
    rate = int(settings.get("rate") or 0)
    names = list((settings.get("characters") or {}).keys())
    pron = novel.load_pron()
    jobs = []   # (chapter title or None, text, voice)
    for ci in chapters:
        title = book["chapters"][ci]["title"]
        if announce:
            jobs.append((title, f'{book["title"]}. {title}.' if ci == chapters[0] else f"{title}.", settings.get("voice_narrator") or ""))
        else:
            jobs.append((title, None, ""))
        for c in novel.chunks(novel.chapter_body(book, ci, root), 180, pron, names):
            jobs.append((None, c["text"], novel.voice_for(c, settings)))
    if not any(j[1] for j in jobs):
        raise ValueError("Nothing to read in those chapters.")
    work = tempfile.mkdtemp(prefix="novel_audio_")
    try:
        sil = os.path.join(work, "gap.mp3")
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{gap}", "-c:a", "libmp3lame",
                        "-q:a", "6", sil], check=True, capture_output=True)
        files, stamps, t = [], [], 0.0
        total = len(jobs)
        for i, (title, text, voice) in enumerate(jobs):
            if cancel and cancel():
                raise RuntimeError("Cancelled.")
            if progress:
                progress(i, total + 1, f"Reading {i + 1}/{total}")
            if title is not None:
                stamps.append((t, title))
            if not text:
                continue
            mp3 = os.path.join(work, f"p{i:05d}.mp3")
            tts(novel.clean_for_speech(text, pron), voice, rate, mp3)
            t += story_video.audio_seconds(ff, mp3) + gap
            files += [os.path.basename(mp3), "gap.mp3"]
        with open(os.path.join(work, "list.txt"), "w", encoding="utf-8") as f:
            for fn in files:
                f.write(f"file '{fn}'\n")
        if progress:
            progress(total, total + 1, "Joining")
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        r = subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c:a", "libmp3lame", "-q:a", "4",
                            "-metadata", f"title={book['title']}", "-metadata", f"artist={book.get('author', '')}", "-metadata", "genre=Audiobook",
                            os.path.abspath(out_path)], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError("ffmpeg failed: " + (r.stderr or "")[-300:])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    stamp_text = "\n".join(f"{_stamp(a)} {b}" for a, b in stamps)
    if progress:
        progress(total + 1, total + 1, "Done")
    return {"audio": out_path, "timestamps": stamp_text, "seconds": round(t, 1), "pieces": sum(1 for j in jobs if j[1])}
