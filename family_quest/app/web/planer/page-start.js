// planer.html: starts the planer after all scripts (a file, not inline – CSP, main.py)
(async () => {
  const root = document.getElementById("planer-root");
  if (window.FQ_PLANER_MODE === "parent") {
    if (!Auth.parent) { root.replaceChildren(h("div.fq-wait", T("Parent PIN required"))); return; }
    try { await startPlaner(root); } catch (e) { root.replaceChildren(h("div.fq-wait", e.message || String(e))); }
    return;
  }
  if (!Auth.kid && !Auth.parent) { location.href = "app"; return; }
  // back to the app: the 🏠 button in the planer's top bar (planer/host.js FQ_NAV_HOOK)
  try { await startPlaner(root); }
  catch (e) { root.replaceChildren(h("div.fq-wait", e.message || String(e))); }
})();
