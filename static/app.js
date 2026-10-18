"use strict";
const $ = (id) => document.getElementById(id);
// CFPB replaces personal details with XXXX and wraps amounts in braces; show that plainly.
const story = (t) => esc(t).replace(/\{\$([\d.,]+)\}/g, "$$$1").replace(/X{2}\/X{2}\/(X{4}|\d{4})/g, '<i class="redact">[date]</i>').replace(/X{2,}/g, '<i class="redact">[redacted]</i>');
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

/* ---- one place to start: files (photos, PDFs, text), or a name / advert typed in ---- */
let files = [];
const isImage = (f) => (f.type || "").startsWith("image/");
function addFiles(list) {
  showError("");
  for (const f of list) {
    if (!isImage(f) && !/pdf|text/.test(f.type || "") && !/\.(pdf|txt)$/i.test(f.name)) { showError(`${f.name} isn't a photo, PDF or text file.`); continue; }
    if (f.size > 15 * 1024 * 1024) { showError(`${f.name} is over 15 MB.`); continue; }
    if (!files.some((g) => g.name === f.name && g.size === f.size)) files.push(f);
  }
  showFiles();
}
function showFiles() {
  const docs = files.filter((f) => !isImage(f));
  $("fileList").innerHTML = files.map((f, i) => `<li><span class="fi" aria-hidden="true">${isImage(f) ? "📷" : "📄"}</span>
    <span class="fn">${esc(f.name)}<small>${isImage(f) ? "Photo: we'll read the offer and the lender" : f === docs[0] ? "Contract: we'll find the clause behind each problem" : "Only one contract is read; this one will be skipped"}</small></span>
    <button type="button" data-rm="${i}" aria-label="Remove ${esc(f.name)}">×</button></li>`).join("");
  $("fileList").hidden = !files.length;
  $("drop").classList.toggle("has", files.length > 0);
}
$("files").addEventListener("change", () => { addFiles($("files").files); $("files").value = ""; });
$("fileList").addEventListener("click", (e) => { const b = e.target.closest("[data-rm]"); if (b) { files.splice(+b.dataset.rm, 1); showFiles(); } });
["dragenter", "dragover"].forEach((t) => $("drop").addEventListener(t, (e) => { e.preventDefault(); $("drop").classList.add("over"); }));
["dragleave", "drop"].forEach((t) => $("drop").addEventListener(t, (e) => { e.preventDefault(); $("drop").classList.remove("over"); }));
$("drop").addEventListener("drop", (e) => addFiles(e.dataTransfer.files));
// A short single line is a lender's name; anything longer is the advert's own words.
const looksLikeName = (t) => t.length <= 60 && !/\n/.test(t) && t.split(/\s+/).length <= 6;

$("tryRow").addEventListener("click", (e) => {
  const b = e.target.closest("[data-try]"); if (!b) return;
  $("quick").value = b.dataset.try; $("productType").value = b.dataset.type || "";
  run();
});
$("sampleBtn").addEventListener("click", async () => {
  const [flyer, contract] = await Promise.all([
    fetch("/api/samples/fictional-bnpl-flyer").then((r) => r.json()),
    fetch("/api/samples/fictional-bnpl-agreement").then((r) => r.json()),
  ]);
  $("quick").value = flyer.text; $("productType").value = "bnpl";
  files = files.filter((f) => f.name !== "sample-contract.txt");
  addFiles([new File([contract.text], "sample-contract.txt", { type: "text/plain" })]);
  $("goBtn").focus();
});

$("goBtn").addEventListener("click", run);
$("quick").addEventListener("input", () => showError(""));
$("quick").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && looksLikeName($("quick").value.trim())) { e.preventDefault(); run(); } });

