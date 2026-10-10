"""
Cursor-following mascot for the web UI. A vanilla-JS port of page-mascot (MIT, (c) Kamran Ahmed,
https://github.com/nilbuild/page-mascot): the head follows the pointer, a click makes it blink and react, and
poking it fast makes it dizzy. Sprite sheets live in data/mascots/ (see LICENSE-page-mascot.txt there).
"""
import json
import os

from nicegui import app, ui

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mascots")
NAMES = ["cat", "fox", "bunny", "panda"]
_mounted = False

_JS = r"""
window.lvMascot = function (id, dirUrl, reactUrl) {
  try {   // the animal the user picked last time
    const nm = localStorage.getItem("lvMascot");
    if (nm && /^(cat|fox|bunny|panda)$/.test(nm)) {
      dirUrl = dirUrl.replace(/\/[a-z]+-directions/, "/" + nm + "-directions");
      reactUrl = reactUrl.replace(/\/[a-z]+-reactions/, "/" + nm + "-reactions");
    }
  } catch (e) {}
  const root = document.getElementById(id);
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const DIRS = ["up-left","up","up-right","left","center","right","down-left","down","down-right"];
  const REACTS = ["blink","heart","sparkle","surprised","wink","bashful","sleepy","dizzy","delighted"];
  const CW = ["right","down-right","down","down-left","left","up-left","up","up-right"];
  const SECTOR = Math.PI * 2 / CW.length, HYST = 0.12, DEAD = 70;
  const PAYOFFS = ["heart","sparkle","delighted"];
  const SQUASH = [
    {transform:"scale(1,1)",easing:"ease-in"},
    {transform:"scale(1.10,0.86)",offset:.18,easing:"ease-out"},
    {transform:"scale(0.95,1.08)",offset:.45,easing:"ease-in-out"},
    {transform:"scale(1.03,0.97)",offset:.72,easing:"ease-in-out"},
    {transform:"scale(1,1)"}];
  const mk = (url) => { const s = document.createElement("span");
    s.style.cssText = "position:absolute;inset:0;background-size:300% 300%;background-repeat:no-repeat;background-image:url(" + url + ")"; return s; };
  const pos = (el, i) => { el.style.backgroundPosition = (i % 3) * 50 + "% " + Math.floor(i / 3) * 50 + "%"; };
  const body = document.createElement("span");
  body.style.cssText = "position:relative;display:block;width:100%;height:100%;transform-origin:50% 78%";
  const d = mk(dirUrl), r = mk(reactUrl);
  pos(d, 4); pos(r, 0); r.style.opacity = 0;
  body.append(d, r); root.append(body);
  const bub = document.createElement("span");   // speech bubble, to the left of the mascot
  bub.style.cssText = "position:absolute;right:100%;top:6px;margin-right:6px;width:max-content;max-width:210px;text-align:left;" +
    "font-size:12px;line-height:1.35;font-weight:600;padding:7px 11px;border-radius:12px 12px 4px 12px;background:var(--lv-surface);" +
    "color:var(--lv-text);border:1px solid var(--lv-border);box-shadow:0 8px 22px rgba(0,0,0,.18);opacity:0;transform:translateY(4px);" +
    "transition:opacity .2s,transform .2s;pointer-events:none;z-index:5";
  root.append(bub);
  const wrap = (a) => Math.atan2(Math.sin(a), Math.cos(a));
  let sector = -1, pointer = null, timers = [], boops = {n: 0, at: 0};
  function aim() {
    if (!pointer) return;
    const b = root.getBoundingClientRect();
    const dx = pointer.x - (b.left + b.width / 2), dy = pointer.y - (b.top + b.height / 2);
    if (Math.hypot(dx, dy) < DEAD) { sector = -1; pos(d, 4); return; }
    const a = Math.atan2(dy, dx);
    if (sector !== -1 && Math.abs(wrap(a - sector * SECTOR)) < SECTOR / 2 + HYST) return;
    sector = (Math.round(a / SECTOR) + CW.length) % CW.length;
    pos(d, DIRS.indexOf(CW[sector]));
  }
  if (matchMedia("(hover: hover) and (pointer: fine)").matches) {
    addEventListener("pointermove", (e) => { pointer = {x: e.clientX, y: e.clientY}; aim(); }, {passive: true});
    addEventListener("scroll", aim, {passive: true});
  }
  function show(name) {
    if (name) { pos(r, REACTS.indexOf(name)); r.style.opacity = 1; d.style.opacity = 0; }
    else { r.style.opacity = 0; d.style.opacity = 1; }
  }
  root.addEventListener("click", () => {
    timers.forEach(clearTimeout); timers = [];
    const later = (ms, n) => timers.push(setTimeout(() => show(n), ms));
    const now = Date.now();
    boops.n = now - boops.at < 1600 ? boops.n + 1 : 1; boops.at = now;
    if (boops.n >= 4) { boops.n = 0; show("dizzy"); later(1100, null); }
    else { show("blink"); later(120, PAYOFFS[(boops.n - 1) % 3]); later(560, null); }
    if (!matchMedia("(prefers-reduced-motion: reduce)").matches)
      body.animate(SQUASH, {duration: 420, easing: "linear"});
    let total = 0;   // she gets fond of you
    try { total = (+localStorage.getItem("lvBoops") || 0) + 1; localStorage.setItem("lvBoops", total); } catch (e) {}
    const LINES = {10: "Hehe, that tickles!", 30: "We are friends now, right?", 60: "You really like me!", 100: "Best human ever."};
    if (LINES[total]) say(LINES[total], "heart");
  });
  let hideT = null, sleepT = null, asleep = false;
  function say(text, react, ms) {
    bub.textContent = text; bub.style.opacity = 1; bub.style.transform = "none";
    clearTimeout(hideT);
    hideT = setTimeout(() => { bub.style.opacity = 0; bub.style.transform = "translateY(4px)"; }, ms || 4500);
    if (react) { timers.forEach(clearTimeout); timers = []; show(react); timers.push(setTimeout(() => show(null), 1500)); }
  }
  function nap() { asleep = true; show("sleepy"); }
  function wake() { clearTimeout(sleepT); if (asleep) { asleep = false; show(null); } sleepT = setTimeout(nap, 90000); }
  ["pointermove", "keydown", "pointerdown"].forEach((ev) => addEventListener(ev, wake, {passive: true}));
  wake();
  window.lvMascotApi = {
    say: say,
    react: (n) => { show(n); setTimeout(() => show(null), 1400); },
    set: (nm) => {
      if (!/^(cat|fox|bunny|panda)$/.test(nm)) return;
      try { localStorage.setItem("lvMascot", nm); } catch (e) {}
      d.style.backgroundImage = "url(" + dirUrl.replace(/\/[a-z]+-directions/, "/" + nm + "-directions") + ")";
      r.style.backgroundImage = "url(" + reactUrl.replace(/\/[a-z]+-reactions/, "/" + nm + "-reactions") + ")";
      say("Hi, I am your " + nm + " now!", "wink");
    },
  };
  try {
    if (!sessionStorage.getItem("lvHi")) {
      sessionStorage.setItem("lvHi", "1");
      const h = new Date().getHours();
      setTimeout(() => say(h < 11 ? "Good morning! Ready to sell?" : h < 18 ? "Hi! Let us make a great live." : "Evening! Big live tonight?", "delighted", 5000), 900);
    }
  } catch (e) {}
};
"""


