# Seller MVP audit and release gate

Audit of the seller loop against the "Next Steps" plan (12 Oct 2026). Status words: **verified** = covered by an offline test that passes; **partial** = code exists, only partly tested; **unknown** = not checked here. Nothing below has been run against a real TikTok LIVE.

Baseline: `python -m pytest tests/unit` = 306 passed, 1 failed (`test_setup_personas_sim.py::test_own_voice_is_applied_only_when_set`, an old voice-engine assertion, not related to selling). `python simulate_live.py --offline` meets all expectations.

## Feature to code map

| # | Feature | Status | Code | Tests / manual check |
|---|---|---|---|---|
| 1 | Product catalog, import, missing-fact check | verified | `utils/product_catalog.py` (`audit_products`), `import_products.py`, Products tab | `test_product_catalog`, `test_import_and_shop_api`, `test_spec_features`; pre-live check lists gaps |
| 2 | Product tour (skips `active: false`) | partial | `product_tour.py` (line ~414 filter) | `test_tour_timing`; run `python product_tour.py --once` against a running app |
| 3 | Catalog-grounded answers, honest unknowns, cheaper/compare | verified | `product_catalog.quick_answer/unknown_answer`, `seller_brain.py` | `test_product_catalog`, `test_spec_features` |
| 4 | Comment triage (spam, repeats, greetings, busy chat) | verified | `utils/triage.py`, hook in `my_handle.py` | `test_spec_features`, `test_release_gate` |
| 5 | Input + output safety, final speech gate | verified | `tiktok_safety.py`, `my_handle.prohibitions_handle`, `speech_gate.py` + hook in `audio.py` | `test_tiktok_safety`, `test_spec_features` (gate logic). The hook inside the audio thread itself is not run by a test |
| 6 | Vietnamese TTS, captions, avatar sync | partial | `audio_handle/my_tts.py`, `speaking.py`, `avatar.py`, overlay | `test_engine`, `test_avatar_seller`; 10-minute simulated session is a manual check |
| 7 | Pause / Take over | verified (logic) | `host_control.py`, `audio.py` (`_silence_watch`, `halt_speech`) | `test_release_gate::test_takeover_edge_stops_speech_once`; timed manual test still needed with real audio |
| 8 | TikTok bridge and reconnect | partial | `tiktok_bridge.py` (backoff loop ~line 255), `bridge_health.py` | `test_bridge_health`; reconnect itself is unknown without a real connection |
| 9 | Honest analytics | verified | `live_analytics.py` | `test_live_analytics`, `test_spec_features` |
| 10 | Start blocked with no active products | verified | `setup_wizard.start_blockers`, `webui_setup.py`, `webui.py` | `test_release_gate` |

## Test matrix

| Scenario | Expected | Evidence |
|---|---|---|
| Known price question | exact catalog answer, no LLM | `test_product_catalog`, simulator `quick` |
| Unknown size or shipping | "cannot confirm", nothing invented | `test_spec_features::test_missing_fact_is_not_invented`, simulator `cannot_confirm` |
| Buying signal | cart call-to-action | simulator `buy_cta` |
| Spam, repeat, link | silent, counted | `test_spec_features`, report "Comments the AI chose not to speak" |
| Off-platform contact / payment | blocked | simulator `blocked` |
| Unsafe LLM pitch | blocked before TTS | `speech_gate` + `prohibitions_handle(scope="output")` |
| AI provider timeout | fallback, no freeze | `test_engine` (`llm_guard`); streamed replies are NOT covered |
| Bridge disconnect | app stays controllable | unknown, manual |
| Human takeover | stops promptly | logic verified; time it by hand |
| No active products | Start refused with a reason | `test_release_gate` |

## Issues found and status

1. **Fixed:** a Chromium profile (`data/chrome_profile`, 1,249 files incl. a cookies database) was tracked in git. It is now untracked and ignored. It is **still in Git history**: anyone with the repo can read it. If it ever held a real login, sign out and rotate that session; to purge history use `git filter-repo --path data/chrome_profile --invert-paths` and force-push (coordinate with Dat first).
2. **Fixed:** Pause / Take over only silenced new replies; queued and playing speech continued, and tour pitches kept being spoken. Both are now stopped.
3. **Fixed:** Start went ahead with zero active products.
4. **Fixed:** `config.json` is tracked and held two sample `api_key` values copied from upstream (AnythingLLM, Dify). They are blanked. The same sample keys still sit in the `__main__` demo blocks of a few upstream provider files and in `tests/` (not used by the app). Keep your real keys in environment variables or an ignored local file, never in `config.json`.
5. **Partly fixed:** streamed replies now report success or failure to the circuit breaker, and once the breaker is open the reply goes the guarded, non-streamed way (timeout plus fallback). A stream that hangs before its first word is still not interrupted.
6. **Open (medium):** TikTok Shop Partner API sync is unverified against a real shop.
7. **Open (medium):** bridge reconnect and pinned-product events are untested without a real stream.
8. **Open (low):** the one failing voice test.
9. Licence: GPL-3.0; the upstream author asks commercial users to get in touch.

