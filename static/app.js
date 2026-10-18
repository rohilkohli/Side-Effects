"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const STEPS = {
  read: ["Reading your offer", "Gemini looks at the photo, PDF or text"],
  match: ["Finding the lender", "Matching it to public complaint records"],
  signal: ["Checking 136,270 complaints", "The same test drug regulators use for side effects"],
  clauses: ["Reading the contract", "Gemini finds the clause behind each problem"],
  compose: ["Writing your leaflet", "In plain words, for your situation"],
};
const STATUS_LABEL = {
  persisting: "Still reported in 2026",
  emerging: "New in 2026",
  fading: "Weaker in 2026",
  not_seen_recently: "Not seen in 2026 data",
  single_period: "",
};

let profileKeys = new Set();
let leaflet = null;
let history = [];

async function init() {
  const meta = await fetch("/api/meta").then((r) => r.json());
  $("companies").innerHTML = meta.companies.map((c) => `<option value="${esc(c)}">`).join("");
  $("profileChips").innerHTML = meta.profiles
    .map((p) => `<button type="button" class="chip" aria-pressed="false" data-key="${p.key}">${esc(p.label)}</button>`).join("");
  $("profileChips").addEventListener("click", (e) => {
    const b = e.target.closest(".chip"); if (!b) return;
    const on = b.getAttribute("aria-pressed") !== "true";
    b.setAttribute("aria-pressed", on); on ? profileKeys.add(b.dataset.key) : profileKeys.delete(b.dataset.key);
  });
}

function showFile(input, label, drop) {
  input.addEventListener("change", () => {
    const names = [...input.files].map((f) => f.name).join(", ");
    if (names) { $(label).textContent = names; $(drop).classList.add("has"); }
  });
}
showFile($("images"), "imagesName", "photoDrop");
showFile($("contract"), "contractName", "pdfDrop");

$("sampleBtn").addEventListener("click", async () => {
  const [flyer, contract] = await Promise.all([
    fetch("/api/samples/fictional-bnpl-flyer").then((r) => r.json()),
    fetch("/api/samples/fictional-bnpl-agreement").then((r) => r.json()),
  ]);
  $("flyerText").value = flyer.text; $("contractText").value = contract.text;
  $("productType").value = "bnpl";
  document.querySelectorAll(".paste")[0].open = true;
});

$("goBtn").addEventListener("click", run);

async function run() {
  const fd = new FormData();
  [...$("images").files].forEach((f) => fd.append("images", f));
  if ($("contract").files[0]) fd.append("contract", $("contract").files[0]);
  fd.append("flyer_text", $("flyerText").value);
  fd.append("contract_text", $("contractText").value);
  fd.append("issuer", $("issuer").value);
  fd.append("product_type", $("productType").value);
  fd.append("profile", [...profileKeys].join(","));
  fd.append("note", $("note").value);
  const hasInput = $("images").files.length || $("contract").files.length || $("flyerText").value.trim() || $("contractText").value.trim();
  if (!hasInput) return showError("Add a photo of the offer, its contract, or paste some text first.");
  showError("");

  $("goBtn").disabled = true;
  $("leaflet").hidden = true; $("pharmFab").hidden = true; $("pharm").hidden = true;
  $("progress").hidden = false;
  $("steps").innerHTML = Object.entries(STEPS).map(([k, [who, what]]) =>
    `<li id="st-${k}"><span class="ic">○</span><div><div class="who">${who}</div><div class="what">${what}</div></div></li>`).join("");
  $("progress").scrollIntoView({ behavior: "smooth", block: "center" });

  try {
    const resp = await fetch("/api/leaflet", { method: "POST", body: fd });
    if (!resp.ok) throw new Error(await resp.text());
    const reader = resp.body.getReader(); const dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n")) >= 0) { handle(JSON.parse(buf.slice(0, i))); buf = buf.slice(i + 1); }
    }
  } catch (err) {
    showError("The leaflet could not be made. " + (err.message || ""));
  } finally { $("goBtn").disabled = false; }
}

