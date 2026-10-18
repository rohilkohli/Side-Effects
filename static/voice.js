/* Voice agent: tap the mic, ask out loud, hear the answer.
   Speech-to-text uses the browser's Web Speech API when it has one; otherwise MediaRecorder records a clip
   and Gemini transcribes it on the server. The answer comes from POST /api/v1/voice (the same Gemini
   assistant and tools) and is read aloud with speechSynthesis. */
(() => {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/^\s*[-*]\s+/gm, "• ").replace(/\n+/g, "<br>");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const canRecord = !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
  const canSpeak = "speechSynthesis" in window;
  const MIC = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5"/></svg>';
  const SUGGEST = ["Is Klarna risky if my income is irregular?", "What's wrong with Apple Card?", "Is a Synchrony store card safe if I carry a balance?"];

  document.addEventListener("DOMContentLoaded", () => {
    const fab = document.createElement("button");
    fab.type = "button"; fab.className = "vx-fab"; fab.setAttribute("aria-label", "Open the voice agent");
    fab.innerHTML = `${MIC}<span class="vx-fab-t">Voice</span>`;
    const box = document.createElement("div");
    box.className = "vx"; box.hidden = true; box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true"); box.setAttribute("aria-labelledby", "vxTitle");
    box.innerHTML = `<div class="vx-card">
      <header><div><b id="vxTitle">Ask SIDE EFFECTS Voice Agent</b><small>Powered by Gemini on Vertex AI · live complaint data</small></div>
        <button type="button" class="vx-x" aria-label="Close">&times;</button></header>
      <div class="vx-log" aria-live="polite"></div>
      <div class="vx-stage" data-s="idle">
        <div class="vx-wave" aria-hidden="true">${"<i></i>".repeat(7)}</div>
        <p class="vx-state">Tap the mic and ask about any lender, card or pay-later plan</p>
        <p class="vx-interim"></p>
      </div>
      <div class="vx-sugg">${SUGGEST.map((q) => `<button type="button">${esc(q)}</button>`).join("")}</div>
      <form class="vx-bar"><input type="text" maxlength="500" placeholder="Or type your question" aria-label="Your question">
        <button type="button" class="vx-mic" aria-label="Start speaking">${MIC}</button></form>
    </div>`;
    document.body.append(fab, box);
    const $ = (s) => box.querySelector(s);
    const stage = $(".vx-stage"), log = $(".vx-log"), input = $(".vx-bar input");
    let srBroken = false;  // the browser has speech recognition but its service fails (offline, Brave): record instead
    let history = [], state = "idle", rec = null, recorder = null, stream = null, timer = null, ctl = null;

    const STATES = { idle: "Tap the mic and ask about any lender, card or pay-later plan", listening: "Listening…",
      thinking: "Checking the complaint data…", speaking: "Speaking…" };
    const setState = (s, label) => {
      state = s; stage.dataset.s = s; $(".vx-state").textContent = label || STATES[s];
      $(".vx-mic").classList.toggle("on", s === "listening");
      $(".vx-mic").setAttribute("aria-label", s === "listening" ? "Stop and send" : s === "speaking" ? "Stop speaking" : "Start speaking");
      fab.classList.toggle("live", s !== "idle");
    };
    const add = (cls, html) => { const d = document.createElement("div"); d.className = "vx-msg " + cls; d.innerHTML = html; log.appendChild(d); log.scrollTop = log.scrollHeight; return d; };

    const open = () => { box.hidden = false; document.body.classList.add("vx-open"); setTimeout(() => $(".vx-mic").focus(), 50); };
    const close = () => { stopAll(); box.hidden = true; document.body.classList.remove("vx-open"); fab.focus(); };
    fab.addEventListener("click", open);
    $(".vx-x").addEventListener("click", close);
    box.addEventListener("click", (e) => { if (e.target === box) close(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !box.hidden) close(); });

    function stopAll() {
      try { rec?.abort(); } catch { /* already stopped */ }
      if (recorder?.state === "recording") { recorder.onstop = null; recorder.stop(); }
      stream?.getTracks().forEach((t) => t.stop()); stream = null; recorder = null; rec = null;
      clearTimeout(timer); ctl?.abort(); ctl = null;
      if (canSpeak) speechSynthesis.cancel();
      $(".vx-interim").textContent = ""; setState("idle");
    }

    // ---- Speech to text ----
    function listen() {
      if (canSpeak) speechSynthesis.cancel();
      if (SR && !srBroken) {
        rec = new SR(); rec.lang = navigator.language || "en-US"; rec.interimResults = true; rec.continuous = false;
        let final = "";
        rec.onresult = (e) => {
          let interim = "";
          for (const r of e.results) (r.isFinal ? (final = r[0].transcript) : (interim += r[0].transcript));
          $(".vx-interim").textContent = final || interim;
        };
        rec.onerror = (e) => {
          if (["network", "service-not-allowed", "language-not-supported", "audio-capture"].includes(e.error) && canRecord) {
            srBroken = true; rec.onend = null; rec = null; return listen();
          }
          if (e.error !== "aborted") setState("idle", e.error === "not-allowed" ? "Microphone blocked. Allow it in the address bar, or type below." : "I didn't catch that. Tap the mic to try again."); };
        rec.onend = () => { rec = null; const q = final.trim(); $(".vx-interim").textContent = ""; if (q) ask({ text: q }); else if (state === "listening") setState("idle", "I didn't catch that. Tap the mic to try again."); };
        setState("listening"); rec.start();
      } else if (canRecord) {
        navigator.mediaDevices.getUserMedia({ audio: true }).then((s) => {
          stream = s; const chunks = [];
          recorder = new MediaRecorder(s);
          recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
          recorder.onstop = () => {
            stream?.getTracks().forEach((t) => t.stop()); stream = null;
            const blob = new Blob(chunks, { type: (recorder?.mimeType || "audio/webm").split(";")[0] }); recorder = null;
            if (blob.size) ask({ audio: blob }); else setState("idle");
          };
          recorder.start(); setState("listening", "Listening… tap again to send");
          timer = setTimeout(() => recorder?.state === "recording" && recorder.stop(), 15000);
        }).catch(() => setState("idle", "Microphone blocked. Allow it in the address bar, or type below."));
      } else setState("idle", "This browser can't use the microphone. Type your question below.");
    }
    $(".vx-mic").addEventListener("click", () => {
      if (state === "listening") { if (rec) rec.stop(); else if (recorder?.state === "recording") { clearTimeout(timer); recorder.stop(); } }
      else if (state === "speaking") { speechSynthesis.cancel(); setState("idle"); }
      else if (state === "idle") listen();
    });
    $(".vx-bar").addEventListener("submit", (e) => { e.preventDefault(); const q = input.value.trim(); if (q && state !== "thinking") { input.value = ""; ask({ text: q }); } });
    $(".vx-sugg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b && state !== "thinking") ask({ text: b.textContent }); });

    // ---- Ask the agent ----
    async function ask({ text, audio }) {
      $(".vx-sugg").hidden = true;
      setState("thinking", audio ? "Gemini is listening to your clip…" : STATES.thinking);
      const me = add("user", text ? esc(text) : "<i>🎙 Voice clip</i>");
      const trace = add("trace", "");
      const leafletId = window.SEAssist?.leafletId || null;
      ctl = new AbortController();
      let req;
      if (audio) {
        const fd = new FormData(); fd.append("audio", audio, "question." + (audio.type.split("/")[1] || "webm"));
        fd.append("history", JSON.stringify(history)); if (leafletId) fd.append("leaflet_id", leafletId);
        req = { method: "POST", body: fd, signal: ctl.signal };
      } else req = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, history, leaflet_id: leafletId }), signal: ctl.signal };
      let heard = text, answer = "", speech = "";
      try {
        const resp = await fetch("/api/v1/voice", req);
        if (!resp.ok) { const b = await resp.json().catch(() => ({})); throw new Error(b.detail || "The voice agent couldn't answer."); }
        const reader = resp.body.getReader(), dec = new TextDecoder(); let buf = "";
        for (;;) {
          const { value, done } = await reader.read(); if (done) break;
          buf += dec.decode(value, { stream: true }); let i;
          while ((i = buf.indexOf("\n")) >= 0) {
            const ev = JSON.parse(buf.slice(0, i)); buf = buf.slice(i + 1);
            if (ev.type === "heard") { heard = ev.text; me.textContent = ev.text; }
            else if (ev.type === "tool") trace.insertAdjacentHTML("beforeend", `<span>${esc(ev.label)}…</span>`);
            else if (ev.type === "tool_done") { const s = trace.querySelector("span:not(.ok)"); if (s) { s.classList.add("ok"); s.textContent = s.textContent.replace(/…$/, "") + (ev.summary ? ` · ${ev.summary}` : ""); } }
            else if (ev.type === "link") trace.insertAdjacentHTML("afterend", `<a class="vx-link" href="${esc(ev.url)}">Open the ${esc(ev.page === "leaflet" ? "leaflet" : "page")}${ev.lender ? " for " + esc(ev.lender) : ""} ›</a>`);
            else if (ev.type === "final") { answer = ev.text; speech = ev.speak ? ev.speech : ""; }
            else if (ev.type === "error") throw new Error(ev.text);
          }
        }
      } catch (e) {
        if (e.name === "AbortError") return;
        if (!trace.innerHTML) trace.remove();
        add("err", esc(e.message)); setState("idle"); return;
      } finally { ctl = null; }
      if (!trace.innerHTML) trace.remove();
      add("bot", md(answer || "Sorry, I don't have an answer to that."));
      if (answer) history.push({ role: "user", text: heard }, { role: "model", text: answer }), history = history.slice(-10);
      say(speech);
    }

    // ---- Text to speech ----
    function say(text) {
      if (!text || !canSpeak || box.hidden) return setState("idle");
      speechSynthesis.cancel();
      const voices = speechSynthesis.getVoices();
      const lang = (navigator.language || "en").slice(0, 2);
      const voice = voices.find((v) => /Google/.test(v.name) && v.lang.startsWith(lang)) || voices.find((v) => v.lang.startsWith(lang));
      const parts = text.match(/[^.!?]+[.!?]*/g) || [text];  // sentence by sentence: long utterances get cut off in Chrome
      parts.forEach((p, i) => {
        const u = new SpeechSynthesisUtterance(p.trim()); if (voice) u.voice = voice; u.rate = 1.03;
        if (i === 0) u.onstart = () => setState("speaking");
        if (i === parts.length - 1) { u.onend = () => state === "speaking" && setState("idle"); u.onerror = () => setState("idle"); }
        speechSynthesis.speak(u);
      });
    }
    if (canSpeak) speechSynthesis.getVoices();  // loads the voice list early

    window.SEVoice = { open, ask: (q) => { open(); ask({ text: q }); } };
  });
})();
