"""
Visual theme for the control panel: dark "studio" look (violet -> pink accent), sidebar navigation, status header,
card / stat helpers. Pure presentation: no business logic lives here.

  apply_theme()                 once, before building the page
  build_shell(tabs, nav)        header + grouped sidebar that drive an (invisible) ui.tabs
  page_title(title, subtitle)   consistent heading for each tab
  stat_card(label, icon)        returns the value label of a KPI card
"""
import socket
from typing import Callable, Dict, List, Optional, Tuple

from nicegui import ui

try:  # serves the Vietnamese dictionary at /lv_i18n
    from utils import i18n as _i18n
    _i18n.mount()
except Exception:  # the UI still works, only the language switch is lost
    _i18n = None

ACCENT = "#8b5cf6"      # violet
ACCENT_2 = "#ec4899"    # pink

CSS = """
:root{
  --lv-bg:#f5f4fb; --lv-surface:#ffffff; --lv-surface-2:#f0eefa; --lv-border:#e3e0f2;
  --lv-text:#1d1b2e; --lv-muted:#6f6b8a; --lv-accent:#8b5cf6; --lv-accent-2:#ec4899;
  --lv-good:#16a34a; --lv-warn:#d97706; --lv-bad:#dc2626;
  --lv-grad:linear-gradient(135deg,#8b5cf6 0%,#ec4899 100%);
  --page-bg:var(--lv-bg); --card-bg:var(--lv-surface); --card-border:var(--lv-border);
}
body.body--dark{
  --lv-bg:#0c0b14; --lv-surface:#151423; --lv-surface-2:#1c1b2e; --lv-border:#2a2842;
  --lv-text:#ecebf8; --lv-muted:#8f8cac; --lv-good:#34d399; --lv-warn:#fbbf24; --lv-bad:#f87171;
  --page-bg:var(--lv-bg); --card-bg:var(--lv-surface); --card-border:var(--lv-border);
}
html,body,.q-layout{ font-family:'Inter','Segoe UI',system-ui,-apple-system,sans-serif !important; }
body{ background:var(--lv-bg) !important; color:var(--lv-text); }
.q-page-container,.q-tab-panels,.q-tab-panel{ background:transparent !important; }
.q-tab-panel{ padding:26px 32px 110px !important; max-width:1320px; margin:0 auto; }

/* ---- header ---- */
.lv-header{ background:color-mix(in srgb,var(--lv-surface) 82%,transparent) !important; backdrop-filter:blur(14px);
  border-bottom:1px solid var(--lv-border); color:var(--lv-text) !important; height:60px; padding:0 20px; }
.lv-brand{ display:flex; align-items:center; gap:12px; }
.lv-logo{ width:34px; height:34px; border-radius:11px; background:var(--lv-grad); display:flex; align-items:center;
  justify-content:center; color:#fff; font-weight:800; box-shadow:0 6px 18px rgba(139,92,246,.45); }
.lv-brand-name{ font-weight:800; font-size:17px; letter-spacing:.2px; }
.lv-brand-sub{ font-size:11px; color:var(--lv-muted); margin-top:-3px; }
.lv-pill{ display:inline-flex; align-items:center; gap:7px; padding:5px 12px; border-radius:999px; font-size:12px;
  font-weight:600; background:var(--lv-surface-2); border:1px solid var(--lv-border); color:var(--lv-muted); }
.lv-dot{ width:8px; height:8px; border-radius:50%; background:#6b6785; }
.lv-pill.on{ color:var(--lv-text); } .lv-pill.on .lv-dot{ background:var(--lv-good); box-shadow:0 0 0 4px rgba(52,211,153,.18); }
.lv-pill.warn .lv-dot{ background:var(--lv-warn); }

/* ---- sidebar ---- */
.lv-bottomnav{ display:none !important; background:color-mix(in srgb,var(--lv-surface) 92%,transparent) !important; backdrop-filter:blur(14px);
  border-top:1px solid var(--lv-border); padding:4px 6px calc(4px + env(safe-area-inset-bottom)); }
.lv-bottomnav .lv-bn{ flex:1; min-height:48px; min-width:44px; color:var(--lv-muted) !important; font-size:11px; font-weight:600; }
.lv-bottomnav .lv-bn.active{ color:var(--lv-accent) !important; }
@media (max-width:899px){ .lv-bottomnav{ display:flex !important; justify-content:space-around; } }
.lv-drawer{ background:var(--lv-surface) !important; border-right:1px solid var(--lv-border) !important; }
.lv-drawer .q-scrollarea__content{ padding:14px 12px 24px; }
.lv-group{ font-size:11px; font-weight:700; letter-spacing:1.4px; text-transform:uppercase; color:var(--lv-muted);
  margin:16px 10px 6px; }
.lv-nav{ width:100%; justify-content:flex-start !important; border-radius:12px !important; padding:9px 12px !important;
  color:var(--lv-muted) !important; font-weight:600; text-transform:none; transition:all .15s ease; }
.lv-nav .q-icon{ font-size:20px; margin-right:12px; }
.lv-nav:hover{ background:var(--lv-surface-2) !important; color:var(--lv-text) !important; }
.lv-nav.active{ background:var(--lv-grad) !important; color:#fff !important; box-shadow:0 8px 20px rgba(139,92,246,.35); }
.lv-nav .q-btn__content{ justify-content:flex-start; flex-wrap:nowrap; text-align:left; }
.lv-hidden-tabs{ display:none !important; }

/* ---- cards / headings ---- */
.lv-title{ font-size:26px; font-weight:800; letter-spacing:-.3px; }
.lv-sub{ color:var(--lv-muted); font-size:14px; margin-top:2px; margin-bottom:18px; }
.lv-card,.q-expansion-item,.q-stepper,.q-table__container.lv-table{
  background:var(--lv-surface) !important; border:1px solid var(--lv-border) !important; border-radius:18px !important;
  box-shadow:0 1px 0 rgba(255,255,255,.02), 0 10px 30px rgba(0,0,0,.06); }
body.body--dark .lv-card, body.body--dark .q-expansion-item, body.body--dark .q-stepper{
  box-shadow:0 1px 0 rgba(255,255,255,.03), 0 14px 34px rgba(0,0,0,.35); }
.q-expansion-item{ margin:12px 0 !important; overflow:hidden; }
.q-card{ border-radius:16px; }
.lv-stat{ min-width:140px; flex:1 1 150px; padding:16px 18px; position:relative; overflow:hidden; }
.lv-stat::after{ content:''; position:absolute; right:-24px; top:-24px; width:90px; height:90px; border-radius:50%;
  background:var(--lv-grad); opacity:.14; }
.lv-stat-label{ white-space:nowrap; font-size:12px; font-weight:600; color:var(--lv-muted); text-transform:uppercase; letter-spacing:.8px; }
.lv-stat-value{ font-size:30px; font-weight:800; line-height:1.15; margin-top:4px; }
.lv-ico{ width:34px; height:34px; border-radius:10px; display:flex; align-items:center; justify-content:center;
  background:var(--lv-surface-2); color:var(--lv-accent); margin-bottom:10px; }
.lv-hero{ background:var(--lv-grad); color:#fff; border-radius:20px; padding:22px 26px;
  box-shadow:0 18px 40px rgba(139,92,246,.35); }
.lv-hero .lv-title{ color:#fff; }
.lv-chip{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600;
  background:var(--lv-surface-2); border:1px solid var(--lv-border); color:var(--lv-muted); margin:2px 4px 2px 0; }
.lv-chip.good{ color:var(--lv-good); } .lv-chip.bad{ color:var(--lv-bad); } .lv-chip.hot{ color:var(--lv-accent-2); }

/* ---- controls ---- */
.q-btn{ border-radius:12px; text-transform:none; font-weight:600; letter-spacing:0; }
.q-btn.bg-primary{ background:var(--lv-grad) !important; }
.q-field--outlined .q-field__control{ border-radius:12px; }
.q-field--standard .q-field__control{ border-radius:10px 10px 0 0; }
.q-field{ margin:4px 6px; }
.q-tab-panels{ padding-bottom:0; }
.q-table th{ font-weight:700; color:var(--lv-muted); text-transform:uppercase; font-size:11px; letter-spacing:.8px; }
.q-table__card{ background:transparent !important; box-shadow:none !important; }
.q-stepper{ background:var(--lv-surface) !important; }
.q-stepper__tab--active .q-stepper__dot, .q-stepper__tab--done .q-stepper__dot{ background:var(--lv-grad) !important; }
.q-separator{ background:var(--lv-border) !important; }
.q-notification{ border-radius:14px; }

.bottom-bar{
  position:fixed; left:50%; bottom:16px; transform:translateX(-50%); z-index:200; gap:10px; padding:10px 16px;
  background:color-mix(in srgb,var(--lv-surface) 88%,transparent); backdrop-filter:blur(14px);
  border:1px solid var(--lv-border); border-radius:18px; box-shadow:0 14px 40px rgba(0,0,0,.35);
}
::-webkit-scrollbar{ width:10px; height:10px; } ::-webkit-scrollbar-thumb{ background:var(--lv-border); border-radius:8px; }
.nicegui-tab-panel{ gap:4px; }
.lv-title{ margin:0; line-height:1.2; } .lv-sub{ margin-bottom:20px; line-height:1.5; }
.q-uploader{ background:var(--lv-surface-2) !important; color:var(--lv-text) !important; border:1px dashed var(--lv-border);
  border-radius:14px; box-shadow:none !important; max-height:150px; }
.q-uploader__header{ background:transparent !important; color:var(--lv-accent) !important; }
.q-uploader__list{ min-height:0 !important; padding:0 !important; }
.q-uploader__dnd{ outline-color:var(--lv-accent); }
.q-field--standard .q-field__control:before{ border-bottom-color:var(--lv-border); }
.q-select__dropdown-icon{ color:var(--lv-muted); }
/* ---- UX polish ---- */
@keyframes lvfade{ from{opacity:0; transform:translateY(6px)} to{opacity:1; transform:none} }
@keyframes lvpulse{ 0%{box-shadow:0 0 0 0 rgba(239,68,68,.55)} 70%{box-shadow:0 0 0 9px rgba(239,68,68,0)} 100%{box-shadow:0 0 0 0 rgba(239,68,68,0)} }
.q-tab-panel > *{ animation:lvfade .25s ease both; }
.lv-pill.live{ background:rgba(239,68,68,.14); border-color:rgba(239,68,68,.45); color:#ef4444; }
.lv-pill.live .lv-dot{ background:#ef4444; animation:lvpulse 1.6s infinite; }
.lv-action{ transition:transform .15s ease, border-color .15s ease, box-shadow .15s ease; }
.lv-action:hover{ transform:translateY(-3px); border-color:var(--lv-accent) !important; box-shadow:0 16px 36px rgba(139,92,246,.25); }
.lv-search .q-field__control{ background:var(--lv-surface-2); border-radius:12px; }
.lv-search{ margin:2px 4px 8px !important; }
.lv-cta{ flex-shrink:0; white-space:nowrap; padding:10px 18px; font-weight:700; }
.lv-hero .q-linear-progress__track{ background:rgba(255,255,255,.3) !important; opacity:1 !important; }
.lv-hero .q-linear-progress__model{ background:#fff !important; }
.lv-empty{ color:var(--lv-muted); }
:focus-visible{ outline:2px solid var(--lv-accent); outline-offset:2px; }
/* legacy tabs: old cards used a fixed light gradient via inline style; force them onto the theme */
.q-card:not(.lv-hero):not(.lv-stat){ background:var(--lv-surface) !important; border:1px solid var(--lv-border); color:var(--lv-text); }
.q-card .q-field__native,.q-card .q-field__input,.q-card .q-field__label,.q-card .q-checkbox__label,.q-card label{ color:inherit; }
.q-table tbody td{ max-width:260px; overflow:hidden; text-overflow:ellipsis; }
.q-table td,.q-table th{ padding:8px 12px; }
.q-field--float .q-field__label{ font-size:13px; }
.q-field__label{ font-size:15px; }
.q-field__native,.q-field__input{ font-size:15px; }
.q-field--standard .q-field__control{ min-height:44px; }
@media (max-width: 900px){ .q-tab-panel{ padding:16px 14px 110px !important; } .lv-title{ font-size:22px; } }
"""