function handle(ev) {
  if (ev.step === "leaflet") { render(ev.leaflet); return; }
  if (ev.status === "error") { showError(ev.detail); return; }
  const li = $("st-" + ev.step); if (!li) return;
  li.querySelector(".ic").innerHTML = ev.status === "running" ? '<span class="spin"></span>' : ev.status === "skipped" ? "–" : "✓";
  li.querySelector(".what").textContent = ev.detail;
}

function showError(msg) { $("formError").textContent = msg; $("formError").hidden = !msg; }

function scale(l) {
  const max = Math.max(6, Math.ceil((l.ci95[1] || l.reported_x) + 0.5));
  const pct = (v) => Math.min(100, (v / max) * 100);
  return `<div class="scale" aria-hidden="true"><div class="axis"></div>
    <div class="peer" style="left:${pct(1)}%"></div>
    <div class="ci" style="left:${pct(l.ci95[0])}%;width:${pct(l.ci95[1]) - pct(l.ci95[0])}%"></div>
    <div class="pt" style="left:${pct(l.reported_x)}%"></div></div>
    <div class="scale-legend"><span>0</span><span>similar lenders = 1×</span><span>${max}×</span></div>`;
}

function clauseHtml(c) {
  if (!c) return "";
  return `<div class="clause"><span class="ref">In this contract: page ${c.page}${c.section ? ", " + esc(c.section) : ""}</span>“${esc(c.quote)}”
    ${c.how_it_causes ? `<div class="small muted" style="font-family:var(--sans);margin-top:6px">${esc(c.how_it_causes)}</div>` : ""}</div>`;
}

function sideEffect(l) {
  const level = l.scope === "bank"
    ? `<span class="t bank">Bank-level complaint signal: ${esc(short(l.company))}</span>`
    : `<span class="t class">Whole product category (all BNPL lenders)</span>`;
  const status = STATUS_LABEL[l.status] ? `<span class="t ${l.status === "emerging" ? "new" : ""}">${STATUS_LABEL[l.status]}</span>` : "";
  const why = l.scope === "bank"
    ? `${(l.share_company * 100).toFixed(1)}% of complaints about ${esc(short(l.company))} are about this, vs ${(l.share_peers * 100).toFixed(1)}% at similar lenders (${l.n.toLocaleString()} reports, ${esc(l.period)}).`
    : `${(l.share_company * 100).toFixed(1)}% of complaints about BNPL lenders are about this, vs ${(l.share_peers * 100).toFixed(1)}% at other lenders (${l.n.toLocaleString()} reports).`;
  const recent = l.recent ? ` In ${esc(l.recent.period)} it was ${l.recent.reported_x}× (${l.recent.n} reports).` : "";
  const stories = (l.stories || []).map((s) =>
    `<div class="story">“${esc(s.text)}”<div class="meta">Real complaint to the US CFPB, ${esc(s.date)}, #${esc(s.complaint_id)}</div></div>`).join("");
  return `<div class="se ${l.relevant_to_you ? "you" : ""}">
    <button aria-expanded="false"><div class="se-head"><span class="se-name">${esc(l.label)}</span>
      <span class="se-x">${l.reported_x}× <small>more often than similar lenders</small></span></div>
      <div class="tags">${level}${l.clause ? '<span class="t clause">Clause in this contract</span>' : ""}${status}${l.relevant_to_you ? '<span class="t you">Matters for you</span>' : ""}</div>
      ${scale(l)}</button>
    <div class="se-body">
      ${l.plain_explanation ? `<p>${esc(l.plain_explanation)}</p>` : ""}
      <p class="small muted">${why}${recent} 95% interval ${l.ci95[0]}–${l.ci95[1]}×.</p>
      ${l.clause ? clauseHtml(l.clause) : '<p class="noclause">No contract clause causes this one; it comes from how the company handles customers in practice.</p>'}
      ${stories}
      ${l.how_to_reduce_risk ? `<p class="tip">${esc(l.how_to_reduce_risk)}</p>` : ""}
    </div></div>`;
}

