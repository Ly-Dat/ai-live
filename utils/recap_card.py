"""
Shareable recap card: one PNG a seller can post after a live. Real numbers only, no viewer names.

  card_stats(summary, names, shop, streak)  -> dict of what the card shows (pure, unit tested)
  render_card(stats, out_path)              -> writes a 1080x1350 PNG (Pillow)
"""
import datetime
import os
from typing import Dict, Optional

W, H = 1080, 1350
_FONTS = [
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]


def card_stats(s: Dict, names: Optional[Dict[str, str]] = None, shop: str = "", streak: int = 0,
               today: Optional[datetime.date] = None) -> Dict:
    names = names or {}
    interest = s.get("product_interest") or {}
    top = None
    if interest:
        pid = max(interest, key=lambda k: sum(interest[k].values()))
        top = {"name": names.get(pid, pid), "questions": sum(interest[pid].values())}
    return {
        "shop": (shop or "My live").strip(),
        "date": (today or datetime.date.today()).strftime("%d %b %Y"),
        "minutes": round(float(s.get("duration_min") or 0)),
        "comments": int(s.get("comments") or 0),
        "viewers": int(s.get("unique_viewers") or 0),
        "buying": int(s.get("buy_intent") or 0),
        "answered": int(s.get("answered") or 0),
        "top": top,
        "streak": int(streak or 0),
    }


def _font(size: int, bold: bool = False):
    from PIL import ImageFont
    for regular, strong in _FONTS:
        path = strong if bold else regular
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _fit(draw, text: str, font_fn, size: int, max_w: int, bold: bool = False):
    while size > 20:
        f = font_fn(size, bold)
        if draw.textlength(text, font=f) <= max_w:
            return f, text
        size -= 4
    f = font_fn(20, bold)
    while text and draw.textlength(text + "...", font=f) > max_w:
        text = text[:-1]
    return f, text + "..."


def render_card(st: Dict, out_path: str) -> str:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H))
    px = img.load()
    c1, c2 = (124, 92, 255), (236, 72, 153)  # violet -> pink, same as the app theme
    for y in range(H):
        for x in range(0, W):
            t = (x / W * 0.45 + y / H * 0.55)
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    d = ImageDraw.Draw(img, "RGBA")
    white, soft = (255, 255, 255, 255), (255, 255, 255, 200)

    f, shop = _fit(d, st["shop"], _font, 64, W - 160, True)
    d.text((80, 90), shop, font=f, fill=white)
    d.text((80, 175), f"Live recap  ·  {st['date']}", font=_font(36), fill=soft)

    d.rounded_rectangle((60, 270, W - 60, 900), radius=48, fill=(0, 0, 0, 70))
    tiles = [("comments", "Comments"), ("viewers", "Viewers"), ("buying", "Buying signals"), ("minutes", "Minutes live")]
    for i, (key, label) in enumerate(tiles):
        cx, cy = 100 + (i % 2) * 450, 320 + (i // 2) * 290
        d.text((cx, cy), str(st[key]), font=_font(150, True), fill=white)
        d.text((cx, cy + 175), label, font=_font(38), fill=soft)

    y = 960
    if st.get("top"):
        d.text((80, y), "Most asked about", font=_font(34), fill=soft)
        f, name = _fit(d, st["top"]["name"], _font, 52, W - 160, True)
        d.text((80, y + 48), name, font=f, fill=white)
        d.text((80, y + 118), f"{st['top']['questions']} viewer questions", font=_font(34), fill=soft)
        y += 190
    if st.get("streak", 0) >= 2:
        label = f"{st['streak']}-day live streak"
        wlab = d.textlength(label, font=_font(38, True))
        d.rounded_rectangle((80, y + 10, 80 + wlab + 56, y + 80), radius=35, fill=(255, 255, 255, 60))
        d.text((108, y + 22), label, font=_font(38, True), fill=white)

    d.text((80, H - 110), "Hosted by an AI streamer  ·  AI Live Studio", font=_font(32), fill=soft)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    img.save(out_path, "PNG")
    return out_path
