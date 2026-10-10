"""Áp dụng bản sửa Story studio vào repo ai-live.

Cách dùng (chạy từ thư mục gốc repo, hoặc truyền đường dẫn repo):
    python apply_story_fix.py
    python apply_story_fix.py C:\\path\\to\\ai-live

Làm 2 việc:
 1. Sửa lỗi  'str' object has no attribute 'get'   (utils/story_llm.py, hàm _cfg)
 2. Thêm mode "Tell it as a full story" + ô tick "Send the pictures to the AI"
Mỗi file được sao lưu thành *.bak_storyfix trước khi sửa. Chạy lại lần 2 sẽ bỏ qua phần đã áp dụng.
"""
import os
import shutil
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

EDITS = {}

# ---------------------------------------------------------------- utils/story_llm.py
EDITS["utils/story_llm.py"] = [
    # 1) bug fix: Config.get(*keys) đi theo key lồng nhau -> chỉ truyền 1 key
    ('''def _cfg(config, key, default=None):
    try:
        v = config.get(key, default) if hasattr(config, "get") else default
    except TypeError:
        v = config.get(key)
    return default if v is None else v
''', '''def _cfg(config, key, default=None):
    # config may be a plain dict or utils.config.Config, whose get(*keys) walks nested keys:
    # get("chat_type", "chatgpt") would call .get on the string "chatgpt". Always pass ONE key.
    try:
        v = config.get(key)
    except Exception:
        v = None
    return default if v is None else v
'''),
    # 2) gửi ảnh cho model vision
    ('''def chat(config, prompt: str, model: str = "", system: str = "", temperature: float = 0.9, max_tokens: int = 4096,
         timeout: float = 600.0) -> str:''', '''def chat(config, prompt: str, model: str = "", system: str = "", temperature: float = 0.9, max_tokens: int = 4096,
         timeout: float = 600.0, images: Optional[List[str]] = None) -> str:'''),
    ('''    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]''',
     '''    # images: data URLs; sent as OpenAI-style image_url parts (needs a vision model: qwen2.5vl, llava, gemma3, gpt-4o ...)
    content = ([{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": u}} for u in images]) if images else prompt
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]'''),
    ('''    if ctype == "chatgpt" or app_llm is None:
        return lambda prompt: chat(config, prompt, model, system, temperature)
    return lambda prompt: clean_reply(app_llm(prompt))''', '''    if ctype == "chatgpt" or app_llm is None:
        return lambda prompt, images=None: chat(config, prompt, model, system, temperature, images=images)
    return lambda prompt, images=None: clean_reply(app_llm(prompt))   # the running app's /llm is text-only'''),
    ('''progress_note: Optional[Callable[[str], None]] = None) -> Callable[[str], str]:''',
     '''progress_note: Optional[Callable[[str], None]] = None) -> Callable[..., str]:'''),
]

