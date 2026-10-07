# ai-live - AI 2D streamer for TikTok LIVE shopping

A fork of [Luna AI / AI-Vtuber](https://github.com/Ikaros-521/AI-Vtuber), translated to English and adapted into an
automatic TikTok LIVE seller:

- Introduces **every product in the cart**, one after another, in a loop (`product_tour.py`).
- **Replies to viewer comments** with an LLM, grounded in your product catalog.
- **TikTok-safe**: every viewer comment and every sentence the AI is about to say passes a Vietnamese-aware policy
  filter (`utils/tiktok_safety.py`) - off-platform contacts/payments, profanity, scams, medical/absolute claims, and so on.
- **Quick answers**: simple price/size/colour/shipping/returns/usage/FAQ questions are answered straight from the catalog (no LLM, nothing invented); anything else goes to the LLM with product context.
- **Vietnamese locale pack**: `python apply_locale.py data/locale_vi.json` switches every spoken template and trigger word in `config.json` to Vietnamese (code and UI stay English).
- Tour extras: AI disclosure line, follow/ask/cart reminders between products, `"active": false` to skip sold-out items.
- Speaks Vietnamese (edge-tts `vi-VN-HoaiMyNeural`) and drives a Live2D avatar; the codebase and UI are English.

## Architecture

```
TikTok LIVE --> tiktok_bridge.py (TikTokLive 7.x, own venv) --POST /send--> main.py :8082
                                                                              |
product_tour.py --POST /send (type=reread)---------------------------------->|
                                                                              v
                    My_handle: filters (badwords + TikTok safety) -> LLM (+ product context) -> TTS -> Live2D
```

## Quick start

1. Install the main app: `pip install -r requirements.txt` (Python 3.10+), then `python main.py` (web UI: http://127.0.0.1:7000).
2. In the web UI choose your LLM (`chat_type`), TTS (edge-tts, voice `vi-VN-HoaiMyNeural`) and Live2D output.
3. Edit **`data/products.json`** with the items in your cart (same order as the cart; fill `order`, `price`, `highlights`, `faq`).
4. Start the TikTok bridge in its own venv: `python tiktok_bridge.py YOUR_TIKTOK_USERNAME --joins --gifts`
5. Start the product tour: `python product_tour.py` (flags: `--gap`, `--pause`, `--rounds`, `--once`, `--cps`).

## Getting the cart into the catalog

TikTok does **not** push the whole shopping cart over the live websocket - only the product currently pinned/popped up
(title, price, image, id) and the total product count. So there are two ways to fill `data/products.json`:

1. **Pin products during the live (automatic).** `tiktok_bridge.py` forwards each pinned product to the app
   (`type: "product"`). The app matches it to your catalog (by TikTok id, then by title) or adds it as
   `"auto_imported": true`, logs `Live cart reports N products, catalog has M`, and - with `products.pitch_on_pop` -
   immediately pitches it. Details you wrote by hand are never overwritten. Settings: `products.auto_add`,
   `products.pitch_on_pop`, `products.pitch_on_pop_cooldown` (seconds).
2. **Import a spreadsheet (before the live).** Export your products from Seller Center (or use your own sheet) and run
   `python import_products.py export.xlsx` (CSV works too; `.xlsx` needs `pip install openpyxl`). English and Vietnamese
   headers are recognised; existing entries are updated, new ones appended; `--dry-run` previews.

Auto-imported products only have a name and price, so add `highlights`, `faq`, etc. by hand for better pitches.
Run the bridge with `--debug-cart cart.jsonl` once in a real live to capture the raw shopping events: TikTok's
`OecLiveShoppingMessageV2` may carry more product detail, and that file shows what is available.
A seller-side route to the full cart would be the TikTok Shop Partner API (requires an approved app); not implemented.

## Configuration

- `config.json -> products`: enable/disable catalog grounding, paths, the text placed before product facts in the LLM prompt.
- `config.json -> filter -> tiktok_safety`: enable the policy filter and set `terms_path`.
- `config.json -> before_prompt`: the host persona and compliance rules sent to the LLM (Vietnamese replies, no contacts, no claims).
- `data/tiktok_policy_terms.json`: the banned-term categories. `scope` is `input` (viewer comments), `output` (AI speech) or `both`;
  `action` is `drop` or `mask`. Categories marked `accent_sensitive` keep Vietnamese tone marks to avoid false positives
  (e.g. "deo" vs "dao"). Review this list regularly - TikTok's enforcement is not public and changes.
- `data/pitch_templates.json`: spoken Vietnamese templates for product pitches.

## Compliance notes

- The AI should be disclosed as AI-generated content according to TikTok's current LIVE rules.
- Pitches are built only from catalog fields; keep them honest and free of medical/absolute claims.
- Never put phone numbers, Zalo/Facebook, links or bank details in the catalog; the filter will drop them anyway.
- License: GPL-3.0 (see `LICENSE`). The upstream project also asks commercial users to contact the author; check this before selling.

## Tests

`python -m py_compile` over the sources, and see `tests/` for per-backend API experiments inherited from upstream.
