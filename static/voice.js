/* Voice Mode: live speech-to-text, the Gemini agent with its tools and the gate, then text-to-speech.
   Speech-to-text uses the browser's Web Speech API (interim words stream into the input) when it has one;
   otherwise MediaRecorder records a clip and Gemini transcribes it on the server. Every turn goes to
   POST /api/v1/voice/turn, which returns the answer, the tools called and the gate's verdict as JSON.
   The answer is spoken with Google Cloud Text-to-Speech when the server sends audio, else speechSynthesis.
   While listening a live waveform is drawn from the microphone (AudioContext + AnalyserNode). */
(() => {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const md = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/^\s*[-*]\s+/gm, "• ").replace(/\n+/g, "<br>");
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const canRecord = !!(navigator.mediaDevices?.getUserMedia && window.MediaRecorder);
  const canSpeak = "speechSynthesis" in window;
  const AC = window.AudioContext || window.webkitAudioContext;
  const MIC = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0M12 17v5"/></svg>';
  const SIMULATE = ["Is Klarna safe for a freelancer with irregular income?", "Why did Synchrony get flagged in Safety Alerts?",
    "How do Indian small finance banks compare in RBI data?"];
  const LOOKUP = new Set(["check_lender", "research_lender", "lender_news", "safety_alerts", "compare_lenders", "find_alternatives",
    "india_rbi_data", "get_side_effects", "search_contract", "complaint_examples", "compare_with", "open_page"]);
  const NAMES = { check_lender: "Complaint lookup", research_lender: "Web research", lender_news: "Google Search news", safety_alerts: "Safety alerts",
    compare_lenders: "Compare lenders", find_alternatives: "Alternatives", gate_check: "Deterministic gate", india_rbi_data: "RBI Ombudsman data",
    open_page: "Link", get_side_effects: "Leaflet", search_contract: "Contract search", complaint_examples: "Real complaints", compare_with: "Compare" };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const store = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } } };

  // ---- Shared audio helpers (also used by "Say it instead" on the agent page) ----
  let actx = null;
  const audioCtx = () => { if (!AC) return null; actx = actx || new AC(); if (actx.state === "suspended") actx.resume(); return actx; };
  /* Draws a live waveform of `stream` on `canvas` until the returned stop() is called. */
  function scope(stream, canvas, color = "#d92d20") {
    const ctx = audioCtx(); if (!ctx || !canvas) return () => {};
    const src = ctx.createMediaStreamSource(stream), an = ctx.createAnalyser(); an.fftSize = 1024; src.connect(an);
    const data = new Uint8Array(an.fftSize), g = canvas.getContext("2d"); let raf = 0, on = true;
    const draw = () => {
      if (!on) return;
      const w = canvas.width = canvas.clientWidth * devicePixelRatio, h = canvas.height = canvas.clientHeight * devicePixelRatio;
      an.getByteTimeDomainData(data); g.clearRect(0, 0, w, h);
      g.lineWidth = 2.5 * devicePixelRatio; g.strokeStyle = color; g.lineJoin = "round"; g.beginPath();
      for (let i = 0; i < data.length; i++) { const x = (i / (data.length - 1)) * w, y = h / 2 + ((data[i] - 128) / 128) * h * 0.9; i ? g.lineTo(x, y) : g.moveTo(x, y); }
      g.stroke(); raf = requestAnimationFrame(draw);
    };
    draw();
    return () => { on = false; cancelAnimationFrame(raf); try { src.disconnect(); } catch { /* gone */ } canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height); };
  }
  /* A natural English voice for speechSynthesis. */
  function pickVoice() {
    const v = canSpeak ? speechSynthesis.getVoices() : [];
    const en = v.filter((x) => /^en(-|_|$)/i.test(x.lang));
    return ["Google US English", "Samantha", "Microsoft Aria Online (Natural)", "Microsoft Jenny Online (Natural)", "Google UK English Female", "Karen", "Daniel"]
      .map((n) => en.find((x) => x.name === n)).find(Boolean) || en.find((x) => /Natural|Neural|Google/.test(x.name)) || en[0] || null;
  }
  /* Speaks `text` (or plays base64 MP3 from Cloud TTS). Calls hooks.start / hooks.end; returns a stop function. */
  function speak(text, b64, hooks = {}) {
    let stopped = false, el = null;
    const end = () => { if (!stopped) { stopped = true; hooks.end?.(); } };
    if (b64) {
      el = new Audio("data:audio/mpeg;base64," + b64);
      const ctx = audioCtx();
      if (ctx && hooks.analyser) { try { const src = ctx.createMediaElementSource(el), an = ctx.createAnalyser(); an.fftSize = 64; src.connect(an); an.connect(ctx.destination); hooks.analyser(an); } catch { /* plays without bars */ } }
      el.onplay = () => hooks.start?.(true); el.onended = end; el.onerror = end;
      el.play().catch(() => { el = null; viaSynth(); });
    } else viaSynth();
    function viaSynth() {
      if (!canSpeak || !text) return end();
      speechSynthesis.cancel();
      const voice = pickVoice(), parts = text.match(/[^.!?]+[.!?]*/g) || [text];  // sentence by sentence: Chrome cuts long utterances
      parts.forEach((p, i) => {
        const u = new SpeechSynthesisUtterance(p.trim()); if (voice) u.voice = voice; u.lang = voice?.lang || "en-US"; u.rate = 1.02;
        if (i === 0) u.onstart = () => hooks.start?.(false);
        if (i === parts.length - 1) { u.onend = end; u.onerror = end; }
        speechSynthesis.speak(u);
      });
    }
    return () => { if (el) { el.pause(); el.src = ""; } if (canSpeak) speechSynthesis.cancel(); end(); };
  }
  if (canSpeak) { speechSynthesis.getVoices(); speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices(); }

  document.addEventListener("DOMContentLoaded", () => {
    const fab = document.createElement("button");
    fab.type = "button"; fab.className = "vx-fab"; fab.setAttribute("aria-label", "Open Voice Mode");
    fab.innerHTML = `${MIC}<span class="vx-fab-t">Voice</span>`;
    const box = document.createElement("div");
    box.className = "vx"; box.hidden = true; box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true"); box.setAttribute("aria-labelledby", "vxTitle");
    box.innerHTML = `<div class="vx-card">
      <header><div><b id="vxTitle">Voice Mode</b><small>Live STT → Gemini agent with tools → TTS · Vertex AI</small></div>
        <div class="vx-hd"><button type="button" class="vx-mute" aria-pressed="false" title="Mute spoken answers">🔊</button>
        <button type="button" class="vx-x" aria-label="Close">&times;</button></div></header>
      <ol class="vx-pipe" aria-label="Voice pipeline">
        <li data-k="stt"><i></i><span>1. Listening (STT)</span></li>
        <li data-k="tools"><i></i><span>2. Intake &amp; Tool Lookup</span></li>
        <li data-k="gate"><i></i><span>3. BigQuery PRR &amp; Clause Check</span></li>
        <li data-k="tts"><i></i><span>4. Speaking (TTS)</span></li></ol>
      <div class="vx-log" aria-live="polite"></div>
      <div class="vx-stage" data-s="idle">
        <div class="vx-viz"><canvas class="vx-scope" aria-hidden="true"></canvas>
          <div class="vx-eq" aria-hidden="true">${"<i></i>".repeat(16)}</div>
          <div class="vx-wave" aria-hidden="true">${"<i></i>".repeat(7)}</div></div>
        <p class="vx-state">Tap the mic and ask about any lender, card or pay-later plan</p>
        <p class="vx-interim"></p>
      </div>
      <div class="vx-sugg"><span>Simulate a voice turn</span>${SIMULATE.map((q) => `<button type="button" data-sim="1">🎤 ${esc(q)}</button>`).join("")}</div>
      <form class="vx-bar"><input type="text" maxlength="500" placeholder="Or type your question" aria-label="Your question">
        <button type="button" class="vx-stop" hidden>Stop speaking</button>
        <button type="button" class="vx-mic" aria-label="Start speaking">${MIC}</button></form>
    </div>`;
    document.body.append(fab, box);
    const $ = (s) => box.querySelector(s);
    const stage = $(".vx-stage"), log = $(".vx-log"), input = $(".vx-bar input"), canvas = $(".vx-scope");
    const eqBars = [...box.querySelectorAll(".vx-eq i")];
    let srBroken = false;  // the browser has speech recognition but its service fails (offline, Brave): record instead
    let history = [], state = "idle", rec = null, recorder = null, stream = null, timer = null, ctl = null, stopScope = null, stopSpeak = null, eqRaf = 0;
    let muted = store.get("se-voice-muted") === "1";
    const setMute = (m) => { muted = m; store.set("se-voice-muted", m ? "1" : "0"); const b = $(".vx-mute"); b.textContent = m ? "🔇" : "🔊"; b.setAttribute("aria-pressed", String(m)); b.title = m ? "Spoken answers are muted" : "Mute spoken answers"; if (m && state === "speaking") stopSpeaking(); };
    setMute(muted);

    const STATES = { idle: "Tap the mic and ask about any lender, card or pay-later plan", listening: "Listening…",
      thinking: "Checking the complaint data…", speaking: "Speaking…" };
    const setState = (s, label) => {
      state = s; stage.dataset.s = s; $(".vx-state").textContent = label || STATES[s];
      $(".vx-mic").classList.toggle("on", s === "listening");
      $(".vx-mic").setAttribute("aria-label", s === "listening" ? "Stop and send" : s === "speaking" ? "Interrupt and speak" : "Start speaking");
      $(".vx-stop").hidden = s !== "speaking";
      fab.classList.toggle("live", s !== "idle");
    };
    const pipe = (k, st) => { const li = box.querySelector(`.vx-pipe [data-k="${k}"]`); li.className = st || ""; };
    const pipeReset = () => ["stt", "tools", "gate", "tts"].forEach((k) => pipe(k, ""));
    const add = (cls, html) => { const d = document.createElement("div"); d.className = "vx-msg " + cls; d.innerHTML = html; log.appendChild(d); log.scrollTop = log.scrollHeight; return d; };

    const open = () => { box.hidden = false; document.body.classList.add("vx-open"); setTimeout(() => $(".vx-mic").focus(), 50); };
    const close = () => { stopAll(); box.hidden = true; document.body.classList.remove("vx-open"); fab.focus(); };
    fab.addEventListener("click", open);
    $(".vx-x").addEventListener("click", close);
    $(".vx-mute").addEventListener("click", () => setMute(!muted));
    $(".vx-stop").addEventListener("click", () => stopSpeaking());
    box.addEventListener("click", (e) => { if (e.target === box) close(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !box.hidden) close(); });

    function stopListening() {
      stopScope?.(); stopScope = null;
      stream?.getTracks().forEach((t) => t.stop()); stream = null;
    }
    function stopSpeaking() {
      const s = stopSpeak; stopSpeak = null; s?.();
      cancelAnimationFrame(eqRaf); eqBars.forEach((b) => (b.style.height = ""));
      if (state === "speaking") setState("idle");
    }
    function stopAll() {
      try { rec?.abort(); } catch { /* already stopped */ }
      if (recorder?.state === "recording") { recorder.onstop = null; recorder.stop(); }
      recorder = null; rec = null; stopListening();
      clearTimeout(timer); ctl?.abort(); ctl = null;
      stopSpeaking();
      $(".vx-interim").textContent = ""; setState("idle");
    }

    // ---- 1. Speech to text, with a live waveform from the microphone ----
    async function micStream() {
      if (!navigator.mediaDevices?.getUserMedia) return null;
      try { return await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); } catch { return null; }
    }
    async function listen() {
      stopSpeaking(); pipeReset(); pipe("stt", "on");
      if (SR && !srBroken) {
        rec = new SR(); rec.lang = navigator.language || "en-US"; rec.interimResults = true; rec.continuous = false;
        let final = "";
        rec.onresult = (e) => {
          let interim = ""; final = "";
          for (const r of e.results) (r.isFinal ? (final += r[0].transcript) : (interim += r[0].transcript));
          $(".vx-interim").textContent = final || interim; input.value = final || interim;
        };
        rec.onerror = (e) => {
          if (["network", "service-not-allowed", "language-not-supported", "audio-capture"].includes(e.error) && canRecord) {
            srBroken = true; rec.onend = null; rec = null; stopListening(); return listen();
          }
          if (e.error !== "aborted") { pipe("stt", "err"); setState("idle", e.error === "not-allowed" ? "Microphone blocked. Allow it in the address bar, or type below." : "I didn't catch that. Tap the mic to try again."); }
        };
        rec.onend = () => {
          rec = null; stopListening(); const q = final.trim() || input.value.trim(); $(".vx-interim").textContent = "";
          if (q && state === "listening") { input.value = ""; ask({ text: q, spoken: true }); }
          else if (state === "listening") { pipe("stt", "err"); setState("idle", "I didn't catch that. Tap the mic to try again."); }
        };
        setState("listening"); rec.start();
        micStream().then((s) => { if (state !== "listening" || !s) return s?.getTracks().forEach((t) => t.stop()); stream = s; stopScope = scope(s, canvas); });
      } else if (canRecord) {
        const s = await micStream();
        if (!s) { pipe("stt", "err"); return setState("idle", "Microphone blocked. Allow it in the address bar, or type below."); }
        stream = s; stopScope = scope(s, canvas); const chunks = [];
        recorder = new MediaRecorder(s);
        recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
        recorder.onstop = () => {
          stopListening();
          const blob = new Blob(chunks, { type: (recorder?.mimeType || "audio/webm").split(";")[0] }); recorder = null;
          if (blob.size) ask({ audio: blob }); else setState("idle");
        };
        recorder.start(); setState("listening", "Listening… tap again to send");
        timer = setTimeout(() => recorder?.state === "recording" && recorder.stop(), 15000);
      } else { pipe("stt", "err"); setState("idle", "This browser can't use the microphone. Type your question below."); }
    }
    $(".vx-mic").addEventListener("click", () => {
      if (state === "listening") { if (rec) rec.stop(); else if (recorder?.state === "recording") { clearTimeout(timer); recorder.stop(); } }
      else if (state === "speaking") { stopSpeaking(); listen(); }  // barge-in: cut the answer off and listen
      else if (state === "idle") listen();
    });
    $(".vx-bar").addEventListener("submit", (e) => { e.preventDefault(); const q = input.value.trim(); if (q && state !== "thinking") { input.value = ""; stopSpeaking(); pipeReset(); ask({ text: q }); } });
    box.addEventListener("click", (e) => {
      const b = e.target.closest(".vx-sugg button, .vx-follow button"); if (!b || state === "thinking") return;
      const q = b.textContent.replace(/^🎤\s*/, "").trim();
      if (b.dataset.sim) simulate(q); else { stopSpeaking(); pipeReset(); ask({ text: q }); }
    });

    /* A voice turn without a microphone: the question is "heard" word by word, then runs for real. */
    async function simulate(q) {
      stopSpeaking(); pipeReset(); pipe("stt", "on"); setState("listening", "Simulated voice turn: listening…");
      stage.classList.add("sim");
      const words = q.split(" ");
      for (let i = 1; i <= words.length; i++) { if (state !== "listening") return stage.classList.remove("sim"); $(".vx-interim").textContent = words.slice(0, i).join(" "); await sleep(70); }
      await sleep(250); stage.classList.remove("sim"); $(".vx-interim").textContent = "";
      ask({ text: q, simulated: true });
    }

    function context() {
      const c = (typeof window.SEContext === "function" && window.SEContext()) || {};
      const page = location.pathname.startsWith("/leaflet") ? "leaflet" : (location.hash.slice(1) || "demo");
      return { current_page: page, leaflet_id: window.SEAssist?.leafletId || null, active_lender: c.lender || null, applicant_profile: c.profile || [] };
    }

    // ---- 2 + 3. The agent, its tools and the gate ----
    async function ask({ text, audio, simulated, spoken }) {
      $(".vx-sugg").hidden = true; box.querySelectorAll(".vx-follow").forEach((f) => f.remove());
      pipe("stt", "done"); pipe("tools", "on");
      setState("thinking", audio ? "Gemini is transcribing your clip…" : "Looking up lenders and complaint data…");
      const me = add("user", (text ? esc(text) : "<i>🎙 Voice clip</i>") + (simulated ? '<small class="vx-tag">Simulated voice turn</small>' : spoken ? '<small class="vx-tag">Heard by speech-to-text</small>' : ""));
      ctl = new AbortController();
      const ctx = context();
      let req;
      if (audio) {
        const fd = new FormData(); fd.append("audio", audio, "question." + (audio.type.split("/")[1] || "webm"));
        fd.append("history", JSON.stringify(history)); fd.append("context", JSON.stringify(ctx));
        req = { method: "POST", body: fd, signal: ctl.signal };
      } else req = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ transcript: text, history, context: ctx }), signal: ctl.signal };
      const t0 = performance.now();
      let d;
      try {
        const resp = await fetch("/api/v1/voice/turn", req);
        d = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(d.detail || "The voice agent couldn't answer.");
      } catch (e) {
        if (e.name === "AbortError") return;
        pipe("tools", "err"); add("err", esc(e.message)); setState("idle"); return;
      } finally { ctl = null; }
      const ms = Math.round(performance.now() - t0);
      if (audio) me.innerHTML = esc(d.transcript) + '<small class="vx-tag">Transcribed by Gemini</small>';
      const lookups = d.tools_called.filter((t) => LOOKUP.has(t.name)), gates = d.tools_called.filter((t) => t.name === "gate_check");
      // Replay what the agent actually did, step by step, so the pipeline reads in order.
      const trace = add("trace", "");
      const chip = (t) => `<span class="${t.status === "ok" ? "ok" : "bad"}"><b>${esc(NAMES[t.name] || t.name)}</b>${t.summary ? " · " + esc(t.summary) : ""}</span>`;
      for (const t of lookups) { trace.insertAdjacentHTML("beforeend", chip(t)); log.scrollTop = log.scrollHeight; await sleep(110); }
      pipe("tools", lookups.length || !gates.length ? "done" : "skip"); pipe("gate", "on");
      $(".vx-state").textContent = gates.length ? "Running the deterministic gate…" : "Checking the answer against the data…";
      await sleep(gates.length ? 380 : 200);
      for (const t of gates) trace.insertAdjacentHTML("beforeend", chip(t));
      pipe("gate", gates.length ? "done" : "skip");
      if (!trace.innerHTML) trace.remove();
      if (d.gate_verdict) {
        const held = d.gate_verdict === "human_review";
        add("gate " + (held ? "held" : "pass"), held
          ? `<b>HELD FOR THE PERSON</b> · human_review${d.gate_severity ? ` · severity ${esc(d.gate_severity)}` : ""}${d.gate_issuer ? ` · ${esc(d.gate_issuer)}` : ""}`
          : `<b>PASS</b> · standard disclosure${d.gate_severity ? ` · severity ${esc(d.gate_severity)}` : ""}${d.gate_issuer ? ` · ${esc(d.gate_issuer)}` : ""}`);
      }
      add("bot", md(d.reply_text || "Sorry, I don't have an answer to that.") + `<small class="vx-ms">${d.tools_called.length} tool${d.tools_called.length === 1 ? "" : "s"} · ${ms.toLocaleString()} ms${d.tts_audio_b64 ? " · Cloud Text-to-Speech" : ""}</small>`);
      (d.links || []).forEach((l) => add("link-row", `<a class="vx-link" href="${esc(l.url)}">Open the ${esc(l.page === "leaflet" ? "leaflet" : "page")}${l.lender ? " for " + esc(l.lender) : ""} ›</a>`));
      if (d.suggested_followups?.length) {
        const f = add("vx-follow", d.suggested_followups.map((q) => `<button type="button">${esc(q)}</button>`).join(""));
        f.classList.remove("vx-msg");
      }
      if (d.reply_text) history.push({ role: "user", text: d.transcript }, { role: "model", text: d.reply_text }), history = history.slice(-10);
      say(d.spoken_summary, d.tts_audio_b64);
    }

    // ---- 4. Text to speech, with a 16-bar equalizer ----
    function say(text, b64) {
      if (!text || box.hidden || muted || (!b64 && !canSpeak)) { pipe("tts", muted ? "skip" : ""); return setState("idle", muted ? "Answer ready (spoken answers are muted)" : undefined); }
      pipe("tts", "on"); setState("speaking");
      let started = false;
      // Some browsers queue speech that never starts (no voices installed): don't leave the turn hanging.
      const guard = setTimeout(() => { if (!started) stopSpeak?.(); }, 4000);
      stopSpeak = speak(text, b64, {
        start: () => { started = true; clearTimeout(guard); setState("speaking"); },
        end: () => { clearTimeout(guard); cancelAnimationFrame(eqRaf); eqBars.forEach((b) => (b.style.height = "")); stage.classList.remove("real-eq"); pipe("tts", "done"); stopSpeak = null; if (state === "speaking") setState("idle"); },
        analyser: (an) => {
          stage.classList.add("real-eq"); const data = new Uint8Array(an.frequencyBinCount);
          const tick = () => { an.getByteFrequencyData(data); eqBars.forEach((b, i) => (b.style.height = `${8 + (data[i + 1] / 255) * 48}px`)); eqRaf = requestAnimationFrame(tick); };
          tick();
        },
      });
    }

    window.SEVoice = { open, ask: (q) => { open(); pipeReset(); ask({ text: q }); }, simulate: (q) => { open(); simulate(q); }, scope, speak, micStream };
  });
})();