async function run() {
  const fd = new FormData();
  const quick = $("quick").value.trim();
  const imgs = files.filter(isImage), doc = files.find((f) => !isImage(f));
  imgs.forEach((f) => fd.append("images", f));
  if (doc) fd.append("contract", doc);
  const typedName = quick && looksLikeName(quick);
  fd.append("flyer_text", typedName ? "" : quick);
  fd.append("contract_text", $("contractText").value);
  fd.append("issuer", $("issuer").value.trim() || (typedName ? quick : ""));
  fd.append("product_type", $("productType").value);
  fd.append("profile", [...profileKeys].join(","));
  fd.append("note", $("note").value);
  if (!files.length && !quick && !$("contractText").value.trim() && !$("issuer").value.trim()) {
    $("quick").focus();
    return showError("Add a photo or PDF of the offer, or type the card or lender's name.");
  }
  showError("");

  $("goBtn").disabled = true;
  $("leaflet").hidden = true; window.SEAssist?.setLeaflet(null);
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
  if (ev.step === "read" && ev.status === "done" && ev.product) startLiveEarly(ev.product);
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
    `<div class="story">“${story(s.text)}”<div class="meta">Real complaint to the US CFPB, ${esc(s.date)}, #${esc(s.complaint_id)}</div></div>`).join("");
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
  const s = String(name || "").replace(/,? (INC\.?|N\.A\.|NATIONAL ASSOCIATION|FINANCIAL CORPORATION|COMPANY|& CO\.|Holdings, Inc|Inc\.|LLC|AB)$/i, "").trim();
  // Complaint records shout names in capitals; show them the way people write them.
  return s === s.toUpperCase() ? s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()).replace(/\b(Usa|Td|Us)\b/g, (m) => m.toUpperCase()) : s;
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
  leaflet = lf;
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
    <div id="lfAlerts"></div>
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

    ${liveName(p) ? `<section class="live" id="live" aria-live="polite"><div class="bq-head"><span class="bq-tag">Live right now</span><span class="small muted">Checked automatically for ${esc(liveName(p))}</span></div>
      <div class="live-grid"><div id="liveComplaints"></div><div id="liveNews"></div></div></section>` : ""}
    ${p.matched_company ? `<div class="radar" id="radar"><div class="bq-head"><span class="radar-tag">In their own words</span><span class="small muted">Gemini reads real complaint stories</span></div>
      <p class="small">The numbers above are statistics. Gemini can read the actual stories people wrote about this lender, group them by what went wrong, and point out problems our statistics don't show.</p>
      <button type="button" class="radar-btn" id="radarBtn">Read the complaint stories</button><div id="radarOut"></div></div>` : ""}
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
  const brand = p.brand_name || p.product_name || "this offer", lender = p.issuer_name && p.issuer_name !== brand ? p.issuer_name : "";
  $("lfSummary").innerHTML = `We read: <b>${esc(brand)}</b>${lender ? ` from ${esc(lender)}` : ""}`;
  $("lfbar").hidden = false;
  $("leaflet").querySelectorAll(".se > button").forEach((b) => b.addEventListener("click", () => {
    const open = b.parentElement.classList.toggle("open"); b.setAttribute("aria-expanded", open);
  }));
  $("leaflet").hidden = false;
  if (liveName(p)) runLive(liveName(p), p.matched_company, p.product_type);
  if (p.matched_company) loadAlerts(p.matched_company, p.product_type);
  $("radarBtn")?.addEventListener("click", () => runRadar(p.matched_company, p.product_type));
  window.scrollTo({ top: 0, behavior: "smooth" });
  const firstEffect = [...lf.side_effects, ...lf.contract_only].map((x) => x.label)[0];
  const alt = lf.alternatives[0] ? short(lf.alternatives[0].company).toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()) : null;
  window.SEAssist?.setLeaflet(lf, [firstEffect ? `What does "${firstEffect}" mean for me?` : "What should I watch out for?",
    "What happens if I pay late?", alt ? `How does it compare with ${alt}?` : "Can I dispute a purchase?"]
    .filter(Boolean));
}

