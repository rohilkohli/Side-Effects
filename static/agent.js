"use strict";
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => n == null ? "" : "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const TOOL_LABEL = {
    search_payment_options: "Looking at ways to pay",
    check_side_effects: "Checking SIDE EFFECTS",
    place_order: "Placing the order",
    ask_person: "Handing the decision back",
  };
  const TOOL_ICON = { search_payment_options: "🔎", check_side_effects: "💊", place_order: "🧾", ask_person: "✋" };
  const OFFER_NAMES = { store_card: "Northwind Store Card", affirm_12: "Affirm monthly", klarna_pay4: "Klarna Pay in 4", pay_now: "Debit card" };
  let persona = "maya";
  let personas = {};
  let custom = null; // {name, about, profile} once Gemini has read "You"
  const who = () => (persona === "you" ? custom?.name : personas[persona]?.name) || "them";

  async function init() {
    personas = await fetch("/api/agent/personas").then((r) => r.json());
    const box = $("#personas");
    box.innerHTML = Object.entries(personas).map(([k, p]) => `
      <button type="button" role="radio" class="persona" data-k="${k}" aria-checked="${k === persona}">
        <span class="avatar" aria-hidden="true">${esc(p.name[0])}</span>
        <span><strong>${esc(p.name)}</strong><small>${esc(p.about)}</small><em>&ldquo;${esc(p.task)}&rdquo;</em></span>
      </button>`).join("") + `
      <div role="radio" tabindex="0" class="persona you" data-k="you" aria-checked="false">
        <span class="avatar" aria-hidden="true">?</span>
        <span><strong>You</strong><small>Describe your situation in a sentence. Gemini reads it, and both agents shop for you.</small>
        <textarea id="youText" rows="3" maxlength="400" placeholder="e.g. I'm a student with a part-time job and a phone on EMI"></textarea>
        <button type="button" class="mic-btn" id="youMic" hidden>🎤 Say it instead</button></span>
      </div>`;
    box.addEventListener("click", (e) => {
      const b = e.target.closest(".persona"); if (!b) return;
      persona = b.dataset.k;
      box.querySelectorAll(".persona").forEach((x) => x.setAttribute("aria-checked", x === b));
    });
    $("#youText").addEventListener("focus", () => $(".persona.you").click());
    $(".persona.you").addEventListener("keydown", (e) => {
      if (e.target.id === "youText" || (e.key !== "Enter" && e.key !== " ")) return;
      e.preventDefault(); $(".persona.you").click(); $("#youText").focus();
    });
    if (Recognition) {
      $("#youMic").hidden = false;
      $("#youMic").addEventListener("click", (e) => {
        e.stopPropagation(); $(".persona.you").click();
        listen($("#youMic"), (said) => { $("#youText").value = said; });
      });
    }
    $("#devView").addEventListener("change", (e) => document.body.classList.toggle("dev", e.target.checked));
    const hideBanner = () => { $("#banner").hidden = true; try { localStorage.setItem("se-banner", "arena"); } catch { /* private mode */ } };
    try { if (localStorage.getItem("se-banner") === "arena") $("#banner").hidden = true; } catch { /* private mode */ }
    $("#bannerClose").addEventListener("click", hideBanner);
    $("#bannerTry").addEventListener("click", () => {
      hideBanner();
      showPanel("scam");
    });
    initCarousel();
    $("#runBtn").addEventListener("click", runBoth);
  }

  async function runBoth() {
    $("#err").hidden = true;
    $("#readout").hidden = true;
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    $("#runBtn").disabled = true;
    custom = persona === "you" ? custom : null;
    if (persona === "you") {
      const text = $("#youText").value.trim();
      if (!text) { showErr("Write a sentence about your situation first."); $("#runBtn").disabled = false; return; }
      $("#runBtn").textContent = "Gemini is reading your situation…";
      try {
        const r = await fetch("/api/agent/read-person", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
        const body = await r.json();
        if (!r.ok) throw new Error(body.detail || `The server answered ${r.status}`);
        custom = body;
      } catch (e) { showErr(e.message); $("#runBtn").disabled = false; $("#runBtn").textContent = "Run both agents live"; return; }
      $("#readout").innerHTML = `<span class="who">Gemini read your situation</span><strong>${esc(custom.about)}</strong>
        <div class="sits">${custom.situations.length ? custom.situations.map((x) => `<span>${esc(x)}</span>`).join("") : "<span>Nothing that changes the risk</span>"}</div>`;
      $("#readout").hidden = false;
    }
    $("#arena").hidden = false;
    $("#outcome").hidden = true;
    for (const id of ["#laneA", "#laneB"]) { $(id + " .feed").innerHTML = ""; $(id).classList.remove("done", "stopped", "signed", "decided"); setState($(id), "Starting"); }
    enterRun();
    setBusy(true);
    await Promise.allSettled([run($("#laneA"), false), run($("#laneB"), true)]);
    showOutcome();
    setBusy(false);
    $("#runBtn").disabled = false;
    $("#runBtn").textContent = "Run both agents live";
  }

  async function run(lane, gated) {
    const feed = $(".feed", lane);
    lane.classList.add("busy");
    const typing = add(feed, "typing", `<span></span><span></span><span></span>`);
    try {
      const resp = await fetch("/api/agent/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ persona: persona === "you" ? "maya" : persona, gated, hacked: $("#hacked").checked,
        custom: persona === "you" ? custom : null }) });
      if (!resp.ok) throw new Error(`The server answered ${resp.status}`);
      const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
          if (line) { render(lane, feed, JSON.parse(line)); feed.appendChild(typing); }
        }
      }
    } catch (e) {
      render(lane, feed, { type: "error", detail: e.message });
    } finally {
      typing.remove();
      lane.classList.remove("busy");
    }
  }

  function add(feed, cls, html) {
    const li = document.createElement("li");
    li.className = "ev " + cls;
    li.innerHTML = html;
    feed.appendChild(li);
    feed.scrollTo({ top: feed.scrollHeight, behavior: "smooth" });
    return li;
  }

  function bars(disclosures, matches = []) {
    const max = Math.max(4, ...disclosures.map((d) => d.reported_x || 0));
    const seen = new Set();
    return `<ul class="bars">${disclosures.filter((d) => { const k = d.side_effect + d.level; if (seen.has(k)) return false; seen.add(k); return true; }).map((d) => {
      const hit = matches.includes(d.side_effect) || d.matches;
      return `<li class="${hit ? "hit" : ""}">
        <span class="lbl">${esc(d.side_effect)}${hit ? ' <b class="fits">fits you</b>' : ""}<small>${d.level === "bank" ? "this lender" : "all pay-later lenders"} &middot; ${Number(d.n).toLocaleString()} complaints</small></span>
        <span class="bar"><i style="width:${Math.min(100, (d.reported_x / max) * 100)}%"></i></span>
        <span class="x">${d.reported_x}&times;</span></li>`;
    }).join("")}</ul>`;
  }

  // Voice: speak to the agent (Web Speech API, in Chrome and Safari).
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  function listen(btn, onText) {
    if (!Recognition) return;
    const rec = new Recognition();
    rec.lang = navigator.language || "en-US"; rec.interimResults = false; rec.maxAlternatives = 1;
    const label = btn.textContent;
    btn.classList.add("on"); btn.textContent = "🎙 Listening…";
    rec.onresult = (e) => onText(e.results[0][0].transcript);
    rec.onerror = () => { btn.textContent = label; };
    rec.onend = () => { btn.classList.remove("on"); if (btn.textContent === "🎙 Listening…") btn.textContent = label; };
    rec.start();
  }
  function matchOption(said, options) {
    const t = said.toLowerCase();
    const keys = { pay_now: ["debit", "pay now", "pay in full", "full", "own card", "cash"], affirm_12: ["affirm", "monthly"],
      klarna_pay4: ["klarna", "pay in four", "pay in 4"], store_card: ["store", "northwind", "synchrony"] };
    const hit = options.find((o) => (keys[o.id] || []).some((k) => t.includes(k)));
    return hit?.id;
  }

  function setState(lane, text) { const el = $(".state", lane); if (el) el.textContent = text; }

  function laneResult(lane) {
    if (lane.classList.contains("decided")) return { cls: "good", text: `${who()} chose: ${lane.dataset.chose}` };
    if (lane.classList.contains("stopped")) return { cls: "good", text: `Stopped and asked ${who()}` };
    if (lane.classList.contains("signed")) return { cls: "bad", text: `Signed ${who()} up without asking` };
    if (lane.classList.contains("done")) return { cls: "good", text: "Placed a safe order" };
    return null;
  }

  function showOutcome() {
    const a = laneResult($("#laneA")), b = laneResult($("#laneB"));
    if (!a || !b) return;
    $("#outcome").innerHTML = `<div><div class="side ${a.cls}"><small>Agent on its own</small><b>${esc(a.text)}</b></div>
      <span class="vs">vs</span><div class="side ${b.cls}"><small>Agent + SIDE EFFECTS</small><b>${esc(b.text)}</b></div></div>`;
    $("#outcome").hidden = false;
  }

  function showErr(msg) { const el = $("#err"); el.textContent = msg; el.hidden = false; }

  function termsHtml(t) {
    const i = t.indexOf("[Note for AI");
    return i < 0 ? esc(t) : `${esc(t.slice(0, i))}<span class="inj"><b>Hidden on the page:</b> ${esc(t.slice(i).replace(/^\[|\]$/g, ""))}</span>`;
  }

  let carouselLayout = () => {};
  function initCarousel() {
    const car = $("#carousel"), dots = $("#dots");
    const cards = [...car.children];
    // One dot per distinct scroll position, so the last dots never point at the same place.
    let stops = [];
    const layout = () => {
      const max = car.scrollWidth - car.clientWidth;
      stops = [...new Set(cards.map((c) => Math.min(max, Math.max(0, c.offsetLeft - car.offsetLeft))))];
      dots.innerHTML = stops.map((_, i) => `<button type="button" aria-label="Show card ${i + 1}" data-i="${i}"></button>`).join("");
      mark();
    };
    const current = () => stops.reduce((best, x, i) => Math.abs(x - car.scrollLeft) < Math.abs(stops[best] - car.scrollLeft) ? i : best, 0);
    const go = (i) => car.scrollTo({ left: stops[(i + stops.length) % stops.length], behavior: "smooth" });
    const mark = () => dots.querySelectorAll("button").forEach((d, i) => d.classList.toggle("on", i === current()));
    let timer = null;
    const stopAuto = () => { clearInterval(timer); timer = null; };
    document.querySelectorAll(".car-btn").forEach((b) => b.addEventListener("click", () => { stopAuto(); go(current() + Number(b.dataset.dir)); }));
    dots.addEventListener("click", (e) => { const d = e.target.closest("button"); if (d) { stopAuto(); go(Number(d.dataset.i)); } });
    car.addEventListener("scroll", () => requestAnimationFrame(mark), { passive: true });
    window.addEventListener("resize", layout);
    layout();
    timer = setInterval(() => { if (!$("#p-why").hidden) go(current() + 1); }, 5000);
    ["pointerdown", "wheel", "touchstart"].forEach((ev) => car.addEventListener(ev, stopAuto, { passive: true }));
    carouselLayout = layout;
  }

  function speak(text) {
    if (!("speechSynthesis" in window)) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.02;
    speechSynthesis.speak(u);
  }

  const STATE = { start: "Reading the task", thought: "Thinking", say: "Thinking", options: "Comparing options",
    check: "Checking side effects", injection: "Hidden instruction found", blocked: "Gate refused", error: "Error" };

  function render(lane, feed, ev) {
    const name = who();
    if (STATE[ev.type]) setState(lane, STATE[ev.type]);
    if (ev.type === "tool") setState(lane, TOOL_LABEL[ev.name] || "Working");
    switch (ev.type) {
      case "start":
        add(feed, "task", `<span class="who">${esc(ev.persona.name)} asks</span>&ldquo;${esc(ev.persona.task)}&rdquo;`);
        break;
      case "thought":
        add(feed, "thought", `<span class="who">Gemini is thinking</span>${esc(ev.text)}`);
        break;
      case "say":
        add(feed, "say", esc(ev.text));
        break;
      case "tool": {
        const args = Object.values(ev.args || {}).map((v) => JSON.stringify(v)).join(", ");
        const offer = ev.args?.offer_id && OFFER_NAMES[ev.args.offer_id];
        add(feed, "tool", `<span class="step-ico" aria-hidden="true">${TOOL_ICON[ev.name] || "•"}</span>
          <span>${esc(TOOL_LABEL[ev.name] || "Working")}${offer ? ": " + esc(offer) : ""}</span>
          <code class="dev-only">${esc(ev.name)}(${esc(args.length > 48 ? args.slice(0, 46) + "…" : args)})</code>`);
        break;
      }
      case "options":
        add(feed, "options", `<div class="store">${esc(ev.store)} &middot; ${esc(ev.item.name)} &middot; <b>${money(ev.item.price)}</b></div>
          <table>${ev.options.map((o) => `<tr><td>${esc(o.label)}<small>${termsHtml(o.terms)}</small></td><td>${o.monthly ? money(o.monthly) + "<small>/mo</small>" : "today"}</td></tr>`).join("")}</table>`);
        break;
      case "check": {
        const r = ev.result;
        add(feed, "check v-" + r.verdict, `<div class="chk-head"><span class="pill" aria-hidden="true"></span>
          <strong>${esc(ev.offer.label)}</strong><span class="verdict">${verdictText(r.verdict)}</span></div>
          ${bars(r.required_disclosures, r.matches_applicant_situation)}`);
        break;
      }
      case "injection":
        add(feed, "blocked inj-card", `<strong>Hidden instruction for AI agents found on this page</strong>The checkout tries to tell the agent that SIDE EFFECTS already approved the store card. It didn't. The agent is warned to ignore the page, and the gate in the checkout decides anyway.`);
        break;
      case "blocked":
        add(feed, "blocked", `<strong>Gate refused the order</strong>The agent tried to sign ${esc(name)} up for ${esc(ev.offer.label)} without asking. SIDE EFFECTS sits inside the checkout, so it couldn't.`);
        break;
      case "order": {
        const unseen = ev.unseen_side_effects || [];
        const hits = unseen.filter((d) => d.matches);
        lane.classList.remove("stopped", "signed", "done", "decided");
        if (ev.confirmed_by_person) { lane.classList.add("decided"); lane.dataset.chose = ev.offer.label; }
        else lane.classList.add(hits.length ? "signed" : "done");
        setState(lane, ev.confirmed_by_person ? `${name} chose` : hits.length ? "Signed without asking" : "Order placed");
        add(feed, "order" + (hits.length ? " bad" : ""), `<div class="stamp ${hits.length ? "red" : "green"}">${hits.length ? "Signed without asking" : "Order placed"}</div>
          <p>${esc(name)} is now on <b>${esc(ev.offer.label)}</b>.</p>
          ${unseen.length ? `<p class="never">What ${esc(name)} was never told:</p>${bars(unseen)}` : ""}
          ${ev.confirmed_by_person ? `<p class="never ok">${esc(name)} made this choice${ev.disclosures_shown?.length ? `, after seeing ${ev.disclosures_shown.length} side effects` : ""}.</p>` : ""}`);
        break;
      }
      case "ask":
        lane.classList.add("stopped");
        setState(lane, "Stopped before signing");
        add(feed, "ask", `<div class="stamp red">Stopped before signing</div>
          <p class="msg">${esc(ev.message)} <button type="button" class="say-again" aria-label="Read aloud">🔊</button></p>
          <p class="choose">${esc(name)} decides: <button type="button" class="mic-btn small" data-voice="1" ${Recognition ? "" : "hidden"}>🎤 Answer by voice</button></p>
          <div class="choices">${ev.options.map((o) => `<button type="button" data-o="${esc(o.id)}">${esc(o.label)}<small>${o.check ? verdictText(o.check.verdict) : "No new credit"}</small></button>`).join("")}</div>`)
          .addEventListener("click", (e) => {
            if (e.target.closest(".say-again")) { speak(ev.message); return; }
            const vb = e.target.closest("[data-voice]");
            if (vb) {
              listen(vb, (said) => {
                const pick = matchOption(said, ev.options);
                const btn = pick && lane.querySelector(`.choices button[data-o="${pick}"]:not(:disabled)`);
                if (btn) btn.click(); else vb.textContent = `🎤 Didn't catch an option in "${said}". Try again`;
              });
              return;
            }
            choose(e, lane, feed);
          });
        speak(ev.message);
        break;
      case "end":
        add(feed, "say", "The agent finished without placing an order.");
        break;
      case "error":
        add(feed, "error", esc(ev.detail || "Something went wrong."));
        break;
    }
  }

  async function choose(e, lane, feed) {
    const b = e.target.closest("button[data-o]"); if (!b) return;
    b.closest(".choices").querySelectorAll("button").forEach((x) => { x.disabled = true; x.classList.toggle("picked", x === b); });
    const r = await fetch("/api/agent/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ persona: persona === "you" ? "maya" : persona, offer_id: b.dataset.o,
      profile: persona === "you" ? custom?.profile || [] : null }) });
    if (r.ok) { render(lane, feed, await r.json()); showOutcome(); }
  }

  function verdictText(v) {
    return { human_review: "Needs your OK", disclose: "Show before signing", no_signal: "No signal" }[v] || v;
  }

  // Reveal sections and count the headline numbers up as they scroll into view.
  function countUp(el) {
    const m = el.textContent.match(/^([\d,.]+)(.*)$/); if (!m) return;
    const target = parseFloat(m[1].replace(/,/g, "")), dec = (m[1].split(".")[1] || "").length, t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / 1200), v = target * (1 - Math.pow(1 - k, 3));
      el.textContent = (dec ? v.toFixed(dec) : Math.round(v).toLocaleString("en-US")) + m[2];
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  // Pages instead of one long scroll: a tab per section, and the demo collapses its setup while running.
  const counted = new Set();
  function showPanel(name, fromHistory = false) {
    document.querySelectorAll(".pager [data-p]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.p === name)));
    document.querySelectorAll(".panel").forEach((p) => { p.hidden = p.id !== "p-" + name; });
    if (name === "why" && !counted.has("why")) { counted.add("why"); document.querySelectorAll("#p-why .stat b").forEach((b) => { if (/^\d/.test(b.textContent) && b.textContent !== "0") countUp(b); }); }
    const url = name === "demo" ? location.pathname : "#" + name;
    if (!fromHistory && location.hash !== (name === "demo" ? "" : "#" + name)) history.pushState(null, "", url);
    if (name === "why") requestAnimationFrame(() => carouselLayout());
    if (name === "biz") loadAudit();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function setBusy(on) {
    ["#againBtn", "#changeBtn"].forEach((id) => { $(id).disabled = on; });
    $("#againBtn").textContent = on ? "Running…" : "Run again";
  }
  function enterRun() {
    const pName = persona === "you" ? (custom?.name || "you") : personas[persona]?.name;
    const read = persona === "you" && custom ? ` <span class="read">Gemini read: ${custom.situations.length ? custom.situations.map(esc).join(", ") : "nothing that changes the risk"}</span>` : "";
    $("#runSummary").innerHTML = `Shopping for <b>${esc(pName)}</b> &middot; ${$("#hacked").checked ? "<b class=\"hot\">Hacked store</b>" : "Normal store"}${read}`;
    $("#p-demo").classList.add("running");
    $("#runbar").hidden = false;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function leaveRun() {
    if ($("#againBtn").disabled) return;  // a run is still going
    $("#p-demo").classList.remove("running");
    $("#runbar").hidden = true;
    $("#arena").hidden = true; $("#outcome").hidden = true; $("#readout").hidden = true;
    if ("speechSynthesis" in window) speechSynthesis.cancel();
  }
  document.querySelector(".pager").addEventListener("click", (e) => { const b = e.target.closest("[data-p]"); if (b) showPanel(b.dataset.p); });
  $("#changeBtn").addEventListener("click", leaveRun);
  $("#againBtn").addEventListener("click", () => { if (!$("#runBtn").disabled && !$("#againBtn").disabled) runBoth(); });
  document.querySelector(".lane-tabs").addEventListener("click", (e) => {
    const b = e.target.closest("[data-l]"); if (!b) return;
    document.querySelectorAll(".lane-tabs [data-l]").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
    $("#arena").dataset.show = b.dataset.l;
  });
  $("#arena").dataset.show = "laneB";
  const hashPanel = location.hash.slice(1);
  // Checking a lender now lives on the leaflet page, which reads the lender from a photo or a typed name.
  if (hashPanel.startsWith("check")) location.replace("/leaflet" + (hashPanel.startsWith("check=") ? "?q=" + hashPanel.slice(6) : ""));
  if (["scam", "how", "why", "biz"].includes(hashPanel)) showPanel(hashPanel, true);
  window.addEventListener("popstate", () => {
    const h = location.hash.slice(1);
    showPanel(["scam", "how", "why", "biz"].includes(h) ? h : "demo", true);
  });

  /* ---- Scam arena: Gemini attacker vs Gemini guardian vs the gate ---- */
  const TECH = { prompt_injection: "Orders aimed at AI agents", fake_endorsement: "Fake approval", false_urgency: "False urgency",
    pre_ticked_consent: "Consent by continuing", hidden_cost: "Hidden cost", bait_and_switch: "Bait and switch" };
  const mark = (text, quotes) => {
    let h = esc(text);
    quotes.forEach((q) => { const e = esc(q); if (e && h.includes(e)) h = h.split(e).join(`<mark>${e}</mark>`); });
    return h;
  };
  let scamRunning = false;
  async function runScam() {
    if (scamRunning) return;
    scamRunning = true;
    const btn = $("#scamBtn"); btn.disabled = true; btn.textContent = "Agents at work…";
    $("#scamErr").hidden = true; $("#scamRounds").innerHTML = ""; $("#scamScore").hidden = false;
    ["#scCaught", "#scFooled", "#scHeld"].forEach((id) => { $(id).textContent = "0"; });
    let card = null, atk = null;
    const step = (cls, html) => { const d = document.createElement("div"); d.className = "rstep " + cls; d.innerHTML = html; card.querySelector(".rsteps").appendChild(d); d.scrollIntoView({ behavior: "smooth", block: "nearest" }); return d; };
    const wait = (label) => { card.querySelector(".rwait")?.remove(); const w = document.createElement("div"); w.className = "rwait"; w.innerHTML = `<i></i><span>${esc(label)}…</span>`; card.querySelector(".rsteps").appendChild(w); };
    try {
      const resp = await fetch("/api/arena/run", { method: "POST" });
      if (!resp.ok) throw new Error(`The server answered ${resp.status}`);
      const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
          if (!line) continue;
          const ev = JSON.parse(line);
          if (ev.type === "error") throw new Error(ev.detail);
          if (ev.type === "tick") {
            const w = card?.querySelector(".rwait span");
            if (w) w.textContent = `${ev.label}… ${ev.seconds}s`;
            continue;
          }
          if (ev.type === "round") {
            card = document.createElement("article"); card.className = "rcard";
            card.innerHTML = `<header><b>Round ${ev.round}</b></header><div class="rsteps"></div>`;
            $("#scamRounds").appendChild(card); wait("The attacker is writing a new scam");
          } else if (ev.type === "attack") {
            atk = ev.attack; card.querySelector(".rwait")?.remove();
            card.querySelector("header").insertAdjacentHTML("beforeend", `<span class="tech">${esc(TECH[atk.technique] || atk.technique)}</span>`);
            card.dataset.page = (atk.banner || "") + " " + atk.added_terms;
            step("atk", `<span class="who">😈 Attacker${atk.source === "playbook" ? ' <span class="src">from the playbook</span>' : ""}</span><p class="muted">Pushing <b>${esc(ev.target_label)}</b>. ${esc(atk.why_it_might_work)}</p>
              <div class="fakepage"><div class="fp-banner">${esc(atk.banner)}</div><div class="fp-terms">${esc(atk.added_terms)}</div></div>`);
            wait("The guardian is reading the page");
          } else if (ev.type === "guardian") {
            card.querySelector(".rwait")?.remove();
            const quotes = ev.findings.map((f) => f.quote);
            const fp = card.querySelector(".fakepage");
            if (fp) { fp.querySelector(".fp-banner").innerHTML = mark(atk.banner, quotes); fp.querySelector(".fp-terms").innerHTML = mark(atk.added_terms, quotes); }
            step(ev.error ? "grd" : ev.caught ? "grd ok" : "grd miss", `<span class="who">🛡️ Guardian</span>
              <p><b>${ev.error ? "No answer this round." : ev.caught ? "Caught it." : "Missed it."}</b> ${esc(ev.advice)}</p>
              ${ev.findings.map((f) => `<p class="finding"><span class="tech sm">${esc(TECH[f.technique] || f.technique)}</span> “${esc(f.quote)}” <span class="muted">${esc(f.explanation)}</span></p>`).join("")}
              ${ev.rejected_quotes ? `<p class="muted small">${ev.rejected_quotes} claimed quote${ev.rejected_quotes > 1 ? "s were" : " was"} not on the page and ${ev.rejected_quotes > 1 ? "were" : "was"} thrown out.</p>` : ""}`);
            wait("An AI agent with no protection is shopping on this page");
          } else if (ev.type === "agent") {
            card.querySelector(".rwait")?.remove();
            step(ev.fooled ? "agt bad" : "agt", `<span class="who">🤖 Agent on its own</span>
              <p>${ev.error ? "The agent could not finish this round." : ev.chosen_label ? `Signed Maya up for <b>${esc(ev.chosen_label)}</b>.` : "Did not sign anything."} ${ev.fooled ? "<b class=\"hot\">It fell for the scam.</b>" : ev.chosen_label ? "Not the scam's pick." : ""}</p>
              ${ev.said ? `<p class="muted small">“${esc(ev.said)}”</p>` : ""}`);
          } else if (ev.type === "gate") {
            step(ev.held ? "gte ok" : "gte", `<span class="who">🔒 With SIDE EFFECTS</span>
              <p>${ev.held ? `<b>The gate held.</b> Nothing is signed until Maya sees: ${esc(ev.matches.join("; "))}.` : ev.offer_label ? `Allowed (${esc(ev.verdict.replace("_", " "))}).` : "Nothing to sign."}</p>`);
          } else if (ev.type === "score") {
            $("#scCaught").textContent = `${ev.score.guardian_caught}/${ev.score.rounds}`;
            $("#scFooled").textContent = `${ev.score.agent_risky}/${ev.score.rounds}`;
            $("#scHeld").textContent = `${ev.score.gate_held}/${ev.score.rounds}`;
          }
        }
      }
    } catch (e) {
      $("#scamErr").textContent = e.message; $("#scamErr").hidden = false;
      card?.querySelector(".rwait")?.remove();
    } finally {
      scamRunning = false; btn.disabled = false; btn.textContent = "Run 3 new rounds";
    }
  }
  $("#scamBtn").addEventListener("click", runScam);

  fetch("/api/version").then((r) => r.ok ? r.json() : null).then((v) => { if (v?.version) $("#ver").textContent = "Version " + v.version; }).catch(() => {});

  init().catch((e) => showErr(e.message));

/* ---- BigQuery audit trail of gate decisions (hidden when BigQuery is off) ---- */
async function loadAudit() {
  try {
    const d = await (await fetch("/api/bigquery/audit")).json();
    const box = document.getElementById("audit");
    if (!d.available || !box) return;
    const label = { human_review: "Held for the person", disclose: "Disclosed", no_signal: "No signal" };
    const rows = d.recent.map((r) => `<li><span>${esc(new Date(r.ts).toLocaleString())}</span><span>${esc(r.lender || "Unknown lender")}</span><b class="v-${esc(r.verdict)}">${esc(label[r.verdict] || r.verdict)}</b></li>`).join("");
    box.innerHTML = `<div class="audit-head"><h3>Every decision, on the record</h3><span class="bq-tag">BigQuery</span></div>
      <p class="muted">Each time an agent checks or tries to sign, the gate's decision is written to an audit table in BigQuery. Last 30 days:</p>
      <div class="audit-stats"><div><b>${d.total.toLocaleString()}</b><span>decisions</span></div><div><b>${d.held.toLocaleString()}</b><span>held for the person</span></div><div><b>${d.disclosed.toLocaleString()}</b><span>signed with disclosures</span></div></div>
      ${rows ? `<ul class="audit-list">${rows}</ul>` : ""}`;
    box.hidden = false;
  } catch (e) { /* optional */ }
}
})();