function contractOnly(c) {
  return `<div class="se ${c.relevant_to_you ? "you" : ""}">
    <button aria-expanded="false"><div class="se-head"><span class="se-name">${esc(c.label)}</span><span class="se-x"><small>no complaint statistics</small></span></div>
      <div class="tags"><span class="t clause">Clause in this contract</span>${c.relevant_to_you ? '<span class="t you">Matters for you</span>' : ""}</div></button>
    <div class="se-body">${c.plain_explanation ? `<p>${esc(c.plain_explanation)}</p>` : ""}${clauseHtml(c)}
      ${c.how_to_reduce_risk ? `<p class="tip">${esc(c.how_to_reduce_risk)}</p>` : ""}</div></div>`;
}

function disclosureHtml(d) {
  return `<p class="small muted" style="margin-top:12px">What customers complained to ${esc(d.bank)} about, in the bank's own published figures (${esc(d.period)}, ${d.total.toLocaleString()} complaints):</p>
    ${d.grounds.map((g) => `<div class="lg"><span>${esc(g.ground)}</span><span class="lg-bar"><i style="width:${g.share * 100}%"></i></span><span class="small">${(g.share * 100).toFixed(1)}%</span></div>`).join("")}
    <p class="small muted">Self-reported by the bank under RBI rules; only its largest complaint categories are published. <a href="${esc(d.url)}" target="_blank" rel="noopener">Source</a></p>`;
}

function localHtml(le) {
  if (!le.groups.length) return le.disclosure ? `<div class="local"><p class="small muted" style="margin-top:16px">Local evidence: ${esc(le.country)}</p>${disclosureHtml(le.disclosure)}</div>` : "";
  const max = Math.max(...le.groups.map((g) => g.per_1000_cards));
  const bars = le.groups.map((g) => `<div class="lg ${le.group && le.group.label === g.label ? "on" : ""}">
      <span>${esc(g.label)}</span><span class="lg-bar"><i style="width:${(g.per_1000_cards / max) * 100}%"></i></span>
      <span class="small">${g.per_1000_cards} <span class="muted">(${g.x_vs_india}×)</span></span></div>`).join("");
  return `<div class="local"><p class="small muted" style="margin-top:16px">Local evidence: ${esc(le.country)}. Complaints to the RBI Ombudsman per 1,000 credit cards, ${esc(le.source.period)}:</p>
    <p>${esc(le.note)}</p>${bars}
    <p class="small muted">Unlike US data this is a true rate: the RBI publishes complaints per 1,000 cards. Bank-group level, not this card.</p>
    ${le.disclosure ? disclosureHtml(le.disclosure) : ""}</div>`;
}

function short(name) {
  return String(name || "").replace(/,? (INC\.?|N\.A\.|NATIONAL ASSOCIATION|FINANCIAL CORPORATION|COMPANY|& CO\.|Holdings, Inc|Inc\.|LLC|AB)$/i, "").trim();
}

const TYPE_LABEL = { credit_card: "Credit card", bnpl: "Buy Now Pay Later", personal_loan: "Personal loan" };