## Go / no-go before a real stream

`python go_nogo.py` runs the computer-checkable items below and lists the rest as MANUAL.

- [ ] Unit tests pass or the failure above is accepted.
- [ ] `python simulate_live.py --offline` meets all expectations.
- [ ] No keys, cookies or personal data in Git (items 1 and 4).
- [ ] Safety verified on viewer input and generated speech.
- [ ] You pressed Pause / Take over during real speech and it stopped.
- [ ] Catalog prices and facts checked by a human.
- [ ] AI disclosure and TikTok's current rules checked for your account and region.
- [ ] Integration method and account permissions confirmed (the bridge is unofficial and may stop working).
- [ ] A person watches chat during the first stream and can stop it.

## Expanded features spec (14 Oct plan): what was built and what was not

| Item | Status | Where |
|---|---|---|
| P0 Seller command center | built (header) | Pause/Resume button, "AI hosting / PAUSED / You are hosting" pill and "Now: product" pill, always visible; the button only writes `data/host_control.json`, so it works when the LLM or TTS is slow. The header also shows the speech queue length and a truthful bridge state (LIVE / connecting / down) |
| P0 Fact confidence and approval | built | `fact_status` per field; AI-drafted description/highlights/intro are saved as `draft` and are blanked for the pitch, quick answers, comparisons and LLM context until the seller presses **Confirm facts** (timestamp `facts_confirmed_at`). "Imported" vs "seller-typed" is not distinguished |
| P0 Pre-live checklist | built | Home pre-live check, `go_nogo.py`; Start now refuses without products and asks for a **logged override** (`data/start_overrides.jsonl`) when the safety filter is off or the AI-disclosure line is missing |
| P0 Resilient speech queue | partial | identical queued lines are dropped (`utils/speech_queue.py`); Pause cuts queued and playing speech. Not done: cancelling stale pitches, TTS-failure recovery beyond the existing engine fallback. Note: tour pitches use priority 30 and comment replies 20 in `filter.priority_mapping`; the tour already waits for quiet chat, but the numbers are worth a look |
| P1 Graceful degraded mode | partial | when the AI gives no answer to a shopping question, the host says a true catalog template (name, price, where to look); TTS-down and text/manual mode are not built |
| P1 Review inbox | exists | Teach tab (questions the host was unsure about; the answer you type is spoken next time) |
| P1 Comparison with unknowns | exists | compare/cheaper only use known fields; unknown is never inferred |
| P1 Intent / FAQ insights | exists | report "What viewers wanted" and "Product interest" |
| P1 Conversation memory | built | `utils/convo.py`: a short follow-up with no product name ("còn size nhỏ hơn không?") resolves to the product just discussed, else the tour's current product; memory-only, 150 s, no viewer names, never overrides a comment that names a product |
| P1 Adaptive pitch scheduler, multilingual policy | not built | would need design and real chat data |
| P2 Accessibility | built (overlay) | Avatar studio > Stage: caption size (normal / large / extra large), high-contrast caption, reduce motion; saved with the stage settings, no effect on safety |
| P2 (gestures, product card overlay sync, campaign playbooks, replay timeline) | not built | `data/speaking.json` and the overlay already follow the active product only loosely |

## Added: stale-line cancellation and TTS recovery
`utils/voice_health.py` (`is_stale`, `record`, `level`, `backup_type`); hooks in `audio.py` (`message_queue_thread`, `only_play_audio`, `_tts_recover`); header pill in `webui.studio_status`. Tests: `tests/unit/test_voice_health.py`. Not verified with real audio.

## Added: pacing, languages, gestures, product card, playbooks, replay
Tests: `tests/unit/test_live_extras.py`. Not verified on a real stream. Known limits: voice stays Vietnamese for English answers; the "lean" gesture needs a logged `pitch` event (comment-triggered spotlights), tour sentences do not log one; the Now-showing card needs a recent voice line (`speaking.json`, 90 s); adaptive pacing reads the analytics log of the newest session.