def _mount() -> None:
    global _mounted
    if _mounted:
        return
    if os.path.isdir(_DIR):
        app.add_static_files("/lv-mascots", _DIR)
    _mounted = True


def say(text: str, react: str = None) -> None:
    """Make the mascot speak (and react) if one is on the page."""
    try:
        ui.run_javascript(f"window.lvMascotApi&&lvMascotApi.say({json.dumps(text)},{json.dumps(react)})")
    except Exception:
        pass


def picker() -> None:
    """Small row to choose the animal; remembered in this browser."""
    with ui.row().style("gap:4px;align-items:center;margin-top:10px"):
        ui.label("Your mascot").classes("lv-stat-label").style("margin-right:6px")
        for n in NAMES:
            ui.button(n.capitalize(), on_click=lambda n=n: ui.run_javascript(f"window.lvMascotApi&&lvMascotApi.set('{n}')")).props("flat dense no-caps")


def mascot(name: str = "cat", size: int = 120) -> None:
    """Place a mascot in the current layout slot. Falls back to nothing if the sprite sheets are missing."""
    _mount()
    name = name if name in NAMES else "cat"
    if not os.path.isfile(os.path.join(_DIR, f"{name}-directions.webp")):
        return
    ui.add_head_html(f"<script>{_JS}</script>", shared=True)
    el = ui.element("button").classes("lv-mascot").props(f'type=button aria-label="Boop the {name}"').style(
        f"position:relative;width:{size}px;height:{size}px;padding:0;border:0;background:transparent;cursor:pointer;flex-shrink:0")
    ui.timer(0.4, lambda: ui.run_javascript(
        f"lvMascot('c{el.id}','/lv-mascots/{name}-directions.webp','/lv-mascots/{name}-reactions.webp')"), once=True)