function boxHtml(lf) {
  const p = lf.product;
  const lines = [...lf.side_effects].sort((a, b) => b.reported_x - a.reported_x);
  const mine = lines.filter((l) => l.relevant_to_you).length + lf.contract_only.filter((c) => c.relevant_to_you).length;
  const top = lines[0];
  const warn = lines.length
    ? `<b>${lines.length} side effect${lines.length > 1 ? "s" : ""}</b> reported up to <b>${top.reported_x}×</b> more often than at similar lenders.${mine ? ` <b>${mine} match${mine > 1 ? "" : "es"} your situation.</b>` : ""}`
    : lf.contract_only.length ? `No complaint statistics for this lender. <b>${lf.contract_only.length} risk${lf.contract_only.length > 1 ? "s" : ""}</b> found in the contract itself.`
    : "No side effect is reported disproportionately often for this lender.";
  const tiles = lines.slice(0, 6).map((l) => `<div class="tile ${l.relevant_to_you ? "you" : ""}">
      <span class="tx">${l.reported_x}×</span><span class="tl">${esc(l.label)}</span>
      <span class="ts">${l.scope === "bank" ? "this lender" : "all BNPL lenders"}${l.relevant_to_you ? " · fits you" : ""}${l.clause ? " · clause p." + l.clause.page : ""}</span></div>`).join("");
  return `<div class="box ${lines.length ? "" : "clean"}">
    <div class="box-front">
      <div class="box-top"><span class="pill" aria-hidden="true"></span>SIDE EFFECTS <span>Leaflet enclosed</span></div>
      <div class="box-name">${esc(p.brand_name || p.product_name || "This product")}</div>
      <div class="box-dose">${esc(p.product_name || "")}${p.product_type ? " · " + esc(TYPE_LABEL[p.product_type] || p.product_type) : ""}${p.jurisdiction ? " · " + esc(p.jurisdiction) : ""}</div>
      ${p.headline_claims?.length ? `<div class="box-claim">“${esc(p.headline_claims[0])}”</div>` : ""}
      <div class="box-warn"><span class="tri" aria-hidden="true">▼</span><span>${warn}</span></div>
    </div>
    ${tiles ? `<div class="tiles">${tiles}</div>` : ""}
  </div>`;
}

