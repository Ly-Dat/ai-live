"""Read a TikTok Shop product page through the user's own Chrome (remote debugging on localhost only),
and download product images into data/product_images/."""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

IMG_DIR = Path("data/product_images")

CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
CHROME_PROFILE = Path("data/chrome_profile")  # separate profile, lives inside the project

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _money(v) -> str:
    s = str(v if v is not None else "").strip()
    if not s:
        return ""
    try:
        n = float(s.replace(",", "")) if re.fullmatch(r"[\d,]+(\.\d+)?", s) else None
    except ValueError:
        n = None
    return f"{int(n):,}".replace(",", ".") + "đ" if n is not None else s


_PAGE_JS = r"""() => {
  const good = s => /tiktokcdn|ibyteimg|byteimg/.test(s) && !/avatar|logo|icon|emoji/.test(s);
  const imgs = [...document.images].filter(i => i.naturalWidth >= 200)
      .map(i => i.currentSrc || i.src).filter(good);
  const body = document.body.innerText || "";
  return {
    title: document.title,
    h1: (document.querySelector("h1") || {}).innerText || "",
    prices: body.match(/[\d.,]+\s*[₫đ]/g) || [],
    imgs, body: body.slice(0, 8000),
  };
}"""


_PRICE_RE = re.compile(r"₫\s*\d[\d.,]*|\d[\d.,]*\s*(?:₫|đ(?!\w))")


def _prices(body: str) -> list:
    return list(dict.fromkeys(m.strip() for m in _PRICE_RE.findall(body or "")))


def _norm_price(s: str) -> str:
    d = re.sub(r"[^\d.,]", "", s or "")
    return d + "₫" if d else ""


_OPT_LABEL = re.compile(r"^(Màu sắc|Màu|Kích cỡ|Kích thước|Size|Phân loại|Kiểu)\s*:\s*(.*)$", re.I)
_OPT_STOP = re.compile(r"^(Số lượng|Quantity|Mua ngay|Thêm vào giỏ|Buy now|Add to cart)", re.I)


def _split_title(title: str):
    """Marketing titles are long: short name = first clause, full title kept as the description."""
    t = " ".join((title or "").split())
    m = re.search(r"[,.;|]| - ", t[20:])
    name = t[:20 + m.start()].strip() if m else t
    if len(name) > 70:
        name = name[:70].rsplit(" ", 1)[0]
    return name, (t if name != t else "")


def _parse_options(body: str) -> str:
    """'Màu sắc: A, B; Kích cỡ: S, M, L' read from the rendered page text (labels end with ':')."""
    groups, cur = [], None
    for line in (ln.strip() for ln in body.splitlines()):
        if not line:
            continue
        if groups and _OPT_STOP.match(line):
            break  # ignore anything below the option block (reviews etc.)
        m = _OPT_LABEL.match(line)
        if m:
            cur = [m.group(1).strip(), []]
            groups.append(cur)
            if m.group(2).strip():
                cur[1].append(m.group(2).strip())  # selected value shown on the label line
            continue
        if cur is not None and len(line) <= 40 and "₫" not in line and line not in cur[1] and len(cur[1]) < 20:
            cur[1].append(line)
    return "; ".join(f"{k}: {', '.join(v)}" for k, v in groups if v)


def _find_chrome():
    """Locate Chrome (or Edge as a fallback) on Windows / macOS / Linux. None if not found."""
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    if sys.platform == "win32":
        import winreg
        for exe in ("chrome.exe", "msedge.exe"):
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                        p = winreg.QueryValue(k, None)
                        if p and Path(p).exists():
                            return p
                except OSError:
                    pass
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"),
                     os.environ.get("LOCALAPPDATA")):
            for sub in (r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe"):
                if base and (Path(base) / sub).exists():
                    return str(Path(base) / sub)
    elif sys.platform == "darwin":
        for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"):
            if Path(p).exists():
                return p
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "chrome", "microsoft-edge"):
        p = shutil.which(name)
        if p:
            return p
    return None


def _cdp_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", CDP_PORT), timeout=1):
            return True
    except OSError:
        return False


def _ensure_chrome() -> None:
    """Start the helper browser (separate profile, debug port on localhost) if it isn't running."""
    if _cdp_up():
        return
    exe = _find_chrome()
    if not exe:
        raise RuntimeError("Chrome/Edge not found. Set the CHROME_PATH environment variable to its full path.")
    first_run = not CHROME_PROFILE.exists()
    args = [exe, f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={CHROME_PROFILE.resolve()}", "--no-first-run"]
    if first_run:
        args.append("https://www.tiktok.com")  # log in / pass the check once in this profile
    subprocess.Popen(args)
    for _ in range(40):
        time.sleep(0.5)
        if _cdp_up():
            return
    raise RuntimeError("Started the browser but its debug port didn't open. "
                       "Close any window using data/chrome_profile and try again.")


def fetch_tiktok_product(url: str) -> dict:
    """Starts the helper browser if needed, opens a tab, reads it, closes it.
    If a Security Check shows up, solve it in that window (waits up to ~2 min)."""
    from playwright.sync_api import sync_playwright  # pip install playwright (no browser download needed)
    _ensure_chrome()
    r, blocked = None, True
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        page = browser.contexts[0].new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.bring_to_front()
            for tries in range(60):
                page.wait_for_timeout(2000)
                try:
                    r = page.evaluate(_PAGE_JS)
                except Exception:
                    continue  # page is still redirecting
                blocked = bool(re.search(r"Security Check|Xác minh|captcha", r["body"], re.I))
                if not blocked and r["h1"] and (_prices(r["body"]) or tries >= 6):
                    break
        finally:
            page.close()
    if not r or blocked:
        return {}

    Path("data").mkdir(exist_ok=True)  # debug dump: send this if fields come out wrong
    Path("data/debug_tiktok.txt").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    full_title = r["h1"] or (r["title"] if r["title"] != "TikTok Shop" else "")
    name, description = _split_title(full_title)
    prices = list(dict.fromkeys(_norm_price(p) for p in _prices(r["body"])))
    num = lambda s: int(re.sub(r"\D", "", s) or 0)
    seen, imgs = set(), []
    for u in r["imgs"]:
        k = u.split("?")[0].split("~")[0]
        if k not in seen:
            seen.add(k)
            imgs.append(u)
    return {
        "name": name,
        "description": description,
        "sizes_colors": _parse_options(r["body"]),
        "price": prices[0] if prices else "",
        "original_price": (max(prices[:3], key=num) if len(prices) > 1 and num(max(prices[:3], key=num)) > num(prices[0])
                           else ""),
        "images": imgs[:6],
    }


def _download_images(pid: str, urls) -> list:
    out = []
    for u in urls:
        try:
            resp = requests.get(u, headers={"User-Agent": UA, "Referer": "https://shop.tiktok.com/"}, timeout=20)
            ext = {"image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}.get(
                resp.headers.get("content-type", "").split(";")[0], ".jpg")
            fname = f"{pid}_{int(time.time() * 1000)}{ext}"
            (IMG_DIR / fname).write_bytes(resp.content)
            out.append(f"{IMG_DIR.as_posix()}/{fname}")
        except Exception:
            continue
    return out