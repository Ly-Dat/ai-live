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
import hashlib
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

CORE = ["idle", "talking", "happy", "surprised", "confused", "thinking"]
EXTRA = ["wink", "shy", "excited", "sad", "sleepy", "laughing", "love", "proud", "blink"]
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
    "blink": "eyes closed, calm smile, closed mouth, looking at viewer",
}
# When a picture is missing the page uses the next one in the chain, ending at idle.
FALLBACK = {"talking": "idle", "happy": "idle", "surprised": "idle", "confused": "idle", "thinking": "idle",
            "wink": "happy", "shy": "happy", "excited": "happy", "sad": "confused", "sleepy": "idle",
            "laughing": "happy", "love": "happy", "proud": "happy", "blink": "idle"}


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
    if cfg.get("engine") == "comfy":
        try:
            fetch(_comfy_base(cfg) + "/system_stats", None, 8)
            return ""
        except Exception as e:
            return (f"Cannot reach ComfyUI at {_comfy_base(cfg)} ({e}). Start ComfyUI, put the {DEFAULT_MODEL} file in "
                    "ComfyUI/models/checkpoints, then try again. The seller works fine without it; use your own pictures meanwhile.")
    try:
        fetch(f"http://{cfg['host']}:{cfg['port']}/sdapi/v1/options", None, 8)
        return ""
    except Exception as e:
        return (f"Cannot reach a Stable Diffusion WebUI at {cfg['host']}:{cfg['port']} ({e}). Start AUTOMATIC1111 or Forge with "
                f"the --api flag, load the {DEFAULT_MODEL} checkpoint, then try again.")


def txt2img(cfg: Dict, prompt: str, seed: int, fetch: Fetch = _http) -> bytes:
    if cfg.get("engine") == "comfy":
        return comfy_txt2img(cfg, prompt, seed, fetch)
    body = {"prompt": prompt, "negative_prompt": NEGATIVE, "steps": int(cfg["steps"]), "cfg_scale": float(cfg["cfg"]),
            "width": int(cfg["width"]), "height": int(cfg["height"]), "sampler_name": cfg["sampler"], "seed": int(seed),
            "batch_size": 1, **_override(cfg)}
    out = json.loads(fetch(f"http://{cfg['host']}:{cfg['port']}/sdapi/v1/txt2img", body, float(cfg["timeout"])))
    imgs = out.get("images") or []
    if not imgs:
        raise RuntimeError("The WebUI returned no image.")
    return _b64_png(imgs[0])


def img2img(cfg: Dict, prompt: str, init_png: bytes, seed: int, fetch: Fetch = _http) -> bytes:
    if cfg.get("engine") == "comfy":
        return comfy_img2img(cfg, prompt, init_png, seed, fetch)
    body = {"init_images": [base64.b64encode(init_png).decode()], "prompt": prompt, "negative_prompt": NEGATIVE,
            "denoising_strength": float(cfg["denoise"]), "steps": int(cfg["steps"]), "cfg_scale": float(cfg["cfg"]),
            "width": int(cfg["width"]), "height": int(cfg["height"]), "sampler_name": cfg["sampler"], "seed": int(seed),
            **_override(cfg)}
    out = json.loads(fetch(f"http://{cfg['host']}:{cfg['port']}/sdapi/v1/img2img", body, float(cfg["timeout"])))
    imgs = out.get("images") or []
    if not imgs:
        raise RuntimeError("The WebUI returned no image.")
    return _b64_png(imgs[0])


# ---- ComfyUI (free, local) -------------------------------------------------------------------------------------------
def _comfy_base(cfg: Dict) -> str:
    port = int(cfg["port"])
    if cfg.get("engine") == "comfy" and port == 7860:
        port = 8188            # ComfyUI's default; 7860 is the Stable Diffusion WebUI's
    return f"http://{cfg['host']}:{port}"