# ---------------------------------------------------------------- utils/story_tools.py
EDITS["utils/story_tools.py"] = [
    ('''def recap_prompt(texts: List[str], title: str = "", lang: str = "vi", style: str = "dramatic",
                 max_chars: int = 220, mode: str = "faithful", start: int = 1, context: str = "", glossary: str = "") -> str:''',
     '''def panel_data_url(path: str, max_side: int = 896) -> str:
    """A panel picture as a small JPEG data URL, to send to a vision model."""
    import base64
    import io
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def recap_prompt(texts: List[str], title: str = "", lang: str = "vi", style: str = "dramatic",
                 max_chars: int = 220, mode: str = "faithful", start: int = 1, context: str = "", glossary: str = "",
                 has_images: bool = False) -> str:'''),
    ('''    if mode == "recap":
        return (''', '''    if mode == "expand":
        seen = (f"The {len(texts)} picture(s) are attached in the same order (first picture = Panel {start}); look at them. "
                if has_images else "You cannot see the pictures, only the text. ")
        return (
            f"You are a narrator for story-recap videos{name}.\\n"
            f"Below is the text OCR found in each picture panel. {seen}{src_line}Write ONE narration per panel in {language}, "
            f"style: {style}, like a storyteller who keeps the viewer hooked.\\n\\n"
            "Rules:\\n"
            "1. Start from what the panel says (translate it), then enrich it with what the picture shows: place, mood, action, "
            "expressions, danger. Only what is really visible or implied. 2-4 flowing sentences, up to "
            f"{max_chars} characters per panel, spoken language (it will be read aloud).\\n"
            "2. Keep the story order. The first real story panel is a hook; the last panel ends on a cliffhanger. "
            "Continue smoothly from the previous panel, never repeat it.\\n"
            "3. Credits, staff names, publisher / platform names, logos and title cards are NOT story: write exactly `-`.\\n"
            "4. A panel marked (no text): " + ("narrate what the picture shows, in 1-2 sentences.\\n" if has_images else "write exactly `-`.\\n") +
            "5. Never invent character names, powers or events that neither the text nor the picture supports.\\n"
            "6. The OCR has mistakes (missing spaces, wrong letters): fix them silently from context.\\n"
            "7. No explanations, titles, notes or markdown outside the format.\\n\\n" + fmt + tail)
    if mode == "recap":
        return ('''),
    ('''                    cancel: Optional[Callable[[], bool]] = None) -> Tuple[List[str], List[int]]:
    """The AI writes''', '''                    cancel: Optional[Callable[[], bool]] = None,
                    images_for: Optional[Callable[[List[int]], List[str]]] = None) -> Tuple[List[str], List[int]]:
    """The AI writes'''),
    ('''    n = len(texts)
    out: List[str] = [""] * n
    missing: List[int] = []
    credits =''', '''    n = len(texts)
    if images_for:
        batch = min(batch, 3)       # pictures are heavy for a local vision model: few panels per request
    out: List[str] = [""] * n
    missing: List[int] = []
    credits ='''),
    ('''                                  glossary=glossary)
            reply = parse_numbered(llm_fn(prompt))''', '''                                  glossary=glossary, has_images=bool(images_for))
            reply = parse_numbered(llm_fn(prompt, images_for(want)) if images_for else llm_fn(prompt))'''),
    # 4) mode "expand": panel ghi công vẫn gửi cho AI (AI tự quyết đọc lại hoặc ghi `-`), và `-` không bị tính là thiếu panel
    ('''    credits = {i for i, t in enumerate(texts) if looks_like_credits(t)}      # title cards / staff pages stay silent, no AI call''',
     '''    # title cards / staff pages stay silent (no AI call), except in "expand" mode where the AI decides (it may answer `-`)
    credits = set() if mode == "expand" else {i for i, t in enumerate(texts) if looks_like_credits(t)}'''),
    ('''                elif key in reply and mode == "faithful":''', '''                elif key in reply and mode in ("faithful", "expand"):'''),
]

# ---------------------------------------------------------------- utils/webui_story.py
EDITS["utils/webui_story.py"] = [
    ('''    def ask_exact(prompt: str) -> str:   # translating / polishing: stay close to the text
        return make_fn(0.3)(prompt)''', '''    def ask_exact(prompt: str, images=None) -> str:   # translating / polishing: stay close to the text
        return make_fn(0.3)(prompt, images)

    def ask_expand(prompt: str, images=None) -> str:  # expanding the story: a bit more freedom
        return make_fn(0.7)(prompt, images)'''),
    ('''"recap": "Recap in my own words (shorter)"},''', '''"recap": "Recap in my own words (shorter)",
                                "expand": "Tell it as a full story (longer, adds what the pictures show)"},'''),
    ('''label="Style (recap only)").classes("w-48")''', '''label="Style (recap / full story)").classes("w-48")
            o_vision = ui.checkbox("Send the pictures to the AI (needs a vision model, e.g. qwen2.5vl / llava / gpt-4o)", value=False)'''),
    ('''                    outs, missing = await run.io_bound(
                        story_tools.write_narration, texts, ask_exact, meta["title"], o_lang.value, o_style.value, o_mode.value,
                        o_names.value or "", 8, 220, lambda a, b, m: ocr_prog.update(a=a, b=b, msg=m))''',
     '''                    expand = o_mode.value == "expand"
                    imgs = ((lambda idx: [story_tools.panel_data_url(story.image_path(meta, j)) for j in idx])
                            if (expand and o_vision.value) else None)
                    outs, missing = await run.io_bound(
                        lambda: story_tools.write_narration(
                            texts, ask_expand if expand else ask_exact, meta["title"], o_lang.value, o_style.value, o_mode.value,
                            o_names.value or "", 8, 450 if expand else 220, lambda a, b, m: ocr_prog.update(a=a, b=b, msg=m),
                            images_for=imgs))'''),
]


