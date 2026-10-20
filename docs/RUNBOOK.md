# Live-day runbook

A short checklist for the person pressing the buttons. Everything below is a button or file that already exists in the app.

## Before you go live (10 minutes)

1. `python go_nogo.py` (or the **Pre-live check** card on Home). Fix every FAIL; a MANUAL line means "look at it yourself".
2. **Products tab**: every product has its price, shipping and return line. AI-drafted facts stay blank on air until you press **Confirm facts**.
3. **Live tools > Campaign playbook**: pick steady / launch / flash hour / warm-up, press **Apply**.
4. **Avatar studio**: preview the overlay at `http://127.0.0.1:8081/overlay`. Old pictures with a solid background: press **Clean backgrounds**, then Ctrl+F5 on the overlay.
5. Start the app, press **Start**, then go LIVE on TikTok. Header pills should read: *Streamer online*, *LIVE*, *AI hosting*, a voice, an AI speed, *Now: product*.

## During the live

| You want to | Do this |
|---|---|
| Stop the AI right now (speech queued or playing included) | **Pause AI** in the header. Press again to resume. |
| Talk yourself | **Avatar studio > I'll take over**; the AI stays silent until you press the AI-hosting button there. |
| Run a sale, giveaway or poll | **Live tools** tab. Only the text you typed is spoken, through the safety filter. |
| See if the host is falling behind | **Queue: n** pill. Old lines are dropped on their own (entrance 20 s, comment 45 s, pitch 120 s). |
| Teach an answer | **Teach** tab: the questions the host was unsure about. |

## What the header pills mean

- **Voice: backup (Edge)**: the main voice failed and lines are being spoken with the free Edge voice. **Voice DOWN**: failed twice in a row on every voice; check the TTS server.
- **Bridge down / LIVE (no chat?) / Bridge connecting**: the TikTok bridge is not delivering comments. Restart it from Setup.
- **AI x.x s slow**: the model answers slowly. Set a fallback provider and timeout in the **AI engine** tab.
- **PAUSED / You are hosting**: the AI is silent on purpose.

## After the live

- **Dashboard**: numbers and the "do this next live" tips. Only counts the app really logged.
- **Live tools > Replay timeline > Load last live**: busiest minute and quiet stretches.
- `python report_session.py` writes the Markdown report.

## When something is wrong

| Symptom | Likely cause and fix |
|---|---|
| Overlay is blank | Wrong address, or the web panel is not running. Open `/overlay`, press Ctrl+F5. |
| Avatar has a box or pale halo | Press **Clean backgrounds** in Avatar studio. |
| Host never answers a product question | The fact is missing or still a draft. Add it and **Confirm facts**; unknowns are answered with "I'll check", never invented. |
| English comment got a Vietnamese answer | Playbook "Slow chat warm-up" turns English answers off; or the switch under the playbook is off. |
| Nothing is spoken but the avatar moves | Host is PAUSED / taken over, or audio output device is wrong. |

Limits you should know: the voice is Vietnamese even for English answers; TikTok never tells us who bought; nothing here has been checked on a real stream by the author, so run one private test live first.
