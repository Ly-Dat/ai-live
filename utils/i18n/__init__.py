"""English / Vietnamese switch for the web UI.

The UI is written in English.  Vietnamese is applied in the browser: a small
script swaps known strings for the ones in ``vi.json`` and keeps doing it as
the page changes.  English is the source of truth, so anything that has no
translation simply stays in English (the page can be mixed in places).

Pieces:
  * ``vi.json``  - {"exact": {english: vietnamese}, "re": [[pattern, template]]}
  * ``mount()``  - serves the folder at /lv_i18n (once)
  * ``body_html()`` - the script; the button itself lives in webui_theme
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "/lv_i18n"
_mounted = False


def mount():
    """Serve vi.json at /lv_i18n/vi.json.  Safe to call more than once."""
    global _mounted
    if _mounted:
        return True
    try:
        from nicegui import app
        app.add_static_files(URL, HERE)
        _mounted = True
    except Exception:
        return False
    return True


def version():
    try:
        return str(int(os.path.getmtime(os.path.join(HERE, "vi.json"))))
    except Exception:
        return "0"


_JS = r"""
(function () {
  if (window.lvLangReady) return;
  window.lvLangReady = true;
  var KEY = 'lvLang', DICT = null, LOADING = false;
  var ATTRS = ['placeholder', 'title', 'aria-label'];
  var orig = new WeakMap();          // text node -> original English
  var applied = new WeakMap();       // text node -> text we wrote
  var origAttr = new WeakMap();      // element -> {attr: original}
  var RX = [];
  var lang = 'en';
  try { lang = localStorage.getItem(KEY) === 'vi' ? 'vi' : 'en'; } catch (e) {}

  function tr(s) {
    if (!DICT) return null;
    var t = s.trim();
    if (!t) return null;
    var v = DICT.exact[t];
    if (v === undefined) {
      for (var i = 0; i < RX.length; i++) {
        var m = RX[i][0].exec(t);
        if (m) { v = RX[i][1].replace(/\$(\d+)/g, function (_, n) { return m[+n] === undefined ? '' : m[+n]; }); break; }
      }
    }
    if (v === undefined) return null;
    var lead = s.match(/^\s*/)[0], tail = s.match(/\s*$/)[0];
    return lead + v + tail;
  }

  function skipEl(el) {
    for (var e = el; e && e.nodeType === 1; e = e.parentNode) {
      var n = e.nodeName;
      if (n === 'SCRIPT' || n === 'STYLE' || n === 'TEXTAREA' || n === 'CODE' || n === 'PRE') return true;
      if (e.classList && e.classList.contains('lv-no-i18n')) return true;
      if (e.isContentEditable) return true;
    }
    return false;
  }

  function doText(node) {
    var cur = node.nodeValue;
    if (applied.has(node) && applied.get(node) === cur) return;     // our own write
    if (lang !== 'vi') { return; }
    if (skipEl(node.parentNode)) return;
    var out = tr(cur);
    orig.set(node, cur);
    if (out !== null && out !== cur) { applied.set(node, out); node.nodeValue = out; }
    else applied.delete(node);
  }

  function doAttrs(el) {
    if (lang !== 'vi' || skipEl(el)) return;
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i];
      if (!el.hasAttribute || !el.hasAttribute(a)) continue;
      var cur = el.getAttribute(a), rec = origAttr.get(el) || {};
      if (rec[a] && rec[a].out === cur) continue;
      var out = tr(cur);
      if (out !== null && out !== cur) {
        rec[a] = { en: cur, out: out }; origAttr.set(el, rec); el.setAttribute(a, out);
      }
    }
  }

  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { doText(root); return; }
    if (root.nodeType !== 1) return;
    doAttrs(root);
    var w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, null);
    var n;
    while ((n = w.nextNode())) { if (n.nodeType === 3) doText(n); else doAttrs(n); }
  }

  function restore() {
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, null), n;
    while ((n = w.nextNode())) {
      if (n.nodeType === 3) {
        if (orig.has(n) && applied.get(n) === n.nodeValue) n.nodeValue = orig.get(n);
        orig.delete(n); applied.delete(n);
      } else {
        var rec = origAttr.get(n);
        if (rec) {
          for (var a in rec) if (n.getAttribute(a) === rec[a].out) n.setAttribute(a, rec[a].en);
          origAttr.delete(n);
        }
      }
    }
  }

  var busy = false;
  var mo = new MutationObserver(function (muts) {
    if (lang !== 'vi' || !DICT || busy) return;
    busy = true;
    try {
      muts.forEach(function (m) {
        if (m.type === 'characterData') doText(m.target);
        else if (m.type === 'attributes') doAttrs(m.target);
        else m.addedNodes.forEach(walk);
      });
    } finally { busy = false; }
  });
  function observe() {
    mo.observe(document.body, { childList: true, subtree: true, characterData: true,
                                attributes: true, attributeFilter: ATTRS });
  }

  function label() {
    var b = document.getElementById('lv-lang');
    if (!b) return;
    var t = b.querySelector('.lv-lang-t');
    if (t) t.textContent = lang === 'vi' ? 'VI' : 'EN';
    b.setAttribute('data-lang', lang);
    document.documentElement.setAttribute('lang', lang);
  }

  function load(cb) {
    if (DICT) return cb();
    if (LOADING) return;
    LOADING = true;
    fetch('__URL__/vi.json?v=__VER__').then(function (r) { return r.json(); }).then(function (d) {
      DICT = d;
      RX = (d.re || []).map(function (p) {
        try { return [new RegExp(p[0], 's'), p[1]]; } catch (e) { return null; }
      }).filter(Boolean);
      LOADING = false; cb();
    }).catch(function () { LOADING = false; lang = 'en'; label(); });
  }

  function apply() {
    if (lang === 'vi') load(function () { walk(document.body); label(); });
    else { busy = true; restore(); busy = false; label(); }
  }

  window.lvSetLang = function (l) {
    lang = l === 'vi' ? 'vi' : 'en';
    try { localStorage.setItem(KEY, lang); } catch (e) {}
    apply();
  };
  window.lvToggleLang = function () { window.lvSetLang(lang === 'vi' ? 'en' : 'vi'); };
  window.lvLang = function () { return lang; };

  function start() { observe(); label(); if (lang === 'vi') apply(); }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
  // the button is created after the script: label it once the page has settled
  setTimeout(label, 300); setTimeout(label, 1500);
})();
"""


def body_html():
    js = _JS.replace("__URL__", URL).replace("__VER__", version())
    return "<script>" + js + "</script>"
