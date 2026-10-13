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
  let persona = "maya";
  let personas = {};

  async function init() {
    personas = await fetch("/api/agent/personas").then((r) => r.json());
    const box = $("#personas");
    box.innerHTML = Object.entries(personas).map(([k, p]) => `
      <button type="button" role="radio" class="persona" data-k="${k}" aria-checked="${k === persona}">
        <span class="avatar" aria-hidden="true">${esc(p.name[0])}</span>
        <span><strong>${esc(p.name)}</strong><small>${esc(p.about)}</small><em>&ldquo;${esc(p.task)}&rdquo;</em></span>
      </button>`).join("");
    box.addEventListener("click", (e) => {
      const b = e.target.closest(".persona"); if (!b) return;
      persona = b.dataset.k;
      box.querySelectorAll(".persona").forEach((x) => x.setAttribute("aria-checked", x === b));
    });
    $("#runBtn").addEventListener("click", runBoth);
  }

  async function runBoth() {
    $("#err").hidden = true;
    $("#arena").hidden = false;
    $("#runBtn").disabled = true;
    for (const id of ["#laneA", "#laneB"]) { $(id + " .feed").innerHTML = ""; $(id).className = $(id).className.replace(/ (done|stopped|signed)/g, ""); }
    $("#arena").scrollIntoView({ behavior: "smooth", block: "start" });
    await Promise.allSettled([run($("#laneA"), false), run($("#laneB"), true)]);
    $("#runBtn").disabled = false;
    $("#runBtn").textContent = "Run again";
  }

  async function run(lane, gated) {
    const feed = $(".feed", lane);
    lane.classList.add("busy");
    const typing = add(feed, "typing", `<span></span><span></span><span></span>`);
    try {
      const resp = await fetch("/api/agent/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ persona, gated }) });
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
    li.scrollIntoView({ behavior: "smooth", block: "nearest" });
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

  function render(lane, feed, ev) {
    const name = personas[persona]?.name || "them";
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
      case "tool":
        const args = Object.values(ev.args || {}).map((v) => JSON.stringify(v)).join(", ");
        add(feed, "tool", `<code>${esc(ev.name)}(${esc(args.length > 48 ? args.slice(0, 46) + "…" : args)})</code><span>${esc(TOOL_LABEL[ev.name] || "")}</span>`);
        break;
      case "options":
        add(feed, "options", `<div class="store">${esc(ev.store)} &middot; ${esc(ev.item.name)} &middot; <b>${money(ev.item.price)}</b></div>
          <table>${ev.options.map((o) => `<tr><td>${esc(o.label)}<small>${esc(o.terms)}</small></td><td>${o.monthly ? money(o.monthly) + "<small>/mo</small>" : "today"}</td></tr>`).join("")}</table>`);
        break;
      case "check": {
        const r = ev.result;
        add(feed, "check v-" + r.verdict, `<div class="chk-head"><span class="pill" aria-hidden="true"></span>
          <strong>${esc(ev.offer.label)}</strong><span class="verdict">${verdictText(r.verdict)}</span></div>
          ${bars(r.required_disclosures, r.matches_applicant_situation)}`);
        break;
      }
      case "blocked":
        add(feed, "blocked", `<strong>Gate refused the order</strong>The agent tried to sign ${esc(name)} up for ${esc(ev.offer.label)} without asking. SIDE EFFECTS sits inside the checkout, so it couldn't.`);
        break;
      case "order": {
        const unseen = ev.unseen_side_effects || [];
        const hits = unseen.filter((d) => d.matches);
        lane.classList.add(hits.length ? "signed" : "done");
        add(feed, "order" + (hits.length ? " bad" : ""), `<div class="stamp ${hits.length ? "red" : "green"}">${hits.length ? "Signed without asking" : "Order placed"}</div>
          <p>${esc(name)} is now on <b>${esc(ev.offer.label)}</b>.</p>
          ${unseen.length ? `<p class="never">What ${esc(name)} was never told:</p>${bars(unseen)}` : ""}
          ${ev.confirmed_by_person ? `<p class="never ok">${esc(name)} made this choice${ev.disclosures_shown?.length ? `, after seeing ${ev.disclosures_shown.length} side effects` : ""}.</p>` : ""}`);
        break;
      }
      case "ask":
        lane.classList.add("stopped");
        add(feed, "ask", `<div class="stamp red">Stopped before signing</div>
          <p class="msg">${esc(ev.message)}</p>
          <p class="choose">${esc(name)} decides:</p>
          <div class="choices">${ev.options.map((o) => `<button type="button" data-o="${esc(o.id)}">${esc(o.label)}<small>${o.check ? verdictText(o.check.verdict) : "No new credit"}</small></button>`).join("")}</div>`)
          .addEventListener("click", (e) => choose(e, lane, feed));
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
    const r = await fetch("/api/agent/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ persona, offer_id: b.dataset.o }) });
    if (r.ok) render(lane, feed, await r.json());
  }

  function verdictText(v) {
    return { human_review: "Needs your OK", disclose: "Show before signing", no_signal: "No signal" }[v] || v;
  }

  init().catch((e) => { const el = $("#err"); el.textContent = e.message; el.hidden = false; });
})();
