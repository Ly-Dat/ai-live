# Avatar studio and seller brain

## Free AI avatar
**Avatar studio** (tab) draws original anime-style sellers with a free image model and shows them on the overlay. Five sub-tabs: Characters, Draw, Stage, Journey, Control.

- **Engine (recommended):** a Stable Diffusion WebUI (AUTOMATIC1111 or Forge) on your own PC, started with `--api`, with **Animagine XL 3.1** loaded. Free, offline, no quota. Needs a GPU with about 8 GB of VRAM. The model is released under the CreativeML OpenRAIL++-M licence, which allows commercial use of its output; read the model card yourself before relying on that.
- **No GPU?** Upload your own pictures per expression, or try the "free web service" engine (Pollinations). That engine is **untested** and its terms are not verified.
- Use an original design, not an existing character or a real person.
- It is a PNGTuber-style sprite set, **not Live2D**: a Live2D rig cannot be made from one picture.

### Characters and looks
Eight ready-made original archetypes (Mimi, Kuro, Yuki, Nana, Haru, Sora, Mei, Leo) or create your own. Adding one only saves its description; you draw it in the Draw tab. Each character can have several **looks** (outfits), each with its own pictures. Switch the active character with "Use".

### 14 expressions
idle, talking, happy, surprised, confused, thinking, wink, shy, excited, sad, sleepy, laughing, love, proud. "Draw the 6 core" is enough to start; "Draw missing" fills the rest. A missing picture falls back to a close one (love -> happy -> idle), so partial sets work. Expressions are redrawn from the first picture so the face stays the same; results vary, so redraw or replace any picture by hand.

What triggers them: reply = talking; sales pitch = proud; gift = surprised, then excited, then love; compliment ("xinh", "cute") = shy; "yêu", "<3" = love; "haha", "kkk" = laughing; "buồn", "huhu" = sad; new viewer = wink; blocked comment = confused; any other comment = thinking; quiet for 3 minutes = sleepy; paused = sleepy. "Talking" flaps between the talking picture and the mood picture for a few seconds after a reply. This is timed from the event, not from the audio level, so it is an approximation of lip-sync.

### Stage
Position (right / left / centre), size, idle motion, glow frame, name tag, an optional "Lv 3 - 4-day streak" badge, and up to 6 rotating hint bubbles ("Ask me about sizes!") that invite viewers to type. Test any expression for 8 seconds from this tab. Add `/overlay` as a browser source (same link as the polls and giveaways).

### Journey
Level, streak, a daily goal (10 viewer questions answered) and 12 achievements, all computed from your real live logs. XP = 50 per live + 2 per answer + 5 per gift + 10 per hour on air. Higher levels unlock cosmetics only: glow frames (glow 2, neon 3, sakura 4, gold 6), idle motions (breathe 2, sway 3, float 5) and more outfit slots (up to 8). Nothing changes what the AI says. Achievements earned before this feature existed are not announced as new.

## Host control
**Pause AI**, **I'll take over**, **Resume AI** in the Avatar studio tab. While not live the AI answers nothing (comments, entrances, gifts) and the avatar rests; viewer questions are still logged as hand-offs. The tour and scheduled announcements follow the same "I am hosting" switch only where they already honour it.

## Seller brain
Answers from the catalog only, before the LLM is asked: compare two products ("so sánh A với B"), picks within a budget ("dưới 300k"), and price / trust / quality doubts ("đắt quá", "có thật không", "có tốt không"). It never says "genuine", "best" or "guaranteed", and says nothing when the product or the needed fields are missing (the normal LLM path then answers). Each character's catchphrases are added to about every third short product reply.

## Not done
Smart chat modes (auto-switch between explaining and entertaining), quizzes and a learning loop that changes the plan by itself are not built; Dashboard and Recap already show what worked.

## Life on stage (v3)

- **Blink**: a 15th expression, `blink` (closed eyes). While idle the avatar blinks every few seconds; if it is not drawn yet, "Draw missing" in the Draw tab makes it. Without it nothing blinks, nothing breaks.
- **Mouth and caption follow the voice**: the voice player tells the overlay what it is saying and for how long (`data/avatar/speaking.json`). The mouth runs exactly that long and a caption bubble above the avatar shows the sentence being spoken (switch it off in Stage). The length of an .mp3 is estimated from its size (edge-tts), so it can be a little off; a .wav is exact. If the voice never reports (older setup), the old 6-second guess is used.
- **Pop and sparkles** when the mood changes (love, happy, surprised ...). They are skipped when the system asks for reduced motion.
- **Same face on later draws**: the first picture is kept (`_base.png`) while the seed and settings stay the same, so "draw the missing ones" no longer changes the face.
- **Regulars** (opt-in "returning viewers" in Setup): the host can add "last time you asked about X" to the welcome-back line. Only the hashed name and a product id are stored.