# ---------------------------------------------------------------- prompt tiếng Việt
# Hai prompt nằm trong hằng số của utils/story_tools.py (có thể sửa thẳng ở đó):
#   VI_FAITHFUL = mode "Read what the panels say" (dịch sát chữ)      VI_EXPAND = mode "Tell it as a full story" (kể dài, nhìn ảnh)
# Token: {name} tên truyện, {p1}{p2}{p3} số panel, {seen} {style} {max_chars} (chỉ VI_EXPAND).
# Sửa VI_PROMPT / VI_EXPAND_PROMPT bên dưới rồi chạy lại script cũng được - script sẽ thay bản cũ trong story_tools.py.
VI_PROMPT = r'''Bạn là dịch giả chuyên dịch truyện tranh Trung Quốc sang tiếng Việt cho video kể chuyện{name}. Tôi sẽ cung cấp văn bản OCR của từng panel. Bạn không nhìn thấy hình ảnh, vì vậy chỉ được sử dụng nội dung OCR được cung cấp.

1. QUY TẮC ÁNH XẠ PANEL — ƯU TIÊN CAO NHẤT

* Mỗi nhãn `Panel N:` trong đầu vào tương ứng chính xác với một panel đầu ra có cùng số N.
* Tuyệt đối không tự chia, gộp, đổi số thứ tự hoặc chuyển nội dung giữa các panel.
* Một panel đầu vào phải tạo ra đúng một dòng đầu ra, kể cả khi panel đó chứa nhiều dòng OCR, nhiều ngôn ngữ hoặc nhiều câu.
* Phải xử lý từng panel độc lập. Không chuyển câu từ panel này sang panel khác để tạo thành câu chuyện liền mạch.
* Không được bỏ qua văn bản tiếng Anh chỉ vì nó nằm sau văn bản tiếng Trung hoặc có vẻ là lời dẫn mở đầu.
* Trước khi trả lời, hãy kiểm tra rằng số lượng panel đầu ra bằng số lượng panel đầu vào.

2. QUY TẮC DỊCH

* Dịch chính xác toàn bộ nội dung có ý nghĩa trong mỗi panel, giữ nguyên thứ tự xuất hiện.
* Dùng tiếng Việt tự nhiên, dễ đọc thành tiếng, nhưng không thêm, bớt hoặc suy diễn nội dung.
* Dịch cả tiếng Trung lẫn tiếng Anh.
* Sửa lỗi OCR hiển nhiên, chẳng hạn thiếu khoảng trắng giữa các từ tiếng Anh.
* Giữ tên riêng và thuật ngữ nhất quán.
* Không tự tạo lời dẫn, tình tiết, bối cảnh hoặc câu nối.

3. QUY TẮC XỬ LÝ NỘI DUNG ĐẶC BIỆT
A. Tiêu đề truyện
Nếu panel chứa tiêu đề chính của truyện, hãy dịch tiêu đề và giữ nguyên ở đúng panel đó. Nếu tiêu đề bị ngắt giữa hai panel liên tiếp, dịch phần chữ xuất hiện ở từng panel; không tự chuyển toàn bộ tiêu đề sang một panel.
B. Thông tin bản quyền và ghi công
Nếu panel chỉ chứa logo, watermark, tên nền tảng, tên tác giả, danh sách nhân sự sản xuất, thông tin chuyển thể hoặc bản quyền, hãy ghi chính xác `-`.
Nếu một panel chứa cả nội dung truyện và thông tin ghi công, chỉ dịch nội dung truyện, bỏ phần ghi công.
C. Panel không có chữ
Nếu OCR ghi `(no text)` hoặc chỉ chứa tiếng động, ký tự vô nghĩa, hãy ghi chính xác `-`.
Không được tự suy luận nội dung từ hình ảnh tưởng tượng, thể loại truyện hoặc các panel xung quanh.
D. Panel có nhiều ngôn ngữ
Nếu panel có câu tiếng Trung và câu tiếng Anh, hãy xử lý toàn bộ văn bản trong chính panel đó. Không được bỏ câu tiếng Anh chỉ vì đã dịch câu tiếng Trung ở một panel khác.
4. ĐỊNH DẠNG ĐẦU RA
Chỉ xuất kết quả theo định dạng:
Panel {p1}: ...
Panel {p2}: ...
Panel {p3}: ...
Tiếp tục cho đến panel cuối cùng. Mỗi panel chỉ có một dòng. Không thêm tiêu đề, giải thích, nhận xét hoặc bất kỳ nội dung nào ngoài kết quả dịch.
5. TỰ KIỂM TRA TRƯỚC KHI TRẢ LỜI
Thực hiện kiểm tra nội bộ, không hiển thị phần kiểm tra:

1. Số panel đầu ra có khớp hoàn toàn với số panel đầu vào không?
2. Nội dung của từng panel có được giữ đúng số thứ tự không?
3. Có bỏ sót câu tiếng Anh hoặc tiếng Trung nào không?
4. Có chuyển nội dung giữa các panel không?
5. Có bịa thêm lời dẫn cho panel `(no text)` không?
6. Có ghi `-` cho panel chỉ chứa thông tin bản quyền hoặc ghi công không?

Nếu phát hiện lỗi, hãy sửa trước khi xuất kết quả cuối cùng.'''

