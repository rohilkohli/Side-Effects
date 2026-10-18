/* SIDE EFFECTS assistant: a Gemini agent on every page. It shows each tool it calls, live, then answers.
   On the leaflet page app.js hands it the open leaflet, so it doubles as the pharmacist. */
(() => {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  // Light formatting for Gemini's answers: **bold**, bullet lines and paragraphs. Everything is escaped first.
  const fmt = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").split(/\n{2,}/).map((block) => {
    const lines = block.split("\n");
    return lines.every((l) => /^\s*[-*•]\s+/.test(l))
      ? `<ul>${lines.map((l) => `<li>${l.replace(/^\s*[-*•]\s+/, "")}</li>`).join("")}</ul>`
      : `<p>${lines.join("<br>")}</p>`;
  }).join("");
  const ICON = { check_lender: "📊", lender_news: "📰", compare_lenders: "⚖️", find_alternatives: "🔀", gate_check: "🛡️", open_page: "🔗", safety_alerts: "🚨",
    get_side_effects: "💊", search_contract: "📄", complaint_examples: "🗣️", compare_with: "⚖️" };
  const PAGE = { leaflet: "Open the leaflet", agent_demo: "Watch the agent demo", scam_arena: "Open the scam arena", safety_alerts: "See the safety alerts", evidence: "See the evidence", business: "For business" };
  const GENERAL = ["Is Apple Card risky for a freelancer?", "Any news about Klarna?", "Compare Capital One and Chase", "What is deferred interest?"];

  const fab = document.createElement("button");
  fab.type = "button"; fab.className = "sa-fab"; fab.setAttribute("aria-label", "Ask the SIDE EFFECTS assistant");
  fab.innerHTML = `<span class="sa-spark" aria-hidden="true">✦</span><span class="sa-fab-t">Ask anything</span>`;
  const panel = document.createElement("aside");
  panel.className = "sa"; panel.hidden = true; panel.setAttribute("aria-label", "SIDE EFFECTS assistant");
  panel.innerHTML = `
    <header><div><strong id="saTitle">Assistant</strong><small id="saSub">Gemini with live complaint data and Google Search</small></div>
      <div class="sa-hd"><button type="button" class="sa-voice" title="Switch to Voice Mode (live STT → agent → TTS)">🎙 Voice Mode</button>
      <button type="button" class="sa-x" aria-label="Close">×</button></div></header>
    <div class="sa-chat" aria-live="polite"><div class="sa-hello"><span class="sa-spark big" aria-hidden="true">✦</span>
      <p><b>Ask about any card, loan or pay-later plan.</b><br>I look things up live: complaints sent to the regulator, the side effects we track, and today's news. You'll see every lookup as it happens.</p></div></div>
    <div class="sa-suggest"></div>
    <form class="sa-form"><button type="button" class="sa-mic" aria-label="Ask by voice" title="Ask by voice">🎤</button>
      <input class="sa-in" placeholder="Ask about a lender, a fee, a term…" autocomplete="off" maxlength="1000" aria-label="Your question">
      <button class="sa-send" type="submit" aria-label="Send">↑</button></form>`;
  document.body.append(fab, panel);
  const $ = (s) => panel.querySelector(s);
  const chat = $(".sa-chat"), input = $(".sa-in");

  let history = [], leafletId = null, leaflet = null, busy = false, spoke = false;
  const suggest = (list) => { $(".sa-suggest").innerHTML = list.map((q) => `<button type="button">${esc(q)}</button>`).join(""); };
  suggest(GENERAL);

  const open = () => { panel.hidden = false; fab.hidden = true; document.body.classList.add("sa-open"); setTimeout(() => input.focus(), 50); };
  const close = () => { panel.hidden = true; fab.hidden = false; document.body.classList.remove("sa-open"); };
  fab.addEventListener("click", open);
  $(".sa-x").addEventListener("click", close);
  $(".sa-voice").addEventListener("click", () => { close(); window.SEVoice?.open(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) close(); });
  $(".sa-suggest").addEventListener("click", (e) => { if (e.target.tagName === "BUTTON") ask(e.target.textContent); });
  $(".sa-form").addEventListener("submit", (e) => { e.preventDefault(); const q = input.value.trim(); if (q) ask(q); });

  function add(cls, html) {
    const d = document.createElement("div"); d.className = cls; d.innerHTML = html;
    chat.appendChild(d); chat.scrollTop = chat.scrollHeight; return d;
  }

  async function ask(q, viaVoice = false) {
    if (busy) return;
    busy = true; input.value = ""; $(".sa-send").disabled = true;
    $(".sa-hello")?.remove();
    add("sa-msg user", esc(q));
    const turn = add("sa-msg model", `<ol class="sa-steps"></ol><div class="sa-ans"><span class="sa-dots"><i></i><i></i><i></i></span></div>`);
    const steps = turn.querySelector(".sa-steps"), ans = turn.querySelector(".sa-ans");
    const pending = [];
    let answer = "";
    try {
      const resp = await fetch("/api/assistant", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, history, leaflet_id: leafletId }) });
      if (!resp.ok) throw new Error();
      const reader = resp.body.getReader(), dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await reader.read(); if (done) break;
        buf += dec.decode(value, { stream: true }); let i;
        while ((i = buf.indexOf("\n")) >= 0) {
          const ev = JSON.parse(buf.slice(0, i)); buf = buf.slice(i + 1);
          if (ev.type === "tool") {
            const li = document.createElement("li"); li.className = "run";
            li.innerHTML = `<span class="sa-ic">${ICON[ev.name] || "•"}</span><span>${esc(ev.label)}<small></small></span><span class="sa-st"><i></i></span>`;
            steps.appendChild(li); pending.push([ev.name, li]); chat.scrollTop = chat.scrollHeight;
          } else if (ev.type === "tool_done") {
            const k = pending.findIndex(([n]) => n === ev.name); if (k < 0) continue;
            const li = pending.splice(k, 1)[0][1];
            li.className = "done"; li.querySelector("small").textContent = ev.summary ? " · " + ev.summary : "";
            li.querySelector(".sa-st").textContent = "✓";
          } else if (ev.type === "link") {
            const label = PAGE[ev.page] || "Open";
            turn.insertAdjacentHTML("beforeend", `<a class="sa-link" href="${esc(ev.url)}">${esc(label)}${ev.lender ? " for " + esc(ev.lender) : ""} ›</a>`);
          } else if (ev.type === "say") {
            answer = ev.text; ans.innerHTML = fmt(ev.text);
          } else if (ev.type === "error") {
            ans.innerHTML = `<p class="sa-err">${esc(ev.text || ev.detail || "Something went wrong.")}</p>`;
          }
        }
      }
      if (!answer && !ans.querySelector(".sa-err")) ans.innerHTML = `<p class="sa-err">No answer came back. Please try again.</p>`;
    } catch {
      ans.innerHTML = `<p class="sa-err">I can't reach the assistant right now. Please try again in a moment.</p>`;
    } finally {
      pending.forEach(([, li]) => { li.className = "done"; li.querySelector(".sa-st").textContent = "–"; });
      busy = false; $(".sa-send").disabled = false; chat.scrollTop = chat.scrollHeight;
    }
    if (answer) {
      history.push({ role: "user", text: q }, { role: "model", text: answer });
      if ((viaVoice || spoke) && "speechSynthesis" in window) speechSynthesis.speak(new SpeechSynthesisUtterance(answer.replace(/\*\*/g, "")));
    }
  }

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) $(".sa-mic").hidden = true;
  $(".sa-mic").addEventListener("click", () => {
    const rec = new SR(); rec.lang = navigator.language || "en-US"; rec.interimResults = false;
    $(".sa-mic").classList.add("on");
    rec.onresult = (e) => { spoke = true; ask(e.results[0][0].transcript, true); };
    rec.onend = () => $(".sa-mic").classList.remove("on");
    rec.start();
  });

  window.SEAssist = {
    open, ask: (q) => { open(); ask(q); },
    get leafletId() { return leafletId; },
    get leaflet() { return leaflet; },
    /* The leaflet page calls this when a leaflet opens (or with null when it closes). */
    setLeaflet(lf, questions) {
      leafletId = lf ? lf.id : null; leaflet = lf || null; history = [];
      chat.innerHTML = "";
      $("#saTitle").textContent = lf ? "Pharmacist" : "Assistant";
      $("#saSub").textContent = lf ? `Knows this leaflet${lf.contract_pages ? ", its contract" : ""} and live complaint data` : "Gemini with live complaint data and Google Search";
      fab.querySelector(".sa-fab-t").textContent = lf ? "Ask the pharmacist" : "Ask anything";
      suggest(lf && questions?.length ? questions : GENERAL);
    },
  };
})();
