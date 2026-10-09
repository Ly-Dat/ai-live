# Novel reader (AI reads a story on your live)

Tab **Novel reader**: add a story (paste, .txt or .epub), pick voices, press **Start**. The AI host reads it chapter after chapter,
steps aside when viewers comment, and carries on a few seconds after answering.

What it has (the usual features of novel-reading apps such as @Voice Aloud, Voice Dream or Speechify):

| Feature | Here |
|---|---|
| Library, chapters, resume where you stopped | yes (`data/novels/`, progress in `data/novel_progress.json`) |
| Import | paste, .txt, .md, .epub (no DRM) |
| Narrator + dialogue voices | yes: quotes ("..." “...” «...») and Vietnamese dash dialogue (— ...) use the second voice |
| Speed, pause between lines | yes (speed works with Edge voices) |
| Pronunciation dictionary | yes, `data/novel_pronunciations.json` |
| Stop after N minutes (sleep timer) | yes |
| Text on screen, line by line | yes, on the overlay (`/overlay`) |
| Chapter title announcements, auto-next | yes |
| Viewer comments first | yes (it pauses like the product tour) |

What it adds for a TikTok live: every line goes through the TikTok policy filter, and **a story must carry a licence you are allowed to
read on a live** (public domain, your own, CC0 / CC BY, or written permission). Copyrighted stories without permission are blocked.
Free sources: Project Gutenberg, Wikisource, your own writing.

Do not run it together with the product tour (both would speak).

## Characters, search and bookmarks
- **Characters - a voice for each:** "Find characters in this story" lists names that appear next to a speech verb ("Lan nói", "said Mark") at least twice. Give each a voice (or press "Give each a different voice"). A line of dialogue is read by the character it is tagged with: `Lan nói: “...”`, `“...” Lan nói.`, `— ... — Lan nói.`. Untagged dialogue uses the dialogue voice.
- **Search and bookmarks:** search the story text and start reading from any hit; bookmark the current place (with a note) and jump back later. Bookmarks are in `data/novel_bookmarks.json`.
- **Time:** the story card shows about how long the whole story takes to listen; the reader shows the time left in the chapter.

## Audiobook, recap, atmosphere, on-screen style
- **Audiobook tab:** pick a chapter range and press "Make the audiobook". The chapters are read with your narrator / dialogue / character voices (free edge-tts, needs internet) and saved as one MP3 in `out/stories/`, with a chapter timestamp list to paste into the post description. Needs ffmpeg (or `pip install imageio-ffmpeg`).
- **Recap:** with "Recap" on (Options), a session that starts at chapter 2 or later first reads the last two sentences of the previous chapter ("Ở chương trước: ..." / "Previously: ...").
- **Background music:** a switch in Options turns on the licensed tracks from Live tools while you read.
- **On-screen text:** small / medium / large and dark / light / sepia for the overlay card.

## Viewers steer the story (opt-in)
Options -> "Viewers steer the story".
- **Commands:** when "Different viewers needed" (default 3) different viewers comment the same command within 30 seconds, the reader obeys: `!tiep` next chapter (next panel in the Story studio), `!lai` read the last lines again, `!truoc` go back. One troll cannot skip the story. The commands are shown on the overlay and the host says one short line when it obeys.
- **End-of-chapter vote:** the host asks "comment 1 for the next chapter, 2 to hear it again", waits the vote time, says the result and acts on it. One vote per viewer; a tie or no votes means next chapter.
- Command and vote comments are counted silently (no AI reply to them), and only while a reader is running with this switched on. Files: `utils/reader_cmds.py`, `data/reader_cmds.json`.

## AI reading companion (Companion tab)

Features borrowed from the popular web-novel sites and AI reading apps, all built only from the chapters read so far (no spoilers):

- **Ask the story**: type a question in the Companion tab, or let viewers comment `!hoi <question>` / `!ask <question>` while the reader runs (Options -> "Viewers can ask"). The host answers aloud from the text up to the current line. One question per viewer every 45 s, at most 3 waiting, 4-140 characters; questions and answers go through the TikTok filter.
- **Previously on ...**: an AI recap of the last 3 chapters (Options -> "AI recap"; falls back to the plain recap if the AI is down). Chapter summaries are cached in `data/novel_summaries.json`.
- **Character cards**: role, traits and relations of the recurring characters, from the text read so far.
- **Reading stats**: listening minutes today / this week / total, chapters finished, day streak (`data/novel_stats.json`).

The AI is the OpenAI-compatible one from Settings (Ollama, LM Studio, OpenAI): no Start Run needed for the AI itself, but viewer questions need the app running (Start Run) because the answer is spoken through it. A 7B+ model is recommended.