function render(lf) {
  leaflet = lf; history = [];
  const p = lf.product;
  const bank = lf.side_effects.filter((l) => l.scope === "bank");
  const klass = lf.side_effects.filter((l) => l.scope !== "bank");
  const byId = Object.fromEntries([...lf.side_effects, ...lf.contract_only].map((l) => [l.id, l.label]));
  const cite = (ids) => ids.length ? ` <span class="small muted">(${ids.map((i) => esc(byId[i] || "")).join("; ")})</span>` : "";

  const nEffects = lf.side_effects.length + lf.contract_only.length;
  const hasAlt = lf.interactions.length || lf.alternatives.length;
  $("leaflet").innerHTML = boxHtml(lf) + `
    <div class="lf-tabs" role="tablist" aria-label="Leaflet sections">
      <button type="button" role="tab" data-t="overview" aria-selected="true">Overview</button>
      <button type="button" role="tab" data-t="effects" aria-selected="false">Side effects${nEffects ? ` <span class="count">${nEffects}</span>` : ""}</button>
      ${hasAlt ? `<button type="button" role="tab" data-t="alt" aria-selected="false">Alternatives</button>` : ""}
      <button type="button" role="tab" data-t="how" aria-selected="false">How we know</button>
    </div>
    <div class="lf-panel" data-t="overview">
    <div class="lf-kicker">Package leaflet: information for the borrower</div>
    <div class="lf-sub">${esc(p.product_name)}${p.matched_company ? " · Lender in complaint records: " + esc(p.matched_company) : ""}</div>
    <div class="lf-box"><strong>Read all of this leaflet carefully before you sign.</strong>
      <ul><li>Keep this leaflet. You may need to read it again.</li>
      <li>The numbers compare how often people report a problem here versus at similar lenders. They are not the chance it will happen to you.</li>
      <li>If you have questions, ask the pharmacist.</li></ul></div>

    <h3><span class="num">1.</span>What ${esc(p.brand_name || "this product")} is</h3>
    <p>${esc(lf.what_it_is)}</p>
    ${p.headline_claims?.length ? `<p class="small">The advert promises: ${p.headline_claims.map((c) => `“${esc(c)}”`).join(", ")}.</p>` : ""}
    ${p.left_unsaid?.length ? `<p class="small"><strong>Not mentioned in the advert:</strong> ${p.left_unsaid.map(esc).join("; ")}.</p>` : ""}

    <h3><span class="num">2.</span>Before you sign</h3>
    <div class="foryou"><strong>For you</strong> <span class="small muted">(${esc(lf.profile)})</span><br>${esc(lf.for_you)}</div>
    ${lf.contraindications.length ? `<ul class="contra">${lf.contraindications.map((c) => `<li><strong>${esc(c.condition)}</strong> ${esc(c.reason)}${cite(c.based_on)}</li>`).join("")}</ul>` : ""}

    <button type="button" class="lf-next" data-go="effects">See the side effects ›</button>
    </div>
    <div class="lf-panel" data-t="effects" hidden>
    <h3><span class="num">3.</span>Possible side effects</h3>
    ${bank.length ? `<p class="small muted">Found in real complaints about this lender, compared with similar lenders. Tap one for the clause and real stories.</p>${bank.map(sideEffect).join("")}` : ""}
    ${klass.length ? `<p class="small muted" style="margin-top:16px">Reported across Buy Now Pay Later lenders as a group, compared with other lenders:</p>${klass.map(sideEffect).join("")}` : ""}
    ${!bank.length && !klass.length ? `<p>${lf.product.matched_company ? "No side effect is reported disproportionately often for this lender compared with its peers." : "We have no complaint statistics for this lender."}</p>` : ""}
    ${lf.local_evidence ? localHtml(lf.local_evidence) : ""}
    ${lf.contract_only.length ? `<p class="small muted" style="margin-top:16px">Found only in the contract (no complaint statistics):</p>${lf.contract_only.map(contractOnly).join("")}` : ""}

    </div>
    <div class="lf-panel" data-t="alt" hidden>
    ${lf.interactions.length ? `<h3><span class="num">4.</span>Interactions</h3><ul>${lf.interactions.map((i) => `<li><strong>With ${esc(i.with_what)}:</strong> ${esc(i.effect)}${cite(i.based_on)}</li>`).join("")}</ul>` : ""}

    ${lf.alternatives.length ? `<h3><span class="num">5.</span>Consider a generic</h3>
      <p class="small muted">Similar lenders without these complaint signals. This is about complaint patterns only, not price or approval.</p>
      ${lf.alternatives.map((a) => `<div class="alt"><span>${esc(short(a.company))}</span><span class="small muted">${a.total_signals ? a.total_signals + " other signal" + (a.total_signals > 1 ? "s" : "") : "no signals"} · ${a.complaints.toLocaleString()} complaints</span></div>`).join("")}` : ""}

    </div>
    <div class="lf-panel" data-t="how" hidden>
    <h3><span class="num">6.</span>How we know</h3>
    <ul class="how">
      <li>${esc(lf.coverage)}</li>
      ${lf.local_evidence ? `<li>${esc(lf.local_evidence.country)}: ${esc(lf.local_evidence.source.name)}.</li>` : ""}
      <li>Statistic: the proportional reporting ratio drug regulators use for adverse-event reports. ${esc(lf.evidence.rule)}</li>
      ${Object.values(lf.evidence.datasets).map((d) => `<li>${esc(d.description)}</li>`).join("")}
      <li>Gemini reads complaint stories to separate real harms from copy-paste templates (${lf.evidence.templates_excluded} of ${lf.evidence.labelled_narratives} in our checked sample were templates and are excluded).</li>
      ${lf.contract_pages ? `<li>Gemini read all ${lf.contract_pages} contract pages. Every quote above was checked word for word against the contract${lf.rejected_quotes ? `; ${lf.rejected_quotes} that could not be found were discarded` : ""}.</li>` : ""}
      <li>${esc(lf.evidence.disclaimer)}</li>
    </ul>
    <details class="devbox"><summary>For developers and AI agents</summary>
    <p class="small">This leaflet is machine-readable, so an agent applying for credit on someone's behalf can read it before signing.</p>
    <div class="agentbox">GET /api/v1/leaflets/${esc(lf.id)}<br>POST /api/v1/check {"issuer": "${esc(p.matched_company || p.issuer_name)}", "product_type": "${esc(p.product_type)}", "applicant_profile": [...]}</div></details>
    </div>
  `;
  const tab = (name) => {
    $("leaflet").querySelectorAll(".lf-tabs [data-t]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.t === name)));
    $("leaflet").querySelectorAll(".lf-panel").forEach((p) => { p.hidden = p.dataset.t !== name; });
  };
  $("leaflet").querySelector(".lf-tabs").addEventListener("click", (e) => { const b = e.target.closest("[data-t]"); if (b) tab(b.dataset.t); });
  $("leaflet").querySelectorAll("[data-go]").forEach((b) => b.addEventListener("click", () => { tab(b.dataset.go); $("leaflet").querySelector(".lf-tabs").scrollIntoView({ behavior: "smooth", block: "start" }); }));
  $("intro").hidden = true; $("input").hidden = true; $("progress").hidden = true;
  $("lfSummary").innerHTML = `Leaflet for <b>${esc(p.brand_name || p.product_name || "this offer")}</b>`;
  $("lfbar").hidden = false;
  $("leaflet").querySelectorAll(".se > button").forEach((b) => b.addEventListener("click", () => {
    const open = b.parentElement.classList.toggle("open"); b.setAttribute("aria-expanded", open);
  }));
  $("leaflet").hidden = false; $("pharmFab").hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
  $("chat").innerHTML = "";
  $("suggest").innerHTML = ["Is this OK for a freelancer?", "What happens if I pay late?", "Can I dispute a purchase?", "How does it compare with Citi?"]
    .map((q) => `<button type="button">${esc(q)}</button>`).join("");
}

/* ---- pharmacist ---- */
$("pharmFab").addEventListener("click", () => { $("pharm").hidden = false; $("pharmFab").hidden = true; $("askInput").focus(); });
$("pharmClose").addEventListener("click", () => { $("pharm").hidden = true; $("pharmFab").hidden = false; });
$("suggest").addEventListener("click", (e) => { if (e.target.tagName === "BUTTON") ask(e.target.textContent); });
$("askForm").addEventListener("submit", (e) => { e.preventDefault(); const q = $("askInput").value.trim(); if (q) ask(q); });

function bubble(role, text) {
  const d = document.createElement("div"); d.className = "msg " + role; d.textContent = text;
  $("chat").appendChild(d); $("chat").scrollTop = $("chat").scrollHeight; return d;
}

let spoke = false;
async function ask(q, viaVoice = false) {
  $("askInput").value = ""; bubble("user", q);
  const pending = bubble("model", "…");
  try {
    const r = await fetch("/api/pharmacist", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ leaflet_id: leaflet.id, question: q, history }) });
    const data = await r.json();
    const text = r.ok ? data.answer : (data.detail || "Sorry, I can't answer right now.");
    pending.textContent = text;
    history.push({ role: "user", text: q }, { role: "model", text });
    if ((viaVoice || spoke) && "speechSynthesis" in window) speechSynthesis.speak(new SpeechSynthesisUtterance(text));
  } catch { pending.textContent = "Sorry, I can't answer right now."; }
}

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SR) $("micBtn").hidden = true;
$("micBtn").addEventListener("click", () => {
  const rec = new SR(); rec.lang = "en-US"; rec.interimResults = false;
  $("micBtn").classList.add("on");
  rec.onresult = (e) => { spoke = true; ask(e.results[0][0].transcript, true); };
  rec.onend = () => $("micBtn").classList.remove("on");
  rec.start();
});

init();

/* ---- fold the form away once a leaflet is made ---- */
$("newLeaflet").addEventListener("click", () => {
  $("lfbar").hidden = true; $("leaflet").hidden = true; $("pharmFab").hidden = true; $("pharm").hidden = true;
  $("intro").hidden = false; $("input").hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
});
$("editLeaflet").addEventListener("click", () => {
  $("input").hidden = false; $("input").scrollIntoView({ behavior: "smooth", block: "start" });
});
fetch("/api/version").then((r) => r.ok ? r.json() : null).then((v) => { if (v?.version) $("ver").textContent = "Version " + v.version; }).catch(() => {});