def _comfy_checkpoint(cfg: Dict, fetch: Fetch) -> str:
    if cfg.get("checkpoint"):
        return cfg["checkpoint"]
    info = json.loads(fetch(_comfy_base(cfg) + "/object_info/CheckpointLoaderSimple", None, 15))
    names = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    if not names:
        raise RuntimeError("ComfyUI has no checkpoint installed. Put the Animagine XL 3.1 file in ComfyUI/models/checkpoints.")
    return next((n for n in names if "animagine" in n.lower()), names[0])


def _comfy_graph(cfg: Dict, ckpt: str, prompt: str, seed: int, init_name: Optional[str] = None) -> dict:
    g = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
         "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
         "3": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["1", 1]}},
         "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                                                    "latent_image": ["4", 0], "seed": int(seed), "steps": int(cfg["steps"]),
                                                    "cfg": float(cfg["cfg"]), "sampler_name": "euler_ancestral",
                                                    "scheduler": "normal", "denoise": 1.0}},
         "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
         "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "ailive"}}}
    if init_name:
        g["8"] = {"class_type": "LoadImage", "inputs": {"image": init_name}}
        g["4"] = {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["1", 2]}}
        g["5"]["inputs"]["denoise"] = float(cfg["denoise"])
    else:
        g["4"] = {"class_type": "EmptyLatentImage", "inputs": {"width": int(cfg["width"]), "height": int(cfg["height"]), "batch_size": 1}}
    return g


def _fill(node, vals: Dict):
    """Replace {{name}} placeholders in a user workflow; a value that is only a placeholder keeps its number type."""
    if isinstance(node, dict):
        return {k: _fill(v, vals) for k, v in node.items()}
    if isinstance(node, list):
        return [_fill(v, vals) for v in node]
    if isinstance(node, str):
        m = re.fullmatch(r"\{\{(\w+)\}\}", node.strip())
        if m and m.group(1) in vals:
            return vals[m.group(1)]
        return re.sub(r"\{\{(\w+)\}\}", lambda mm: str(vals.get(mm.group(1), mm.group(0))), node)
    return node


def _comfy_run(cfg: Dict, graph: dict, fetch: Fetch, sleep: Callable[[float], None] = time.sleep) -> bytes:
    base = _comfy_base(cfg)
    out = json.loads(fetch(base + "/prompt", {"prompt": graph}, 30))
    pid = out.get("prompt_id")
    if not pid:
        raise RuntimeError(f"ComfyUI refused the workflow: {out.get('error') or out}")
    waited, limit = 0.0, float(cfg["timeout"])
    while waited <= limit:
        hist = json.loads(fetch(f"{base}/history/{pid}", None, 15)).get(pid)
        if hist and hist.get("outputs"):
            for node in hist["outputs"].values():
                for im in node.get("images") or []:
                    q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")})
                    return fetch(f"{base}/view?{q}", None, 60)
            raise RuntimeError("ComfyUI finished but returned no image. Check that the workflow has a SaveImage node.")
        sleep(1.0)
        waited += 1.0
    raise RuntimeError(f"ComfyUI did not finish within {int(limit)} s.")


def _comfy_upload(cfg: Dict, png: bytes) -> str:
    """Upload the base picture so img2img can start from it. Returns the stored file name."""
    boundary = "----ailive" + hashlib.sha1(png[:64]).hexdigest()[:12]
    name = "ailive_base_" + hashlib.sha1(png).hexdigest()[:10] + ".png"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\nContent-Type: image/png\r\n\r\n").encode() \
        + png + f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(_comfy_base(cfg) + "/upload/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()).get("name", name)


