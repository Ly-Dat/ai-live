# Story studio

A tab for stories told with pictures, the way manhua / webtoon channels do it: plot -> panels -> narration -> live or video.

## The flow
1. **Write the plot** - pick genre / tone / idea; the app builds a prompt. Paste it into any free chat AI, paste the answer back, and the narration plus a list of pictures to make are filled in. (Nothing is sent anywhere by the app.)
2. **Add the pictures** - upload PNG / JPG / WEBP (or one .zip), in name order. One paragraph of narration per panel, or `Panel 3: ...`.
3. **Check the narration** - edit text, reorder, delete panels. The licence of the story is set here.
4. **Read it on my live** - `story_reader.py` shows one panel at a time on the overlay (`/overlay`, add it as a browser source) and the AI host narrates it through the same `/send` "reread" path as the Novel reader. Viewer comments always go first. Pause / stop / loop / sleep timer, TikTok policy filter on every line.
5. **Make a video** - 9:16, 1080x1920: picture + AI voice (edge-tts, free) + burned-in captions, hook at the start, "follow for part N+1" at the end, optional licensed background music from the Live tools music list. Also writes `.srt`, a cover picture and a caption with hashtags (and the credit lines). Works from a picture story or from a chapter of a Novel-reader story (text on a gradient). Output: `out/stories/`.

Needs `ffmpeg` (or `pip install imageio-ffmpeg`), Pillow and edge-tts; the tab says what is missing.

## Licence rule (important)
Pictures and text must be yours (drawn, written, or made by you with a free AI tool), public domain, CC0 / CC BY (credit is added automatically), or used with written permission. Panels taken from a manhua / webtoon / novel site are copyrighted: choose "Copyrighted" and the live reader and the video export refuse to run. There is intentionally no "fetch from a site" feature.

## Files
`utils/story.py` logic, `utils/story_video.py` video builder, `story_reader.py` live reader, `utils/webui_story.py` tab, `data/stories/<id>/` library, `data/story_state.json` / `data/story_status.json` control + status.

## Tall webtoon strips
Upload one long vertical strip and leave "Cut it into panels automatically" on: the strip is cut at the empty bands between panels (tiny pieces are merged, pieces with no gap are cut at their calmest row). Check the result in step 3 and fix the narration per panel.
