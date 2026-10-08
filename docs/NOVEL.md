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