VI_EXPAND_PROMPT = r'''Bạn là người dẫn truyện cho video kể chuyện tranh{name}. Dưới đây là chữ OCR của từng panel. {seen}Hãy viết MỘT đoạn lời dẫn tiếng Việt cho mỗi panel, giọng kể cuốn hút, tự nhiên, dễ đọc thành tiếng (voice-over). Phong cách: {style}.

QUY TẮC

1. Mỗi panel đúng một dòng `Panel N:`, đúng số thứ tự, không gộp, không bỏ sót panel nào. Panel nào cũng phải có lời dẫn để đọc; chỉ ghi `-` cho panel chỉ có logo hoặc danh sách nhân sự sản xuất (chủ bút, trợ lý, họa sĩ, biên tập...).
2. Panel có chữ: dịch đầy đủ ý nghĩa (cả tiếng Trung lẫn tiếng Anh, sửa lỗi OCR hiển nhiên), giữ đúng ai nói gì, rồi làm phong phú thêm bằng những gì ảnh cho thấy: bối cảnh, hành động, biểu cảm, cảm giác nguy hiểm.
3. Câu bị ngắt giữa hai panel liên tiếp (ví dụ tiêu đề bị cắt đôi): ghép thành câu trọn vẹn khi đọc. Panel đầu kết thúc bằng "…", panel sau mở đầu bằng "…".
4. Thông tin giới thiệu, bản quyền, nền tảng, tác giả, nhà xuất bản: đọc lại ngắn gọn, tự nhiên trong một đến hai câu, không liệt kê khô khan.
5. Panel không có chữ: nếu nhìn thấy ảnh thì kể 2-3 câu về điều đang diễn ra trong ảnh (bối cảnh, hành động, cảm xúc, nguy hiểm) và nối tiếp mạch của panel trước, không lặp lại. Nếu không nhìn thấy ảnh thì viết 1-2 câu nối mạch dựa trên các panel xung quanh, không thêm sự kiện mới.
6. Mỗi panel 2-3 câu, tối đa {max_chars} ký tự. Panel đầu tiên của truyện là lời mở đầu thu hút người xem; panel cuối cùng kết bằng một câu gợi sự tò mò.
7. Không bịa tên nhân vật, sức mạnh, địa danh hay sự kiện mà chữ và ảnh không cho thấy. Giữ tên riêng và thuật ngữ nhất quán.
8. Không thêm tiêu đề, giải thích, nhận xét hay Markdown. Chỉ xuất kết quả theo định dạng:

Panel {p1}: ...
Panel {p2}: ...
Panel {p3}: ...
(tiếp tục cho đến panel cuối cùng, mỗi panel một dòng)'''

CONSTS = [("VI_FAITHFUL", VI_PROMPT), ("VI_EXPAND", VI_EXPAND_PROMPT)]

VI_BRANCH = r'''    if lang == "vi":
        return (VI_FAITHFUL.replace("{name}", name).replace("{p1}", str(start)).replace("{p2}", str(start + 1))
                .replace("{p3}", str(start + 2)) + "\n\n" + tail)
'''
EN_ANCHOR = '    return (\n        f"You are a translator for story videos{name}.'
OLD_BRANCH_HEAD = '    if lang == "vi":\n        return (\n            f"Bạn là dịch giả chuyên dịch'

VI_EXPAND_BRANCH = r'''    if mode == "expand" and lang == "vi":
        seen = (f"{len(texts)} ảnh của các panel được đính kèm theo đúng thứ tự (ảnh đầu tiên là Panel {start}); hãy nhìn ảnh. "
                if has_images else "Bạn không nhìn thấy ảnh, chỉ có chữ OCR. ")
        style_vi = {"dramatic": "kịch tính", "funny": "hài hước", "sweet": "ngọt ngào", "scary": "rùng rợn", "mysterious": "bí ẩn"}
        return (VI_EXPAND.replace("{name}", name).replace("{seen}", seen).replace("{style}", style_vi.get(style, style))
                .replace("{max_chars}", str(max_chars)).replace("{p1}", str(start)).replace("{p2}", str(start + 1))
                .replace("{p3}", str(start + 2)) + "\n\n" + tail)
'''
EXPAND_ANCHOR = '    if mode == "expand":\n        seen = ('

