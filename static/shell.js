/* App shell shared by every page: sidebar navigation, a top bar with the page title and an ask bar (⌘K),
   and a slide-in menu on phones. The pages keep their own routing; the sidebar just drives it. */
(() => {
  "use strict";
  const NAV = [
    { group: "Check", items: [
      { id: "leaflet", icon: "search", label: "Check an offer", href: "/leaflet" },
      { id: "alerts", icon: "bell", label: "Safety alerts", href: "/#alerts", badge: "Live" },
    ] },
    { group: "AI agents", items: [
      { id: "demo", icon: "cart", label: "Agent checkout", href: "/" },
      { id: "scam", icon: "shield", label: "Scam arena", href: "/#scam" },
      { id: "biz", icon: "code", label: "API, MCP & audit", href: "/#biz" },
    ] },
    { group: "Learn", items: [
      { id: "how", icon: "steps", label: "How it works", href: "/#how" },
      { id: "why", icon: "chart", label: "Evidence", href: "/#why" },
    ] },
  ];
  const TITLES = { leaflet: "Check an offer", alerts: "Safety alerts", demo: "Agent checkout", scam: "Scam arena", biz: "API, MCP & audit", how: "How it works", why: "Evidence" };
  const P = {
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    bell: '<path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    cart: '<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2.5 3h3l2.7 12.4a2 2 0 0 0 2 1.6h7.6a2 2 0 0 0 2-1.5L21.5 8H6.1"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    code: '<path d="m16 18 6-6-6-6"/><path d="m8 6-6 6 6 6"/>',
    steps: '<path d="M4 6h16M4 12h10M4 18h6"/>',
    chart: '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
    spark: '<path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  };
  const svg = (k) => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[k]}</svg>`;
  const mac = /Mac|iPhone|iPad/.test(navigator.platform);

  document.addEventListener("DOMContentLoaded", () => {
    const onAgentPage = !!document.querySelector(".pager");
    document.body.classList.add("app");
    const side = document.createElement("aside");
    side.className = "side"; side.setAttribute("aria-label", "Main menu");
    side.innerHTML = `<a class="side-brand" href="/"><span class="pill" aria-hidden="true"></span><span>SIDE EFFECTS</span></a>
      <nav>${NAV.map((g) => `<div class="side-group">${g.group}</div>${g.items.map((i) =>
        `<a class="side-item" data-id="${i.id}" href="${i.href}">${svg(i.icon)}<span>${i.label}</span>${i.badge ? `<em>${i.badge}</em>` : ""}</a>`).join("")}`).join("")}</nav>
      <div class="side-foot"><div class="side-card"><b>Built on Google Cloud</b><span>Gemini on Vertex AI · BigQuery · Gemini document reading · Cloud Run · Cloud Scheduler · Google Search grounding</span></div></div>`;
    const scrim = document.createElement("div"); scrim.className = "side-scrim";
    document.body.prepend(side, scrim);

    // Top bar: menu button (phones), page title, ask bar, theme switch (theme.js adds it to .top).
    const top = document.querySelector(".top");
    const menu = document.createElement("button");
    menu.type = "button"; menu.className = "top-menu"; menu.setAttribute("aria-label", "Open menu"); menu.innerHTML = svg("menu");
    const title = document.createElement("div"); title.className = "top-title";
    const ask = document.createElement("button");
    ask.type = "button"; ask.className = "top-ask";
    ask.innerHTML = `${svg("spark")}<span>Ask anything about a lender, a fee or a term</span><kbd>${mac ? "⌘" : "Ctrl"} K</kbd>`;
    ask.addEventListener("click", () => window.SEAssist?.open());
    const voice = document.createElement("button");
    voice.type = "button"; voice.className = "top-voice"; voice.title = "Voice Mode: speak to the agent, hear the answer";
    voice.innerHTML = `<i aria-hidden="true"></i><span>Voice Mode</span>`;
    voice.addEventListener("click", () => window.SEVoice?.open());
    top.prepend(menu, title);
    top.querySelector(".brand")?.after(ask);
    if (!top.querySelector(".brand")) title.after(ask);
    ask.after(voice);

    const openMenu = (on) => document.body.classList.toggle("side-open", on);
    menu.addEventListener("click", () => openMenu(true));
    scrim.addEventListener("click", () => openMenu(false));
    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); window.SEAssist?.open(); }
      if (e.key === "Escape") openMenu(false);
    });

    const setActive = (id) => {
      side.querySelectorAll(".side-item").forEach((a) => a.classList.toggle("on", a.dataset.id === id));
      title.textContent = TITLES[id] || "";
    };
    // On the agent page the sidebar drives the existing tabs, so history and deep links keep working.
    side.addEventListener("click", (e) => {
      const a = e.target.closest(".side-item"); if (!a) return;
      openMenu(false);
      const tab = onAgentPage && document.querySelector(`.pager [data-p="${a.dataset.id}"]`);
      if (tab) { e.preventDefault(); tab.click(); }
    });
    // Motion: staggered entrances, PRR gauges against the 1.0x baseline, view transitions.
    if (document.startViewTransition) document.documentElement.classList.add("vt");
    document.querySelectorAll(".bento, #at-known, .arch, #scamSample").forEach((box) => [...box.children].forEach((c, i) => c.style.setProperty("--i", i)));
    const io = "IntersectionObserver" in window ? new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("on"); io.unobserve(e.target); } })) : null;
    window.SEGauges = (root = document) => root.querySelectorAll("[data-x]:not(.g-done)").forEach((el) => {
      const x = parseFloat(el.dataset.x); if (!(x > 0)) return;
      el.classList.add("g-done");
      const g = document.createElement("span");
      g.className = "gauge"; g.setAttribute("aria-hidden", "true"); g.dataset.tip = `${x}× · baseline 1.0× = similar lenders`;
      g.style.setProperty("--w", Math.min(100, (x / 4) * 100) + "%"); g.innerHTML = "<i></i>";
      if (el.matches(".sig-prr, .stat b")) { g.classList.add("in"); el.append(g); } else el.after(g);
      io ? io.observe(g) : g.classList.add("on");
    });
    window.SEGauges();
    if (onAgentPage) {
      const sync = () => setActive(document.querySelector('.pager [aria-selected="true"]')?.dataset.p || "demo");
      new MutationObserver(sync).observe(document.querySelector(".pager"), { subtree: true, attributes: true, attributeFilter: ["aria-selected"] });
      sync();
    } else setActive("leaflet");
  });
})();