/* ---- live check of whatever lender Gemini read: the regulator's feed + Gemini with Google Search ---- */
const liveName = (p) => p.brand_name || p.issuer_name || p.matched_company || "";
const KIND = { enforcement: "Regulator", lawsuit: "Lawsuit", outage: "Outage", data_breach: "Data breach", fees_or_terms: "Fees or terms", other: "News" };
const wait = (t) => `<p class="small muted radar-wait"><i></i>${esc(t)}</p>`;
let liveSeq = 0, early = null;
const liveType = (t) => (t === "bnpl" ? "bnpl" : "credit_card");
// News is searched by the name people know (the brand); complaints are filed against the lender behind it.
const liveFetch = (name, type, lender) => {
  const q = (n) => `name=${encodeURIComponent(n)}&product_type=${type}`;
  return { name, type, check: fetch(`/api/live/check?${q(name)}&lender=${encodeURIComponent(lender || "")}`).then((r) => r.json()), news: fetch(`/api/live/news?${q(name)}`).then((r) => r.json()) };
};
// Start the live lookups the moment Gemini has read the lender, while the rest of the leaflet is still being written.
function startLiveEarly(product) {
  const name = liveName(product);
  early = name ? liveFetch(name, liveType(product.product_type), product.issuer_name) : null;
  early?.check.catch(() => {}); early?.news.catch(() => {});
}
function runLive(name, company, productType) {
  const seq = ++liveSeq, type = liveType(productType);
  const got = early && early.name === name && early.type === type ? early : liveFetch(name, type, company);
  early = null;
  $("liveComplaints").innerHTML = `<h4>Complaints this quarter</h4>` + wait("Asking the regulator's live complaint feed…");
  $("liveNews").innerHTML = `<h4>In the news <span class="g-tag">Gemini + Google Search</span></h4>` + wait("Gemini is searching today's news…");
  got.check.then((d) => { if (seq === liveSeq) showComplaints(d); })
    .catch(() => { if (seq === liveSeq) $("liveComplaints").innerHTML = `<h4>Complaints this quarter</h4><p class="small muted">Couldn't reach the complaint feed just now.</p>`; });
  got.news.then((d) => { if (seq === liveSeq) showNews(d); })
    .catch(() => { if (seq === liveSeq) $("liveNews").innerHTML = `<h4>In the news</h4><p class="small muted">Couldn't search the news just now.</p>`; });
}
/* ---- safety alerts: a new spike in this lender's complaints, found by the daily scan ---- */
async function loadAlerts(company, productType) {
  try {
    const d = await (await fetch(`/api/alerts?name=${encodeURIComponent(company)}&product_type=${encodeURIComponent(productType || "credit_card")}`)).json();
    const box = $("lfAlerts"); if (!box || !d.alerts?.length) return;
    box.innerHTML = d.alerts.map((a) => `<div class="lf-alert" role="alert"><span class="lf-alert-tag">Safety alert · ${esc(a.date)}</span>
      <b>${esc(a.headline)}</b><p>${esc(a.what_changed)} ${esc(a.what_to_do)}</p><a href="/#alerts">How we found this ›</a></div>`).join("");
  } catch { /* alerts are an extra */ }
}

