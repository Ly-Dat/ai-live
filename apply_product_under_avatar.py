"""Product picture directly under Mimi's name tag (centred under her), and Mimi shrinks a little so nothing is cut off.

Put this file in the ai-live folder (next to product_tour.py) and run:  python apply_product_layout_v2.py
Works whether or not you already ran apply_product_under_avatar.py. Safe to run twice. Backups: *.bak_pp2.
Then restart the app and the tour, and press F5 on /overlay.
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def load(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        sys.exit(f"Not found: {path}\nPut this script in the ai-live folder.")
    text = open(path, "rb").read().decode("utf-8")
    return path, text, ("\r\n" if "\r\n" in text else "\n")


def swap(text, old, new, nl, rel):
    old, new = old.replace("\n", nl), new.replace("\n", nl)
    if text.count(old) != 1:
        sys.exit(f"[error] {rel}: expected text not found exactly once, nothing changed:\n{old[:110]!r}")
    return text.replace(old, new)


def save(path, text, rel):
    shutil.copyfile(path, path + ".bak_pp2")
    open(path, "wb").write(text.encode("utf-8"))
    print(f"[ok]   {rel}")


CSS_V1 = (
    "#pp{position:fixed;bottom:12px;display:none;pointer-events:none;width:22vh}\n"
    "#pp.right{right:24px}#pp.left{left:24px}#pp.center{left:50%;margin-left:-11vh}\n"
    "#pp img{width:22vh;height:22vh;object-fit:cover;display:block;border-radius:14px;background:#fff;box-shadow:0 6px 18px rgba(0,0,0,.45)}\n"
    "body.pp #av{bottom:calc(56px + 24vh)}\n"
)
CSS_V2 = (
    "/*pp2*/#pp{display:none;margin:8px auto 0;width:16vh;pointer-events:none}\n"
    "#pp img{width:16vh;height:16vh;object-fit:cover;display:block;border-radius:12px;background:#fff;box-shadow:0 6px 18px rgba(0,0,0,.45)}\n"
    "body.pp #av #avi{max-height:48vh;width:auto}\n"
)
CSS_ANCHOR = "#avb{font-size:11px;opacity:.8;font-weight:600;margin-left:8px}\n"
MK_V1 = '<div id="pp"><img id="ppi" alt=""></div><div id="av">'
MK_V1_AV = '<div id="av">'
NAME_END = '<span id="avb"></span></div><div id="avt"></div></div>'
NAME_END_V2 = '<span id="avb"></span></div><div id="pp"><img id="ppi" alt=""></div><div id="avt"></div></div>'
JS_SIDE = 'p.className=avState.side;p.style.display="block"'
JS_NOSIDE = 'p.style.display="block"'
JS_ANCHOR = "setInterval(tipTick,1000);\n"
JS_FULL = (
    'var ppU="",ppI=0,ppL=[],PT="http://127.0.0.1:8091";\n'
    'function ppHide(){document.getElementById("pp").style.display="none";document.body.classList.remove("pp")}\n'
    'function setProd(){fetch(PT+"/current").then(function(r){return r.json()}).then(function(d){var p=document.getElementById("pp"),im=document.getElementById("ppi");\n'
    ' if(!avState||!d.name||!d.images||!d.images.length){ppHide();return}\n'
    ' var k=d.name+"|"+d.images.join(",");if(k!==ppU){ppU=k;ppL=d.images;ppI=0}\n'
    ' p.style.display="block";document.body.classList.add("pp");\n'
    ' var u=PT+"/img/"+encodeURIComponent(ppL[ppI%ppL.length]);if(im.getAttribute("data-u")!==u){im.setAttribute("data-u",u);im.src=u}}).catch(ppHide)}\n'
    "setInterval(setProd,3000);setInterval(function(){ppI++},6000);setProd();\n"
)

rel = "utils/overlay_page.py"
path, t, nl = load(rel)
if "/*pp2*/" in t:
    print(f"[skip] {rel}: already v2")
else:
    if 'id="pp"' in t:      # upgrade from the first version
        t = swap(t, CSS_V1, CSS_V2, nl, rel)
        t = swap(t, MK_V1, MK_V1_AV, nl, rel)
        t = swap(t, JS_SIDE, JS_NOSIDE, nl, rel)
    else:                   # clean file
        t = swap(t, CSS_ANCHOR, CSS_ANCHOR + CSS_V2, nl, rel)
        t = swap(t, JS_ANCHOR, JS_ANCHOR + JS_FULL, nl, rel)
    t = swap(t, NAME_END, NAME_END_V2, nl, rel)
    save(path, t, rel)

rel = "product_tour.py"
path, t, nl = load(rel)
if "Access-Control-Allow-Origin" in t:
    print(f"[skip] {rel}: already patched")
else:
    t = swap(t, '            self.send_header("Cache-Control", "no-cache")\n            self.end_headers()\n',
             '            self.send_header("Cache-Control", "no-cache")\n            self.send_header("Access-Control-Allow-Origin", "*")\n            self.end_headers()\n', nl, rel)
    save(path, t, rel)

print("\nDone. Restart the app and the product tour, then press F5 on http://127.0.0.1:8081/overlay")