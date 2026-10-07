"""
Logic behind the web UI "Setup" tab and launcher.py (no UI imports, so it is unit tested).

  * data/setup.json keeps the seller's answers (shop name, TikTok username, persona, options).
  * apply_setup() writes them into config.json / products.json.
  * ProcessManager starts and stops the TikTok bridge and the product tour as child processes.
"""
import json
import os
import subprocess
import sys
from typing import Dict, List, Optional

from . import personas

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SETUP_PATH = os.path.join(ROOT, "data", "setup.json")

DEFAULT_SETUP = {
    "shop_name": "",
    "tiktok_username": "",
    "persona_id": "friendly_girl",
    "gifts": True,
    "joins": False,
    "auto_tour": True,
    "tour_min_minutes": 5,
    "tour_max_minutes": 10,
    "tour_quiet": 2,
    "mode": "seller",            # "seller" (cart, pitches) or "creator" (just chatting, no products)
    "returning_viewers": False,  # opt-in welcome-back greetings (hashed viewer book)
}


def load_setup(path: str = SETUP_PATH) -> Dict:
    data = dict(DEFAULT_SETUP)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data.update(json.load(f))
    except (OSError, ValueError):
        pass
    return data


def save_setup(data: Dict, path: str = SETUP_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_username(name: str) -> str:
    """Accepts '@name', 'tiktok.com/@name/live' or 'name'; returns 'name'."""
    name = (name or "").strip()
    if "@" in name:
        name = name.split("@", 1)[1]
    return name.split("/")[0].split("?")[0].strip()


def validate(answers: Dict) -> List[str]:
    problems = []
    if not clean_username(answers.get("tiktok_username", "")):
        problems.append("Enter your TikTok username (the account that goes live).")
    return problems


def apply_setup(config_path: str, products_path: str, personas_path: str, answers: Dict) -> List[str]:
    """Write the wizard answers into config.json and products.json. Returns what changed."""
    changes = []
    with open(config_path, "r", encoding="utf-8") as f:
        raw = f.read()
    crlf = "\r\n" in raw
    cfg = json.loads(raw)
    cfg["room_display_id"] = clean_username(answers["tiktok_username"])
    changes.append(f"room_display_id = {cfg['room_display_id']}")
    persona_changes = personas.apply_to_config(cfg, personas.load(personas_path), answers.get("persona_id", "friendly_girl"))
    changes += persona_changes
    creator = answers.get("mode") == "creator"
    if isinstance(cfg.get("products"), dict):
        cfg["products"]["enable"] = not creator
        changes.append(f"products.enable = {not creator}")
    text = json.dumps(cfg, ensure_ascii=False, indent=2)
    with open(config_path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", "\r\n") if crlf else text)

    if answers.get("shop_name") and os.path.exists(products_path):
        with open(products_path, "r", encoding="utf-8") as f:
            raw = f.read()
        crlf = "\r\n" in raw
        pdata = json.loads(raw)
        pdata["shop_name"] = answers["shop_name"].strip()
        text = json.dumps(pdata, ensure_ascii=False, indent=2)
        with open(products_path, "w", encoding="utf-8", newline="") as f:
            f.write(text.replace("\n", "\r\n") if crlf else text)
        changes.append(f"shop_name = {pdata['shop_name']}")
    return changes


def bridge_python(root: str = ROOT) -> Optional[str]:
    for rel in (("venv_tt", "Scripts", "python.exe"), ("venv_tt", "bin", "python")):
        p = os.path.join(root, *rel)
        if os.path.exists(p):
            return p
    return None


def ensure_bridge_env(root: str = ROOT, log=print) -> str:
    """Create venv_tt with TikTokLive 7.x if it does not exist yet (needs internet). Returns its python path."""
    py = bridge_python(root)
    if py:
        return py
    log("Creating the TikTok bridge environment (venv_tt) ...")
    subprocess.check_call([sys.executable, "-m", "venv", os.path.join(root, "venv_tt")])
    py = bridge_python(root)
    subprocess.check_call([py, "-m", "pip", "install", "--quiet", "TikTokLive>=7"])
    return py


def voice_python(root: str = ROOT) -> Optional[str]:
    for rel in (("venv_voice", "Scripts", "python.exe"), ("venv_voice", "bin", "python")):
        p = os.path.join(root, *rel)
        if os.path.exists(p):
            return p
    return None


def ensure_voice_env(root: str = ROOT, log=print) -> str:
    """Create venv_voice with the free VieNeu-TTS package (own env: it pulls gradio/onnxruntime/librosa)."""
    py = voice_python(root)
    if py:
        return py
    log("Creating the voice environment (venv_voice) and installing VieNeu-TTS ...")
    subprocess.check_call([sys.executable, "-m", "venv", os.path.join(root, "venv_voice")])
    py = voice_python(root)
    subprocess.check_call([py, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    subprocess.check_call([py, "-m", "pip", "install", "--quiet", "vieneu"])
    return py


def voice_command(python: str) -> List[str]:
    return [python, "-m", "apps.openai_speech"]


def bridge_command(setup: Dict, python: str) -> List[str]:
    cmd = [python, "tiktok_bridge.py", clean_username(setup["tiktok_username"])]
    if setup.get("gifts"):
        cmd.append("--gifts")
    if setup.get("joins") or setup.get("returning_viewers"):
        cmd.append("--joins")
    return cmd


def tour_command(setup: Dict, python: str = sys.executable) -> List[str]:
    lo = float(setup.get("tour_min_minutes", 5) or 5)
    hi = max(lo, float(setup.get("tour_max_minutes", 10) or 10))
    return [python, "product_tour.py", "--min-minutes", f"{lo:g}", "--max-minutes", f"{hi:g}",
            "--quiet", f"{float(setup.get('tour_quiet', 2) or 2):g}"]


class ProcessManager:
    """Start / stop named child processes (bridge, tour). Lives inside the web UI process."""

    def __init__(self, root: str = ROOT):
        self.root = root
        self.procs: Dict[str, subprocess.Popen] = {}

    def running(self, name: str) -> bool:
        p = self.procs.get(name)
        return p is not None and p.poll() is None

    def start(self, name: str, cmd: List[str], env: Optional[Dict[str, str]] = None) -> bool:
        if self.running(name):
            return False
        os.makedirs(os.path.join(self.root, "log"), exist_ok=True)
        logf = open(os.path.join(self.root, "log", f"{name}.log"), "a", encoding="utf-8")
        full_env = dict(os.environ, **env) if env else None
        self.procs[name] = subprocess.Popen(cmd, cwd=self.root, stdout=logf, stderr=subprocess.STDOUT, env=full_env)
        return True

    def stop(self, name: str) -> bool:
        p = self.procs.get(name)
        if p is None or p.poll() is not None:
            return False
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
        return True

    def stop_all(self) -> None:
        for n in list(self.procs):
            self.stop(n)


PM_VOICE = ProcessManager()  # the VieNeu voice server; separate from the bridge/tour manager


def tail(path: str, lines: int = 12) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""
