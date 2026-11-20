// planer.html, before i18n.js (a file, not inline – CSP, main.py)
window.I18N_EXTRA = ["planer"];
// planer?mode=parent (parent area → Chores, in a frame): only the chore plan and the planer settings.
// In the app the chore plan and the settings are hidden – they belong to the parents.
window.FQ_PLANER_MODE = new URLSearchParams(location.search).get("mode") === "parent" ? "parent" : "app";
if (window.FQ_PLANER_MODE === "parent") {
  window.FQ_PARENT_AREA = true;
  window.FQ_PLANER_ONLY = ["aemtliplan", "einstellungen"];
  window.FQ_PLANER_DEFAULT = "aemtliplan";
  window.FQ_PLANER_THEME = "fq";            // the look of the parent area
  document.documentElement.classList.add("fq-in-parent");
} else {
  window.FQ_PLANER_HIDE = ["aemtliplan", "einstellungen"];
}
