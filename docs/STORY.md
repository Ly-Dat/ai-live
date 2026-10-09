# Story studio

A tab for stories told with pictures, the way manhua / webtoon channels do it: plot -> panels -> narration -> live or video.

## The flow
1. **Write the plot** - pick genre / tone / idea; the app builds a prompt. Paste it into any free chat AI, paste the answer back, and the narration plus a list of pictures to make are filled in. (Nothing is sent anywhere by the app.)
2. **Add the pictures** - upload PNG / JPG / WEBP (or one .zip), in name order. One paragraph of narration per panel, or `Panel 3: ...`.
3. **Check the narration** - edit text, reorder, delete panels. The licence of the story is set here.
4. **Read it on my live** - `story_reader.py` shows one panel at a time on the overlay (`/overlay`, add it as a browser source) and the AI host narrates it through the same `/send` "reread" path as the Novel reader. Viewer comments always go first. Pause / stop / loop / sleep timer, TikTok policy filter on every line.
5. **Make a video** - 9:16, 1080x1920: picture + AI voice (edge-tts, free) + burned-in captions, hook at the start, "follow for part N+1" at the end, optional licensed background music from the Live tools music list. Also writes `.srt`, a cover picture and a caption with hashtags (and the credit lines). Works from a picture story or from a chapter of a Novel-reader story (text on a gradient). Output: `out/stories/`.

### Tools for picture stories (`utils/story_tools.py`)
- **Auto-crop** (step 2 switch): a long vertical strip is cut at the empty gaps between panels; strips with no gap are cut by height only.
- **Read the text + AI recap** (step 3b): OCR of every panel (`pip install rapidocr-onnxruntime`, or Tesseract), a ready prompt for any free chat AI, and the answer is put into the narration boxes for you to edit in step 3.

Needs `ffmpeg` (or `pip install imageio-ffmpeg`), Pillow and edge-tts; the tab says what is missing.

## Licence rule (important)
Pictures and text must be yours (drawn, written, or made by you with a free AI tool), public domain, CC0 / CC BY (credit is added automatically), or used with written permission. Panels taken from a manhua / webtoon / novel site are copyrighted: choose "Copyrighted" and the live reader and the video export refuse to run. There is intentionally no "fetch from a site" feature.

## Files
`utils/story.py` logic, `utils/story_video.py` video builder, `story_reader.py` live reader, `utils/webui_story.py` tab, `data/stories/<id>/` library, `data/story_state.json` / `data/story_status.json` control + status.

## Tall webtoon strips
Upload one long vertical strip and leave "Cut it into panels automatically" on: the strip is cut at the empty bands between panels (tiny pieces are merged, pieces with no gap are cut at their calmest row). Check the result in step 3 and fix the narration per panel.

## Recap / review videos ("review truyện") and YouTube

Story studio now covers the whole recap-channel workflow, free and offline except the voice (edge-tts):

1. **Script** - step 1 has a *Recap / review video* helper: write your own notes, get a prompt for any free chat AI (hook, story beats, *your take*, cliffhanger), paste the answer back and it becomes one scene per panel. Step 2 shows a live check: words, spoken length, long sentences, missing "follow" line.
2. **Pictures** - as before (your own, public domain, CC, permission). The licence gate still refuses copyrighted panels.
3. **Video** - step 5: *Shape* vertical 9:16 or wide 16:9, *Picture movement* (still / slow zoom / zoom + pan), fade between pictures, and *cut into parts of N minutes* (parts end on "to be continued - part N+1", the last one uses your ending line).
4. **Upload kit** - TikTok caption + hashtags, YouTube title ideas, description with **chapters** (0:00 first, 3+ chapters, 10 s+ each), tags and a pinned comment, plus a checklist (original commentary, licence, licensed music, honest AI disclosure). *Make a YouTube thumbnail* gives a 1280x720 jpg.

Zoom / pan moves only the picture; the captions stay still. A 3-minute movement video renders in a few minutes on a normal PC (ffmpeg, veryfast preset); choose *Still pictures* for the fastest export.