PATCH_UNITS = len(CONSTS) + 2   # số "đoạn" patch_vi quản lý (để báo cáo)


def _const_block(name, prompt):
    return "# <<%s_BEGIN>>\n%s = \"\"\"%s\"\"\"\n# <<%s_END>>\n\n\n" % (name, name, prompt, name)


def patch_vi(text):
    """Trả về (text mới, số đoạn đã đổi). Chạy lại nhiều lần vẫn an toàn; tự nâng cấp bản prompt cũ."""
    changed = 0
    # a) các hằng số prompt
    for name, prompt in CONSTS:
        block, begin, end = _const_block(name, prompt), "# <<%s_BEGIN>>" % name, "# <<%s_END>>" % name
        if begin in text:
            i, j = text.index(begin), text.index(end) + len(end) + 3          # + "\n\n\n"
            if text[i:j] != block:
                text = text[:i] + block + text[j:]
                changed += 1
        else:
            k = text.index("def panel_data_url")
            text = text[:k] + block + text[k:]
            changed += 1
    # b) nhánh tiếng Việt của mode "faithful"
    if VI_BRANCH not in text:
        if OLD_BRANCH_HEAD in text:               # bản prompt cũ nhúng thẳng trong hàm -> thay bằng nhánh mới
            i = text.index(OLD_BRANCH_HEAD)
            j = text.index("+ tail)\n", i) + len("+ tail)\n")
            text = text[:i] + VI_BRANCH + text[j:]
        elif EN_ANCHOR in text:
            text = text.replace(EN_ANCHOR, VI_BRANCH + EN_ANCHOR, 1)
        else:
            sys.exit("Không tìm thấy chỗ chèn nhánh tiếng Việt (faithful) trong utils/story_tools.py")
        changed += 1
    # c) nhánh tiếng Việt của mode "expand"
    if VI_EXPAND_BRANCH not in text:
        if EXPAND_ANCHOR not in text:
            sys.exit("Không tìm thấy chỗ chèn nhánh tiếng Việt (expand) trong utils/story_tools.py")
        text = text.replace(EXPAND_ANCHOR, VI_EXPAND_BRANCH + EXPAND_ANCHOR, 1)
        changed += 1
    return text, changed


def main():
    paths = {rel: os.path.join(ROOT, *rel.split("/")) for rel in EDITS}
    missing = [p for p in paths.values() if not os.path.isfile(p)]
    if missing:
        sys.exit("Không thấy file: %s\nChạy script từ thư mục gốc repo ai-live, hoặc truyền đường dẫn repo." % ", ".join(missing))

    # đọc + tính toán tất cả trước, chỉ ghi khi mọi thứ khớp (tránh sửa dở)
    results = {}
    for rel, edits in EDITS.items():
        with open(paths[rel], encoding="utf-8", newline="") as f:
            raw = f.read()
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        applied = skipped = 0
        for old, new in edits:
            if new in text:          # kiểm tra "đã có sẵn" trước (đoạn gốc có thể nằm trong đoạn mới)
                skipped += 1
            elif old in text:
                text = text.replace(old, new, 1)
                applied += 1
            else:
                sys.exit("Không áp dụng được một đoạn trong %s (file đã bị sửa khác bản gốc?):\n---\n%s\n---" % (rel, old[:200]))
        if rel == "utils/story_tools.py":
            text, n = patch_vi(text)
            applied += n
            skipped += PATCH_UNITS - n
        results[rel] = (text.replace("\n", "\r\n") if crlf else text, applied, skipped)

    for rel, (text, applied, skipped) in results.items():
        if applied:
            shutil.copy2(paths[rel], paths[rel] + ".bak_storyfix")
            with open(paths[rel], "w", encoding="utf-8", newline="") as f:
                f.write(text)
        print("%-24s đã sửa %d đoạn, bỏ qua %d đoạn (đã có sẵn)" % (rel, applied, skipped))
    print("Xong. Restart webui rồi thử lại.")


if __name__ == "__main__":
    main()