def comfy_txt2img(cfg: Dict, prompt: str, seed: int, fetch: Fetch = _http) -> bytes:
    ckpt = _comfy_checkpoint(cfg, fetch)
    wf = cfg.get("workflow")
    if wf:      # your own API-format workflow with {{prompt}} {{negative}} {{seed}} {{checkpoint}} {{width}} {{height}} {{steps}} {{cfg}}
        with open(wf, "r", encoding="utf-8") as f:
            graph = _fill(json.load(f), {"prompt": prompt, "negative": NEGATIVE, "seed": int(seed), "checkpoint": ckpt,
                                         "width": int(cfg["width"]), "height": int(cfg["height"]), "steps": int(cfg["steps"]), "cfg": float(cfg["cfg"])})
    else:
        graph = _comfy_graph(cfg, ckpt, prompt, seed)
    return _comfy_run(cfg, graph, fetch)


def comfy_img2img(cfg: Dict, prompt: str, init_png: bytes, seed: int, fetch: Fetch = _http) -> bytes:
    name = _comfy_upload(cfg, init_png)
    return _comfy_run(cfg, _comfy_graph(cfg, _comfy_checkpoint(cfg, fetch), prompt, seed, name), fetch)


def pollinations(cfg: Dict, prompt: str, seed: int, fetch: Fetch = _http) -> bytes:
    q = urllib.parse.quote(prompt + ", " + QUALITY)
    url = f"https://image.pollinations.ai/prompt/{q}?width=768&height=1024&seed={int(seed)}&nologo=true"
    return fetch(url, None, float(cfg["timeout"]))


def _reach(close, seed):
    """Cells of `close` connected (4-neighbour) to a seed cell. Spreads along whole runs of pixels at once, so it takes a few
    passes instead of one pass per pixel of distance (same result as the old one-pixel-at-a-time grow)."""
    import numpy as np
    cur = seed & close
    for _ in range(400):
        before = int(cur.sum())
        for transposed in (False, True):
            c = close.T if transposed else close
            s = cur.T if transposed else cur
            flat = c.ravel()
            starts = flat & ~np.concatenate(([False], flat[:-1]))
            starts[::c.shape[1]] = flat[::c.shape[1]]          # a run never continues onto the next row
            lab = np.cumsum(starts) * flat
            hit = np.bincount(lab[(s & c).ravel()], minlength=int(lab.max()) + 1) > 0
            hit[0] = False
            res = hit[lab].reshape(c.shape) & c
            cur = res.T if transposed else res
        if int(cur.sum()) == before:
            break
    return cur


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
    edge = np.zeros_like(close)
    edge[0, :], edge[-1, :], edge[:, 0], edge[:, -1] = True, True, True, True
    bg = _reach(close, edge)    # background = close-to-corner pixels that connect to the picture edge
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
    if cfg["engine"] in ("local", "comfy"):
        problem = check_server(cfg, fetch)
        if problem:
            return {"made": [], "failed": {"all": problem}}
        # The base picture is kept (_base.png) so a later "draw the missing ones" keeps the same face instead of a new one.
        base_key = hashlib.sha1(json.dumps([character_prompt(char), int(seed), cfg["width"], cfg["height"], cfg["steps"], cfg["cfg"],
                                            cfg["sampler"], cfg.get("checkpoint", "")], sort_keys=True, default=str).encode()).hexdigest()
        base_png, base_meta = os.path.join(out_dir, "_base.png"), os.path.join(out_dir, "_base.json")
        try:
            with open(base_meta, "r", encoding="utf-8") as f:
                same = json.load(f).get("key") == base_key
            if same:
                with open(base_png, "rb") as f:
                    base = f.read()
                say("Reusing the base picture (same face) ...")
        except (OSError, ValueError):
            base = None
        if not base:
            say("Drawing the base picture ...")
            try:
                base = txt2img(cfg, character_prompt(char), seed, fetch)
                with open(base_png, "wb") as f:
                    f.write(base)
                with open(base_meta, "w", encoding="utf-8") as f:
                    json.dump({"key": base_key}, f)
            except Exception as e:
                return {"made": [], "failed": {"all": f"Base picture failed: {e}"}}
    for ex in expressions:
        say(f"Drawing {ex} ...")
        try:
            if cfg["engine"] in ("local", "comfy"):
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
