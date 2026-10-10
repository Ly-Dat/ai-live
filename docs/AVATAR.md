# Avatar studio and seller brain

## Free AI avatar
**Avatar studio** (tab) draws an original anime-style seller with a free image model and shows it on the overlay.

- **Engine (recommended):** a Stable Diffusion WebUI (AUTOMATIC1111 or Forge) on your own PC, started with `--api`, with **Animagine XL 3.1** loaded. Free, offline, no quota. Needs a GPU with about 8 GB of VRAM. The model is released under the CreativeML OpenRAIL++-M licence, which allows commercial use of its output; read the model card yourself before relying on that.
- **No GPU?** Upload your own pictures per expression in the same tab, or try the "free web service" engine (Pollinations). That engine is **untested** and its terms are not verified.
- Describe the character (hair, eyes, outfit). Use an original design, not an existing character or a real person.
- Six expressions are drawn: idle, talking, happy, surprised, confused, thinking. The first picture is drawn with text-to-image; the others are image-to-image from it so the face stays recognisable. A flat white background is cut out automatically.
- It is a PNGTuber-style sprite pack, **not Live2D**: a Live2D rig cannot be made from one picture.

On stream the avatar changes with what happens (gift = surprised then happy, question = thinking, blocked comment = confused, reply = talking). "Talking" flaps between the talking picture and the mood picture for a few seconds after a reply. This is timed from the event, not from the audio level, so it is an approximation of lip-sync.

Add `/overlay` as a browser source (same link as the polls and giveaways).

## Host control
**Pause AI**, **I'll take over**, **Resume AI** in the Avatar studio tab. While not live the AI answers nothing (comments, entrances, gifts) and the avatar rests; viewer questions are still logged as hand-offs. The tour and scheduled announcements follow the same "I am hosting" switch only where they already honour it.

## Seller brain
Answers from the catalog only, before the LLM is asked: compare two products ("so sánh A với B"), picks within a budget ("dưới 300k"), and price / trust / quality doubts ("đắt quá", "có thật không", "có tốt không"). It never says "genuine", "best" or "guaranteed", and says nothing when the product or the needed fields are missing (the normal LLM path then answers). Catchphrases from the Avatar studio are added to about every third short product reply.

## Not done
Smart chat modes (auto-switch between explaining and entertaining), quizzes and a learning loop that changes the plan by itself are not built; Dashboard and Recap already show what worked.
