"""
Cursor-following mascot for the web UI. A vanilla-JS port of page-mascot (MIT, (c) Kamran Ahmed,
https://github.com/nilbuild/page-mascot): the head follows the pointer, a click makes it blink and react, and
poking it fast makes it dizzy. Sprite sheets live in data/mascots/ (see LICENSE-page-mascot.txt there).
"""
import os

from nicegui import app, ui

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "mascots")
NAMES = ["cat", "fox", "bunny", "panda"]
_mounted = False

_JS = r"""
window.lvMascot = function (id, dirUrl, reactUrl) {
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
  });
};
"""


def _mount() -> None:
    global _mounted
    if _mounted:
        return
    if os.path.isdir(_DIR):
        app.add_static_files("/lv-mascots", _DIR)
    _mounted = True


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
