"""Free AI art for the on-stream avatar: one original anime-style character in several expressions.

Default engine: a Stable Diffusion WebUI (AUTOMATIC1111 or Forge) running on your own computer, started with --api.
Recommended model: Animagine XL 3.1 (SDXL, CreativeML OpenRAIL++-M licence, which allows commercial use of the
images; check the model card yourself before you rely on it). Everything runs locally, so it is free and has no quota.
It needs a GPU with roughly 8 GB of video memory; there is no GPU in the build sandbox, so only the request/response
handling is tested here (against a fake server), never a real image.

Optional engine "pollinations": a free web image service that needs no GPU. It is UNTESTED here and its terms are not
verified, so read them before using its pictures commercially.

The character is described once (hair, eyes, outfit, vibe) and every expression reuses the same description and seed.
For the local engine each expression is an img2img pass from the base picture, which keeps the face recognisable.
Plain-background removal is a flood fill from the picture edges, so the prompt asks for a flat white background.
"""
import base64
import io
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

CORE = ["idle", "talking", "happy", "surprised", "confused", "thinking"]
EXTRA = ["wink", "shy", "excited", "sad", "sleepy", "laughing", "love", "proud"]
EXPRESSIONS = CORE + EXTRA
_EXPR_TAGS = {
    "idle": "calm smile, closed mouth, looking at viewer",
    "talking": "open mouth, cheerful, looking at viewer",
    "happy": "big happy smile, closed eyes, sparkles",
    "surprised": "surprised, wide eyes, open mouth, raised eyebrows",
    "confused": "confused, tilted head, sweat drop, small frown",
    "thinking": "thinking, hand on chin, looking up, closed mouth",
    "wink": "wink, one eye closed, smile, peace sign",
    "shy": "blush, shy, embarrassed, looking away, hands on cheeks",
    "excited": "excited, sparkling eyes, open mouth, fists raised",
    "sad": "sad, teary eyes, small frown, looking down",
    "sleepy": "sleepy, half-closed eyes, yawning",
    "laughing": "laughing, closed eyes, open mouth, tears of joy",
    "love": "heart-shaped pupils, blush, smile, floating hearts",
    "proud": "smug, proud smile, hand on hip, closed eyes",
}
# When a picture is missing the page uses the next one in the chain, ending at idle.
FALLBACK = {"talking": "idle", "happy": "idle", "surprised": "idle", "confused": "idle", "thinking": "idle",
            "wink": "happy", "shy": "happy", "excited": "happy", "sad": "confused", "sleepy": "idle",
            "laughing": "happy", "love": "happy", "proud": "happy"}


def resolve(expr: str, have) -> str:
    """The expression to actually show: expr itself if drawn, else down its fallback chain, else idle."""
    for _ in range(4):
        if expr in have:
            return expr
        expr = FALLBACK.get(expr, "idle")
    return "idle"


QUALITY = "masterpiece, best quality, very aesthetic, absurdres"
NEGATIVE = ("lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, "
            "worst quality, low quality, signature, watermark, username, blurry, background, scenery")
DEFAULT_MODEL = "Animagine XL 3.1"
DEFAULTS = {"engine": "local", "host": "127.0.0.1", "port": 7860, "checkpoint": "", "steps": 28, "cfg": 6.0,
            "width": 832, "height": 1216, "sampler": "Euler a", "denoise": 0.5, "timeout": 300}

Fetch = Callable[[str, Optional[dict], float], bytes]


def character_prompt(c: Dict) -> str:
    """Danbooru-style tags (what Animagine understands) from a plain character sheet."""
    gender = {"male": "1boy", "female": "1girl"}.get((c.get("gender") or "female").lower(), "1girl")
    parts = [gender, "solo", "upper body", c.get("hair", "long pink hair"), c.get("eyes", "blue eyes"),
             c.get("outfit", "white blouse, red ribbon"), c.get("extra", ""),
             "simple background, white background", QUALITY]
    return ", ".join(p.strip() for p in parts if p and p.strip())


def expression_prompt(c: Dict, expr: str) -> str:
    return character_prompt(c).replace("looking at viewer", "") + ", " + _EXPR_TAGS.get(expr, _EXPR_TAGS["idle"])


def _http(url: str, body: Optional[dict], timeout: float) -> bytes:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _b64_png(raw: str) -> bytes:
    return base64.b64decode(raw.split(",", 1)[-1])


def _override(cfg: Dict) -> dict:
    return {"override_settings": {"sd_model_checkpoint": cfg["checkpoint"]}} if cfg.get("checkpoint") else {}


def check_server(cfg: Dict, fetch: Fetch = _http) -> str:
    """'' when the WebUI answers, otherwise a plain message saying what to do."""
    try:
        fetch(f"http://{cfg['host']}:{cfg['port']}/sdapi/v1/options", None, 8)
        return ""
    except Exception as e:
        return (f"Cannot reach a Stable Diffusion WebUI at {cfg['host']}:{cfg['port']} ({e}). Start AUTOMATIC1111 or Forge with "
                f"the --api flag, load the {DEFAULT_MODEL} checkpoint, then try again.")


