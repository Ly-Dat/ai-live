"""Pre-stream go / no-go check. Run it before every real LIVE:  python go_nogo.py

It checks what a computer can check (PASS / FAIL) and lists what only a person can check (MANUAL).
Exit code 1 when any check FAILS. Nothing is changed and nothing is sent anywhere.
"""
import json
import os
import re
import subprocess
import sys

from utils import setup_wizard, host_control
from utils.product_catalog import audit_products

ROOT = os.path.dirname(os.path.abspath(__file__))
PASS, FAIL, MANUAL = "PASS", "FAIL", "MANUAL"


def _load(path, default):
    try:
        with open(os.path.join(ROOT, path), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def checks():
    out = []
    add = lambda status, label, note="": out.append((status, label, note))

    v = sys.version_info
    add(PASS if (v.major, v.minor) in ((3, 10), (3, 11)) else FAIL, f"Python {v.major}.{v.minor}", "3.10 or 3.11 is required; 3.12+ breaks pinned packages")

    cfg = _load("config.json", {})
    prods = _load(cfg.get("products", {}).get("path") or "data/products.json", {}).get("products", [])
    active = [p for p in prods if p.get("active", True)]
    blockers = setup_wizard.start_blockers({}, os.path.join(ROOT, cfg.get("products", {}).get("path") or "data/products.json"))
    add(FAIL if blockers else PASS, f"{len(active)} active product(s)", blockers[0] if blockers else "")
    noprice = [p.get("name", "?")[:30] for p in active if not p.get("price")]
    add(FAIL if noprice else PASS, "Every active product has a price", ", ".join(noprice[:3]))
    gaps = audit_products(prods)
    add(PASS if not gaps else MANUAL, "Product facts complete" if not gaps else f"{len(gaps)} product(s) miss facts",
        "The host will say it cannot confirm those; fill them in the Products tab if viewers will ask" if gaps else "")

    tpl = _load("data/pitch_templates.json", {})
    add(PASS if tpl.get("disclosure") else FAIL, "AI-disclosure line is set", "pitch_templates.json -> disclosure")
    filt = cfg.get("filter", {}).get("tiktok_safety", {})
    add(PASS if filt.get("enable") and os.path.exists(os.path.join(ROOT, filt.get("terms_path", "x"))) else FAIL,
        "Safety filter on, with its term list", "config.json -> filter -> tiktok_safety")
    add(PASS if cfg.get("analytics", {}).get("enable") else FAIL, "Analytics on (needed for the post-live report)")
    add(PASS if cfg.get("triage", {}).get("enable") is not False else MANUAL, "Comment triage on")
    state = host_control.load(os.path.join(ROOT, host_control.PATH))["state"]
    add(PASS if state == "live" else FAIL, f"Host state: {state}", "Resume the AI in Avatar studio > Control" if state != "live" else "")

    try:
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.splitlines()
        bad = [f for f in files if f.startswith("data/chrome_profile/") or f.lower().endswith(("/cookies", ".pem", ".p12"))]
        add(FAIL if bad else PASS, "No browser profile / cookies tracked by git", bad[0] if bad else "")
    except Exception:
        add(MANUAL, "Could not run git to check tracked files")
    raw = open(os.path.join(ROOT, "config.json"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "config.json")) else ""
    keys = re.findall(r'"(?:api_key|token|secret|cookie)"\s*:\s*"([^"]{12,})"', raw)
    real = [k for k in keys if not k.lower().startswith(("your", "sk-xxx"))]
    add(FAIL if real else PASS, "No API keys / tokens inside the tracked config.json", f"{len(real)} value(s) found: move them to environment variables" if real else "")

    sim = subprocess.run([sys.executable, "simulate_live.py", "--offline"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    add(PASS if sim.returncode == 0 else FAIL, "Offline simulation meets its expectations", sim.stdout.strip().splitlines()[-1] if sim.stdout.strip() else sim.stderr[-200:])

    for label in ("Unit tests pass (python -m pytest tests/unit); accept or fix any failure",
                  "Prices and facts in the catalog checked by a person",
                  "AI disclosure and TikTok's current LIVE rules checked for your account and region",
                  "Integration method and account permissions confirmed (the chat bridge is unofficial and can stop working)",
                  "Pressed Pause and Take over during real speech and it stopped",
                  "Someone watches chat for the first stream and can end it"):
        add(MANUAL, label)
    return out


def main():
    rows = checks()
    for s, label, note in rows:
        print(f"[{s:<6}] {label}" + (f"  - {note}" if note else ""))
    fails = sum(1 for r in rows if r[0] == FAIL)
    manual = sum(1 for r in rows if r[0] == MANUAL)
    print(f"\n{'NO-GO' if fails else 'GO (computer checks)'}: {fails} failed, {manual} to confirm by hand.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
