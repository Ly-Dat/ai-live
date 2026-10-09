"""Talk to the AI chosen in Settings WITHOUT starting the live (Start Run).

Most setups (OpenAI, Ollama, LM Studio, vLLM, any OpenAI-compatible server) are reached directly through
`openai.api` + `openai.api_key` in config.json, so the Story studio can write while you are offline from TikTok.
Other providers fall back to the running app (POST /llm), which needs Start Run.
Pure functions + urllib, no extra packages. The HTTP part is unit tested against a fake server.
"""
import json
import re
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional

THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
DEFAULT_BASE = "http://127.0.0.1:11434/v1"


def _cfg(config, key, default=None):
    try:
        v = config.get(key, default) if hasattr(config, "get") else default
    except TypeError:
        v = config.get(key)
    return default if v is None else v


def endpoint(config) -> Dict:
    """{base, key, model} from config.json: the OpenAI-compatible server and the model name."""
    oa = _cfg(config, "openai", {}) or {}
    base = str(oa.get("api") or DEFAULT_BASE).rstrip("/")
    keys = oa.get("api_key")
    key = (keys[0] if isinstance(keys, list) and keys else keys) or "sk"
    model = (_cfg(config, "chatgpt", {}) or {}).get("model") or ""
    return {"base": base, "key": str(key), "model": str(model)}


def _http(url: str, key: str, body: Optional[dict], timeout: float):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def list_models(config, timeout: float = 6.0) -> List[str]:
    """Model names the server offers (GET /models). Raises RuntimeError with a how-to when it cannot be reached."""
    ep = endpoint(config)
    try:
        res = _http(ep["base"] + "/models", ep["key"], None, timeout)
    except Exception as e:
        raise RuntimeError(f"Cannot reach the AI server at {ep['base']} ({type(e).__name__}). Start it (e.g. Ollama / LM Studio) or "
                           "set the address in Settings -> OpenAI.") from e
    return sorted(m.get("id", "") for m in (res.get("data") or res.get("models") or []) if isinstance(m, dict) and m.get("id"))


def best_model(names: List[str], preferred: str = "") -> str:
    """The model to use by default: the one from Settings if the server has it, else the biggest chat model (not an embedding
    model) up to ~34B - writing quality grows with size, but a giant model is too slow on a home PC."""
    if preferred and preferred in names:
        return preferred
    chat_models = [n for n in names if not re.search(r"embed|nomic|bge|minilm|rerank|whisper|tts", n, re.I)]

    def score(n: str):
        m = re.search(r"(\d+(?:\.\d+)?)\s*b\b", n, re.I)
        size = float(m.group(1)) if m else 0.0
        return (size if size <= 34 else 0.5 / size, "instruct" in n.lower() or "chat" in n.lower(), n)
    return max(chat_models or names, key=score) if (chat_models or names) else ""


def clean_reply(text: str) -> str:
    """Drop <think>..</think> blocks (reasoning models) and code fences around the answer."""
    t = THINK_RE.sub("", text or "")
    t = re.sub(r"^\s*```[a-zA-Z]*\n|\n```\s*$", "", t.strip())
    return t.strip()


def chat(config, prompt: str, model: str = "", system: str = "", temperature: float = 0.9, max_tokens: int = 4096,
         timeout: float = 600.0) -> str:
    """One chat completion. Long timeout: local models are slow. Raises RuntimeError with a readable message."""
    ep = endpoint(config)
    model = model or ep["model"]
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": model, "messages": msgs, "temperature": temperature, "max_tokens": max_tokens, "stream": False}
    try:
        res = _http(ep["base"] + "/chat/completions", ep["key"], body, timeout)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        raise RuntimeError(f"The AI server said {e.code}: {detail or e.reason}. Model: {model!r}. Pick a model it has (Story studio -> AI model).") from e
    except Exception as e:
        raise RuntimeError(f"Cannot reach the AI server at {ep['base']} ({type(e).__name__}). Start it (e.g. Ollama / LM Studio) or "
                           "set the address in Settings -> OpenAI.") from e
    try:
        text = clean_reply(res["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError):
        text = ""
    if not text:
        raise RuntimeError("The AI answered with nothing. Try again or pick another model.")
    return text


def make_llm(config, model: str = "", system: str = "", temperature: float = 0.9, app_llm: Optional[Callable[[str], str]] = None,
             progress_note: Optional[Callable[[str], None]] = None) -> Callable[[str], str]:
    """llm_fn(prompt) -> reply. chat_type 'chatgpt' (the OpenAI-compatible setting) goes direct, no Start Run needed;
    any other provider uses `app_llm` (the running app's /llm)."""
    ctype = str(_cfg(config, "chat_type", "chatgpt"))
    if ctype == "chatgpt" or app_llm is None:
        return lambda prompt: chat(config, prompt, model, system, temperature)
    return lambda prompt: clean_reply(app_llm(prompt))