def txt2img(cfg: Dict, prompt: str, seed: int, fetch: Fetch = _http) -> bytes:
    body = {"prompt": prompt, "negative_prompt": NEGATIVE, "steps": int(cfg["steps"]), "cfg_scale": float(cfg["cfg"]),
            "width": int(cfg["width"]), "height": int(cfg["height"]), "sampler_name": cfg["sampler"], "seed": int(seed),
            "batch_size": 1, **_override(cfg)}
    out = json.loads(fetch(f"http://{cfg['host']}:{cfg['port']}/sdapi/v1/txt2img", body, float(cfg["timeout"])))
    imgs = out.get("images") or []
    if not imgs:
        raise RuntimeError("The WebUI returned no image.")
    return _b64_png(imgs[0])


def img2img(cfg: Dict, prompt: str, init_png: bytes, seed: int, fetch: Fetch = _http) -> bytes:
    body = {"init_images": [base64.b64encode(init_png).decode()], "prompt": prompt, "negative_prompt": NEGATIVE,
            "denoising_strength": float(cfg["denoise"]), "steps": int(cfg["steps"]), "cfg_scale": float(cfg["cfg"]),
            "width": int(cfg["width"]), "height": int(cfg["height"]), "sampler_name": cfg["sampler"], "seed": int(seed),
            **_override(cfg)}
    out = json.loads(fetch(f"http://{cfg['host']}:{cfg['port']}/sdapi/v1/img2img", body, float(cfg["timeout"])))
    imgs = out.get("images") or []
    if not imgs:
        raise RuntimeError("The WebUI returned no image.")
    return _b64_png(imgs[0])


def pollinations(cfg: Dict, prompt: str, seed: int, fetch: Fetch = _http) -> bytes:
    q = urllib.parse.quote(prompt + ", " + QUALITY)
    url = f"https://image.pollinations.ai/prompt/{q}?width=768&height=1024&seed={int(seed)}&nologo=true"
    return fetch(url, None, float(cfg["timeout"]))


def remove_flat_background(png: bytes, tolerance: int = 28) -> bytes:
    """Make the plain background transparent: the pixels close to the corner colour that connect to the picture edge."""
    from PIL import Image
    import numpy as np
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    a = np.array(im)
    rgb = a[:, :, :3].astype(int)
    corners = np.array([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]])
    ref = np.median(corners, axis=0)
    close = np.abs(rgb - ref).max(axis=2) <= tolerance
    bg = np.zeros_like(close)
    bg[0, :], bg[-1, :], bg[:, 0], bg[:, -1] = close[0, :], close[-1, :], close[:, 0], close[:, -1]
    for _ in range(max(a.shape[:2])):   # grow inwards through connected background pixels
        grown = bg.copy()
        grown[1:, :] |= bg[:-1, :]
        grown[:-1, :] |= bg[1:, :]
        grown[:, 1:] |= bg[:, :-1]
        grown[:, :-1] |= bg[:, 1:]
        grown &= close
        if (grown == bg).all():
            break
        bg = grown
    a[bg, 3] = 0
    out = io.BytesIO()
    Image.fromarray(a).save(out, "PNG")
    return out.getvalue()


def safe_name(name: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", (name or "").lower()).strip("-")[:40] or "character"


def generate_pack(char: Dict, cfg: Dict, out_dir: str, seed: int = 1234, expressions: Optional[List[str]] = None,
                  fetch: Fetch = _http, progress: Optional[Callable[[str], None]] = None) -> Dict:
    """Write out_dir/<expr>.png for each expression. Returns {"made": [...], "failed": {expr: reason}}."""
    cfg = {**DEFAULTS, **(cfg or {})}
    expressions = expressions or EXPRESSIONS
    os.makedirs(out_dir, exist_ok=True)
    say = progress or (lambda m: None)
    made, failed = [], {}
    base = None
    if cfg["engine"] == "local":
        problem = check_server(cfg, fetch)
        if problem:
            return {"made": [], "failed": {"all": problem}}
        say("Drawing the base picture ...")
        try:
            base = txt2img(cfg, character_prompt(char), seed, fetch)
        except Exception as e:
            return {"made": [], "failed": {"all": f"Base picture failed: {e}"}}
    for ex in expressions:
        say(f"Drawing {ex} ...")
        try:
            if cfg["engine"] == "local":
                png = base if ex == "idle" else img2img(cfg, expression_prompt(char, ex), base, seed, fetch)
            else:
                png = pollinations(cfg, expression_prompt(char, ex), seed, fetch)
            try:
                png = remove_flat_background(png)
            except Exception:
                pass   # keep the opaque picture; the overlay still works on a plain background
            with open(os.path.join(out_dir, ex + ".png"), "wb") as f:
                f.write(png)
            made.append(ex)
        except Exception as e:
            failed[ex] = str(e)
    return {"made": made, "failed": failed}
