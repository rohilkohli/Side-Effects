/* Leaflet page flows on top of app.js:
   - a live 5-stage multi-agent trace while the leaflet is made, then a clickable trace in the leaflet
   - "What if": toggling the person's situation re-runs the deterministic gate (POST /api/v1/check) and
     moves the warnings that fit them to the top, on the leaflet and on the Klarna sample
   - "Advert vs contract": the advert's own claims side by side with the verified contract clauses
   Every number shown comes from the server's data (leaflet JSON or /api/v1/check). */
"use strict";
(() => {
  const STAGES = ["Intake", "Evidence (PRR)", "Clause verifier", "Composer", "Deterministic gate"];
  const STAGE_OF = { read: 0, match: 1, signal: 1, clauses: 2, compose: 3 };
  const KIND = { gemini: "Gemini", code: "Code", "gemini+code": "Gemini + code check" };
  const SHORT = { irregular_income: "Irregular income", carries_balance: "Carries a balance", other_bnpl: "Uses other pay-later plans",
    new_to_credit: "New to credit", big_purchase: "Big purchase", travels: "Travels abroad" };
  const ms = (n) => `${Number(n).toLocaleString()} ms`;

  /* ---------- FLIP: animate elements to their new place after a reorder ---------- */
  function flip(els, mutate) {
    const before = new Map(els.map((e) => [e, e.getBoundingClientRect().top]));
    mutate();
    els.forEach((e) => {
      const dy = before.get(e) - e.getBoundingClientRect().top; if (!dy) return;
      e.animate([{ transform: `translateY(${dy}px)` }, { transform: "none" }], { duration: 380, easing: "cubic-bezier(0.22,1,0.36,1)" });
    });
  }
  /* Matching items first, in their original order otherwise. */
  function reorder(list, items, fits) {
    const orig = items.slice().sort((a, b) => (+a.dataset.o) - (+b.dataset.o));
    const sorted = [...orig.filter(fits), ...orig.filter((x) => !fits(x))];
    const inDom = [...list.children].filter((c) => items.includes(c));
    const anchor = inDom[inDom.length - 1].nextSibling;  // the group's items are contiguous; keep them where they are
    flip(items, () => sorted.forEach((x) => list.insertBefore(x, anchor)));
  }

  /* ---------- Gate banner (shared by the sample and the leaflet) ---------- */
  async function gateCall(issuer, productType, profile) {
    const t0 = performance.now();
    const r = await fetch("/api/v1/check", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ issuer, product_type: productType, applicant_profile: profile }) });
    if (!r.ok) throw new Error(`The gate answered ${r.status}`);
    return { d: await r.json(), ms: Math.round(performance.now() - t0) };
  }
  function banner(el, d, took) {
    const held = d.verdict === "human_review";
    el.classList.remove("held", "pass"); void el.offsetWidth; el.classList.add(held ? "held" : "pass", "flash");
    el.innerHTML = held
      ? `<b>HELD FOR THE PERSON</b><span>human_review triggered via /api/v1/check · severity ${esc(d.severity)}${took != null ? ` · ${ms(took)}` : ""}</span>`
      : `<b>PASS</b><span>${d.verdict === "disclose" ? "Standard Disclosure" : "No complaint signal"} · <code>${esc(d.verdict)}</code> · severity ${esc(d.severity)}${took != null ? ` · ${ms(took)}` : ""}</span>`;
  }

  /* ---------- Klarna sample: live what-if ---------- */
  const sx = document.getElementById("sxWhatIf");
  if (sx) {
    const items = [...document.querySelectorAll("#sxList > li[data-label]")];
    items.forEach((li, i) => (li.dataset.o = i));
    let seq = 0;
    sx.addEventListener("click", async (e) => {
      const b = e.target.closest(".wi-pill"); if (!b) return;
      b.setAttribute("aria-pressed", String(b.getAttribute("aria-pressed") !== "true"));
      const keys = [...sx.querySelectorAll('.wi-pill[aria-pressed="true"]')].map((x) => x.dataset.key);
      const my = ++seq; document.getElementById("sxBanner").classList.add("busy");
      try {
        const { d, ms: took } = await gateCall("Klarna", "bnpl", keys);
        if (my !== seq) return;
        banner(document.getElementById("sxBanner"), d, took);
        const held = d.verdict === "human_review";
        document.getElementById("sxPill").textContent = held ? "Held for the person" : "Disclose";
        document.getElementById("sxPill").classList.toggle("ok", !held);
        document.getElementById("sxHead").textContent = `${d.severity[0] + d.severity.slice(1).toLowerCase()} risk for this profile`;
        document.getElementById("sxSub").innerHTML = `Top signal 3.25&times; more often than other pay-later lenders &middot; gate verdict <code>${esc(d.verdict)}</code>`;
        const fits = (li) => d.matches_applicant_situation.includes(li.dataset.label);
        items.forEach((li) => li.classList.toggle("fit", fits(li)));
        reorder(document.getElementById("sxList"), items, fits);
      } catch (err) { document.getElementById("sxBanner").innerHTML = `<b>Gate unavailable</b><span>${esc(err.message)}</span>`; }
      finally { if (my === seq) document.getElementById("sxBanner").classList.remove("busy"); }
    });
  }

  /* ---------- Live pipeline while the leaflet is made ---------- */
  const progress = document.getElementById("progress");
  const live = document.createElement("div");
  live.className = "tr-live"; live.setAttribute("aria-label", "Multi-agent pipeline");
  progress.querySelector("h2").after(live);
  const resetLive = () => { live.innerHTML = STAGES.map((s, i) => `<div class="tr-node" style="--i:${i}"><i></i><b>${i + 1}</b><span>${s}</span></div>`).join(""); };
  const node = (i) => live.children[i];
  const origHandle = handle;
  // app.js calls handle() for every streamed event; light up the stage it belongs to as well.
  handle = function (ev) {  // eslint-disable-line no-global-assign
    if (ev.step === "read" && ev.status === "running") resetLive();
    const i = STAGE_OF[ev.step];
    if (i != null && node(i)) {
      if (ev.status === "running") { node(i).classList.remove("done"); node(i).classList.add("on"); }
      else if (ev.status === "done" || ev.status === "skipped") {
        if (ev.step !== "match") { node(i).classList.remove("on"); node(i).classList.add(ev.status === "skipped" ? "skip" : "done"); }
      } else if (ev.status === "error") node(i).classList.add("err");
    }
    if (ev.step === "leaflet" && node(4)) { node(4).classList.add("done"); }
    return origHandle(ev);
  };
  resetLive();

  /* ---------- After a leaflet renders: trace, what-if and advert vs contract ---------- */
  const origRender = render;
  render = function (lf) {  // eslint-disable-line no-global-assign
    origRender(lf);
    try { traceHtml(lf); whatIf(lf); } catch (e) { console.warn("leaflet extras", e); }
  };

  function traceHtml(lf) {
    const t = lf.agent_trace; if (!t?.length) return;
    const total = t.reduce((a, s) => a + (s.ms || 0), 0);
    const el = document.createElement("details");
    el.className = "trace"; el.open = innerWidth > 700;
    el.innerHTML = `<summary><span class="tr-dot"></span><b>Multi-Agent Pipeline Trace</b>
        <span class="tr-meta">${t.length} stages · <b class="${lf.unsourced_numbers ? "bad" : "ok"}">${lf.unsourced_numbers} hallucinated number${lf.unsourced_numbers === 1 ? "" : "s"}</b> · ${ms(total)}</span></summary>
      <ol class="tr-steps">${t.map((s, i) => `<li style="--i:${i}"><button type="button" class="tr-step ${esc(s.status)}" data-i="${i}">
          <span class="tr-n">${i + 1}</span><span class="tr-b"><b>${esc(s.stage)}</b><small>${esc(KIND[s.kind] || s.kind)}${s.model ? " · " + esc(s.model) : ""} · ${ms(s.ms)}</small>
          <em>${esc(s.summary)}</em></span></button></li>`).join("")}</ol>
      <p class="tr-note">Gemini reads and writes; code counts. Click a stage to see exactly what it produced. "Hallucinated numbers" counts any number in Gemini's words that is not in the data.</p>`;
    document.getElementById("leaflet").querySelector(".lf-tabs").before(el);
    el.querySelector(".tr-steps").addEventListener("click", (e) => { const b = e.target.closest(".tr-step"); if (b) drawer(t[+b.dataset.i], +b.dataset.i); });
  }

  /* Dark drawer with a stage's real output. */
  const dr = document.createElement("aside");
  dr.className = "tr-drawer"; dr.hidden = true; dr.setAttribute("role", "dialog"); dr.setAttribute("aria-label", "Stage detail");
  document.body.appendChild(dr);
  const closeDr = () => { dr.classList.remove("in"); setTimeout(() => (dr.hidden = true), 220); };
  dr.addEventListener("click", (e) => { if (e.target.closest(".tr-x")) closeDr(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !dr.hidden) closeDr(); });
  const json = (v) => esc(JSON.stringify(v, null, 2)).replace(/&quot;([^&]+?)&quot;:/g, '<i class="k">"$1"</i>:').replace(/: (-?\d+(\.\d+)?)/g, ': <i class="n">$1</i>');
  function drawer(s, i) {
    dr.innerHTML = `<header><div><small>Stage ${i + 1} of 5 · ${esc(KIND[s.kind] || s.kind)}</small><b>${esc(s.stage)}</b></div><button type="button" class="tr-x" aria-label="Close">×</button></header>
      <dl><dt>Agent</dt><dd>${esc(s.agent)}</dd><dt>Model</dt><dd>${esc(s.model || "none (deterministic code)")}</dd>
        <dt>Started</dt><dd>+${ms(s.started_ms)}</dd><dt>Took</dt><dd>${ms(s.ms)}</dd><dt>Status</dt><dd>${esc(s.status)}</dd><dt>Result</dt><dd>${esc(s.summary)}</dd></dl>
      <pre>${json(s.output)}</pre>`;
    dr.hidden = false; requestAnimationFrame(() => dr.classList.add("in")); dr.querySelector(".tr-x").focus();
  }

  /* What if: re-run the gate for this leaflet's lender with a different situation. */
  function whatIf(lf) {
    const p = lf.product, issuer = p.matched_company || p.issuer_name || p.brand_name;
    const overview = document.querySelector('#leaflet .lf-panel[data-t="overview"]');
    if (!issuer || !overview) return;
    const keys = new Set(profileKeys);
    const box = document.createElement("section");
    box.className = "wi";
    box.innerHTML = `<div class="wi-head"><b>What if your situation changes?</b><span class="small muted">Toggle to re-run the deterministic gate live</span></div>
      <div class="wi-row">${Object.entries(SHORT).map(([k, label]) => `<button type="button" class="wi-pill" data-key="${k}" aria-pressed="${keys.has(k)}">${label}</button>`).join("")}</div>
      <div class="wi-banner" aria-live="polite"></div>`;
    overview.prepend(box);
    const ban = box.querySelector(".wi-banner");
    if (lf.gate) banner(ban, lf.gate, null); else ban.innerHTML = "<b>No gate decision</b><span>No lender to check</span>";
    // Remember each warning's place so a reorder can be undone.
    const groups = groupsOf();
    let seq = 0;
    box.addEventListener("click", async (e) => {
      const b = e.target.closest(".wi-pill"); if (!b) return;
      const on = b.getAttribute("aria-pressed") !== "true"; b.setAttribute("aria-pressed", String(on));
      on ? keys.add(b.dataset.key) : keys.delete(b.dataset.key);
      const my = ++seq; ban.classList.add("busy");
      try {
        const { d, ms: took } = await gateCall(issuer, p.product_type, [...keys]);
        if (my !== seq) return;
        banner(ban, d, took);
        const fits = (el) => d.matches_applicant_situation.includes(el.dataset.label);
        groups.forEach(({ parent, items }) => { items.forEach((x) => x.classList.toggle("fit", fits(x))); reorder(parent, items, fits); });
      } catch (err) { ban.innerHTML = `<b>Gate unavailable</b><span>${esc(err.message)}</span>`; }
      finally { if (my === seq) ban.classList.remove("busy"); }
    });
  }
  /* Groups of warnings that move together: each run of side effects in the leaflet, and the box's tiles. */
  function groupsOf() {
    const out = [], lf = document.getElementById("leaflet");
    const tiles = [...lf.querySelectorAll(".tiles > .tile")];
    tiles.forEach((t, i) => { t.dataset.o = i; t.dataset.label = t.querySelector(".tl").textContent; t.insertAdjacentHTML("beforeend", '<em class="fit-b">Matches your situation</em>'); });
    if (tiles.length) out.push({ parent: tiles[0].parentElement, items: tiles });
    let run = [];
    const flush = () => { if (run.length) out.push({ parent: run[0].parentElement, items: run }); run = []; };
    lf.querySelectorAll('.lf-panel[data-t="effects"] > *').forEach((el) => {
      if (el.classList.contains("se")) {
        el.dataset.o = run.length; el.dataset.label = el.querySelector(".se-name").textContent;
        el.querySelector(".tags")?.insertAdjacentHTML("beforeend", '<span class="t fit-t">Matches your situation</span>');
        run.push(el);
      } else flush();
    });
    flush();
    return out;
  }

  /* ---------- Advert vs contract ---------- */
  const STEMS = ["interest", "fee", "late", "pay", "free", "credit", "cancel", "refund", "debit", "charge", "approv", "instal", "limit", "rate", "apr", "dispute"];
  const stems = (t) => STEMS.filter((s) => t.toLowerCase().includes(s));
  const vs = document.createElement("div");
  vs.className = "vs-drawer"; vs.hidden = true; vs.setAttribute("role", "dialog"); vs.setAttribute("aria-label", "Advert vs contract");
  document.body.appendChild(vs);
  const vsBtn = document.createElement("button");
  vsBtn.type = "button"; vsBtn.className = "lfbar-btn"; vsBtn.id = "vsBtn"; vsBtn.innerHTML = '<span class="lg-only">Advert vs contract</span><span class="sm-only">Ad vs contract</span>';
  document.getElementById("editLeaflet").before(vsBtn);
  vsBtn.addEventListener("click", () => openVs(leaflet));
  vs.addEventListener("click", (e) => { if (e.target === vs || e.target.closest(".vs-x")) closeVs(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !vs.hidden) closeVs(); });
  const closeVs = () => { vs.classList.remove("in"); setTimeout(() => (vs.hidden = true), 220); };
  function openVs(lf) {
    if (!lf) return;
    const p = lf.product;
    const claims = [...(p.headline_claims || []).map((c) => ({ t: c, k: "Headline claim" })), ...(p.stated_terms || []).map((s) => ({ t: `${s.name}: ${s.value}`, k: "Stated term" }))];
    const clauses = [...lf.side_effects.filter((l) => l.clause).map((l) => ({ label: l.label, x: l.reported_x, n: l.n, c: l.clause })),
      ...lf.contract_only.map((c) => ({ label: c.label, x: null, c }))];
    const unsaid = p.left_unsaid || [];
    vs.innerHTML = `<div class="vs-card"><header><div><b>Advert vs contract</b><small>${esc(p.brand_name || p.product_name || "This offer")} · what they promise, next to what the contract says</small></div><button type="button" class="vs-x" aria-label="Close">×</button></header>
      <div class="vs-cols">
        <section><h4>📣 The advert says</h4>${claims.length ? claims.map((c, i) => `<div class="vs-claim" style="--i:${i}" data-s="${stems(c.t).join(" ")}"><small>${c.k}</small>“${esc(c.t)}”</div>`).join("") : '<p class="muted small">No advert was given, so there are no claims to compare.</p>'}
          ${unsaid.length ? `<h5>Not mentioned in the advert</h5><ul>${unsaid.map((u) => `<li>${esc(u)}</li>`).join("")}</ul>` : ""}</section>
        <section><h4>📄 The contract says <span class="vs-v">verified word for word</span></h4>${clauses.length ? clauses.map((c, i) => `<div class="vs-clause" style="--i:${i + claims.length}" data-s="${stems(c.c.quote + " " + c.label).join(" ")}">
            <div class="vs-ch"><b>${esc(c.label)}</b>${c.x ? `<span class="vs-prr">${c.x}× · ${c.n.toLocaleString()} complaints</span>` : '<span class="vs-prr none">contract only</span>'}</div>
            <q><mark>${esc(c.c.quote)}</mark></q><small>Page ${c.c.page}${c.c.section ? ", " + esc(c.c.section) : ""}</small></div>`).join("")
          : `<p class="muted small">${lf.contract_pages ? "No clause behind these side effects was found word for word in the contract." : "No contract was given. Add the contract to see its clauses here."}</p>`}
          ${lf.rejected_quotes ? `<p class="vs-rej">${lf.rejected_quotes} quote${lf.rejected_quotes > 1 ? "s" : ""} Gemini offered could not be found in the contract and ${lf.rejected_quotes > 1 ? "were" : "was"} thrown away.</p>` : ""}</section>
      </div><p class="vs-tip">Hover or tap a claim to light up the clauses about the same thing.</p></div>`;
    vs.hidden = false; requestAnimationFrame(() => vs.classList.add("in"));
    const light = (el) => {
      vs.querySelectorAll(".lit").forEach((x) => x.classList.remove("lit"));
      if (!el) return; const s = el.dataset.s.split(" ").filter(Boolean); el.classList.add("lit");
      vs.querySelectorAll(".vs-clause").forEach((c) => { if (s.some((k) => c.dataset.s.split(" ").includes(k))) c.classList.add("lit"); });
    };
    vs.querySelectorAll(".vs-claim").forEach((c) => { c.addEventListener("mouseenter", () => light(c)); c.addEventListener("click", () => light(c)); });
    vs.querySelector(".vs-cols").addEventListener("mouseleave", () => light(null));
  }

  /* The voice agent asks what is on screen: the lender in front of the person and their situation. */
  window.SEContext = () => {
    const p = leaflet?.product;
    const wi = document.querySelector("#leaflet:not([hidden]) .wi");
    const keys = wi ? [...wi.querySelectorAll('.wi-pill[aria-pressed="true"]')].map((b) => b.dataset.key) : [...profileKeys];
    return { lender: p && !document.getElementById("leaflet").hidden ? (p.brand_name || p.issuer_name || p.matched_company) : null, profile: keys };
  };
})();