def apply_theme() -> None:
    """Colours, fonts, global CSS. Call once, before building any element."""
    ui.colors(primary=ACCENT, secondary=ACCENT_2, accent="#22d3ee", positive="#22c55e", negative="#ef4444",
              warning="#f59e0b", info="#38bdf8")
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_css(CSS)


def page_title(title: str, subtitle: str = "") -> None:
    ui.label(title).classes("lv-title")
    if subtitle:
        ui.label(subtitle).classes("lv-sub")


def stat_card(label: str, icon: str = "insights", value: str = "0") -> ui.label:
    with ui.card().classes("lv-card lv-stat").props("flat"):
        with ui.element("div").classes("lv-ico"):
            ui.icon(icon)
        ui.label(label).classes("lv-stat-label")
        return ui.label(value).classes("lv-stat-value")


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket() as s:
            s.settimeout(0.4)
            return s.connect_ex((host, int(port))) == 0
    except (OSError, ValueError):
        return False


def _pill(text: str, on: bool = False, warn: bool = False):
    el = ui.element("div").classes("lv-pill" + (" on" if on else "") + (" warn" if warn else ""))
    with el:
        ui.element("span").classes("lv-dot")
        lbl = ui.label(text)
    return el, lbl


_THEME_JS = """
(function(){
  function apply(){
    if(!window.Quasar||!Quasar.Dark){return false}
    var v=null;try{v=localStorage.getItem("lvDark")}catch(e){}
    Quasar.Dark.set(v===null?true:v==="1");return true}
  // the server also sets a dark default when the page connects; keep re-applying the saved choice for a few seconds
  var n=0,t=setInterval(function(){apply();if(++n>40)clearInterval(t)},150);
  window.lvToggleDark=function(){Quasar.Dark.toggle();try{localStorage.setItem("lvDark",Quasar.Dark.isActive?"1":"0")}catch(e){}}
})();
"""


