// ==UserScript==
// @name         ai-live chat relay (fallback)
// @namespace    ai-live
// @version      0.1
// @description  Fallback when the TikTokLive library breaks: reads chat from the TikTok LIVE page open in YOUR browser and forwards it to ai-live on this computer.
// @match        https://www.tiktok.com/@*/live*
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// ==/UserScript==

// HOW TO USE: install Tampermonkey, add this script, open your own live page (tiktok.com/@you/live) and keep the tab open.
// It only reads what the page already shows you and posts it to http://127.0.0.1:<port>/send (your own PC).
//
// HONEST NOTE: TikTok's page markup changes without notice and these selectors have NOT been verified against the
// current page. If nothing is forwarded, open DevTools on a chat line, find its attribute (data-e2e=...) and edit SELECTORS.
// Last resort: use "Ask the host" in Live tools to type questions by hand.

(function () {
  "use strict";
  const API = "http://127.0.0.1:8082/send";   // change the port if you changed api_port in config.json
  const SELECTORS = {
    message: '[data-e2e="chat-message"]',
    name: '[data-e2e="message-owner-name"]',
  };
  const MIN_LEN = 3, MAX_PER_10S = 6;
  const sent = [];
  const seen = new WeakSet();

  function allowed() {
    const now = Date.now();
    while (sent.length && now - sent[0] > 10000) sent.shift();
    if (MAX_PER_10S && sent.length >= MAX_PER_10S) return false;
    sent.push(now);
    return true;
  }

  function post(username, content) {
    GM_xmlhttpRequest({
      method: "POST", url: API, headers: { "Content-Type": "application/json" },
      data: JSON.stringify({ type: "comment", data: { platform: "tiktok", username: username, content: content } }),
    });
  }

  function handle(node) {
    if (!node || seen.has(node)) return;
    seen.add(node);
    const nameEl = node.querySelector(SELECTORS.name);
    const username = (nameEl ? nameEl.innerText : "viewer").trim();
    let text = (node.innerText || "").trim();
    if (nameEl) text = text.replace(nameEl.innerText, "").replace(/^[\s:：]+/, "").trim();
    text = text.replace(/\[[A-Za-z_]+\]/g, "").trim();            // emote codes
    if (text.length < MIN_LEN || !/[\p{L}\p{N}]/u.test(text) || !allowed()) return;
    post(username, text);
  }

  new MutationObserver((muts) => {
    for (const m of muts) for (const n of m.addedNodes) {
      if (n.nodeType !== 1) continue;
      if (n.matches && n.matches(SELECTORS.message)) handle(n);
      else if (n.querySelectorAll) n.querySelectorAll(SELECTORS.message).forEach(handle);
    }
  }).observe(document.body, { childList: true, subtree: true });
  // Existing lines at load time are ignored on purpose (they are old chat).
})();