function showComplaints(d) {
  const c = d.complaints || {}, a = d.archive || {}, box = $("liveComplaints"); if (!box) return;
  const top = (list) => list?.length ? `<ul class="bq-top">${list.map((i) => `<li><span>${esc(i.issue)}</span><b>${i.n.toLocaleString()}</b></li>`).join("")}</ul>` : "";
  if (!d.company) {
    box.innerHTML = `<h4>Complaints this quarter</h4><p class="small muted">${esc(d.name)} isn't in the US complaint records we can check, so there are no live complaint numbers. The news check still covers it.</p>`;
  } else if (c.available) {
    const ch = c.change_pct, trend = ch == null ? "" : ch > 0 ? `<span class="up">▲ ${ch}%</span>` : ch < 0 ? `<span class="down">▼ ${Math.abs(ch)}%</span>` : "no change";
    box.innerHTML = `<h4>Complaints this quarter</h4>
      <div class="live-big"><b>${c.last_90_days.toLocaleString()}</b><span>complaints about ${esc(short(c.company))} in the last 90 days${trend ? `, ${trend} on the 90 days before` : ""}</span></div>
      ${top(c.top_issues)}<p class="small muted">${esc(c.source)}${c.latest_complaint ? `, newest ${esc(c.latest_complaint)}` : ""}. All of the company's products; complaints are unverified.</p>`;
  } else if (a.available) {
    box.innerHTML = `<h4>Complaints <span class="bq-tag">BigQuery</span></h4><p class="small muted">The regulator's live feed didn't answer, so this is Google's public copy in BigQuery.</p>
      <div class="live-big"><b>${a.last_12_months.toLocaleString()}</b><span>complaints in the 12 months to ${esc(a.latest_date)}</span></div>${top(a.top_issues)}`;
  } else {
    box.innerHTML = `<h4>Complaints this quarter</h4><p class="small muted">The regulator's live feed didn't answer just now.</p>`;
  }
}
function showNews(d) {
  const box = $("liveNews"); if (!box) return;
  if (!d.available) { box.innerHTML = `<h4>In the news</h4><p class="small muted">${esc(d.reason || "Not available right now.")}</p>`; return; }
  box.innerHTML = `<h4>In the news <span class="g-tag">Gemini + Google Search</span></h4><p>${esc(d.summary)}</p>
    ${d.items.length ? `<ol class="live-news">${d.items.map((i) => `<li><span class="kind k-${esc(i.kind)}">${esc(KIND[i.kind] || "News")}</span><b>${esc(i.headline)}</b> <span class="muted small">${esc(i.date)} · ${esc(i.source)}</span><p class="small">${esc(i.what_it_means)}</p></li>`).join("")}</ol>` : ""}
    ${d.sources.length ? `<details class="live-src"><summary>${d.sources.length} source${d.sources.length > 1 ? "s" : ""} Gemini used</summary><ul>${d.sources.map((s) => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title)}</a></li>`).join("")}</ul></details>` : `<p class="small muted">No web sources came back, so treat this as unverified.</p>`}`;
}

/* ---- emerging side effects: Gemini reads the newest complaint stories ---- */
async function runRadar(company, productType) {
  const btn = $("radarBtn"), out = $("radarOut");
  btn.disabled = true; btn.textContent = "Gemini is reading…";
  out.innerHTML = `<p class="small muted radar-wait"><i></i>Gemini is reading complaint stories about ${esc(short(company))}. This takes about 20 seconds…</p>`;
  try {
    const d = await (await fetch(`/api/radar?issuer=${encodeURIComponent(company)}&product_type=${encodeURIComponent(productType || "credit_card")}`)).json();
    if (!d.available) { out.innerHTML = `<p class="small muted">${esc(d.reason || "Not available right now.")}</p>`; return; }
    out.innerHTML = `<p class="small muted">Read ${d.stories_read} stories (${esc(d.source)}). ${d.new ? `<b>${d.new} not in our statistics.</b>` : ""}</p>` +
      d.themes.map((t) => `<div class="theme${t.known ? "" : " new"}"><div class="theme-top"><b>${esc(t.label)}</b>
        <span class="theme-n">${t.count} ${t.count > 1 ? "stories" : "story"}</span>${t.known ? `<span class="theme-k">Already on this leaflet</span>` : `<span class="theme-new">New</span>`}</div>
        ${t.quote ? `<p class="theme-q">“${story(t.quote)}”</p>` : ""}<p class="small muted">${esc(t.why_it_matters)} Latest: ${esc(t.latest)}.</p></div>`).join("") +
      `<p class="small muted">Read by Gemini; each quote is checked word for word against the complaint, and counts are complaints Gemini pointed to that really exist. Unverified reports.</p>`;
  } catch (e) {
    out.innerHTML = `<p class="small muted">Could not read the complaints just now.</p>`;
  } finally {
    btn.disabled = false; btn.textContent = "Read them again";
  }
}

init();

// /leaflet?q=Apple+Card fills in the name and starts straight away (used by links from the agent demo).
const startQ = new URLSearchParams(location.search).get("q");
if (startQ) { $("quick").value = startQ.slice(0, 80); setTimeout(run); }

/* ---- fold the form away once a leaflet is made ---- */
$("newLeaflet").addEventListener("click", () => {
  $("lfbar").hidden = true; $("leaflet").hidden = true; window.SEAssist?.setLeaflet(null);
  $("intro").hidden = false; $("input").hidden = false;
  ["quick", "contractText", "issuer", "note", "productType"].forEach((id) => { $(id).value = ""; });
  files = []; showFiles(); liveSeq++; window.history.replaceState(null, "", "/leaflet");
  document.querySelectorAll(".chip[aria-pressed='true']").forEach((c) => c.click());
  window.scrollTo({ top: 0, behavior: "smooth" });
});
$("editLeaflet").addEventListener("click", () => {
  $("input").hidden = false; $("input").scrollIntoView({ behavior: "smooth", block: "start" });
});
fetch("/api/version").then((r) => r.ok ? r.json() : null).then((v) => { if (v?.version) $("ver").textContent = "Version " + v.version; }).catch(() => {});
