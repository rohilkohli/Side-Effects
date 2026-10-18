"use strict";
// Light/dark theme toggle shared by every page. Follows the system until the visitor picks one.
(() => {
  const root = document.documentElement;
  const saved = (() => { try { return localStorage.getItem("se-theme"); } catch { return null; } })();
  if (saved === "light" || saved === "dark") root.dataset.theme = saved;
  const current = () => root.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const icon = () => (current() === "dark" ? "☀︎" : "☾");
  document.addEventListener("DOMContentLoaded", () => {
    const nav = document.querySelector(".top");
    if (!nav) return;
    const b = document.createElement("button");
    b.type = "button"; b.className = "theme-toggle"; b.textContent = icon();
    b.setAttribute("aria-label", "Switch light or dark mode");
    b.addEventListener("click", () => {
      const next = current() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("se-theme", next); } catch { /* private mode */ }
      b.textContent = icon();
    });
    nav.appendChild(b);
    // Sticky bars sit right under the header, whose height changes when it wraps on a phone.
    const setTop = () => root.style.setProperty("--top-h", nav.offsetHeight + "px");
    setTop();
    if ("ResizeObserver" in window) new ResizeObserver(setTop).observe(nav); else addEventListener("resize", setTop);
  });
})();