def theme_switch(dark=None):
    """Sun/moon button, always visible (also on phones). Remembers the choice in this browser; default is dark."""
    ui.add_head_html("<style>.lv-sun{display:none}.lv-moon{display:inline-flex}"
                     "body.body--dark .lv-sun{display:inline-flex}body.body--dark .lv-moon{display:none}</style>")
    ui.add_body_html("<script>" + _THEME_JS + "</script>")
    if _i18n is not None:
        ui.add_body_html(_i18n.body_html())
        with ui.button().props("flat dense no-caps id=lv-lang").classes("lv-no-i18n").tooltip("Language / Ngôn ngữ") as lb:
            ui.label("EN").classes("lv-lang-t lv-no-i18n").style("font-weight:700;font-size:12px;letter-spacing:.04em")
        lb.on("click", js_handler="() => window.lvToggleLang && window.lvToggleLang()")
    with ui.button(on_click=lambda: ui.run_javascript("window.lvToggleDark&&window.lvToggleDark()")).props("flat round dense").tooltip("Light / dark") as b:
        ui.icon("light_mode").classes("lv-sun")
        ui.icon("dark_mode").classes("lv-moon")
    return b


def build_shell(tabs, nav: List[Tuple[str, List[Tuple[str, str, object]]]], dark, status_fn: Optional[Callable[[], Dict]] = None,
                go_live: Optional[Callable[[], None]] = None, title: str = "AI Live Studio") -> Callable:
    """Header + sidebar. `tabs` is the (hidden) ui.tabs; `nav` is [(group, [(label, icon, tab), ...]), ...].
    Returns select(tab) so other code can navigate."""
    buttons: Dict[object, ui.button] = {}
    bottom: Dict[object, ui.button] = {}

    def select(tab):
        tabs.set_value(tab)
        for group in (buttons, bottom):
            for t, b in group.items():
                b.classes(add="active" if t is tab else None, remove=None if t is tab else "active")

    with ui.header(elevated=False).classes("lv-header items-center justify-between no-wrap"):
        with ui.element("div").classes("lv-brand"):
            ui.button(icon="menu", on_click=lambda: drawer.toggle()).props("flat round dense").classes("lt-md")
            with ui.element("div").classes("lv-logo"):
                ui.label("AI")
            with ui.element("div"):
                ui.label(title).classes("lv-brand-name")
                ui.label("TikTok LIVE seller").classes("lv-brand-sub")
        with ui.row().classes("items-center gt-xs").style("gap:8px"):
            pills = {
                "app": _pill("Streamer offline"),
                "bridge": _pill("Not live"),
                "voice": _pill("Voice: edge-tts"),
            }
        theme_switch(dark)

    def refresh():
        if not status_fn:
            return
        st = status_fn()
        for key, (el, lbl) in pills.items():
            info = st.get(key)
            if not info:
                continue
            text, on = info[0], info[1]
            lbl.text = text
            el.classes(add="on" if on else None, remove=None if on else "on")
            if key == "bridge":
                el.classes(add="live" if on else None, remove=None if on else "live")
    ui.timer(4.0, refresh)

    drawer = ui.left_drawer(value=None, fixed=True, bordered=False).props("width=250 breakpoint=900").classes("lv-drawer")
    groups = []  # (group label element, [(label, button)])
    with drawer:
        search = ui.input(placeholder="Search settings...").props("dense outlined clearable").classes("lv-search w-full")
        for group, items in nav:
            glabel = ui.label(group).classes("lv-group")
            members = []
            for label, icon, tab in items:
                b = ui.button(label, icon=icon, on_click=lambda t=tab: select(t)).props("flat no-caps align=left").classes("lv-nav")
                buttons[tab] = b
                members.append((label, b))
            groups.append((glabel, members))

    def apply_filter(e=None):
        q = (search.value or "").strip().lower()
        for glabel, members in groups:
            shown = 0
            for label, b in members:
                vis = (not q) or q in label.lower()
                b.set_visibility(vis)
                shown += vis
            glabel.set_visibility(shown > 0)
    search.on("update:model-value", apply_filter)

    # Phone layout: the five things a seller needs, one tap away (the drawer holds the rest).
    flat = {label: (icon, tab) for _, items in nav for label, icon, tab in items}
    with ui.footer(fixed=True, elevated=False).classes("lv-bottomnav items-center no-wrap"):
        for label in ("Home", "Setup", "Dashboard", "Products"):
            if label in flat:
                icon, tab = flat[label]
                bottom[tab] = ui.button(label, icon=icon, on_click=lambda t=tab: select(t)).props("flat stack no-caps dense").classes("lv-bn")
        ui.button("More", icon="menu", on_click=lambda: drawer.toggle()).props("flat stack no-caps dense").classes("lv-bn")

    select.by_label = {label: tab for _, items in nav for label, _, tab in items}
    return select
